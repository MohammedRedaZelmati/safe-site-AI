import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import cv2
from confluent_kafka import Producer
from minio import Minio

from app.publish_frames import parse_minio_endpoint
from app.worker_runtime import WorkerHeartbeat


def stream_camera(
    source: str,
    camera_id: str,
    topic: str,
    bucket: str,
    object_prefix: str,
    sample_fps: float,
    jpeg_quality: int,
    max_frames: int | None,
    loop_source: bool,
    realtime: bool,
    heartbeat_file: Path | None,
) -> dict:
    if not camera_id or len(camera_id) > 64:
        raise ValueError("camera_id must contain between 1 and 64 characters")
    if sample_fps <= 0:
        raise ValueError("sample_fps must be greater than zero")
    if not 1 <= jpeg_quality <= 100:
        raise ValueError("jpeg_quality must be between 1 and 100")
    if max_frames is not None and max_frames <= 0:
        raise ValueError("max_frames must be greater than zero")

    capture = cv2.VideoCapture(int(source) if source.isdigit() else source)
    if not capture.isOpened():
        raise RuntimeError(f"Could not open camera source: {source}")
    source_fps = float(capture.get(cv2.CAP_PROP_FPS))
    if source_fps <= 0:
        source_fps = sample_fps
    sample_every = max(round(source_fps / sample_fps), 1)

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
            "client.id": f"safesite-camera-{camera_id}",
            "enable.idempotence": True,
            "acks": "all",
            "message.timeout.ms": 10000,
        }
    )
    heartbeat = WorkerHeartbeat(heartbeat_file, f"camera-ingestion:{camera_id}")
    heartbeat.update("starting", 0, force=True, source=source, topic=topic)
    sequence = 0
    source_frame_index = 0
    stream_started = time.monotonic()
    delivery_errors = []

    def delivery_report(error, message) -> None:
        if error is not None:
            delivery_errors.append(str(error))

    try:
        while max_frames is None or sequence < max_frames:
            success, frame = capture.read()
            if not success:
                if loop_source:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    source_frame_index = 0
                    continue
                break
            current_frame_index = source_frame_index
            source_frame_index += 1
            if current_frame_index % sample_every != 0:
                heartbeat.update("waiting", sequence, camera_id=camera_id, topic=topic)
                continue

            captured_at = datetime.now(timezone.utc)
            source_video_timestamp_ms = max(int(capture.get(cv2.CAP_PROP_POS_MSEC)), 0)
            video_timestamp_ms = int((time.monotonic() - stream_started) * 1000)
            encoded, jpeg = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
            )
            if not encoded:
                raise RuntimeError("OpenCV could not encode the camera frame")
            jpeg_bytes = jpeg.tobytes()
            timestamp_token = captured_at.strftime("%Y%m%dT%H%M%S%fZ")
            object_name = (
                f"{object_prefix.strip('/')}/{camera_id}/{timestamp_token}-{sequence:09d}.jpg"
            )
            minio_client.put_object(
                bucket,
                object_name,
                BytesIO(jpeg_bytes),
                length=len(jpeg_bytes),
                content_type="image/jpeg",
                metadata={"camera-id": camera_id, "captured-at": captured_at.isoformat()},
            )
            identity = f"{camera_id}:{captured_at.isoformat()}:{sequence}:{hashlib.sha256(jpeg_bytes).hexdigest()}"
            event = {
                "schema_version": 2,
                "event_id": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                "camera_id": camera_id,
                "sample_index": sequence,
                "source_frame_index": current_frame_index,
                "video_timestamp_ms": video_timestamp_ms,
                "source_video_timestamp_ms": source_video_timestamp_ms,
                "source_fps": source_fps,
                "captured_at": captured_at.isoformat(),
                "source_type": "camera" if source.isdigit() or "://" in source else "video_simulation",
                "object_uri": f"s3://{bucket}/{object_name}",
                "content_type": "image/jpeg",
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
            producer.produce(
                topic,
                key=camera_id.encode("utf-8"),
                value=json.dumps(event, separators=(",", ":")).encode("utf-8"),
                on_delivery=delivery_report,
            )
            remaining = producer.flush(10)
            if remaining or delivery_errors:
                details = "; ".join(delivery_errors) or f"{remaining} pending"
                raise RuntimeError(f"Camera event delivery failed: {details}")
            sequence += 1
            heartbeat.update(
                "running",
                sequence,
                force=True,
                camera_id=camera_id,
                topic=topic,
                last_event_id=event["event_id"],
                last_captured_at=event["captured_at"],
            )
            if realtime:
                time.sleep(1 / sample_fps)
    finally:
        capture.release()
        producer.flush(10)
        heartbeat.update("stopped", sequence, force=True, camera_id=camera_id, topic=topic)

    return {
        "camera_id": camera_id,
        "source": source,
        "topic": topic,
        "frames_published": sequence,
        "sample_fps": sample_fps,
        "source_fps": source_fps,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Continuously sample a camera or video and publish timestamped Bronze events."
    )
    parser.add_argument("--source", required=True)
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--topic", default="safesite.frames.raw")
    parser.add_argument("--bucket", default="safesite-bronze")
    parser.add_argument("--object-prefix", default="live-frames")
    parser.add_argument("--sample-fps", type=float, default=5.0)
    parser.add_argument("--jpeg-quality", type=int, default=90)
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--realtime", action="store_true")
    parser.add_argument("--heartbeat-file", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = stream_camera(
        source=args.source,
        camera_id=args.camera_id,
        topic=args.topic,
        bucket=args.bucket,
        object_prefix=args.object_prefix,
        sample_fps=args.sample_fps,
        jpeg_quality=args.jpeg_quality,
        max_frames=args.max_frames,
        loop_source=args.loop,
        realtime=args.realtime,
        heartbeat_file=args.heartbeat_file,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
