import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from confluent_kafka import Producer
from minio import Minio


def parse_minio_endpoint(endpoint: str) -> tuple[str, bool]:
    parsed = urlparse(endpoint if "://" in endpoint else f"http://{endpoint}")
    if not parsed.netloc or parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Invalid MinIO endpoint: {endpoint}")
    return parsed.netloc, parsed.scheme == "https"


def load_frames(
    manifest_path: Path,
    limit: int | None,
    start_sample_index: int = 0,
) -> list[dict]:
    if limit is not None and limit <= 0:
        raise ValueError("limit must be greater than zero")
    if start_sample_index < 0:
        raise ValueError("start_sample_index cannot be negative")
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Frame manifest does not exist: {manifest_path}")

    frames = []
    with manifest_path.open(encoding="utf-8") as manifest:
        for line_number, line in enumerate(manifest, start=1):
            if not line.strip():
                continue
            frame = json.loads(line)
            required_fields = {
                "camera_id",
                "sample_index",
                "source_frame_index",
                "video_timestamp_ms",
                "source_fps",
                "image_path",
            }
            missing_fields = required_fields - frame.keys()
            if missing_fields:
                missing = ", ".join(sorted(missing_fields))
                raise ValueError(f"Manifest line {line_number} is missing: {missing}")

            image_path = Path(frame["image_path"])
            if not image_path.is_file():
                raise FileNotFoundError(
                    f"Manifest line {line_number} references a missing image: {image_path}"
                )
            if not str(frame["camera_id"]).strip():
                raise ValueError(f"Manifest line {line_number} has an empty camera_id")
            sample_index = int(frame["sample_index"])
            if sample_index < 0 or int(frame["video_timestamp_ms"]) < 0:
                raise ValueError(f"Manifest line {line_number} contains a negative index or timestamp")
            if sample_index < start_sample_index:
                continue

            frames.append(frame)
            if limit is not None and len(frames) >= limit:
                break

    if not frames:
        raise ValueError(f"Frame manifest contains no records: {manifest_path}")
    return frames


def build_event(frame: dict, bucket: str, object_name: str) -> dict:
    identity = ":".join(
        [
            str(frame["camera_id"]),
            str(frame["sample_index"]),
            str(frame["video_timestamp_ms"]),
            bucket,
            object_name,
        ]
    )
    return {
        "schema_version": 1,
        "event_id": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        "camera_id": frame["camera_id"],
        "sample_index": int(frame["sample_index"]),
        "source_frame_index": int(frame["source_frame_index"]),
        "video_timestamp_ms": int(frame["video_timestamp_ms"]),
        "source_fps": float(frame["source_fps"]),
        "object_uri": f"s3://{bucket}/{object_name}",
        "content_type": "image/jpeg",
        "published_at": datetime.now(timezone.utc).isoformat(),
    }


def publish_frames(
    manifest_path: Path,
    bucket: str,
    object_prefix: str,
    topic: str,
    limit: int | None,
    start_sample_index: int = 0,
) -> list[dict]:
    frames = load_frames(manifest_path, limit, start_sample_index)
    minio_endpoint, minio_secure = parse_minio_endpoint(
        os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    )
    minio_client = Minio(
        minio_endpoint,
        access_key=os.getenv("MINIO_ACCESS_KEY", "safesite"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "safesite_dev_password"),
        secure=minio_secure,
    )
    if not minio_client.bucket_exists(bucket):
        minio_client.make_bucket(bucket)

    producer = Producer(
        {
            "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092"),
            "client.id": "safesite-frame-producer",
            "enable.idempotence": True,
            "acks": "all",
            "message.timeout.ms": 10000,
        }
    )
    delivery_errors = []
    published_events = []

    def delivery_report(error, message) -> None:
        if error is not None:
            delivery_errors.append(str(error))

    for frame in frames:
        image_path = Path(frame["image_path"])
        object_name = "/".join(
            part.strip("/")
            for part in (object_prefix, str(frame["camera_id"]), image_path.name)
            if part.strip("/")
        )
        minio_client.fput_object(
            bucket,
            object_name,
            str(image_path),
            content_type="image/jpeg",
            metadata={
                "camera-id": str(frame["camera_id"]),
                "video-timestamp-ms": str(frame["video_timestamp_ms"]),
            },
        )
        event = build_event(frame, bucket, object_name)
        producer.produce(
            topic,
            key=str(frame["camera_id"]).encode("utf-8"),
            value=json.dumps(event, separators=(",", ":")).encode("utf-8"),
            on_delivery=delivery_report,
        )
        producer.poll(0)
        published_events.append(event)

    remaining_messages = producer.flush(10)
    if remaining_messages or delivery_errors:
        details = "; ".join(delivery_errors) or f"{remaining_messages} message(s) pending"
        raise RuntimeError(f"Kafka delivery failed: {details}")
    return published_events


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload sampled JPEG frames to MinIO and publish their metadata to Kafka."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--bucket", default="safesite-bronze")
    parser.add_argument("--object-prefix", default="raw-frames")
    parser.add_argument("--topic", default="safesite.frames.raw")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--start-sample-index", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    events = publish_frames(
        manifest_path=args.manifest,
        bucket=args.bucket,
        object_prefix=args.object_prefix,
        topic=args.topic,
        limit=args.limit,
        start_sample_index=args.start_sample_index,
    )
    print(
        json.dumps(
            {
                "uploaded_objects": len(events),
                "published_messages": len(events),
                "bucket": args.bucket,
                "topic": args.topic,
                "start_sample_index": args.start_sample_index,
                "events": events,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
