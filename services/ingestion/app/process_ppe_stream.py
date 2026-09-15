import argparse
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import cv2
from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from minio import Minio
from ultralytics import YOLO

from app.associate_ppe_tracks import (
    POSITIVE_PPE_CLASSES,
    VIOLATION_CLASSES,
    associate_frame,
    draw_frame,
)
from app.consume_frames import EVENT_ID_PATTERN, atomic_write_json
from app.infer_frame_events import sha256
from app.publish_frames import parse_minio_endpoint
from app.temporal_violations import TemporalViolationEngine
from app.track_frames import extract_tracks
from app.worker_runtime import WorkerHeartbeat


REQUIRED_DETECTION_FIELDS = {
    "schema_version",
    "event_id",
    "source_event_id",
    "camera_id",
    "sample_index",
    "video_timestamp_ms",
    "source_object_uri",
    "detections",
}


def parse_detection_event(message_value: bytes, message_key: bytes | None) -> dict:
    try:
        event = json.loads(message_value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Kafka message value is not valid UTF-8 JSON") from error
    if not isinstance(event, dict):
        raise ValueError("Detection event must be a JSON object")
    missing = REQUIRED_DETECTION_FIELDS - event.keys()
    if missing:
        raise ValueError(f"Detection event is missing: {', '.join(sorted(missing))}")
    if event["schema_version"] != 1:
        raise ValueError(f"Unsupported detection-event schema: {event['schema_version']}")
    if not EVENT_ID_PATTERN.fullmatch(str(event["event_id"])):
        raise ValueError("event_id must be a lowercase 64-character SHA256 value")
    if not isinstance(event["detections"], list):
        raise ValueError("detections must be a list")
    if int(event["sample_index"]) < 0 or int(event["video_timestamp_ms"]) < 0:
        raise ValueError("Detection event contains a negative index or timestamp")
    key = message_key.decode("utf-8") if message_key is not None else None
    if key != event["camera_id"]:
        raise ValueError(
            f"Kafka key {key!r} does not match camera_id {event['camera_id']!r}"
        )
    source_uri = urlparse(event["source_object_uri"])
    if source_uri.scheme != "s3" or not source_uri.netloc or not source_uri.path.lstrip("/"):
        raise ValueError(f"Invalid source object URI: {event['source_object_uri']}")
    return event


def build_track_evidence(tracks: list[dict], associations: list[dict]) -> list[dict]:
    associations_by_track = defaultdict(list)
    for association in associations:
        associations_by_track[association["track_id"]].append(association)

    evidence = []
    for track in tracks:
        track_id = track["track_id"]
        matched = associations_by_track[track_id]
        evidence.append(
            {
                "track_id": track_id,
                "person_box_xyxy": track["box_xyxy"],
                "positive_evidence": sorted(
                    item["class_name"]
                    for item in matched
                    if item["class_name"] in POSITIVE_PPE_CLASSES
                ),
                "violation_evidence": sorted(
                    item["class_name"]
                    for item in matched
                    if item["class_name"] in VIOLATION_CLASSES
                ),
                "unknown_is_not_violation": not matched,
            }
        )
    return evidence


def deterministic_id(*parts: object) -> str:
    return hashlib.sha256(":".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def download_source_frame(minio_client: Minio, event: dict, destination: Path) -> None:
    source_uri = urlparse(event["source_object_uri"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_suffix(".jpg.part")
    try:
        minio_client.fget_object(
            source_uri.netloc,
            source_uri.path.lstrip("/"),
            str(temporary_path),
        )
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def upload_gold_frame(
    minio_client: Minio,
    bucket: str,
    camera_id: str,
    frame_id: str,
    annotated_path: Path,
    record_path: Path,
) -> tuple[str, str]:
    if not minio_client.bucket_exists(bucket):
        minio_client.make_bucket(bucket)
    prefix = f"tracking/{camera_id}/{frame_id}"
    annotated_name = f"{prefix}/annotated.jpg"
    record_name = f"{prefix}/record.json"
    minio_client.fput_object(
        bucket, annotated_name, str(annotated_path), content_type="image/jpeg"
    )
    minio_client.fput_object(
        bucket, record_name, str(record_path), content_type="application/json"
    )
    return f"s3://{bucket}/{annotated_name}", f"s3://{bucket}/{record_name}"


def process_ppe_stream(
    input_topic: str,
    track_topic: str,
    candidate_topic: str,
    group_id: str,
    output_dir: Path,
    tracking_model_path: Path,
    gold_bucket: str,
    max_messages: int,
    idle_timeout_seconds: float,
    tracking_confidence: float,
    image_size: int,
    device: str,
    window_size: int,
    evidence_threshold: int,
    cooldown_ms: int,
    maximum_opposite_evidence: int,
    continuous: bool = False,
    max_cameras: int = 3,
    heartbeat_file: Path | None = None,
) -> dict:
    if not tracking_model_path.is_file():
        raise FileNotFoundError(f"Tracking model does not exist: {tracking_model_path}")
    if not continuous and output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")
    if idle_timeout_seconds <= 0 or image_size <= 0:
        raise ValueError("timeout and image size must be positive")
    if not continuous and max_messages <= 0:
        raise ValueError("max_messages must be positive in finite mode")
    if not 0 <= tracking_confidence <= 1:
        raise ValueError("tracking_confidence must be between zero and one")
    if max_cameras <= 0:
        raise ValueError("max_cameras must be greater than zero")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    annotated_dir = output_dir / "annotated"
    records_dir = output_dir / "records"
    for directory in (raw_dir, annotated_dir, records_dir):
        directory.mkdir(parents=True, exist_ok=True)

    minio_endpoint, minio_secure = parse_minio_endpoint(
        os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    )
    minio_client = Minio(
        minio_endpoint,
        access_key=os.getenv("MINIO_ACCESS_KEY", "safesite"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "safesite_dev_password"),
        secure=minio_secure,
    )
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    consumer = Consumer(
        {
            "bootstrap.servers": kafka_servers,
            "group.id": group_id,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    producer = Producer(
        {
            "bootstrap.servers": kafka_servers,
            "client.id": "safesite-tracking-producer",
            "enable.idempotence": True,
            "acks": "all",
            "message.timeout.ms": 10000,
        }
    )
    model_hash = sha256(tracking_model_path)
    models = {}
    temporal_engines = {}
    delivery_errors = []
    processed_records = []
    processed_count = 0
    candidate_events = []
    track_observations = Counter()
    association_counts = Counter()
    unassociated_counts = Counter()
    camera_ids = set()
    previous_sample_indices = {}
    heartbeat = WorkerHeartbeat(heartbeat_file, "tracking")
    heartbeat.update("starting", 0, force=True, input_topic=input_topic, track_topic=track_topic)
    idle_deadline = time.monotonic() + idle_timeout_seconds

    def delivery_report(error, message) -> None:
        if error is not None:
            delivery_errors.append(str(error))

    consumer.subscribe([input_topic])
    try:
        while continuous or processed_count < max_messages:
            heartbeat.update(
                "waiting",
                processed_count,
                cameras=sorted(camera_ids),
                input_topic=input_topic,
            )
            message = consumer.poll(1.0)
            if message is None:
                if not continuous and time.monotonic() >= idle_deadline:
                    raise TimeoutError(
                        f"No PPE event arrived within {idle_timeout_seconds} seconds"
                    )
                continue
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(message.error())

            event = parse_detection_event(message.value(), message.key())
            camera_id = event["camera_id"]
            if camera_id not in models:
                if len(models) >= max_cameras:
                    raise ValueError(f"Worker camera capacity exceeded: {max_cameras}")
                models[camera_id] = YOLO(str(tracking_model_path))
                temporal_engines[camera_id] = TemporalViolationEngine(
                    window_size=window_size,
                    evidence_threshold=evidence_threshold,
                    cooldown_ms=cooldown_ms,
                    maximum_opposite_evidence=maximum_opposite_evidence,
                )
                camera_ids.add(camera_id)
            previous_sample_index = previous_sample_indices.get(camera_id)
            if previous_sample_index is not None and event["sample_index"] <= previous_sample_index:
                raise ValueError(f"PPE events for {camera_id} must arrive in increasing sample order")
            previous_sample_indices[camera_id] = event["sample_index"]

            source_path = raw_dir / f'{event["event_id"]}.jpg'
            download_source_frame(minio_client, event, source_path)
            result = models[camera_id].track(
                source=str(source_path),
                conf=tracking_confidence,
                imgsz=image_size,
                device=device,
                classes=[0],
                tracker="bytetrack.yaml",
                persist=True,
                verbose=False,
            )[0]
            tracks = [track for track in extract_tracks(result) if track["track_id"] is not None]
            associations, unassociated = associate_frame(tracks, event["detections"])
            track_evidence = build_track_evidence(tracks, associations)
            for track in tracks:
                track_observations[f"{camera_id}:{track['track_id']}"] += 1
            for association in associations:
                association_counts[association["class_name"]] += 1
            for detection in unassociated:
                unassociated_counts[detection["class_name"]] += 1

            frame_id = deterministic_id(
                "tracking-v1", event["event_id"], model_hash, tracking_confidence, image_size
            )
            annotated_path = annotated_dir / f"{frame_id}.jpg"
            image = cv2.imread(str(source_path))
            if image is None:
                raise RuntimeError(f"Could not read downloaded frame: {source_path}")
            draw_frame(image, tracks, associations)
            if not cv2.imwrite(str(annotated_path), image):
                raise RuntimeError(f"Could not write annotated frame: {annotated_path}")

            annotated_uri = f"s3://{gold_bucket}/tracking/{event['camera_id']}/{frame_id}/annotated.jpg"
            association_record = {
                "schema_version": 1,
                "event_id": frame_id,
                "source_detection_event_id": event["event_id"],
                "camera_id": event["camera_id"],
                "sample_index": event["sample_index"],
                "video_timestamp_ms": event["video_timestamp_ms"],
                "captured_at": event.get("captured_at"),
                "image_path": event["source_object_uri"],
                "annotated_image": annotated_uri,
                "tracked_people": len(tracks),
                "tracks": tracks,
                "track_evidence": track_evidence,
                "associations": associations,
                "unassociated_supported_detections": unassociated,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            timeline_rows, new_candidates = temporal_engines[camera_id].evaluate(
                association_record
            )
            for candidate in new_candidates:
                candidate["event_id"] = deterministic_id(
                    "candidate-v1",
                    event["camera_id"],
                    candidate["track_id"],
                    candidate["violation_type"],
                    candidate["window_end_timestamp_ms"],
                )
                candidate["source_tracking_event_id"] = frame_id
                candidate["occurred_at"] = event.get("captured_at")
                candidate["status"] = "candidate_published_to_kafka"

            track_event = {
                **association_record,
                "timeline": timeline_rows,
                "candidate_events": new_candidates,
            }
            record_path = records_dir / f"{frame_id}.json"
            atomic_write_json(record_path, track_event)
            annotated_uri, record_uri = upload_gold_frame(
                minio_client=minio_client,
                bucket=gold_bucket,
                camera_id=event["camera_id"],
                frame_id=frame_id,
                annotated_path=annotated_path,
                record_path=record_path,
            )
            track_event["annotated_image"] = annotated_uri
            track_event["record_object_uri"] = record_uri
            atomic_write_json(record_path, track_event)
            minio_client.fput_object(
                gold_bucket,
                urlparse(record_uri).path.lstrip("/"),
                str(record_path),
                content_type="application/json",
            )

            producer.produce(
                track_topic,
                key=event["camera_id"].encode("utf-8"),
                value=json.dumps(track_event, separators=(",", ":")).encode("utf-8"),
                on_delivery=delivery_report,
            )
            for candidate in new_candidates:
                producer.produce(
                    candidate_topic,
                    key=event["camera_id"].encode("utf-8"),
                    value=json.dumps(candidate, separators=(",", ":")).encode("utf-8"),
                    on_delivery=delivery_report,
                )
            producer.poll(0)
            remaining_messages = producer.flush(30)
            if remaining_messages or delivery_errors:
                details = "; ".join(delivery_errors) or f"{remaining_messages} pending"
                raise RuntimeError(f"Kafka delivery failed: {details}")
            consumer.commit(message=message, asynchronous=False)
            processed_count += 1
            heartbeat.update(
                "running",
                processed_count,
                force=True,
                cameras=sorted(camera_ids),
                input_topic=input_topic,
                last_event_id=frame_id,
                last_camera_id=camera_id,
            )
            if not continuous:
                candidate_events.extend(new_candidates)
                processed_records.append(track_event)
            idle_deadline = time.monotonic() + idle_timeout_seconds

        producer.flush(30)
    finally:
        consumer.close()
        heartbeat.update("stopped", processed_count, force=True, cameras=sorted(camera_ids))

    events_path = output_dir / "candidate_events.jsonl"
    events_path.write_text(
        "".join(json.dumps(event) + "\n" for event in candidate_events),
        encoding="utf-8",
    )
    summary = {
        "input_topic": input_topic,
        "track_topic": track_topic,
        "candidate_topic": candidate_topic,
        "consumer_group": group_id,
        "camera_ids": sorted(camera_ids),
        "frames_processed": len(processed_records),
        "tracking_model": str(tracking_model_path),
        "tracking_model_sha256": model_hash,
        "tracking_confidence": tracking_confidence,
        "image_size": image_size,
        "unique_track_ids": sorted(track_observations),
        "track_observations": {
            str(track_id): count for track_id, count in sorted(track_observations.items())
        },
        "associated_class_counts": dict(sorted(association_counts.items())),
        "unassociated_class_counts": dict(sorted(unassociated_counts.items())),
        "candidate_event_count": len(candidate_events),
        "candidate_events_by_type": dict(
            sorted(Counter(event["violation_type"] for event in candidate_events).items())
        ),
        "window_size": window_size,
        "evidence_threshold": evidence_threshold,
        "cooldown_ms": cooldown_ms,
        "maximum_opposite_evidence": maximum_opposite_evidence,
        "commit_rule": "Commit each source event only after Gold uploads and Kafka deliveries succeed",
        "safety_rule": "Missing PPE detection remains unknown and never becomes a violation",
        "worker_limit": f"Up to {max_cameras} ordered camera streams with isolated tracking state",
    }
    atomic_write_json(output_dir / "summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Track PPE events, associate equipment, and publish temporal candidates."
    )
    parser.add_argument("--input-topic", default="safesite.ppe.detections")
    parser.add_argument("--track-topic", default="safesite.tracks")
    parser.add_argument("--candidate-topic", default="safesite.candidate-violations")
    parser.add_argument("--group-id", default="safesite-ppe-tracker")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tracking-model", type=Path, required=True)
    parser.add_argument("--gold-bucket", default="safesite-gold")
    parser.add_argument("--max-messages", type=int, default=30)
    parser.add_argument("--idle-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--tracking-confidence", type=float, default=0.25)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--evidence-threshold", type=int, default=3)
    parser.add_argument("--cooldown-ms", type=int, default=10000)
    parser.add_argument("--maximum-opposite-evidence", type=int, default=0)
    parser.add_argument("--max-cameras", type=int, default=3)
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Wait indefinitely and process messages until the service is stopped.",
    )
    parser.add_argument("--heartbeat-file", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = process_ppe_stream(
        input_topic=args.input_topic,
        track_topic=args.track_topic,
        candidate_topic=args.candidate_topic,
        group_id=args.group_id,
        output_dir=args.output_dir,
        tracking_model_path=args.tracking_model,
        gold_bucket=args.gold_bucket,
        max_messages=args.max_messages,
        idle_timeout_seconds=args.idle_timeout_seconds,
        tracking_confidence=args.tracking_confidence,
        image_size=args.image_size,
        device=args.device,
        window_size=args.window_size,
        evidence_threshold=args.evidence_threshold,
        cooldown_ms=args.cooldown_ms,
        maximum_opposite_evidence=args.maximum_opposite_evidence,
        continuous=args.continuous,
        max_cameras=args.max_cameras,
        heartbeat_file=args.heartbeat_file,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
