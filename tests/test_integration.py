import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers import temporary_episode
from ui_faultlab.reporting import build_report


class IntegrationTest(unittest.TestCase):
    def test_scripted_oracle_passes_all_clean_tasks(self):
        for task in ("create_event", "add_attendee", "reschedule_event", "delete_event"):
            with temporary_episode(task=task) as (_, result):
                self.assertTrue(result["task_success"], task)

    def test_app_fault_breaks_oracle_path(self):
        with temporary_episode(task="delete_event", condition="application_fault") as (_, result):
            self.assertFalse(result["task_success"])
            self.assertEqual(result["gold_label"], "application_bug")

    def test_agent_fault_records_changed_execution(self):
        with temporary_episode(task="create_event", condition="agent_fault") as (root, result):
            steps = [json.loads(line) for line in (root / "episodes" / result["episode_id"] / "steps.jsonl").read_text().splitlines()]
            injected = [s for s in steps if s["fault_injected"]]
            self.assertEqual(len(injected), 1)
            self.assertNotEqual(injected[0]["intended_action"], injected[0]["executed_action"])

    def test_reset_replay_reproduces_app_failure(self):
        with temporary_episode(task="delete_event", condition="application_fault") as (_, result):
            self.assertEqual(result["predictions"]["active"]["label"], "application_bug")
            self.assertEqual(result["predictions"]["active"]["probes_used"], 1)

    def test_full_bundle_exists(self):
        with temporary_episode(condition="agent_fault") as (root, result):
            episode = root / "episodes" / result["episode_id"]
            required = {"manifest.json", "steps.jsonl", "gold.json", "evaluation.json", "diagnosis_terminal.json", "diagnosis_trajectory.json", "diagnosis_active.json"}
            self.assertTrue(required.issubset({p.name for p in episode.iterdir()}))
            self.assertTrue(list(episode.glob("step_*.png")))

    def test_active_diagnosis_respects_probe_budget(self):
        with temporary_episode(task="add_attendee", condition="agent_fault") as (_, result):
            self.assertLessEqual(result["predictions"]["active"]["probes_used"], 1)

    def test_report_builder_on_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            with temporary_episode(condition="agent_fault") as (source, result):
                target = Path(directory) / "artifacts" / "episodes" / result["episode_id"]
                import shutil
                shutil.copytree(source / "episodes" / result["episode_id"], target)
            report = Path(directory) / "report" / "REPORT.md"
            metrics = build_report(Path(directory) / "artifacts", report)
            self.assertEqual(metrics["episode_count"], 1)
            self.assertTrue(report.exists())

    def test_server_shutdown_closes_listener(self):
        from app.server import serve

        class FakeServer:
            instance = None

            def __init__(self, address, handler):
                self.server_address = address
                self.closed = False
                FakeServer.instance = self

            def serve_forever(self):
                raise KeyboardInterrupt

            def server_close(self):
                self.closed = True

        serve("127.0.0.1", 0, FakeServer)
        self.assertTrue(FakeServer.instance.closed)


if __name__ == "__main__":
    unittest.main()
