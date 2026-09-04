import json
import tempfile
import unittest

from ui_faultlab.diagnosis.trajectory import public_trajectory
from ui_faultlab.environment import BrowserEnvironment
from tests.helpers import temporary_episode


FORBIDDEN = {"events", "backend", "gold_label", "fault_type", "fault_injected", "executed_action", "draft", "selected_event_id"}


class PrivilegedBoundaryTest(unittest.TestCase):
    def test_agent_input_contains_only_screenshot_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = BrowserEnvironment("create_event", 0, directory, "save_noop").serialize_agent_input()
            self.assertTrue(FORBIDDEN.isdisjoint(payload))
            self.assertIn("screenshot_path", payload)

    def test_diagnoser_serialization_hides_execution_and_gold(self):
        with temporary_episode(condition="agent_fault") as (root, result):
            steps = [json.loads(line) for line in (root / "episodes" / result["episode_id"] / "steps.jsonl").read_text().splitlines()]
            serialized = public_trajectory(steps)
            flattened = json.dumps(serialized)
            for key in FORBIDDEN:
                self.assertNotIn(f'"{key}"', flattened)

    def test_screenshot_filename_has_no_fault_name(self):
        with temporary_episode(condition="application_fault") as (root, result):
            episode = root / "episodes" / result["episode_id"]
            for path in episode.glob("*.png"):
                self.assertNotIn(str(result["gold_fault_type"]), path.name)


if __name__ == "__main__":
    unittest.main()

