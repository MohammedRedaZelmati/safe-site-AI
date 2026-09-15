import argparse
import json
from collections import Counter
from pathlib import Path
from time import perf_counter

import cv2
from ultralytics import YOLO

from app.detect_image import extract_detections


REQUIRED_MANIFEST_FIELDS = {
    "camera_id",
    "sample_index",
    "source_frame_index",
    "video_timestamp_ms",
    "source_fps",
    "image_path",
}


def load_manifest(manifest_path: Path) -> list[dict]:
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest does not exist: {manifest_path}")

    records = []
    with manifest_path.open(encoding="utf-8") as manifest:
        for line_number, line in enumerate(manifest, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on manifest line {line_number}") from error

            missing_fields = REQUIRED_MANIFEST_FIELDS - record.keys()
            if missing_fields:
                raise ValueError(
                    f"Manifest line {line_number} is missing fields: {sorted(missing_fields)}"
                )
            image_path = Path(record["image_path"])
            if not image_path.is_file():
                raise FileNotFoundError(
                    f"Manifest line {line_number} references a missing image: {image_path}"
                )
            records.append(record)

    if not records:
        raise ValueError("Manifest contains no frame records")
    return records


def detect_frames(
    manifest_path: Path,
    output_dir: Path,
    model_name: str,
    confidence_threshold: float,
    image_size: int,
    device: str,
) -> dict:
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold must be between 0 and 1")
    if image_size <= 0:
        raise ValueError("image_size must be greater than zero")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")

    records = load_manifest(manifest_path)
    annotated_dir = output_dir / "annotated"
    predictions_path = output_dir / "predictions.jsonl"
    summary_path = output_dir / "summary.json"
    annotated_dir.mkdir(parents=True, exist_ok=True)

    model = YOLO(model_name)
    image_paths = [record["image_path"] for record in records]
    results = model.predict(
        source=image_paths,
        conf=confidence_threshold,
        imgsz=image_size,
        device=device,
        stream=True,
        verbose=False,
    )

    started_at = perf_counter()
    class_counts = Counter()
    detections_per_frame = Counter()
    frames_with_detections = 0
    total_detections = 0

    with predictions_path.open("w", encoding="utf-8") as predictions:
        for record, result in zip(records, results, strict=True):
            detections = extract_detections(result)
            detection_count = len(detections)
            total_detections += detection_count
            detections_per_frame[detection_count] += 1
            if detections:
                frames_with_detections += 1
            class_counts.update(detection["class_name"] for detection in detections)

            source_path = Path(record["image_path"])
            annotated_path = annotated_dir / f"{source_path.stem}_annotated.jpg"
            if not cv2.imwrite(str(annotated_path), result.plot()):
                raise RuntimeError(f"Could not write annotated image: {annotated_path}")

            prediction = {
                **record,
                "annotated_image": str(annotated_path),
                "original_shape": list(result.orig_shape),
                "detection_count": detection_count,
                "detections": detections,
            }
            predictions.write(json.dumps(prediction) + "\n")

    elapsed_seconds = perf_counter() - started_at
    summary = {
        "manifest": str(manifest_path),
        "predictions": str(predictions_path),
        "model": model_name,
        "device": device,
        "image_size": image_size,
        "confidence_threshold": confidence_threshold,
        "frames_processed": len(records),
        "frames_with_detections": frames_with_detections,
        "frames_without_detections": len(records) - frames_with_detections,
        "total_detections": total_detections,
        "detections_per_frame": dict(sorted(detections_per_frame.items())),
        "class_counts": dict(sorted(class_counts.items())),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "average_seconds_per_frame": round(elapsed_seconds / len(records), 4),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run YOLO on every frame in a JSONL manifest.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default="/data/models/yolo26n.pt")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = detect_frames(
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        model_name=args.model,
        confidence_threshold=args.confidence,
        image_size=args.image_size,
        device=args.device,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
