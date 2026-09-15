import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from analyze_drift import build_report, dataset_measurements


class DriftAnalysisTests(unittest.TestCase):
    def write_dataset(self, root: Path, name: str, values: list[int], confidences: list[float]):
        directory = root / name
        directory.mkdir()
        manifest = directory / "frames.jsonl"
        predictions = directory / "predictions.jsonl"
        manifest_rows = []
        prediction_rows = []
        for index, value in enumerate(values):
            image_path = directory / f"frame-{index}.png"
            pixels = np.full((24, 24), value, dtype=np.uint8)
            if index % 2:
                pixels[::2, ::2] = min(255, value + 20)
            Image.fromarray(pixels).save(image_path)
            manifest_rows.append({"image_path": str(image_path)})
            prediction_rows.append({"detections": [{"confidence": confidences[index]}]})
        manifest.write_text("\n".join(json.dumps(row) for row in manifest_rows), encoding="utf-8")
        predictions.write_text("\n".join(json.dumps(row) for row in prediction_rows), encoding="utf-8")
        return manifest, predictions

    def test_same_dataset_is_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, predictions = self.write_dataset(root, "baseline", [70, 80, 90, 100], [0.3, 0.4, 0.5, 0.6])
            measurements = dataset_measurements(manifest, predictions, root)
            report = build_report(measurements, measurements, manifest, manifest)
            self.assertEqual(report["status"], "stable")
            self.assertEqual(report["alerts"], [])

    def test_large_distribution_change_is_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline_manifest, baseline_predictions = self.write_dataset(root, "baseline", [20, 25, 30, 35], [0.1, 0.15, 0.2, 0.25])
            current_manifest, current_predictions = self.write_dataset(root, "current", [220, 225, 230, 235], [0.8, 0.85, 0.9, 0.95])
            baseline = dataset_measurements(baseline_manifest, baseline_predictions, root)
            current = dataset_measurements(current_manifest, current_predictions, root)
            report = build_report(baseline, current, baseline_manifest, current_manifest)
            self.assertEqual(report["status"], "drift")
            self.assertEqual(report["comparisons"]["brightness"]["status"], "drift")
            self.assertEqual(report["comparisons"]["confidence"]["status"], "drift")


if __name__ == "__main__":
    unittest.main()
