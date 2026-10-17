"""One owner for the class-scoped temporary directory every fact test needs.

Seventeen test classes carried the same `tearDownClass` body. The tool found it, this is the
canonical home it proposed, and removing the copies is what closing that finding means.
"""
import atexit
import os
import shutil
import tempfile
import unittest

# The suite checks what each detector finds on its fixture. Which detectors a reader is shown is measured on the
# labelled precision set (tools/precision.py) and tested on its own (test_precision), so the suite runs with no
# verdicts unless a test sets them. Every test module that audits a fixture imports this module.
os.environ.setdefault('EAOS_DETECTOR_VERDICTS', '')


def scratch(prefix=None):
    """A temporary folder removed when the test run ends, for a fixture built outside a test's own setUp (a repository,
    a report): the suite leaves nothing in the temporary folder (one run had left 111 folders, and over weeks 24,000)."""
    folder = tempfile.mkdtemp(prefix=prefix)
    atexit.register(shutil.rmtree, folder, True)
    return folder


class Workspace(unittest.TestCase):
    """A test class that builds a fixture per test and removes it per test."""

    def setUp(self):
        self.tmp = scratch()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TemporaryWorkspace(unittest.TestCase):
    """A test class that builds a fixture once and cleans it up once.

    Subclasses set `cls.tmp` in their own setUpClass — via `cls.workspace()` — and inherit the
    teardown. A subclass that never creates one is not punished for it.
    """

    tmp = None

    @classmethod
    def workspace(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        return cls.tmp

    @classmethod
    def tearDownClass(cls):
        if cls.tmp is not None:
            cls.tmp.cleanup()
            cls.tmp = None
