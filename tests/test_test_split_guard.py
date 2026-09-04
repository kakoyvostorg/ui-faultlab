import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestSplitGuardTest(unittest.TestCase):
    def test_test_split_requires_both_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "scripts/run_experiment.py", "--split", "test", "--artifacts", directory],
                text=True, capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("both --evaluate-test and --allow-test", result.stderr + result.stdout)

    def test_test_access_is_logged_after_freeze(self):
        with tempfile.TemporaryDirectory() as directory:
            config = json.loads(Path("configs/experiment.yaml").read_text())
            from ui_faultlab.instrumentation import atomic_write_json, canonical_hash
            atomic_write_json(Path(directory) / "freeze.json", {"config_hash": canonical_hash(config)})
            result = subprocess.run(
                [sys.executable, "scripts/run_experiment.py", "--split", "test", "--artifacts", directory, "--evaluate-test", "--allow-test"],
                text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(directory) / "test_access_log.jsonl").exists())


if __name__ == "__main__":
    unittest.main()

