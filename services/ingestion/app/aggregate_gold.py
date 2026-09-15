import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as parquet


FRAME_SCHEMA = pa.schema(
    [
        ("event_id", pa.string()),
        ("source_detection_event_id", pa.string()),
        ("camera_id", pa.string()),
        ("captured_at", pa.timestamp("us", tz="UTC")),
        ("event_date", pa.date32()),
        ("sample_index", pa.int64()),
        ("video_timestamp_ms", pa.int64()),
        ("image_path", pa.string()),
        ("annotated_image", pa.string()),
        ("record_object_uri", pa.string()),
        ("tracked_people", pa.int32()),
        ("association_count", pa.int32()),
        ("candidate_count", pa.int32()),
        ("processed_at", pa.timestamp("us", tz="UTC")),
        ("source_record_path", pa.string()),
    ]
)

WORKER_EVIDENCE_SCHEMA = pa.schema(
    [
        ("event_id", pa.string()),
        ("camera_id", pa.string()),
        ("captured_at", pa.timestamp("us", tz="UTC")),
        ("event_date", pa.date32()),
        ("sample_index", pa.int64()),
        ("video_timestamp_ms", pa.int64()),
        ("track_id", pa.int64()),
        ("positive_evidence", pa.list_(pa.string())),
        ("violation_evidence", pa.list_(pa.string())),
        ("has_violation_evidence", pa.bool_()),
        ("unknown_state_count", pa.int32()),
    ]
)

DAILY_SUMMARY_SCHEMA = pa.schema(
    [
        ("event_date", pa.date32()),
        ("camera_id", pa.string()),
        ("frame_count", pa.int64()),
        ("unique_event_count", pa.int64()),
        ("tracked_person_observations", pa.int64()),
        ("association_count", pa.int64()),
        ("candidate_count", pa.int64()),
        ("worker_evidence_rows", pa.int64()),
        ("violation_evidence_rows", pa.int64()),
        ("association_class_counts_json", pa.string()),
    ]
)

OUTPUT_FILES = {
    "frames": "frames.parquet",
    "worker_evidence": "worker_evidence.parquet",
    "daily_camera_summary": "daily_camera_summary.parquet",
    "summary": "aggregation-summary.json",
}


def parse_utc_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty ISO-8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone: {value}")
    return parsed.astimezone(timezone.utc)


def require_text(record: dict, field_name: str, source_path: Path) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{source_path}: {field_name} must be non-empty text")
    return value


def require_non_negative_integer(record: dict, field_name: str, source_path: Path) -> int:
    value = record.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{source_path}: {field_name} must be a non-negative integer")
    return value


def require_list(record: dict, field_name: str, source_path: Path) -> list:
    value = record.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"{source_path}: {field_name} must be a list")
    return value


def load_gold_records(input_dir: Path) -> list[tuple[Path, dict]]:
    paths = sorted(input_dir.glob("*.json"))
    if not paths:
        raise ValueError(f"No Gold JSON records found in {input_dir}")

    records = []
    for path in paths:
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError(f"{path}: top-level JSON value must be an object")
        records.append((path, record))
    return records


def build_rows(records: list[tuple[Path, dict]]) -> tuple[list[dict], list[dict], list[dict]]:
    frame_rows = []
    worker_rows = []
    daily = defaultdict(
        lambda: {
            "event_ids": set(),
            "frame_count": 0,
            "tracked_person_observations": 0,
            "association_count": 0,
            "candidate_count": 0,
            "worker_evidence_rows": 0,
            "violation_evidence_rows": 0,
            "association_classes": defaultdict(int),
        }
    )

    for source_path, record in records:
        event_id = require_text(record, "event_id", source_path)
        source_detection_event_id = require_text(
            record, "source_detection_event_id", source_path
        )
        camera_id = require_text(record, "camera_id", source_path)
        captured_at = parse_utc_datetime(record.get("captured_at"), "captured_at")
        processed_at = parse_utc_datetime(record.get("processed_at"), "processed_at")
        sample_index = require_non_negative_integer(record, "sample_index", source_path)
        video_timestamp_ms = require_non_negative_integer(
            record, "video_timestamp_ms", source_path
        )
        tracked_people = require_non_negative_integer(record, "tracked_people", source_path)
        tracks = require_list(record, "tracks", source_path)
        evidence_rows = require_list(record, "track_evidence", source_path)
        associations = require_list(record, "associations", source_path)
        candidate_events = require_list(record, "candidate_events", source_path)
        timeline = require_list(record, "timeline", source_path)
        if tracked_people != len(tracks):
            raise ValueError(
                f"{source_path}: tracked_people={tracked_people} but tracks={len(tracks)}"
            )
        if tracked_people != len(evidence_rows):
            raise ValueError(
                f"{source_path}: tracked_people={tracked_people} "
                f"but track_evidence={len(evidence_rows)}"
            )

        event_date = captured_at.date()
        frame_rows.append(
            {
                "event_id": event_id,
                "source_detection_event_id": source_detection_event_id,
                "camera_id": camera_id,
                "captured_at": captured_at,
                "event_date": event_date,
                "sample_index": sample_index,
                "video_timestamp_ms": video_timestamp_ms,
                "image_path": require_text(record, "image_path", source_path),
                "annotated_image": require_text(record, "annotated_image", source_path),
                "record_object_uri": require_text(
                    record, "record_object_uri", source_path
                ),
                "tracked_people": tracked_people,
                "association_count": len(associations),
                "candidate_count": len(candidate_events),
                "processed_at": processed_at,
                "source_record_path": str(source_path.resolve()),
            }
        )

        unknown_by_track = defaultdict(int)
        for timeline_entry in timeline:
            if timeline_entry.get("state") == "unknown":
                unknown_by_track[timeline_entry.get("track_id")] += 1

        for evidence in evidence_rows:
            track_id = evidence.get("track_id")
            if (
                not isinstance(track_id, int)
                or isinstance(track_id, bool)
                or track_id < 0
            ):
                raise ValueError(
                    f"{source_path}: track_evidence track_id must be non-negative"
                )
            positive = evidence.get("positive_evidence", [])
            violations = evidence.get("violation_evidence", [])
            if not isinstance(positive, list) or not all(
                isinstance(value, str) for value in positive
            ):
                raise ValueError(f"{source_path}: positive_evidence must be a text list")
            if not isinstance(violations, list) or not all(
                isinstance(value, str) for value in violations
            ):
                raise ValueError(f"{source_path}: violation_evidence must be a text list")
            worker_rows.append(
                {
                    "event_id": event_id,
                    "camera_id": camera_id,
                    "captured_at": captured_at,
                    "event_date": event_date,
                    "sample_index": sample_index,
                    "video_timestamp_ms": video_timestamp_ms,
                    "track_id": track_id,
                    "positive_evidence": sorted(set(positive)),
                    "violation_evidence": sorted(set(violations)),
                    "has_violation_evidence": bool(violations),
                    "unknown_state_count": unknown_by_track[track_id],
                }
            )

        daily_key = (event_date, camera_id)
        daily_record = daily[daily_key]
        daily_record["event_ids"].add(event_id)
        daily_record["frame_count"] += 1
        daily_record["tracked_person_observations"] += tracked_people
        daily_record["association_count"] += len(associations)
        daily_record["candidate_count"] += len(candidate_events)
        daily_record["worker_evidence_rows"] += len(evidence_rows)
        daily_record["violation_evidence_rows"] += sum(
            bool(evidence.get("violation_evidence")) for evidence in evidence_rows
        )
        for association in associations:
            class_name = association.get("class_name")
            if isinstance(class_name, str) and class_name:
                daily_record["association_classes"][class_name] += 1

    frame_rows.sort(key=lambda row: (row["captured_at"], row["camera_id"], row["sample_index"]))
    worker_rows.sort(
        key=lambda row: (
            row["captured_at"],
            row["camera_id"],
            row["sample_index"],
            row["track_id"],
        )
    )
    daily_rows = []
    for (event_date, camera_id), values in sorted(daily.items()):
        daily_rows.append(
            {
                "event_date": event_date,
                "camera_id": camera_id,
                "frame_count": values["frame_count"],
                "unique_event_count": len(values["event_ids"]),
                "tracked_person_observations": values["tracked_person_observations"],
                "association_count": values["association_count"],
                "candidate_count": values["candidate_count"],
                "worker_evidence_rows": values["worker_evidence_rows"],
                "violation_evidence_rows": values["violation_evidence_rows"],
                "association_class_counts_json": json.dumps(
                    dict(sorted(values["association_classes"].items())),
                    separators=(",", ":"),
                ),
            }
        )
    return frame_rows, worker_rows, daily_rows


def write_parquet_atomic(rows: list[dict], schema: pa.Schema, path: Path) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    table = pa.Table.from_pylist(rows, schema=schema)
    parquet.write_table(table, temporary_path, compression="zstd")
    temporary_path.replace(path)


def write_json_atomic(payload: dict, path: Path) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary_path.replace(path)


def aggregate_gold(input_dir: Path, output_dir: Path, overwrite: bool = False) -> dict:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    managed_paths = [output_dir / name for name in OUTPUT_FILES.values()]
    existing = [path.name for path in managed_paths if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            f"Managed output files already exist in {output_dir}: {sorted(existing)}"
        )

    records = load_gold_records(input_dir)
    frame_rows, worker_rows, daily_rows = build_rows(records)
    write_parquet_atomic(frame_rows, FRAME_SCHEMA, output_dir / OUTPUT_FILES["frames"])
    write_parquet_atomic(
        worker_rows,
        WORKER_EVIDENCE_SCHEMA,
        output_dir / OUTPUT_FILES["worker_evidence"],
    )
    write_parquet_atomic(
        daily_rows,
        DAILY_SUMMARY_SCHEMA,
        output_dir / OUTPUT_FILES["daily_camera_summary"],
    )

    summary = {
        "status": "aggregated",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_directory": str(input_dir),
        "output_directory": str(output_dir),
        "source_record_count": len(records),
        "frame_row_count": len(frame_rows),
        "worker_evidence_row_count": len(worker_rows),
        "daily_camera_row_count": len(daily_rows),
        "output_files": {
            key: str(output_dir / filename) for key, filename in OUTPUT_FILES.items()
        },
    }
    write_json_atomic(summary, output_dir / OUTPUT_FILES["summary"])
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate SafeSite Gold JSON records into analytics Parquet tables."
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = aggregate_gold(args.input_dir, args.output_dir, args.overwrite)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
