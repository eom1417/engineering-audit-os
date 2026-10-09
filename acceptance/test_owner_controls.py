"""NS46.T17 owner-request acceptance, planned 2026-10-09; live evidence is mandatory."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import north_star_measure as measure
import north_star_studio as studio


class OwnerControls(unittest.TestCase):
    def test_both_projects_have_current_real_owner_control_evidence(self):
        value, evidence = studio.owner_controls_value(measure.REPORTS)
        self.assertEqual(value, 1.0, evidence)
