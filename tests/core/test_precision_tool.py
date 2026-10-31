"""A verdict comes from judged labels (M18.5): the score moves only the detectors it judged, against the bar."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools' / 'judging'))
import precision  # noqa: E402

BAR = {'precision': 0.8, 'recall': 0.5, 'judged': 5}
BASE = {'bar': BAR, 'hidden': {'old': 'why', 'kept': 'why'}, 'shown': ['seen']}


def judged(true, false): return [{'true': True}] * true + [{'true': False}] * false


class PrecisionTool(unittest.TestCase):
    def test_a_score_is_counted_from_its_judged_outputs_and_what_was_planted(self):
        rows = judged(3, 1) + [{'planted': True, 'found': True}, {'planted': True, 'found': False}]
        self.assertEqual(precision.measured(rows), {'judged': 4, 'precision': 0.75, 'recall': 0.5})

    def test_a_detector_passes_only_above_the_bar_and_the_look_needs_more_judged(self):
        good = precision.measured(judged(6, 0))
        self.assertIsNone(precision.why_hidden('hotspot', good, BAR))
        self.assertIn('bar 20', precision.why_hidden('design:looks', good, BAR))
        self.assertIn('precision', precision.why_hidden('hotspot', precision.measured(judged(4, 2)), BAR))

    def test_only_what_was_scored_moves(self):
        moved = precision.apply(BASE, {'old': precision.measured(judged(6, 0)), 'seen': precision.measured(judged(1, 0))})
        self.assertEqual(moved['shown'], ['old'])
        self.assertEqual(set(moved['hidden']), {'kept', 'seen'})


if __name__ == '__main__':
    unittest.main()
