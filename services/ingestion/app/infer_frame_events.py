import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from minio import Minio
from ultralytics import YOLO

from app.consume_frames import atomic_write_json, download_event_frame, parse_event
from app.detect_image import extract_detections
from app.publish_frames import parse_minio_endpoint
from app.worker_runtime import WorkerHeartbeat


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_detection_id(
    source_event_id: str,
    model_sha256: str,
    confidence_threshold: float,
    image_size: int,
) -> str:
    identity = ":".join(
        [source_event_id, model_sha256, str(confidence_threshold), str(image_size)]
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def run_inference(
    model: YOLO,
    input_path: Path,
    annotated_path: Path,
    prediction_path: Path,
    model_path: Path,
    model_sha256: str,
    confidence_threshold: float,
    image_size: int,
    device: str,
    source_event: dict,
) -> dict:
    results = model.predict(
        source=str(input_path),
        conf=confidence_threshold,
        imgsz=image_size,
        device=device,
        verbose=False,
    )
    result = results[0]
    detections = extract_detections(result)

    annotated_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_annotated_path = annotated_path.with_name(f"{annotated_path.stem}.part.jpg")
    try:
        if not cv2.imwrite(str(temporary_annotated_path), result.plot()):
            raise RuntimeError(f"Could not write annotated image: {temporary_annotated_path}")
        temporary_annotated_path.replace(annotated_path)
    finally:
        temporary_annotated_path.unlink(missing_ok=True)

    prediction = {
        "schema_version": 1,
        "source_event_id": source_event["event_id"],
        "camera_id": source_event["camera_id"],
        "sample_index": source_event["sample_index"],
        "video_timestamp_ms": source_event["video_timestamp_ms"],
        "captured_at": source_event.get("captured_at"),
        "source_object_uri": source_event["object_uri"],
        "model": str(model_path),
        "model_sha256": model_sha256,
        "device": device,
        "image_size": image_size,
        "confidence_threshold": confidence_threshold,
        "original_shape": list(result.orig_shape),
        "detection_count": len(detections),
        "detections": detections,
        "inferred_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json(prediction_path, prediction)
    return prediction


def upload_silver_outputs(
    minio_client: Minio,
    bucket: str,
    camera_id: str,
    detection_id: str,
    annotated_path: Path,
    prediction_path: Path,
) -> tuple[str, str]:
    if not minio_client.bucket_exists(bucket):
        minio_client.make_bucket(bucket)

    prefix = f"detections/{camera_id}/{detection_id}"
    annotated_name = f"{prefix}/annotated.jpg"
    prediction_name = f"{prefix}/prediction.json"
    minio_client.fput_object(
        bucket,
        annotated_name,
        str(annotated_path),
        content_type="image/jpeg",
    )
    minio_client.fput_object(
        bucket,
        prediction_name,
        str(prediction_path),
        content_type="application/json",
    )
    return f"s3://{bucket}/{annotated_name}", f"s3://{bucket}/{prediction_name}"


def process_frame_events(
    input_topic: str,
    output_topic: str,
    group_id: str,
    output_dir: Path,
    model_path: Path,
    silver_bucket: str,
    confidence_threshold: float,
    image_size: int,
    device: str,
    max_messages: int,
    idle_timeout_seconds: float,
    continuous: bool = False,
    heartbeat_file: Path | None = None,
) -> list[dict]:
    if not model_path.is_file():
        raise FileNotFoundError(f"YOLO model does not exist: {model_path}")
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold must be between zero and one")
    if image_size <= 0 or idle_timeout_seconds <= 0:
        raise ValueError("image_size and idle timeout must be positive")
    if not continuous and max_messages <= 0:
        raise ValueError("max_messages must be positive in finite mode")

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
            "client.id": "safesite-inference-producer",
            "enable.idempotence": True,
            "acks": "all",
            "message.timeout.ms": 10000,
        }
    )
    model_hash = sha256(model_path)
    model = YOLO(str(model_path))
    processed = []
    processed_count = 0
    heartbeat = WorkerHeartbeat(heartbeat_file, "ppe-inference")
    heartbeat.update("starting", 0, force=True, input_topic=input_topic, output_topic=output_topic)
    delivery_errors = []
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
                input_topic=input_topic,
                output_topic=output_topic,
            )
            message = consumer.poll(1.0)
            if message is None:
                if not continuous and time.monotonic() >= idle_deadline:
                    raise TimeoutError(
                        f"No frame message arrived within {idle_timeout_seconds} seconds"
                    )
                continue
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(message.error())

            source_event, source_bucket, source_object = parse_event(
                message.value(), message.key()
            )
            raw_dir = output_dir / "raw"
            raw_record = download_event_frame(
                minio_client=minio_client,
                event=source_event,
                bucket=source_bucket,
                object_name=source_object,
                output_dir=raw_dir,
                kafka_metadata={
                    "topic": message.topic(),
                    "partition": message.partition(),
                    "offset": message.offset(),
                    "consumer_group": group_id,
                },
            )
            source_image_path = Path(raw_record["local_image_path"])
            detection_id = build_detection_id(
                source_event["event_id"], model_hash, confidence_threshold, image_size
            )
            prediction_dir = output_dir / "detections" / detection_id
            annotated_path = prediction_dir / "annotated.jpg"
            prediction_path = prediction_dir / "prediction.json"
            prediction = run_inference(
                model=model,
                input_path=source_image_path,
                annotated_path=annotated_path,
                prediction_path=prediction_path,
                model_path=model_path,
                model_sha256=model_hash,
                confidence_threshold=confidence_threshold,
                image_size=image_size,
                device=device,
                source_event=source_event,
            )
            annotated_uri, prediction_uri = upload_silver_outputs(
                minio_client=minio_client,
                bucket=silver_bucket,
                camera_id=source_event["camera_id"],
                detection_id=detection_id,
                annotated_path=annotated_path,
                prediction_path=prediction_path,
            )
            detection_event = {
                "schema_version": 1,
                "event_id": detection_id,
                "source_event_id": source_event["event_id"],
                "camera_id": source_event["camera_id"],
                "sample_index": source_event["sample_index"],
                "video_timestamp_ms": source_event["video_timestamp_ms"],
                "captured_at": source_event.get("captured_at"),
                "source_object_uri": source_event["object_uri"],
                "annotated_object_uri": annotated_uri,
                "prediction_object_uri": prediction_uri,
                "model_sha256": model_hash,
                "confidence_threshold": confidence_threshold,
                "image_size": image_size,
                "detection_count": prediction["detection_count"],
                "detections": prediction["detections"],
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
            producer.produce(
                output_topic,
                key=str(source_event["camera_id"]).encode("utf-8"),
                value=json.dumps(detection_event, separators=(",", ":")).encode("utf-8"),
                on_delivery=delivery_report,
            )
            remaining_messages = producer.flush(10)
            if remaining_messages or delivery_errors:
                details = "; ".join(delivery_errors) or f"{remaining_messages} pending"
                raise RuntimeError(f"Detection-event delivery failed: {details}")

            consumer.commit(message=message, asynchronous=False)
            record = {
                "source_kafka": {
                    "topic": message.topic(),
                    "partition": message.partition(),
                    "offset": message.offset(),
                    "committed_next_offset": message.offset() + 1,
                    "consumer_group": group_id,
                },
                "detection_topic": output_topic,
                "detection_event": detection_event,
                "local_annotated_image": str(annotated_path),
                "local_prediction_json": str(prediction_path),
            }
            atomic_write_json(prediction_dir / "processing_record.json", record)
            processed_count += 1
            heartbeat.update(
                "running",
                processed_count,
                force=True,
                input_topic=input_topic,
                output_topic=output_topic,
                last_event_id=detection_event["event_id"],
                last_camera_id=source_event["camera_id"],
            )
            if not continuous:
                processed.append(record)
            idle_deadline = time.monotonic() + idle_timeout_seconds
    finally:
        consumer.close()
        heartbeat.update("stopped", processed_count, force=True)

    return processed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consume MinIO frame events, run YOLO, and publish detection events."
    )
    parser.add_argument("--input-topic", default="safesite.frames.raw")
    parser.add_argument("--output-topic", default="safesite.detections")
    parser.add_argument("--group-id", default="safesite-yolo-inference")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("/data/models/yolo26n.pt"))
    parser.add_argument("--silver-bucket", default="safesite-silver")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-messages", type=int, default=1)
    parser.add_argument("--idle-timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Wait indefinitely and process messages until the service is stopped.",
    )
    parser.add_argument("--heartbeat-file", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = process_frame_events(
        input_topic=args.input_topic,
        output_topic=args.output_topic,
        group_id=args.group_id,
        output_dir=args.output_dir,
        model_path=args.model,
        silver_bucket=args.silver_bucket,
        confidence_threshold=args.confidence,
        image_size=args.image_size,
        device=args.device,
        max_messages=args.max_messages,
        idle_timeout_seconds=args.idle_timeout_seconds,
        continuous=args.continuous,
        heartbeat_file=args.heartbeat_file,
    )
    print(
        json.dumps(
            {
                "processed_frames": len(records),
                "input_topic": args.input_topic,
                "output_topic": args.output_topic,
                "consumer_group": args.group_id,
                "records": records,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
