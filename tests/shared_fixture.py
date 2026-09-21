"""One owner for the class-scoped temporary directory every fact test needs.

Seventeen test classes carried the same `tearDownClass` body. The tool found it, this is the
canonical home it proposed, and removing the copies is what closing that finding means.
"""
import shutil
import tempfile
import unittest


class Workspace(unittest.TestCase):
    """A test class that builds a fixture per test and removes it per test."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

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
