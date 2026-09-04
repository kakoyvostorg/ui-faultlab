import unittest

from app.tasks import success_predicate
from tests.helpers import temporary_episode


class SuccessPredicateTest(unittest.TestCase):
    def test_gold_and_negative_fixtures_for_all_tasks(self):
        for task in ("create_event", "add_attendee", "reschedule_event", "delete_event"):
            with temporary_episode(task=task, condition="clean") as (root, result):
                self.assertTrue(result["task_success"])
            with temporary_episode(task=task, condition="application_fault") as (root, result):
                self.assertFalse(result["task_success"])


if __name__ == "__main__":
    unittest.main()

