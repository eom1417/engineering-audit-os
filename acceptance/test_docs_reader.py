"""NS46.T23 owner-request acceptance (owner, 2026-10-10: a professional document reader), planned 2026-10-10.

The evidence is the full screen gate of the shipped Studio ($EAOS_MEASURE/studio-gates/gates.json, tools/studio_gates.py
--studio) with its page `document-diagram` (a document holding a mermaid diagram and a table), and
$EAOS_MEASURE/docs-reader/trial.json from the real document of a check: {"diagrams_drawn", "diagrams", "tables"}.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import north_star_measure as measure


class DocsReader(unittest.TestCase):
    def test_every_diagram_of_a_real_document_is_drawn_and_the_screen_gate_passes_on_it(self):
        trial_path, gates_path = measure.REPORTS / 'docs-reader/trial.json', measure.REPORTS / 'studio-gates/gates.json'
        for path in (trial_path, gates_path): self.assertTrue(path.is_file(), f'no evidence at {path}')
        trial = json.loads(trial_path.read_text(encoding='utf-8'))
        self.assertGreaterEqual(trial.get('diagrams') or 0, 1)
        self.assertEqual(trial.get('diagrams_drawn'), trial.get('diagrams'))
        self.assertGreaterEqual(trial.get('tables') or 0, 1)
        gates = json.loads(gates_path.read_text(encoding='utf-8'))
        self.assertTrue(gates.get('pass'), 'the screen gate passed')
        self.assertIn('document-diagram', json.dumps(gates.get('pages') or gates))


if __name__ == '__main__':
    unittest.main()
