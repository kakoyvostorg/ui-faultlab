import json
import unittest
from pathlib import Path

from scripts.build_paired_report import build_metrics


ROOT = Path(__file__).resolve().parents[1]


class PairedReportingTest(unittest.TestCase):
    def test_frozen_summary_rebuilds_headline_metrics(self):
        summary = json.loads((ROOT / "artifacts" / "paired_same_task_summary.json").read_text())
        metrics = build_metrics(summary, 1024.101, 168.48, 234.0)
        paired = metrics["paired_differential"]
        terminal = metrics["terminal_only_comparator"]
        self.assertEqual(paired["accuracy_count"], [20, 21])
        self.assertEqual(paired["application_bug_precision_count"], [3, 3])
        self.assertEqual(paired["non_application_false_bug_report_count"], [0, 18])
        self.assertEqual(paired["ambiguous_count"], [7, 21])
        self.assertEqual(terminal["accuracy_count"], [3, 21])
        self.assertEqual(terminal["non_application_false_bug_report_count"], [18, 18])


if __name__ == "__main__":
    unittest.main()
