import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import cv2


POSITIVE_PPE_CLASSES = {"helmet", "goggles", "vest", "gloves", "boots"}
VIOLATION_CLASSES = {"no_helmet", "no_goggle", "no_gloves", "no_boots"}
SUPPORTED_CLASSES = POSITIVE_PPE_CLASSES | VIOLATION_CLASSES
VERTICAL_REGIONS = {
    "helmet": (0.0, 0.38),
    "no_helmet": (0.0, 0.38),
    "goggles": (0.0, 0.45),
    "no_goggle": (0.0, 0.45),
    "vest": (0.12, 0.72),
    "gloves": (0.18, 0.85),
    "no_gloves": (0.18, 0.85),
    "boots": (0.55, 1.05),
    "no_boots": (0.55, 1.05),
}
CLASS_COLORS = {
    "helmet": (0, 220, 0),
    "goggles": (255, 180, 0),
    "vest": (0, 220, 255),
    "gloves": (255, 0, 255),
    "boots": (180, 100, 0),
    "no_helmet": (0, 0, 255),
    "no_goggle": (0, 0, 255),
    "no_gloves": (0, 0, 255),
    "no_boots": (0, 0, 255),
}


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"JSONL file does not exist: {path}")

    records = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}") from error
    if not records:
        raise ValueError(f"JSONL file contains no records: {path}")
    return records


def intersection_ratio(item_box: list[float], person_box: list[float]) -> float:
    item_x1, item_y1, item_x2, item_y2 = item_box
    person_x1, person_y1, person_x2, person_y2 = person_box
    intersection_width = max(0.0, min(item_x2, person_x2) - max(item_x1, person_x1))
    intersection_height = max(0.0, min(item_y2, person_y2) - max(item_y1, person_y1))
    item_area = max(0.0, item_x2 - item_x1) * max(0.0, item_y2 - item_y1)
    if item_area == 0:
        return 0.0
    return intersection_width * intersection_height / item_area


def association_score(detection: dict, track: dict) -> float | None:
    person_x1, person_y1, person_x2, person_y2 = track["box_xyxy"]
    item_x1, item_y1, item_x2, item_y2 = detection["box_xyxy"]
    person_width = person_x2 - person_x1
    person_height = person_y2 - person_y1
    if person_width <= 0 or person_height <= 0:
        return None

    center_x = (item_x1 + item_x2) / 2
    center_y = (item_y1 + item_y2) / 2
    margin_x = person_width * 0.12
    margin_y = person_height * 0.08
    if not (
        person_x1 - margin_x <= center_x <= person_x2 + margin_x
        and person_y1 - margin_y <= center_y <= person_y2 + margin_y
    ):
        return None

    relative_y = (center_y - person_y1) / person_height
    minimum_y, maximum_y = VERTICAL_REGIONS[detection["class_name"]]
    if not minimum_y <= relative_y <= maximum_y:
        return None

    overlap = intersection_ratio(detection["box_xyxy"], track["box_xyxy"])
    normalized_x_distance = abs(center_x - (person_x1 + person_x2) / 2) / person_width
    return overlap - 0.05 * normalized_x_distance


def associate_frame(tracks: list[dict], detections: list[dict]) -> tuple[list[dict], list[dict]]:
    tracked_people = [track for track in tracks if track.get("track_id") is not None]
    chosen_by_track_and_class = {}
    unassociated = []

    for detection in detections:
        class_name = detection["class_name"]
        if class_name not in SUPPORTED_CLASSES:
            continue

        candidates = []
        for track in tracked_people:
            score = association_score(detection, track)
            if score is not None:
                candidates.append((score, track))
        if not candidates:
            unassociated.append(detection)
            continue

        score, selected_track = max(candidates, key=lambda candidate: candidate[0])
        association = {
            **detection,
            "track_id": selected_track["track_id"],
            "association_score": round(score, 4),
        }
        key = (selected_track["track_id"], class_name)
        previous = chosen_by_track_and_class.get(key)
        if previous is None or association["confidence"] > previous["confidence"]:
            if previous is not None:
                unassociated.append({**previous, "reason": "lower-confidence duplicate"})
            chosen_by_track_and_class[key] = association
        else:
            unassociated.append({**association, "reason": "lower-confidence duplicate"})

    associations = sorted(
        chosen_by_track_and_class.values(),
        key=lambda item: (item["track_id"], item["class_name"]),
    )
    return associations, unassociated


def draw_frame(image, tracks: list[dict], associations: list[dict]) -> None:
    evidence_by_track = defaultdict(list)
    for association in associations:
        evidence_by_track[association["track_id"]].append(association["class_name"])
        x1, y1, x2, y2 = [int(value) for value in association["box_xyxy"]]
        color = CLASS_COLORS[association["class_name"]]
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        label = f'{association["class_name"]} {association["confidence"]:.2f}'
        cv2.putText(image, label, (x1, max(18, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    for track in tracks:
        if track.get("track_id") is None:
            continue
        x1, y1, x2, y2 = [int(value) for value in track["box_xyxy"]]
        track_id = track["track_id"]
        evidence = ", ".join(sorted(evidence_by_track[track_id])) or "unknown PPE"
        cv2.rectangle(image, (x1, y1), (x2, y2), (255, 255, 255), 2)
        cv2.putText(
            image,
            f"ID {track_id}: {evidence}",
            (x1, max(22, y1 - 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            2,
        )


def associate_ppe_tracks(tracks_path: Path, predictions_path: Path, output_dir: Path) -> dict:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")

    track_records = load_jsonl(tracks_path)
    prediction_records = load_jsonl(predictions_path)
    if len(track_records) != len(prediction_records):
        raise ValueError("Tracking and prediction files contain different frame counts")

    annotated_dir = output_dir / "annotated"
    associations_path = output_dir / "associations.jsonl"
    summary_path = output_dir / "summary.json"
    annotated_dir.mkdir(parents=True, exist_ok=True)

    evidence_counts = defaultdict(Counter)
    frames_observed = Counter()
    frames_with_evidence = Counter()
    total_associations = Counter()
    total_unassociated = Counter()

    with associations_path.open("w", encoding="utf-8") as output:
        for track_record, prediction_record in zip(
            track_records, prediction_records, strict=True
        ):
            identity_fields = ("camera_id", "sample_index", "video_timestamp_ms", "image_path")
            if any(track_record[field] != prediction_record[field] for field in identity_fields):
                raise ValueError(
                    f'Mismatched frame records at sample {track_record.get("sample_index")}'
                )

            tracked_people = [
                track for track in track_record["tracks"] if track.get("track_id") is not None
            ]
            associations, unassociated = associate_frame(
                tracked_people, prediction_record["detections"]
            )
            associations_by_track = defaultdict(list)
            for association in associations:
                associations_by_track[association["track_id"]].append(association)
                evidence_counts[association["track_id"]][association["class_name"]] += 1
                total_associations[association["class_name"]] += 1
            for detection in unassociated:
                total_unassociated[detection["class_name"]] += 1

            track_evidence = []
            for track in tracked_people:
                track_id = track["track_id"]
                frames_observed[track_id] += 1
                evidence = associations_by_track[track_id]
                if evidence:
                    frames_with_evidence[track_id] += 1
                positive = sorted(
                    item["class_name"]
                    for item in evidence
                    if item["class_name"] in POSITIVE_PPE_CLASSES
                )
                violations = sorted(
                    item["class_name"]
                    for item in evidence
                    if item["class_name"] in VIOLATION_CLASSES
                )
                track_evidence.append(
                    {
                        "track_id": track_id,
                        "person_box_xyxy": track["box_xyxy"],
                        "positive_evidence": positive,
                        "violation_evidence": violations,
                        "unknown_is_not_violation": not evidence,
                    }
                )

            image = cv2.imread(track_record["image_path"])
            if image is None:
                raise RuntimeError(f'Could not read image: {track_record["image_path"]}')
            draw_frame(image, tracked_people, associations)
            source_path = Path(track_record["image_path"])
            annotated_path = annotated_dir / f"{source_path.stem}_associated.jpg"
            if not cv2.imwrite(str(annotated_path), image):
                raise RuntimeError(f"Could not write annotated image: {annotated_path}")

            output.write(
                json.dumps(
                    {
                        "camera_id": track_record["camera_id"],
                        "sample_index": track_record["sample_index"],
                        "video_timestamp_ms": track_record["video_timestamp_ms"],
                        "image_path": track_record["image_path"],
                        "annotated_image": str(annotated_path),
                        "tracked_people": len(tracked_people),
                        "track_evidence": track_evidence,
                        "associations": associations,
                        "unassociated_supported_detections": unassociated,
                    }
                )
                + "\n"
            )

    track_statistics = {}
    for track_id in sorted(frames_observed):
        observed = frames_observed[track_id]
        class_frames = evidence_counts[track_id]
        track_statistics[str(track_id)] = {
            "frames_observed": observed,
            "evidence_frames": {
                class_name: class_frames[class_name] for class_name in sorted(SUPPORTED_CLASSES)
            },
            "evidence_coverage": {
                class_name: round(class_frames[class_name] / observed, 4)
                for class_name in sorted(SUPPORTED_CLASSES)
            },
            "frames_without_any_supported_ppe": observed - frames_with_evidence[track_id],
        }

    summary = {
        "tracks": str(tracks_path),
        "predictions": str(predictions_path),
        "associations": str(associations_path),
        "frames_processed": len(track_records),
        "association_rule": "PPE center inside a tracked person and expected vertical body region",
        "duplicate_rule": "Keep only the highest-confidence box per track and PPE class per frame",
        "safety_rule": "Missing positive PPE evidence is unknown, not a violation",
        "associated_class_counts": dict(sorted(total_associations.items())),
        "unassociated_class_counts": dict(sorted(total_unassociated.items())),
        "track_statistics": track_statistics,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Associate PPE detections with stable tracked people across ordered frames."
    )
    parser.add_argument("--tracks", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = associate_ppe_tracks(args.tracks, args.predictions, args.output_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
