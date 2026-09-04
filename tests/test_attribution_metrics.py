import unittest

from ui_faultlab.evaluation.attribution import attribution_metrics, confusion_matrix


class AttributionMetricsTest(unittest.TestCase):
    def test_confusion_matrix_matches_fixture(self):
        gold = ["agent_error", "agent_error", "application_bug"]
        pred = ["application_bug", "agent_error", "application_bug"]
        matrix = confusion_matrix(gold, pred)
        self.assertEqual(matrix["agent_error"]["application_bug"], 1)
        self.assertEqual(matrix["application_bug"]["application_bug"], 1)

    def test_false_bug_report_rate_uses_agent_error_denominator(self):
        metrics = attribution_metrics(
            ["agent_error", "agent_error", "application_bug"],
            ["application_bug", "agent_error", "application_bug"],
        )
        self.assertEqual(metrics["false_bug_report_count"], [1, 2])
        self.assertEqual(metrics["false_bug_report_rate"], .5)


if __name__ == "__main__":
    unittest.main()

