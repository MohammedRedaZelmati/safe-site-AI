import unittest

from validate_events import validate_events


VALID_EVENT = {
    "id": 1,
    "occurred_at": "2026-08-29T10:00:00+00:00",
    "camera_id": "camera-01",
    "track_id": 10,
    "violation_type": "NO_HELMET",
    "confidence": 0.91,
    "frame_uri": "gold/camera-01/evidence.jpg",
    "event_key": "a" * 64,
    "created_at": "2026-08-29T10:00:01+00:00",
}


class GreatExpectationsTests(unittest.TestCase):
    def test_valid_events_pass(self):
        report = validate_events([VALID_EVENT])
        self.assertEqual(report["status"], "passed")
        self.assertGreaterEqual(report["expectation_count"], 20)
        self.assertEqual(report["failed_expectation_count"], 0)

    def test_bad_confidence_and_type_fail(self):
        bad_event = dict(VALID_EVENT, confidence=1.5, violation_type="UNKNOWN")
        report = validate_events([bad_event])
        self.assertEqual(report["status"], "failed")
        failed_columns = {failure["column"] for failure in report["failures"]}
        self.assertIn("confidence", failed_columns)
        self.assertIn("violation_type", failed_columns)


if __name__ == "__main__":
    unittest.main()
