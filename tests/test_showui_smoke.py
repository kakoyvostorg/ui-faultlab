import unittest
from pathlib import Path

from scripts.showui_smoke import run_two_inference_smoke
from ui_faultlab.agents.showui import ShowUIOutputError, parse_showui_action


class FakeShowUIAgent:
    def __init__(self):
        self.calls = 0

    def raw_action(self, screenshot_path, instruction, history):
        self.calls += 1
        return "{'action': 'CLICK', 'value': None, 'position': [0.8, 0.15]}", 12.5


class ShowUISmokeTest(unittest.TestCase):
    def test_runner_makes_exactly_two_calls(self):
        cases = [
            {"task_id": "a", "seed": 1, "instruction": "one", "screenshot_path": str(Path("a.png")), "screenshot_sha256": "a"},
            {"task_id": "b", "seed": 1, "instruction": "two", "screenshot_path": str(Path("b.png")), "screenshot_sha256": "b"},
        ]
        agent = FakeShowUIAgent()
        outputs = run_two_inference_smoke(agent, cases)
        self.assertEqual(agent.calls, 2)
        self.assertEqual(len(outputs), 2)
        self.assertTrue(all(row["parsed_action"]["type"] == "tap" for row in outputs))

    def test_runner_rejects_any_other_case_count(self):
        with self.assertRaises(ValueError):
            run_two_inference_smoke(FakeShowUIAgent(), [])

    def test_official_click_and_input_formats_are_mapped(self):
        click = parse_showui_action("{'action': 'CLICK', 'value': None, 'position': [0.8, 0.15]}")
        entered = parse_showui_action("{'action': 'INPUT', 'value': 'hello', 'position': [0.4, 0.35]}")
        self.assertEqual(click.type, "tap")
        self.assertEqual(entered.type, "input")
        self.assertEqual(entered.text, "hello")

    def test_mixed_generic_format_is_rejected_without_repair(self):
        with self.assertRaises(ShowUIOutputError):
            parse_showui_action("{'type': 'tap', 'x': 0.8, 'y': 0.15}")


if __name__ == "__main__":
    unittest.main()
