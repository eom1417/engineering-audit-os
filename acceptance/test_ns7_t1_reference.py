"""NS7.T1 — a catalogue of reference architectures, and a chooser that picks the right one per project.

Interface this task must provide:
    eaos/rules/reference-architectures.json
      {"schema_version": 1, "types": [{"id", "name", "detect": {...},
        "layers": [{"name", "responsibility", "allowed_dependencies": [layer names of the same type]}],
        "infrastructure_baseline": [{"area", "item", "reason", "success_measure"}]}]}
    from eaos.reference_architecture import choose
    choose(project_dir) -> the id of the type that fits, read from the project's own files only
      (package.json dependencies, pyproject/requirements, entry files); never runs anything.
    Required ids, one per corpus stack:
      react-vite-spa-rest            React + Vite single page app calling an HTTP API (FleetManageWeb: axios)
      react-tanstack-start-supabase  React + TanStack Start/Router + Supabase (finance-os)
      python-desktop                 Python desktop or command-line application (RendaPerene)
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import dev_paths  # noqa: E402

CORPUS = dev_paths.CORPUS
EXPECTED = {'FleetManageWeb': 'react-vite-spa-rest', 'finance-os-a0192b7b': 'react-tanstack-start-supabase',
            'RendaPerene': 'python-desktop'}
BASELINE = {'configuration', 'data', 'ci', 'tests', 'observability', 'secrets'}


class Reference(unittest.TestCase):
    def catalogue(self):
        return json.loads((ROOT / 'eaos/rules/reference-architectures.json').read_text(encoding='utf-8'))

    def test_every_type_is_complete_and_reasoned(self):
        types = self.catalogue()['types']
        self.assertTrue(set(EXPECTED.values()) <= {t['id'] for t in types})
        for kind in types:
            names = {layer['name'] for layer in kind['layers']}
            self.assertGreaterEqual(len(names), 3, kind['id'])
            for layer in kind['layers']:
                self.assertTrue(layer['responsibility'], (kind['id'], layer['name']))
                self.assertLessEqual(set(layer['allowed_dependencies']), names - {layer['name']}, (kind['id'], layer['name']))
            areas = {row['area'] for row in kind['infrastructure_baseline']}
            self.assertLessEqual(BASELINE, areas, kind['id'])
            for row in kind['infrastructure_baseline']:
                self.assertTrue(row['reason'] and row['success_measure'], (kind['id'], row['area']))

    def test_the_chooser_picks_the_right_type_for_each_corpus_project(self):
        from eaos.reference_architecture import choose
        for name, expected in EXPECTED.items():
            if not (CORPUS / name).is_dir():
                self.fail(f'{CORPUS / name} is missing: run python tools/north_star.py fetch')
            self.assertEqual(choose(CORPUS / name), expected, name)


if __name__ == '__main__':
    unittest.main()
