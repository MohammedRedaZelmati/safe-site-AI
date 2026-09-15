import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from confluent_kafka import Consumer, KafkaError, KafkaException
from minio import Minio

from app.publish_frames import parse_minio_endpoint


EVENT_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_FIELDS = {
    "schema_version",
    "event_id",
    "camera_id",
    "sample_index",
    "source_frame_index",
    "video_timestamp_ms",
    "source_fps",
    "object_uri",
    "content_type",
    "published_at",
}


def parse_event(message_value: bytes, message_key: bytes | None) -> tuple[dict, str, str]:
    try:
        event = json.loads(message_value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Kafka message value is not valid UTF-8 JSON") from error
    if not isinstance(event, dict):
        raise ValueError("Kafka message value must be a JSON object")

    missing_fields = REQUIRED_FIELDS - event.keys()
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise ValueError(f"Frame event is missing: {missing}")
    if event["schema_version"] not in {1, 2}:
        raise ValueError(f"Unsupported frame-event schema: {event['schema_version']}")
    if event["schema_version"] == 2:
        captured_at = event.get("captured_at")
        if not isinstance(captured_at, str):
            raise ValueError("Version 2 frame events require captured_at")
        try:
            parsed_capture_time = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("captured_at must be a valid ISO 8601 timestamp") from error
        if parsed_capture_time.tzinfo is None or parsed_capture_time.utcoffset() is None:
            raise ValueError("captured_at must include a timezone offset")
    if not EVENT_ID_PATTERN.fullmatch(str(event["event_id"])):
        raise ValueError("event_id must be a lowercase 64-character SHA256 value")
    if event["content_type"] != "image/jpeg":
        raise ValueError(f"Unsupported content type: {event['content_type']}")
    if int(event["sample_index"]) < 0 or int(event["video_timestamp_ms"]) < 0:
        raise ValueError("Frame event contains a negative index or timestamp")

    key = message_key.decode("utf-8") if message_key is not None else None
    if key != event["camera_id"]:
        raise ValueError(
            f"Kafka key {key!r} does not match camera_id {event['camera_id']!r}"
        )

    object_uri = urlparse(event["object_uri"])
    if object_uri.scheme != "s3" or not object_uri.netloc or not object_uri.path.lstrip("/"):
        raise ValueError(f"Invalid MinIO object URI: {event['object_uri']}")
    return event, object_uri.netloc, object_uri.path.lstrip("/")


def atomic_write_json(path: Path, payload: dict) -> None:
    temporary_path = path.with_suffix(path.suffix + ".part")
    try:
        temporary_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def download_event_frame(
    minio_client: Minio,
    event: dict,
    bucket: str,
    object_name: str,
    output_dir: Path,
    kafka_metadata: dict,
) -> dict:
    event_id = event["event_id"]
    image_path = output_dir / f"{event_id}.jpg"
    temporary_image_path = image_path.with_suffix(".jpg.part")
    metadata_path = output_dir / f"{event_id}.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        minio_client.fget_object(bucket, object_name, str(temporary_image_path))
        temporary_image_path.replace(image_path)
    finally:
        temporary_image_path.unlink(missing_ok=True)

    object_stat = minio_client.stat_object(bucket, object_name)
    record = {
        "event": event,
        "kafka": kafka_metadata,
        "minio": {
            "bucket": bucket,
            "object_name": object_name,
            "etag": object_stat.etag,
            "size_bytes": object_stat.size,
            "content_type": object_stat.content_type,
        },
        "local_image_path": str(image_path),
    }
    atomic_write_json(metadata_path, record)
    return record


def consume_frames(
    topic: str,
    group_id: str,
    output_dir: Path,
    max_messages: int,
    idle_timeout_seconds: float,
) -> list[dict]:
    if max_messages <= 0:
        raise ValueError("max_messages must be greater than zero")
    if idle_timeout_seconds <= 0:
        raise ValueError("idle_timeout_seconds must be greater than zero")

    minio_endpoint, minio_secure = parse_minio_endpoint(
        os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    )
    minio_client = Minio(
        minio_endpoint,
        access_key=os.getenv("MINIO_ACCESS_KEY", "safesite"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "safesite_dev_password"),
        secure=minio_secure,
    )
    consumer = Consumer(
        {
            "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092"),
            "group.id": group_id,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    consumed_records = []
    idle_deadline = time.monotonic() + idle_timeout_seconds

    consumer.subscribe([topic])
    try:
        while len(consumed_records) < max_messages:
            message = consumer.poll(1.0)
            if message is None:
                if time.monotonic() >= idle_deadline:
                    raise TimeoutError(
                        f"No frame message arrived within {idle_timeout_seconds} seconds"
                    )
                continue
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(message.error())

            event, bucket, object_name = parse_event(message.value(), message.key())
            record = download_event_frame(
                minio_client=minio_client,
                event=event,
                bucket=bucket,
                object_name=object_name,
                output_dir=output_dir,
                kafka_metadata={
                    "topic": message.topic(),
                    "partition": message.partition(),
                    "offset": message.offset(),
                    "consumer_group": group_id,
                },
            )
            consumer.commit(message=message, asynchronous=False)
            record["kafka"]["committed_next_offset"] = message.offset() + 1
            atomic_write_json(output_dir / f"{event['event_id']}.json", record)
            consumed_records.append(record)
            idle_deadline = time.monotonic() + idle_timeout_seconds
    finally:
        consumer.close()

    return consumed_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consume frame events from Kafka and download their JPEG objects from MinIO."
    )
    parser.add_argument("--topic", default="safesite.frames.raw")
    parser.add_argument("--group-id", default="safesite-frame-downloader")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-messages", type=int, default=1)
    parser.add_argument("--idle-timeout-seconds", type=float, default=15.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = consume_frames(
        topic=args.topic,
        group_id=args.group_id,
        output_dir=args.output_dir,
        max_messages=args.max_messages,
        idle_timeout_seconds=args.idle_timeout_seconds,
    )
    print(
        json.dumps(
            {
                "consumed_messages": len(records),
                "downloaded_images": len(records),
                "topic": args.topic,
                "consumer_group": args.group_id,
                "records": records,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
