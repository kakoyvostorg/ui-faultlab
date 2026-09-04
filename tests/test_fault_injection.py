import tempfile
import unittest

from ui_faultlab.actions import Action
from ui_faultlab.environment import BrowserEnvironment
from ui_faultlab.faults.agent_faults import AgentFaultInjector


class FaultInjectionTest(unittest.TestCase):
    def test_agent_fault_preserves_intended_and_changes_executed(self):
        intended = Action("tap", .82, .15, reason="open new event")
        result = AgentFaultInjector("coordinate_jitter", "create_event").intercept(intended, 0)
        self.assertEqual(result.intended, intended)
        self.assertNotEqual(result.executed, intended)
        self.assertTrue(result.injected)

    def test_save_noop_changes_transition_not_just_text(self):
        with tempfile.TemporaryDirectory() as directory:
            env = BrowserEnvironment("create_event", 0, directory, "save_noop")
            env.state.update({"screen": "edit", "draft": {"title": "X", "date": "2026-09-20", "time": "14:30", "attendees": []}, "selected_event_id": None})
            count = len(env.state["events"])
            env.apply(Action("tap", .72, .88))
            self.assertEqual(len(env.state["events"]), count)
            self.assertEqual(env.state["screen"], "calendar")

    def test_value_corruption_persists_wrong_state(self):
        with tempfile.TemporaryDirectory() as directory:
            env = BrowserEnvironment("reschedule_event", 0, directory, "value_corruption")
            env.state.update({"screen": "edit", "selected_event_id": "evt-design", "draft": dict(env.state["events"][0])})
            env.state["draft"]["time"] = "15:00"
            env.apply(Action("tap", .72, .88))
            design = next(e for e in env.state["events"] if e["event_id"] == "evt-design")
            self.assertEqual(design["time"], "09:99")

    def test_confirmation_bug_closes_modal_without_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            env = BrowserEnvironment("delete_event", 0, directory, "confirmation_transition_bug")
            env.state.update({"screen": "edit", "selected_event_id": "evt-sync", "draft": dict(env.state["events"][1]), "confirm_delete": True})
            env.apply(Action("tap", .65, .65))
            self.assertTrue(any(e["event_id"] == "evt-sync" for e in env.state["events"]))
            self.assertFalse(env.state["confirm_delete"])


if __name__ == "__main__":
    unittest.main()

