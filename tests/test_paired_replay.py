import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_paired_protocol import audit
from scripts.run_paired_showui import run_case
from ui_faultlab.instrumentation import canonical_hash
from ui_faultlab.paired import PairedCase, validate_case_balance
from ui_faultlab.runner import load_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "paired_same_task_v1.json"


class FakeAgent:
    def __init__(self, outputs):
        self.outputs = iter(outputs)

    def raw_action(self, screenshot_path, instruction, history):
        return next(self.outputs), 5.0


def delete_actions(card_y: float) -> list[str]:
    return [
        f"{{'action': 'CLICK', 'value': None, 'position': [0.2, {card_y}]}}",
        "{'action': 'CLICK', 'value': None, 'position': [0.25, 0.88]}",
        "{'action': 'CLICK', 'value': None, 'position': [0.65, 0.65]}",
        "{'action': 'ANSWER', 'value': 'done', 'position': None}",
    ]


class PairedReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(CONFIG_PATH)
        cls.cases = [PairedCase.from_dict(row) for row in cls.config["cases"]]

    def test_manifest_is_balanced_with_six_variants_per_task(self):
        validate_case_balance(self.cases)
        for task_id in {case.task_id for case in self.cases}:
            rows = [case for case in self.cases if case.task_id == task_id]
            self.assertEqual(len(rows), 6)
            self.assertEqual(sum(case.candidate_fault is None for case in rows), 3)

    def test_preregistration_audit_confirms_isolation_and_complete_budget(self):
        result = audit(CONFIG_PATH)
        self.assertEqual(result["case_count"], 24)
        self.assertEqual(result["condition_counts"], {"clean": 12, "faulted": 12})
        self.assertEqual(result["split_counts"], {"dev": 8, "test": 8, "validation": 8})
        self.assertLessEqual(result["max_possible_calls"], result["max_total_calls"])
        self.assertTrue(result["label_isolation"]["public_manifest_hidden_fields_absent"])

    def test_faulted_candidate_and_successful_exact_replay_is_app_regression(self):
        case = next(row for row in self.cases if row.case_id == "delete_01")
        with tempfile.TemporaryDirectory() as directory:
            result = run_case(
                agent=FakeAgent(delete_actions(0.5)),
                case=case,
                run_root=Path(directory),
                config=self.config,
                config_hash=canonical_hash(self.config),
            )
            self.assertFalse(result["candidate"]["task_success"])
            self.assertTrue(result["reference"]["task_success"])
            self.assertEqual(result["reference"]["vlm_calls"], 0)
            self.assertEqual(result["prediction"], "application_regression")
            self.assertEqual(result["gold_label"], "application_regression")
            public = json.loads((Path(directory) / "cases" / case.case_id / "manifest.json").read_text())
            self.assertNotIn("candidate_fault", public)

    def test_same_wrong_actions_on_clean_pair_are_agent_or_harness(self):
        case = next(row for row in self.cases if row.case_id == "delete_02")
        with tempfile.TemporaryDirectory() as directory:
            result = run_case(
                agent=FakeAgent(delete_actions(0.5)),
                case=case,
                run_root=Path(directory),
                config=self.config,
                config_hash=canonical_hash(self.config),
            )
            self.assertFalse(result["candidate"]["task_success"])
            self.assertFalse(result["reference"]["task_success"])
            self.assertEqual(result["candidate"]["final_sha256"], result["reference"]["final_sha256"])
            self.assertEqual(result["prediction"], "agent_or_harness")
            self.assertEqual(result["gold_label"], "agent_or_harness")


if __name__ == "__main__":
    unittest.main()
