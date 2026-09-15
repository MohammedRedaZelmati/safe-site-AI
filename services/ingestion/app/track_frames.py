import argparse
import json
from collections import Counter
from pathlib import Path
from time import perf_counter

import cv2
from ultralytics import YOLO

from app.detect_frames import load_manifest


def extract_tracks(result) -> list[dict]:
    tracks = []
    if result.boxes is None:
        return tracks

    for box in result.boxes:
        class_id = int(box.cls.item())
        track_id = int(box.id.item()) if box.id is not None else None
        x1, y1, x2, y2 = [round(value, 2) for value in box.xyxy[0].tolist()]
        tracks.append(
            {
                "track_id": track_id,
                "class_id": class_id,
                "class_name": result.names[class_id],
                "confidence": round(float(box.conf.item()), 4),
                "box_xyxy": [x1, y1, x2, y2],
            }
        )
    return tracks


def track_frames(
    manifest_path: Path,
    output_dir: Path,
    model_name: str,
    tracker_name: str,
    confidence_threshold: float,
    image_size: int,
    device: str,
    class_ids: list[int] | None,
) -> dict:
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold must be between 0 and 1")
    if image_size <= 0:
        raise ValueError("image_size must be greater than zero")
    if class_ids is not None and any(class_id < 0 for class_id in class_ids):
        raise ValueError("class IDs must be zero or greater")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")

    records = load_manifest(manifest_path)
    annotated_dir = output_dir / "annotated"
    tracks_path = output_dir / "tracks.jsonl"
    summary_path = output_dir / "summary.json"
    annotated_dir.mkdir(parents=True, exist_ok=True)

    model = YOLO(model_name)
    image_paths = [record["image_path"] for record in records]
    results = model.track(
        source=image_paths,
        conf=confidence_threshold,
        imgsz=image_size,
        device=device,
        classes=class_ids,
        tracker=tracker_name,
        persist=True,
        stream=True,
        verbose=False,
    )

    started_at = perf_counter()
    class_counts = Counter()
    tracks_per_frame = Counter()
    observations_per_track = Counter()
    track_spans = {}
    frames_with_tracks = 0
    total_tracked_detections = 0
    untracked_detections = 0

    with tracks_path.open("w", encoding="utf-8") as tracks_file:
        for record, result in zip(records, results, strict=True):
            tracks = extract_tracks(result)
            tracked = [track for track in tracks if track["track_id"] is not None]
            tracked_count = len(tracked)
            total_tracked_detections += tracked_count
            untracked_detections += len(tracks) - tracked_count
            tracks_per_frame[tracked_count] += 1
            if tracked:
                frames_with_tracks += 1

            for track in tracked:
                track_id = track["track_id"]
                class_counts[track["class_name"]] += 1
                observations_per_track[track_id] += 1
                if track_id not in track_spans:
                    track_spans[track_id] = {
                        "first_sample_index": record["sample_index"],
                        "first_timestamp_ms": record["video_timestamp_ms"],
                    }
                track_spans[track_id].update(
                    {
                        "last_sample_index": record["sample_index"],
                        "last_timestamp_ms": record["video_timestamp_ms"],
                    }
                )

            source_path = Path(record["image_path"])
            annotated_path = annotated_dir / f"{source_path.stem}_tracked.jpg"
            if not cv2.imwrite(str(annotated_path), result.plot()):
                raise RuntimeError(f"Could not write annotated image: {annotated_path}")

            track_record = {
                **record,
                "annotated_image": str(annotated_path),
                "original_shape": list(result.orig_shape),
                "tracked_count": tracked_count,
                "tracks": tracks,
            }
            tracks_file.write(json.dumps(track_record) + "\n")

    elapsed_seconds = perf_counter() - started_at
    track_statistics = {
        str(track_id): {
            "frames_observed": observations_per_track[track_id],
            "frame_coverage": round(observations_per_track[track_id] / len(records), 4),
            **track_spans[track_id],
        }
        for track_id in sorted(observations_per_track)
    }
    summary = {
        "manifest": str(manifest_path),
        "tracks": str(tracks_path),
        "model": model_name,
        "tracker": tracker_name,
        "device": device,
        "image_size": image_size,
        "confidence_threshold": confidence_threshold,
        "class_ids": class_ids,
        "frames_processed": len(records),
        "frames_with_tracks": frames_with_tracks,
        "frames_without_tracks": len(records) - frames_with_tracks,
        "total_tracked_detections": total_tracked_detections,
        "untracked_detections": untracked_detections,
        "unique_track_ids": sorted(observations_per_track),
        "tracks_per_frame": dict(sorted(tracks_per_frame.items())),
        "class_counts": dict(sorted(class_counts.items())),
        "track_statistics": track_statistics,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "average_seconds_per_frame": round(elapsed_seconds / len(records), 4),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run YOLO and ByteTrack on every ordered frame in a JSONL manifest."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default="/data/models/yolo26n.pt")
    parser.add_argument("--tracker", default="bytetrack.yaml")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--class-id", type=int, action="append", dest="class_ids")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = track_frames(
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        model_name=args.model,
        tracker_name=args.tracker,
        confidence_threshold=args.confidence,
        image_size=args.image_size,
        device=args.device,
        class_ids=args.class_ids,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
