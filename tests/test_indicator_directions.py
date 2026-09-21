"""Indicator direction tests: every indicator in _LOWER_IS_BETTER is correctly classified."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from eaos.progress import _LOWER_IS_BETTER
from eaos.sustainability import DEFAULT_TARGETS


INDICATORS = ('single_source', 'minimal_path', 'data_owners', 'honest_boundaries',
               'verifiable_paths', 'understandable_units')


class IndicatorDirectionTests(unittest.TestCase):
    def test_every_indicator_has_a_target(self):
        for indicator in INDICATORS:
            self.assertIn(indicator, DEFAULT_TARGETS)

    def test_every_indicator_is_in_lower_is_better(self):
        """All six indicators are 'lower is better': the goal is to reduce the gap."""
        for indicator in INDICATORS:
            self.assertIn(indicator, _LOWER_IS_BETTER,
                          f'{indicator} should be in _LOWER_IS_BETTER; '
                          'every EAOS indicator points the same way (zero is best).')

    def test_target_for_lower_is_better_is_zero(self):
        for indicator in INDICATORS:
            self.assertEqual(DEFAULT_TARGETS[indicator], 0.0,
                              f'{indicator} target must be 0.0 because lower is better.')


class IndicatorSemanticTests(unittest.TestCase):
    """Each indicator must mean what the documentation says it means."""

    def test_verifiable_paths_target_is_zero(self):
        # The indicator counts flows that stop at the first boundary.
        # We want all flows to reach code, so the target is 0.
        self.assertEqual(DEFAULT_TARGETS['verifiable_paths'], 0.0)

    def test_single_source_target_is_zero(self):
        # We want no duplicated definitions.
        self.assertEqual(DEFAULT_TARGETS['single_source'], 0.0)

    def test_minimal_path_target_is_zero(self):
        # We want no redundant work.
        self.assertEqual(DEFAULT_TARGETS['minimal_path'], 0.0)
