import argparse
import json
from collections import Counter, defaultdict, deque
from pathlib import Path

from app.associate_ppe_tracks import load_jsonl


VIOLATION_RULES = {
    "no_helmet": {"event_type": "NO_HELMET", "opposite_class": "helmet"},
    "no_goggle": {"event_type": "NO_GOGGLE", "opposite_class": "goggles"},
    "no_gloves": {"event_type": "NO_GLOVES", "opposite_class": "gloves"},
    "no_boots": {"event_type": "NO_BOOTS", "opposite_class": "boots"},
}


class TemporalViolationEngine:
    def __init__(
        self,
        window_size: int,
        evidence_threshold: int,
        cooldown_ms: int,
        maximum_opposite_evidence: int,
    ) -> None:
        if window_size <= 0:
            raise ValueError("window_size must be greater than zero")
        if not 1 <= evidence_threshold <= window_size:
            raise ValueError("evidence_threshold must be between 1 and window_size")
        if cooldown_ms < 0:
            raise ValueError("cooldown_ms must be zero or greater")
        if not 0 <= maximum_opposite_evidence <= window_size:
            raise ValueError("maximum_opposite_evidence must be between 0 and window_size")

        self.window_size = window_size
        self.evidence_threshold = evidence_threshold
        self.cooldown_ms = cooldown_ms
        self.maximum_opposite_evidence = maximum_opposite_evidence
        self.windows = defaultdict(lambda: deque(maxlen=window_size))
        self.last_event_timestamp = {}
        self.last_timestamp_by_camera = {}
        self.state_counts = Counter()
        self.blocked_by_cooldown = Counter()

    def evaluate(self, record: dict) -> tuple[list[dict], list[dict]]:
        camera_id = record["camera_id"]
        timestamp_ms = record["video_timestamp_ms"]
        previous_timestamp = self.last_timestamp_by_camera.get(camera_id)
        if previous_timestamp is not None and timestamp_ms < previous_timestamp:
            raise ValueError(f"Timestamps go backwards for camera {camera_id}")
        self.last_timestamp_by_camera[camera_id] = timestamp_ms

        timeline_rows = []
        candidate_events = []
        for track_evidence in record["track_evidence"]:
            track_id = track_evidence["track_id"]
            for violation_class, rule in VIOLATION_RULES.items():
                key = (camera_id, track_id, violation_class)
                state = evidence_state(track_evidence, violation_class)
                confidence = confidence_for(record["associations"], track_id, violation_class)
                observation = {
                    "sample_index": record["sample_index"],
                    "video_timestamp_ms": timestamp_ms,
                    "state": state,
                    "confidence": confidence,
                    "image_path": record["image_path"],
                    "annotated_image": record["annotated_image"],
                }
                self.windows[key].append(observation)
                self.state_counts[(violation_class, state)] += 1

                window = list(self.windows[key])
                violation_observations = [
                    item for item in window if item["state"] == "violation"
                ]
                opposite_count = sum(item["state"] == "opposite" for item in window)
                window_ready = len(window) == self.window_size
                threshold_reached = (
                    window_ready
                    and len(violation_observations) >= self.evidence_threshold
                    and opposite_count <= self.maximum_opposite_evidence
                )
                last_event_ms = self.last_event_timestamp.get(key)
                cooldown_active = (
                    last_event_ms is not None
                    and timestamp_ms - last_event_ms < self.cooldown_ms
                )
                event_created = threshold_reached and not cooldown_active
                if threshold_reached and cooldown_active:
                    self.blocked_by_cooldown[violation_class] += 1

                if event_created:
                    confidences = [
                        item["confidence"]
                        for item in violation_observations
                        if item["confidence"] is not None
                    ]
                    event = {
                        "camera_id": camera_id,
                        "track_id": track_id,
                        "violation_type": rule["event_type"],
                        "source_violation_class": violation_class,
                        "video_timestamp_ms": timestamp_ms,
                        "sample_index": record["sample_index"],
                        "confidence": round(sum(confidences) / len(confidences), 4),
                        "evidence_count": len(violation_observations),
                        "window_size": self.window_size,
                        "window_start_timestamp_ms": window[0]["video_timestamp_ms"],
                        "window_end_timestamp_ms": window[-1]["video_timestamp_ms"],
                        "frame_uri": record["annotated_image"],
                        "status": "candidate_not_sent_to_api",
                    }
                    candidate_events.append(event)
                    self.last_event_timestamp[key] = timestamp_ms

                timeline_rows.append(
                    {
                        "camera_id": camera_id,
                        "track_id": track_id,
                        "violation_class": violation_class,
                        "violation_type": rule["event_type"],
                        "sample_index": record["sample_index"],
                        "video_timestamp_ms": timestamp_ms,
                        "state": state,
                        "window_states": [item["state"] for item in window],
                        "violation_count": len(violation_observations),
                        "opposite_count": opposite_count,
                        "window_ready": window_ready,
                        "threshold_reached": threshold_reached,
                        "cooldown_active": cooldown_active,
                        "event_created": event_created,
                    }
                )
        return timeline_rows, candidate_events


def evidence_state(track_evidence: dict, violation_class: str) -> str:
    rule = VIOLATION_RULES[violation_class]
    if violation_class in track_evidence["violation_evidence"]:
        return "violation"
    if rule["opposite_class"] in track_evidence["positive_evidence"]:
        return "opposite"
    return "unknown"


def confidence_for(
    associations: list[dict], track_id: int, violation_class: str
) -> float | None:
    matches = [
        association["confidence"]
        for association in associations
        if association["track_id"] == track_id
        and association["class_name"] == violation_class
    ]
    return max(matches) if matches else None


def build_temporal_events(
    associations_path: Path,
    output_dir: Path,
    window_size: int,
    evidence_threshold: int,
    cooldown_ms: int,
    maximum_opposite_evidence: int,
) -> dict:
    engine = TemporalViolationEngine(
        window_size=window_size,
        evidence_threshold=evidence_threshold,
        cooldown_ms=cooldown_ms,
        maximum_opposite_evidence=maximum_opposite_evidence,
    )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")

    records = load_jsonl(associations_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    timeline_path = output_dir / "timeline.jsonl"
    events_path = output_dir / "candidate_events.jsonl"
    summary_path = output_dir / "summary.json"

    candidate_events = []

    with timeline_path.open("w", encoding="utf-8") as timeline:
        for record in records:
            timeline_rows, new_events = engine.evaluate(record)
            candidate_events.extend(new_events)
            for timeline_row in timeline_rows:
                timeline.write(json.dumps(timeline_row) + "\n")

    with events_path.open("w", encoding="utf-8") as events_file:
        for event in candidate_events:
            events_file.write(json.dumps(event) + "\n")

    event_counts = Counter(event["violation_type"] for event in candidate_events)
    summary = {
        "associations": str(associations_path),
        "timeline": str(timeline_path),
        "candidate_events": str(events_path),
        "frames_processed": len(records),
        "window_size": window_size,
        "evidence_threshold": evidence_threshold,
        "cooldown_ms": cooldown_ms,
        "maximum_opposite_evidence": maximum_opposite_evidence,
        "rule": "Direct violation evidence reaches threshold in a full sliding window",
        "unknown_rule": "Unknown evidence neither confirms nor cancels a violation",
        "opposite_rule": "Too much opposite PPE evidence prevents confirmation",
        "api_status": "Candidate events are not sent to FastAPI in this lesson",
        "candidate_event_count": len(candidate_events),
        "candidate_events_by_type": dict(sorted(event_counts.items())),
        "observations_by_class_and_state": {
            violation_class: {
                state: engine.state_counts[(violation_class, state)]
                for state in ("violation", "opposite", "unknown")
            }
            for violation_class in VIOLATION_RULES
        },
        "windows_blocked_by_cooldown": dict(sorted(engine.blocked_by_cooldown.items())),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert per-track direct PPE violation evidence into temporal candidate events."
    )
    parser.add_argument("--associations", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--evidence-threshold", type=int, default=3)
    parser.add_argument("--cooldown-ms", type=int, default=10000)
    parser.add_argument("--maximum-opposite-evidence", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build_temporal_events(
        associations_path=args.associations,
        output_dir=args.output_dir,
        window_size=args.window_size,
        evidence_threshold=args.evidence_threshold,
        cooldown_ms=args.cooldown_ms,
        maximum_opposite_evidence=args.maximum_opposite_evidence,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
