import tempfile
import unittest

from ui_faultlab.artifacts.registry import ArtifactRegistry


class RegistryResumeTest(unittest.TestCase):
    def test_completed_matching_episode_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/registry.json"
            registry = ArtifactRegistry(path)
            registry.update("ep", {"status": "completed", "config_hash": "abc"})
            loaded = ArtifactRegistry(path)
            self.assertFalse(loaded.should_run("ep", "abc"))
            self.assertTrue(loaded.should_run("ep", "different"))


if __name__ == "__main__":
    unittest.main()

