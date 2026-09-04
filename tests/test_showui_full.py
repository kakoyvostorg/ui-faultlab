import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_showui_full import build_summary, run_episode
from ui_faultlab.instrumentation import canonical_hash


CONFIG = {
    "resolution": [960, 640],
    "max_consecutive_no_change": 2,
    "task_version": "1.1",
    "prompt": "official-showui-navigation-v1",
}


class FakeAgent:
    def __init__(self, outputs):
        self.outputs = iter(outputs)

    def raw_action(self, screenshot_path, instruction, history):
        return next(self.outputs), 10.0


class ShowUIFullRunnerTest(unittest.TestCase):
    def test_delete_episode_runs_closed_loop_to_success(self):
        outputs = [
            "{'action': 'CLICK', 'value': None, 'position': [0.2, 0.5]}",
            "{'action': 'CLICK', 'value': None, 'position': [0.25, 0.88]}",
            "{'action': 'CLICK', 'value': None, 'position': [0.65, 0.65]}",
        ]
        with tempfile.TemporaryDirectory() as directory:
            result = run_episode(
                agent=FakeAgent(outputs), task_id="delete_event", seed=1, split="validation",
                run_root=Path(directory), config=CONFIG, config_hash=canonical_hash(CONFIG),
            )
            self.assertTrue(result["task_success"])
            self.assertEqual(result["vlm_calls"], 3)
            self.assertEqual(result["stop_reason"], "task_success")
            steps = list((Path(directory) / "episodes" / result["episode_id"] / "steps.jsonl").read_text().splitlines())
            self.assertEqual(len(steps), 3)
            self.assertTrue(all(json.loads(step)["parse_error"] is None for step in steps))

    def test_invalid_output_is_recorded_as_agent_error(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_episode(
                agent=FakeAgent(["not a dictionary"]), task_id="delete_event", seed=1,
                split="validation", run_root=Path(directory), config=CONFIG,
                config_hash=canonical_hash(CONFIG),
            )
            self.assertFalse(result["task_success"])
            self.assertEqual(result["gold_label"], "agent_error")
            self.assertEqual(result["parse_failures"], 1)
            self.assertEqual(result["stop_reason"], "parse_error")

    def test_summary_aggregates_real_call_latency(self):
        rows = [{
            "task_id": "delete_event", "split": "validation", "task_success": True,
            "vlm_calls": 2, "steps": 2, "parse_failures": 0, "invalid_actions": 0,
            "no_change_steps": 0, "loop_repetitions": 0, "stop_reason": "task_success",
            "latency_ms": {"total": 30.0, "mean": 15.0},
        }]
        summary = build_summary(rows, CONFIG, canonical_hash(CONFIG))
        self.assertEqual(summary["overall"]["mean_inference_latency_ms"], 15.0)


if __name__ == "__main__":
    unittest.main()
