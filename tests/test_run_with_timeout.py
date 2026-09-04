import subprocess
import sys
import unittest


class TimeoutWrapperTest(unittest.TestCase):
    def test_propagates_success(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_with_timeout.py", "--timeout-seconds", "2", "--", sys.executable, "-c", "pass"],
            check=False,
        )
        self.assertEqual(result.returncode, 0)

    def test_terminates_slow_command(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_with_timeout.py", "--timeout-seconds", "1", "--", sys.executable, "-c", "import time; time.sleep(5)"],
            check=False,
        )
        self.assertEqual(result.returncode, 124)


if __name__ == "__main__":
    unittest.main()
