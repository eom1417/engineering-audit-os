"""An engine's function measure longer than the function EAOS measured is set aside (excalidraw, 2026-11-04)."""
import unittest

from eaos.facts.misread import set_aside


def lizard(line, nloc):
    return {'kind': 'engine_finding', 'location': {'path': 'src/render.ts', 'line': line},
            'value': {'engine': 'lizard', 'kind': 'complexity', 'measurements': [{'name': 'nloc', 'value': nloc}]}}


SPAN = {'location': {'path': 'src/render.ts', 'start_line': 460, 'end_line': 722, 'symbol': 'drawElementOnCanvas'},
        'value': {'scope': 'function', 'lines': 263}}


class MisreadTests(unittest.TestCase):
    def test_a_measure_longer_than_its_function_is_set_aside_and_counted(self):
        # Lizard: 729 code lines for drawElementOnCanvas, which runs 263 lines; its complexity 110 reached a card.
        kept, count = set_aside([lizard(462, 729), lizard(462, 240)], [SPAN])
        self.assertEqual(([_length(f) for f in kept], count), ([240], 1))

    def test_a_measure_eaos_cannot_place_is_kept(self):
        kept, count = set_aside([lizard(900, 729)], [SPAN])
        self.assertEqual(count, 0)
        self.assertEqual(len(kept), 1)


def _length(fact): return fact['value']['measurements'][0]['value']


if __name__ == '__main__':
    unittest.main()
