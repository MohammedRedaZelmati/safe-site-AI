import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as parquet


REQUIRED_FRAME_COLUMNS = {
    "event_id",
    "camera_id",
    "captured_at",
    "event_date",
    "sample_index",
    "video_timestamp_ms",
    "tracked_people",
    "association_count",
    "candidate_count",
}
REQUIRED_WORKER_COLUMNS = {
    "event_id",
    "camera_id",
    "event_date",
    "track_id",
    "positive_evidence",
    "violation_evidence",
    "has_violation_evidence",
}
REQUIRED_DAILY_COLUMNS = {
    "event_date",
    "camera_id",
    "frame_count",
    "unique_event_count",
    "tracked_person_observations",
    "association_count",
    "candidate_count",
    "worker_evidence_rows",
    "violation_evidence_rows",
}


def write_json_atomic(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def validate_quality(output_dir: Path, report_path: Path | None = None) -> dict:
    output_dir = output_dir.resolve()
    report_path = (report_path or output_dir / "quality-report.json").resolve()
    frames_table = parquet.read_table(output_dir / "frames.parquet")
    worker_table = parquet.read_table(output_dir / "worker_evidence.parquet")
    daily_table = parquet.read_table(output_dir / "daily_camera_summary.parquet")
    frames = frames_table.to_pylist()
    workers = worker_table.to_pylist()
    daily_rows = daily_table.to_pylist()
    checks = []

    def add_check(name: str, passed: bool, expectation: str, observed: object) -> None:
        checks.append(
            {
                "name": name,
                "status": "passed" if passed else "failed",
                "expectation": expectation,
                "observed": observed,
            }
        )

    frame_columns = set(frames_table.column_names)
    worker_columns = set(worker_table.column_names)
    daily_columns = set(daily_table.column_names)
    add_check("frames_not_empty", bool(frames), "at least one frame row", len(frames))
    add_check(
        "frame_schema",
        REQUIRED_FRAME_COLUMNS <= frame_columns,
        "all required frame columns exist",
        sorted(REQUIRED_FRAME_COLUMNS - frame_columns),
    )
    add_check(
        "worker_schema",
        REQUIRED_WORKER_COLUMNS <= worker_columns,
        "all required worker columns exist",
        sorted(REQUIRED_WORKER_COLUMNS - worker_columns),
    )
    add_check(
        "daily_schema",
        REQUIRED_DAILY_COLUMNS <= daily_columns,
        "all required daily columns exist",
        sorted(REQUIRED_DAILY_COLUMNS - daily_columns),
    )

    event_ids = [row.get("event_id") for row in frames]
    invalid_event_ids = [value for value in event_ids if not isinstance(value, str) or not value]
    event_id_counts = Counter(value for value in event_ids if value)
    duplicate_event_ids = sorted(
        value for value, count in event_id_counts.items() if count > 1
    )
    invalid_cameras = [
        row.get("camera_id")
        for row in frames
        if not isinstance(row.get("camera_id"), str) or not row.get("camera_id")
    ]
    add_check(
        "event_ids_present",
        not invalid_event_ids,
        "every frame has a non-empty event_id",
        len(invalid_event_ids),
    )
    add_check(
        "event_ids_unique",
        not duplicate_event_ids,
        "event_id is unique across Gold frames",
        duplicate_event_ids,
    )
    add_check(
        "camera_ids_present",
        not invalid_cameras,
        "every frame has a non-empty camera_id",
        len(invalid_cameras),
    )

    invalid_times = []
    for row in frames:
        captured_at = row.get("captured_at")
        if not isinstance(captured_at, datetime) or captured_at.utcoffset() is None:
            invalid_times.append(row.get("event_id"))
        elif captured_at.astimezone(timezone.utc).utcoffset().total_seconds() != 0:
            invalid_times.append(row.get("event_id"))
    add_check(
        "captured_at_timezone",
        not invalid_times,
        "every captured_at is timezone-aware UTC",
        invalid_times,
    )

    count_columns = (
        "sample_index",
        "video_timestamp_ms",
        "tracked_people",
        "association_count",
        "candidate_count",
    )
    invalid_counts = []
    for row in frames:
        for column in count_columns:
            value = row.get(column)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                invalid_counts.append({"event_id": row.get("event_id"), "column": column})
    add_check(
        "non_negative_counts",
        not invalid_counts,
        "frame indexes and counts are non-negative integers",
        invalid_counts,
    )

    frame_event_ids = set(event_ids)
    orphan_worker_events = sorted(
        {
            row.get("event_id")
            for row in workers
            if row.get("event_id") not in frame_event_ids
        }
    )
    add_check(
        "worker_frame_relationship",
        not orphan_worker_events,
        "every worker evidence row belongs to a frame",
        orphan_worker_events,
    )

    expected_daily = defaultdict(
        lambda: {
            "frame_count": 0,
            "event_ids": set(),
            "tracked_person_observations": 0,
            "association_count": 0,
            "candidate_count": 0,
            "worker_evidence_rows": 0,
            "violation_evidence_rows": 0,
        }
    )
    for row in frames:
        key = (row.get("event_date"), row.get("camera_id"))
        expected_daily[key]["frame_count"] += 1
        expected_daily[key]["event_ids"].add(row.get("event_id"))
        expected_daily[key]["tracked_person_observations"] += row.get(
            "tracked_people", 0
        )
        expected_daily[key]["association_count"] += row.get("association_count", 0)
        expected_daily[key]["candidate_count"] += row.get("candidate_count", 0)
    for row in workers:
        key = (row.get("event_date"), row.get("camera_id"))
        expected_daily[key]["worker_evidence_rows"] += 1
        expected_daily[key]["violation_evidence_rows"] += bool(
            row.get("has_violation_evidence")
        )

    daily_mismatches = []
    actual_keys = set()
    for row in daily_rows:
        key = (row.get("event_date"), row.get("camera_id"))
        actual_keys.add(key)
        expected = expected_daily.get(key)
        if expected is None:
            daily_mismatches.append({"key": str(key), "reason": "unexpected row"})
            continue
        expected_values = {
            "frame_count": expected["frame_count"],
            "unique_event_count": len(expected["event_ids"]),
            "tracked_person_observations": expected["tracked_person_observations"],
            "association_count": expected["association_count"],
            "candidate_count": expected["candidate_count"],
            "worker_evidence_rows": expected["worker_evidence_rows"],
            "violation_evidence_rows": expected["violation_evidence_rows"],
        }
        different = {
            field: {"expected": value, "actual": row.get(field)}
            for field, value in expected_values.items()
            if row.get(field) != value
        }
        if different:
            daily_mismatches.append({"key": str(key), "different": different})
    for missing_key in sorted(set(expected_daily) - actual_keys, key=str):
        daily_mismatches.append({"key": str(missing_key), "reason": "missing row"})
    add_check(
        "daily_summary_reconciles",
        not daily_mismatches,
        "daily totals equal the detailed frame and worker tables",
        daily_mismatches,
    )

    summary_path = output_dir / "aggregation-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary_counts_match = (
        summary.get("source_record_count") == len(frames)
        and summary.get("frame_row_count") == len(frames)
        and summary.get("worker_evidence_row_count") == len(workers)
        and summary.get("daily_camera_row_count") == len(daily_rows)
    )
    add_check(
        "aggregation_summary_reconciles",
        summary_counts_match,
        "aggregation summary row counts equal Parquet row counts",
        {
            "frames": len(frames),
            "workers": len(workers),
            "daily": len(daily_rows),
        },
    )

    failed_checks = [check["name"] for check in checks if check["status"] == "failed"]
    report = {
        "status": "passed" if not failed_checks else "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_directory": str(output_dir),
        "row_counts": {
            "frames": len(frames),
            "worker_evidence": len(workers),
            "daily_camera_summary": len(daily_rows),
        },
        "check_count": len(checks),
        "failed_check_count": len(failed_checks),
        "failed_checks": failed_checks,
        "checks": checks,
    }
    write_json_atomic(report, report_path)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate SafeSite Gold Parquet tables before analytics use."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = validate_quality(args.output_dir, args.report)
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    sys.exit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
