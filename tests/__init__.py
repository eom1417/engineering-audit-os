"""Lets `python -m unittest tests.test_x` work as well as `discover -s tests`: the tests import their
shared fixtures (shared_fixture, and the like) by bare name, from this directory."""
import sys
from pathlib import Path

HERE = str(Path(__file__).resolve().parent)
if HERE not in sys.path: sys.path.insert(0, HERE)
# The check uses the person's assistant unless they said no; a test never calls the real one unless it says so.
import os
os.environ.setdefault('EAOS_ASSISTANT', 'none')
