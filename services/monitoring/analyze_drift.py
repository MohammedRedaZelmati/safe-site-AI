import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import fmean, median
from typing import Any

import numpy as np
from PIL import Image


BRIGHTNESS_BINS = np.linspace(0.0, 256.0, 9)
SHARPNESS_LOG_BINS = np.array([0.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 14.0])
CONFIDENCE_BINS = np.linspace(0.0, 1.000001, 11)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"JSONL file not found: {path}")
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON on line {line_number} of {path}") from error
        if not isinstance(value, dict):
            raise ValueError(f"Line {line_number} of {path} is not a JSON object")
        records.append(value)
    if not records:
        raise ValueError(f"JSONL file is empty: {path}")
    return records


def resolve_data_path(raw_path: str, data_root: Path) -> Path:
    path = Path(raw_path)
    if path.is_file():
        return path
    normalized = raw_path.replace("\\", "/")
    if normalized.startswith("/data/"):
        candidate = data_root / normalized.removeprefix("/data/")
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Referenced image not found: {raw_path}")


def image_measurements(path: Path) -> tuple[float, float]:
    with Image.open(path) as image:
        gray = np.asarray(image.convert("L"), dtype=np.float64)
    brightness = float(gray.mean())
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        sharpness = 0.0
    else:
        center = gray[1:-1, 1:-1]
        laplacian = (
            gray[:-2, 1:-1]
            + gray[2:, 1:-1]
            + gray[1:-1, :-2]
            + gray[1:-1, 2:]
            - 4.0 * center
        )
        sharpness = float(laplacian.var())
    return brightness, sharpness


def dataset_measurements(
    manifest_path: Path,
    predictions_path: Path,
    data_root: Path,
    minimum_confidence: float = 0.0,
) -> dict[str, list[float] | int]:
    manifest = read_jsonl(manifest_path)
    predictions = read_jsonl(predictions_path)
    brightness_values = []
    sharpness_values = []
    for record in manifest:
        image_path = record.get("image_path")
        if not isinstance(image_path, str) or not image_path:
            raise ValueError(f"Manifest record has no image_path: {record}")
        brightness, sharpness = image_measurements(resolve_data_path(image_path, data_root))
        brightness_values.append(brightness)
        sharpness_values.append(sharpness)

    confidences = []
    for record in predictions:
        detections = record.get("detections")
        if not isinstance(detections, list):
            raise ValueError("Prediction record detections must be a list")
        for detection in detections:
            confidence = detection.get("confidence")
            if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
                raise ValueError(f"Invalid detection confidence: {confidence}")
            if confidence >= minimum_confidence:
                confidences.append(float(confidence))

    return {
        "frame_count": len(manifest),
        "prediction_record_count": len(predictions),
        "brightness": brightness_values,
        "sharpness": sharpness_values,
        "confidence": confidences,
    }


def distribution_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "minimum": None, "mean": None, "median": None, "p95": None, "maximum": None}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return {
        "count": len(values),
        "minimum": round(ordered[0], 6),
        "mean": round(fmean(values), 6),
        "median": round(median(values), 6),
        "p95": round(ordered[p95_index], 6),
        "maximum": round(ordered[-1], 6),
    }


def population_stability_index(
    baseline: list[float],
    current: list[float],
    bins: np.ndarray,
) -> float | None:
    if not baseline or not current:
        return None
    baseline_counts, _ = np.histogram(np.asarray(baseline), bins=bins)
    current_counts, _ = np.histogram(np.asarray(current), bins=bins)
    epsilon = 1e-6
    baseline_share = baseline_counts.astype(np.float64) + epsilon
    current_share = current_counts.astype(np.float64) + epsilon
    baseline_share /= baseline_share.sum()
    current_share /= current_share.sum()
    value = np.sum((current_share - baseline_share) * np.log(current_share / baseline_share))
    return round(float(value), 6)


def drift_level(psi: float | None) -> str:
    if psi is None:
        return "insufficient_data"
    if psi >= 0.25:
        return "drift"
    if psi >= 0.1:
        return "warning"
    return "stable"


def build_report(
    baseline: dict[str, list[float] | int],
    current: dict[str, list[float] | int],
    baseline_manifest: Path,
    current_manifest: Path,
    minimum_confidence: float = 0.0,
) -> dict[str, Any]:
    comparisons = {}
    configurations = {
        "brightness": BRIGHTNESS_BINS,
        "sharpness": SHARPNESS_LOG_BINS,
        "confidence": CONFIDENCE_BINS,
    }
    for name, bins in configurations.items():
        baseline_values = list(baseline[name])
        current_values = list(current[name])
        if name == "sharpness":
            baseline_for_psi = [math.log1p(value) for value in baseline_values]
            current_for_psi = [math.log1p(value) for value in current_values]
        else:
            baseline_for_psi = baseline_values
            current_for_psi = current_values
        psi = population_stability_index(baseline_for_psi, current_for_psi, bins)
        comparisons[name] = {
            "baseline": distribution_summary(baseline_values),
            "current": distribution_summary(current_values),
            "psi": psi,
            "status": drift_level(psi),
        }

    statuses = [comparison["status"] for comparison in comparisons.values()]
    overall_status = "drift" if "drift" in statuses else "warning" if "warning" in statuses else "stable"
    alerts = [f"{name} distribution is {value['status']} (PSI={value['psi']})" for name, value in comparisons.items() if value["status"] in {"warning", "drift"}]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": overall_status,
        "method": "population_stability_index",
        "minimum_confidence": minimum_confidence,
        "thresholds": {"stable_below": 0.1, "drift_at_or_above": 0.25},
        "baseline": {
            "manifest": str(baseline_manifest.resolve()),
            "frame_count": baseline["frame_count"],
            "prediction_record_count": baseline["prediction_record_count"],
        },
        "current": {
            "manifest": str(current_manifest.resolve()),
            "frame_count": current["frame_count"],
            "prediction_record_count": current["prediction_record_count"],
        },
        "comparisons": comparisons,
        "alerts": alerts,
        "interpretation": "Drift indicates changed input or confidence distributions; it does not prove accuracy degradation without new ground-truth labels.",
    }


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare SafeSite image and confidence distributions.")
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--baseline-predictions", type=Path, required=True)
    parser.add_argument("--current-manifest", type=Path, required=True)
    parser.add_argument("--current-predictions", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--minimum-confidence", type=float, default=0.0, choices=None)
    parser.add_argument("--output", type=Path, default=Path("data/monitoring/drift-report.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0.0 <= args.minimum_confidence <= 1.0:
        raise ValueError("minimum confidence must be between 0 and 1")
    baseline = dataset_measurements(
        args.baseline_manifest,
        args.baseline_predictions,
        args.data_root,
        args.minimum_confidence,
    )
    current = dataset_measurements(
        args.current_manifest,
        args.current_predictions,
        args.data_root,
        args.minimum_confidence,
    )
    report = build_report(
        baseline,
        current,
        args.baseline_manifest,
        args.current_manifest,
        args.minimum_confidence,
    )
    write_json_atomic(args.output, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
