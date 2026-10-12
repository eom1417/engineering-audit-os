"""The reference catalogue: a type per kind of project, chosen from the project's own files."""
import json
from pathlib import Path

from shared_fixture import Workspace

from eaos.reference_architecture import by_id, catalogue, choose, layer_of


class ReferenceTests(Workspace):
    def project(self, packages=None, pyproject=None, files=()):
        root = Path(self.tmp) / f'p{len(list(Path(self.tmp).iterdir()))}'
        root.mkdir()
        if packages is not None: (root / 'package.json').write_text(json.dumps({'dependencies': {p: '1' for p in packages}}))
        if pyproject: (root / 'pyproject.toml').write_text(pyproject)
        for name in files: (root / name).write_text('x = 1\n')
        return root

    def test_the_catalogue_is_consistent_and_the_most_specific_pattern_places_a_file(self):
        for kind in catalogue()['types']:
            names = {layer['name'] for layer in kind['layers']}
            for layer in kind['layers']:
                self.assertLessEqual(set(layer['allowed_dependencies']), names - {layer['name']}, (kind['id'], layer['name']))
                self.assertTrue(layer['paths'], (kind['id'], layer['name']))
        reference = by_id('react-tanstack-start-supabase')
        cases = {'src/components/ui/button.tsx': 'ui', 'src/components/accounts/Card.tsx': 'features',
                 'src/lib/market.server.ts': 'server', 'vite.config.ts': None}
        for path, layer in cases.items():
            self.assertEqual(layer_of(path, reference)[0], layer, path)

    def test_each_kind_of_project_gets_its_own_type(self):
        cases = [(dict(packages=['next', 'react']), 'nextjs-app'),
                 (dict(packages=['react', 'vite', '@supabase/supabase-js']), 'react-vite-supabase'),
                 (dict(pyproject='[project]\nname="x"\ndependencies=["flask>=3"]\n', files=['app.py']), 'python-web'),
                 (dict(files=['tool.py']), 'python-cli'),
                 (dict(pyproject='[project]\nname="x"\ndependencies=["streamlit"]\n', files=['App.spec', 'app.py']),
                  'python-desktop'),
                 ({}, None)]
        for options, expected in cases:
            with self.subTest(expected):
                self.assertEqual(choose(self.project(**options)), expected)
