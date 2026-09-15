import argparse
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SUPPORTED_API_TYPES = {"NO_HELMET"}
REQUIRED_CANDIDATE_FIELDS = {
    "camera_id",
    "track_id",
    "violation_type",
    "video_timestamp_ms",
    "confidence",
    "frame_uri",
}


def load_candidates(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"Candidate event file does not exist: {path}")

    candidates = []
    with path.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on candidate line {line_number}") from error
            missing = REQUIRED_CANDIDATE_FIELDS - candidate.keys()
            if missing:
                raise ValueError(
                    f"Candidate line {line_number} is missing fields: {sorted(missing)}"
                )
            candidates.append(candidate)
    return candidates


def parse_base_time(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError("base_occurred_at must be a valid ISO 8601 timestamp") from error
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("base_occurred_at must include a timezone offset")
    return timestamp


def build_payload(candidate: dict, base_occurred_at: datetime | None) -> dict:
    camera_id = candidate["camera_id"]
    track_id = candidate["track_id"]
    violation_type = candidate["violation_type"]
    video_timestamp_ms = candidate["video_timestamp_ms"]
    confidence = candidate["confidence"]

    if not isinstance(camera_id, str) or not 1 <= len(camera_id) <= 64:
        raise ValueError("camera_id must contain between 1 and 64 characters")
    if not isinstance(track_id, int) or isinstance(track_id, bool) or track_id < 0:
        raise ValueError("track_id must be a non-negative integer")
    if violation_type not in SUPPORTED_API_TYPES:
        raise ValueError(f"Unsupported API violation type: {violation_type}")
    if (
        not isinstance(video_timestamp_ms, (int, float))
        or isinstance(video_timestamp_ms, bool)
        or video_timestamp_ms < 0
    ):
        raise ValueError("video_timestamp_ms must be zero or greater")
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 1
    ):
        raise ValueError("confidence must be between 0 and 1")

    candidate_occurred_at = candidate.get("occurred_at")
    if candidate_occurred_at is not None:
        occurred_at = parse_base_time(candidate_occurred_at)
    elif base_occurred_at is not None:
        occurred_at = base_occurred_at + timedelta(milliseconds=video_timestamp_ms)
    else:
        raise ValueError("Candidate requires occurred_at when no base time is supplied")
    return {
        "occurred_at": occurred_at.isoformat(),
        "camera_id": camera_id,
        "track_id": track_id,
        "violation_type": violation_type,
        "confidence": confidence,
        "frame_uri": candidate["frame_uri"],
    }


def request_json(
    url: str, method: str = "GET", payload: dict | None = None
) -> tuple[int, object]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API returned HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach API: {error.reason}") from error

def publish_candidates(
    candidates_path: Path,
    output_dir: Path,
    base_occurred_at: datetime,
    api_url: str,
    send: bool,
) -> dict:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")
    if not api_url.startswith(("http://", "https://")):
        raise ValueError("api_url must start with http:// or https://")

    candidates = load_candidates(candidates_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "publish_results.jsonl"
    summary_path = output_dir / "summary.json"
    status_counts = Counter()

    with results_path.open("w", encoding="utf-8") as results_file:
        for candidate_index, candidate in enumerate(candidates):
            violation_type = candidate["violation_type"]
            if violation_type not in SUPPORTED_API_TYPES:
                result = {
                    "candidate_index": candidate_index,
                    "status": "skipped_unsupported_type",
                    "violation_type": violation_type,
                    "supported_api_types": sorted(SUPPORTED_API_TYPES),
                }
            else:
                payload = build_payload(candidate, base_occurred_at)
                if not send:
                    result = {
                        "candidate_index": candidate_index,
                        "status": "dry_run",
                        "payload": payload,
                    }
                else:
                    response_status, response_body = request_json(
                        f"{api_url}/violations", method="POST", payload=payload
                    )
                    if response_status == 201:
                        publish_status = "published"
                    elif response_status == 200:
                        publish_status = "skipped_duplicate"
                    else:
                        raise RuntimeError(
                            f"Unexpected API success status: {response_status}"
                        )
                    result = {
                        "candidate_index": candidate_index,
                        "status": publish_status,
                        "payload": payload,
                        "api_status_code": response_status,
                        "api_response": response_body,
                    }
            status_counts[result["status"]] += 1
            results_file.write(json.dumps(result) + "\n")

    summary = {
        "candidates": str(candidates_path),
        "results": str(results_path),
        "mode": "send" if send else "dry_run",
        "api_url": api_url,
        "base_occurred_at": base_occurred_at.isoformat(),
        "supported_api_types": sorted(SUPPORTED_API_TYPES),
        "candidate_count": len(candidates),
        "status_counts": dict(sorted(status_counts.items())),
        "safety_rule": "Unsupported types are skipped and sending requires explicit --send",
        "duplicate_rule": "The API event key and PostgreSQL unique index are authoritative",
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate temporal candidate events and optionally publish supported types."
    )
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-occurred-at", required=True)
    parser.add_argument("--api-url", default="http://api:8000")
    parser.add_argument(
        "--send",
        action="store_true",
        help="Publish to FastAPI; without this flag the command is a dry run.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = publish_candidates(
        candidates_path=args.candidates,
        output_dir=args.output_dir,
        base_occurred_at=parse_base_time(args.base_occurred_at),
        api_url=args.api_url.rstrip("/"),
        send=args.send,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
