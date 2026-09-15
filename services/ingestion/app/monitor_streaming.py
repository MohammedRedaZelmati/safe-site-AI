import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from confluent_kafka import Consumer, TopicPartition


def parse_named_value(value: str) -> tuple[str, str]:
    name, separator, data = value.partition("=")
    if not separator or not name or not data:
        raise argparse.ArgumentTypeError("Expected NAME=VALUE")
    return name, data


def kafka_lag(topic: str, group_id: str) -> dict:
    consumer = Consumer(
        {
            "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092"),
            "group.id": group_id,
            "enable.auto.commit": False,
        }
    )
    try:
        metadata = consumer.list_topics(topic, timeout=5)
        topic_metadata = metadata.topics.get(topic)
        if topic_metadata is None or topic_metadata.error is not None:
            raise RuntimeError(f"Kafka topic unavailable: {topic}")
        partitions = [TopicPartition(topic, partition_id) for partition_id in topic_metadata.partitions]
        committed = consumer.committed(partitions, timeout=5)
        partition_lag = {}
        for partition in committed:
            low, high = consumer.get_watermark_offsets(
                TopicPartition(topic, partition.partition), timeout=5
            )
            next_offset = partition.offset if partition.offset >= 0 else low
            partition_lag[str(partition.partition)] = max(high - next_offset, 0)
        return {
            "topic": topic,
            "group_id": group_id,
            "partition_lag": partition_lag,
            "total_lag": sum(partition_lag.values()),
        }
    finally:
        consumer.close()


def read_heartbeat(path: Path, stale_after_seconds: float) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    updated_at = datetime.fromisoformat(payload["updated_at"].replace("Z", "+00:00"))
    age_seconds = (datetime.now(timezone.utc) - updated_at).total_seconds()
    return {**payload, "age_seconds": round(age_seconds, 2), "stale": age_seconds > stale_after_seconds}


def endpoint_status(url: str) -> dict:
    started = time.monotonic()
    with urlopen(url, timeout=5) as response:
        body = response.read().decode("utf-8", errors="replace")
        return {
            "url": url,
            "status_code": response.status,
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
            "body": body[:500],
        }


def build_report(
    pipelines: list[tuple[str, str]],
    heartbeats: list[tuple[str, str]],
    lag_warning: int,
    stale_after_seconds: float,
    api_health_url: str,
    minio_health_url: str,
) -> dict:
    alerts = []
    lag_results = {}
    for name, specification in pipelines:
        topic, separator, group_id = specification.partition(",")
        try:
            if not separator:
                raise ValueError("Pipeline must use NAME=TOPIC,GROUP")
            result = kafka_lag(topic, group_id)
            lag_results[name] = result
            if result["total_lag"] > lag_warning:
                alerts.append(f"{name} lag is {result['total_lag']} messages")
        except Exception as error:
            lag_results[name] = {"error": str(error)}
            alerts.append(f"{name} lag check failed: {error}")

    heartbeat_results = {}
    for name, path_text in heartbeats:
        try:
            heartbeat_results[name] = read_heartbeat(Path(path_text), stale_after_seconds)
            if heartbeat_results[name]["stale"]:
                alerts.append(f"{name} heartbeat is stale")
            if heartbeat_results[name].get("status") not in {"starting", "waiting", "running"}:
                alerts.append(
                    f"{name} worker status is {heartbeat_results[name].get('status', 'unknown')}"
                )
        except Exception as error:
            heartbeat_results[name] = {"error": str(error)}
            alerts.append(f"{name} heartbeat check failed: {error}")

    endpoints = {}
    for name, url in (("api", api_health_url), ("minio", minio_health_url)):
        try:
            endpoints[name] = endpoint_status(url)
        except Exception as error:
            endpoints[name] = {"url": url, "error": str(error)}
            alerts.append(f"{name} health check failed: {error}")

    return {
        "schema_version": 1,
        "status": "healthy" if not alerts else "degraded",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "alerts": alerts,
        "kafka": lag_results,
        "heartbeats": heartbeat_results,
        "endpoints": endpoints,
    }


def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    try:
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor worker heartbeats, Kafka lag, API, and MinIO.")
    parser.add_argument("--pipeline", action="append", default=[], type=parse_named_value)
    parser.add_argument("--heartbeat", action="append", default=[], type=parse_named_value)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lag-warning", type=int, default=10)
    parser.add_argument("--stale-after-seconds", type=float, default=15)
    parser.add_argument("--api-health-url", default="http://api:8000/health")
    parser.add_argument("--minio-health-url", default="http://minio:9000/minio/health/live")
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.lag_warning < 0 or args.stale_after_seconds <= 0 or args.interval_seconds <= 0:
        raise ValueError("monitor thresholds and interval are invalid")
    while True:
        report = build_report(
            pipelines=args.pipeline,
            heartbeats=args.heartbeat,
            lag_warning=args.lag_warning,
            stale_after_seconds=args.stale_after_seconds,
            api_health_url=args.api_health_url,
            minio_health_url=args.minio_health_url,
        )
        atomic_write(args.output, report)
        print(json.dumps(report), flush=True)
        if not args.continuous:
            raise SystemExit(0 if report["status"] == "healthy" else 1)
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
