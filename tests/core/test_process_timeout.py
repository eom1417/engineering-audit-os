"""A command that runs out of time is reported with its whole timeout, not the last slice it was waited for."""
import subprocess
import sys
import unittest
from eaos.kernel.system.process import run_command


class TimeoutTests(unittest.TestCase):
    def test_the_whole_timeout_is_said(self):
        with self.assertRaises(subprocess.TimeoutExpired) as raised:
            run_command([sys.executable, '-c', 'import time; time.sleep(5)'], timeout=0.6)
        self.assertEqual(raised.exception.timeout, 0.6)


if __name__ == '__main__':
    unittest.main()
