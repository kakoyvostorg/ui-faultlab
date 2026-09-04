import tempfile
import unittest

from ui_faultlab.environment import BrowserEnvironment
from ui_faultlab.snapshots import snapshot_hash


class TaskResetTest(unittest.TestCase):
    def test_reset_is_identical_for_every_task(self):
        with tempfile.TemporaryDirectory() as directory:
            for task in ("create_event", "add_attendee", "reschedule_event", "delete_event"):
                env = BrowserEnvironment(task, 2, directory)
                before = snapshot_hash(env.snapshot())
                env.state["events"].clear()
                env.reset()
                self.assertEqual(before, snapshot_hash(env.snapshot()))

    def test_snapshot_is_a_deep_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            env = BrowserEnvironment("create_event", 0, directory)
            snapshot = env.snapshot()
            snapshot["events"][0]["title"] = "changed"
            self.assertEqual(env.state["events"][0]["title"], "Design Review")


if __name__ == "__main__":
    unittest.main()

