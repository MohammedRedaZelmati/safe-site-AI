import unittest

from compare_ppe_runs import metric_name, rank_runs


class RunComparisonTests(unittest.TestCase):
    def test_metric_names_are_mlflow_safe(self):
        self.assertEqual(metric_name("metrics/mAP50-95(B)"), "metrics_mAP50-95_B_")

    def test_higher_map50_95_wins(self):
        rows = [
            {"run_name": "smoke", "map50_95": 0.01, "recall": 0.8, "precision": 0.8},
            {"run_name": "baseline", "map50_95": 0.2, "recall": 0.4, "precision": 0.5},
        ]
        self.assertEqual(rank_runs(rows)[0]["run_name"], "baseline")

    def test_recall_breaks_equal_map_tie(self):
        rows = [
            {"run_name": "a", "map50_95": 0.2, "recall": 0.3, "precision": 0.9},
            {"run_name": "b", "map50_95": 0.2, "recall": 0.5, "precision": 0.4},
        ]
        self.assertEqual(rank_runs(rows)[0]["run_name"], "b")


if __name__ == "__main__":
    unittest.main()
