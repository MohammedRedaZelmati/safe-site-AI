import argparse
import hashlib
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer

from app.consume_frames import EVENT_ID_PATTERN, atomic_write_json
from app.publish_candidate_events import build_payload, parse_base_time
from app.worker_runtime import WorkerHeartbeat


SUPPORTED_API_TYPES = {"NO_HELMET"}
REQUIRED_FIELDS = {
    "event_id",
    "camera_id",
    "track_id",
    "violation_type",
    "video_timestamp_ms",
    "confidence",
    "frame_uri",
}


def parse_candidate_event(message_value: bytes, message_key: bytes | None) -> dict:
    try:
        candidate = json.loads(message_value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Candidate message is not valid UTF-8 JSON") from error
    if not isinstance(candidate, dict):
        raise ValueError("Candidate message must be a JSON object")
    missing = REQUIRED_FIELDS - candidate.keys()
    if missing:
        raise ValueError(f"Candidate event is missing: {', '.join(sorted(missing))}")
    if not EVENT_ID_PATTERN.fullmatch(str(candidate["event_id"])):
        raise ValueError("event_id must be a lowercase 64-character SHA256 value")
    if not isinstance(candidate["camera_id"], str) or not 1 <= len(candidate["camera_id"]) <= 64:
        raise ValueError("camera_id must contain between 1 and 64 characters")
    if (
        not isinstance(candidate["track_id"], int)
        or isinstance(candidate["track_id"], bool)
        or candidate["track_id"] < 0
    ):
        raise ValueError("track_id must be a non-negative integer")
    if (
        not isinstance(candidate["confidence"], (int, float))
        or isinstance(candidate["confidence"], bool)
        or not 0 <= candidate["confidence"] <= 1
    ):
        raise ValueError("confidence must be between zero and one")
    if (
        not isinstance(candidate["video_timestamp_ms"], (int, float))
        or isinstance(candidate["video_timestamp_ms"], bool)
        or candidate["video_timestamp_ms"] < 0
    ):
        raise ValueError("video_timestamp_ms must be zero or greater")
    if not isinstance(candidate["frame_uri"], str) or not candidate["frame_uri"]:
        raise ValueError("frame_uri must be a non-empty string")
    key = message_key.decode("utf-8") if message_key is not None else None
    if key != candidate["camera_id"]:
        raise ValueError(
            f"Kafka key {key!r} does not match camera_id {candidate['camera_id']!r}"
        )
    return candidate


def post_json_with_retries(
    url: str,
    payload: dict,
    max_attempts: int,
    retry_backoff_seconds: float,
) -> tuple[int, object, int]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(1, max_attempts + 1):
        try:
            with urlopen(request, timeout=10) as response:
                response_body = json.loads(response.read().decode("utf-8"))
                return response.status, response_body, attempt
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            try:
                response_body = json.loads(details)
            except json.JSONDecodeError:
                response_body = {"detail": details}
            if error.code < 500:
                return error.code, response_body, attempt
            last_error = RuntimeError(f"API returned HTTP {error.code}: {details}")
        except (URLError, TimeoutError) as error:
            last_error = RuntimeError(f"Could not reach API: {error}")

        if attempt < max_attempts:
            time.sleep(retry_backoff_seconds * attempt)
    raise last_error


def publish_confirmed(
    producer: Producer,
    topic: str,
    key: bytes,
    value: dict,
) -> None:
    delivery_errors = []

    def delivery_report(error, message) -> None:
        if error is not None:
            delivery_errors.append(str(error))

    producer.produce(
        topic,
        key=key,
        value=json.dumps(value, separators=(",", ":")).encode("utf-8"),
        on_delivery=delivery_report,
    )
    remaining = producer.flush(10)
    if remaining or delivery_errors:
        details = "; ".join(delivery_errors) or f"{remaining} pending"
        raise RuntimeError(f"Kafka delivery failed: {details}")


def dead_letter_event(message, error: str) -> dict:
    raw_value = message.value()
    return {
        "schema_version": 1,
        "source_topic": message.topic(),
        "source_partition": message.partition(),
        "source_offset": message.offset(),
        "source_key": (
            message.key().decode("utf-8", errors="replace")
            if message.key() is not None
            else None
        ),
        "raw_value": raw_value.decode("utf-8", errors="replace"),
        "error": error,
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }


def consume_candidate_events(
    topic: str,
    dead_letter_topic: str,
    group_id: str,
    output_dir: Path,
    base_occurred_at: datetime | None,
    api_url: str,
    max_messages: int,
    idle_timeout_seconds: float,
    max_attempts: int,
    retry_backoff_seconds: float,
    continuous: bool = False,
    heartbeat_file: Path | None = None,
) -> dict:
    if not continuous and output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")
    if idle_timeout_seconds <= 0 or max_attempts <= 0:
        raise ValueError("timeout and attempts must be positive")
    if not continuous and max_messages <= 0:
        raise ValueError("max_messages must be positive in finite mode")
    if retry_backoff_seconds < 0:
        raise ValueError("retry_backoff_seconds must be zero or greater")
    if not api_url.startswith(("http://", "https://")):
        raise ValueError("api_url must start with http:// or https://")

    output_dir.mkdir(parents=True, exist_ok=True)
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
            "client.id": "safesite-candidate-dlq-producer",
            "enable.idempotence": True,
            "acks": "all",
            "message.timeout.ms": 10000,
        }
    )
    results = []
    processed_count = 0
    status_counts = Counter()
    heartbeat = WorkerHeartbeat(heartbeat_file, "candidate-api-delivery")
    heartbeat.update("starting", 0, force=True, topic=topic, api_url=api_url)
    idle_deadline = time.monotonic() + idle_timeout_seconds

    consumer.subscribe([topic])
    try:
        while continuous or processed_count < max_messages:
            heartbeat.update("waiting", processed_count, topic=topic, api_url=api_url)
            message = consumer.poll(1.0)
            if message is None:
                if not continuous and time.monotonic() >= idle_deadline:
                    raise TimeoutError(
                        f"No candidate message arrived within {idle_timeout_seconds} seconds"
                    )
                continue
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(message.error())

            try:
                candidate = parse_candidate_event(message.value(), message.key())
            except ValueError as error:
                dlq_event = dead_letter_event(message, str(error))
                publish_confirmed(
                    producer,
                    dead_letter_topic,
                    message.key() or b"invalid",
                    dlq_event,
                )
                result = {
                    "status": "dead_letter_invalid_event",
                    "error": str(error),
                    "dead_letter_event": dlq_event,
                }
            else:
                if candidate["violation_type"] not in SUPPORTED_API_TYPES:
                    error = (
                        f"Unsupported API violation type: {candidate['violation_type']}"
                    )
                    dlq_event = dead_letter_event(message, error)
                    publish_confirmed(
                        producer,
                        dead_letter_topic,
                        message.key() or b"invalid",
                        dlq_event,
                    )
                    result = {
                        "status": "dead_letter_unsupported_type",
                        "candidate_event_id": candidate["event_id"],
                        "error": error,
                        "dead_letter_event": dlq_event,
                    }
                else:
                    try:
                        payload = build_payload(candidate, base_occurred_at)
                    except ValueError as error:
                        dlq_event = dead_letter_event(message, str(error))
                        publish_confirmed(
                            producer,
                            dead_letter_topic,
                            message.key() or b"invalid",
                            dlq_event,
                        )
                        result = {
                            "status": "dead_letter_missing_event_time",
                            "candidate_event_id": candidate["event_id"],
                            "error": str(error),
                            "dead_letter_event": dlq_event,
                        }
                    else:
                        response_status, response_body, attempts = post_json_with_retries(
                            f"{api_url.rstrip('/')}/violations",
                            payload,
                            max_attempts=max_attempts,
                            retry_backoff_seconds=retry_backoff_seconds,
                        )
                        if response_status == 201:
                            publish_status = "published"
                        elif response_status == 200:
                            publish_status = "skipped_duplicate"
                        else:
                            error = f"API rejected candidate with HTTP {response_status}"
                            dlq_event = dead_letter_event(message, error)
                            dlq_event["api_response"] = response_body
                            publish_confirmed(
                                producer,
                                dead_letter_topic,
                                message.key() or b"invalid",
                                dlq_event,
                            )
                            result = {
                                "status": "dead_letter_api_rejection",
                                "candidate_event_id": candidate["event_id"],
                                "payload": payload,
                                "api_status_code": response_status,
                                "api_response": response_body,
                                "dead_letter_event": dlq_event,
                            }
                            publish_status = None
                        if publish_status is not None:
                            result = {
                                "status": publish_status,
                                "candidate_event_id": candidate["event_id"],
                                "payload": payload,
                                "api_status_code": response_status,
                                "api_response": response_body,
                                "attempts": attempts,
                            }

            consumer.commit(message=message, asynchronous=False)
            result["source_kafka"] = {
                "topic": message.topic(),
                "partition": message.partition(),
                "offset": message.offset(),
                "committed_next_offset": message.offset() + 1,
                "consumer_group": group_id,
            }
            result_id = result.get("candidate_event_id") or hashlib.sha256(
                message.value()
            ).hexdigest()
            atomic_write_json(output_dir / f"{result_id}-{message.offset()}.json", result)
            processed_count += 1
            if not continuous:
                results.append(result)
            status_counts[result["status"]] += 1
            heartbeat.update(
                "running",
                processed_count,
                force=True,
                topic=topic,
                api_url=api_url,
                last_status=result["status"],
                last_candidate_event_id=result.get("candidate_event_id"),
            )
            idle_deadline = time.monotonic() + idle_timeout_seconds
    finally:
        consumer.close()
        heartbeat.update("stopped", processed_count, force=True, topic=topic)

    summary = {
        "topic": topic,
        "dead_letter_topic": dead_letter_topic,
        "consumer_group": group_id,
        "api_url": api_url,
        "base_occurred_at": base_occurred_at.isoformat() if base_occurred_at else None,
        "messages_handled": processed_count,
        "status_counts": dict(sorted(status_counts.items())),
        "supported_api_types": sorted(SUPPORTED_API_TYPES),
        "commit_rule": "Commit only after API success, duplicate confirmation, or confirmed DLQ delivery",
        "retry_rule": "Retry network and server failures; route permanent failures to the DLQ",
    }
    atomic_write_json(output_dir / "summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consume confirmed Kafka candidates and publish them safely to FastAPI."
    )
    parser.add_argument("--topic", default="safesite.candidate-violations")
    parser.add_argument(
        "--dead-letter-topic", default="safesite.candidate-violations.dlq"
    )
    parser.add_argument("--group-id", default="safesite-candidate-api-publisher")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-occurred-at")
    parser.add_argument("--api-url", default="http://api:8000")
    parser.add_argument("--max-messages", type=int, default=1)
    parser.add_argument("--idle-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-backoff-seconds", type=float, default=1.0)
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--heartbeat-file", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = consume_candidate_events(
        topic=args.topic,
        dead_letter_topic=args.dead_letter_topic,
        group_id=args.group_id,
        output_dir=args.output_dir,
        base_occurred_at=(
            parse_base_time(args.base_occurred_at) if args.base_occurred_at else None
        ),
        api_url=args.api_url,
        max_messages=args.max_messages,
        idle_timeout_seconds=args.idle_timeout_seconds,
        max_attempts=args.max_attempts,
        retry_backoff_seconds=args.retry_backoff_seconds,
        continuous=args.continuous,
        heartbeat_file=args.heartbeat_file,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
