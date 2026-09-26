"""The reference catalogue: a type per kind of project, chosen from the project's own files."""
import json
from pathlib import Path

from shared_fixture import Workspace

from eaos.reference_architecture import by_id, catalogue, choose, layer_of


class CatalogueTests(Workspace):
    def test_every_layer_dependency_names_another_layer_of_the_same_type(self):
        for kind in catalogue()['types']:
            names = {layer['name'] for layer in kind['layers']}
            for layer in kind['layers']:
                self.assertLessEqual(set(layer['allowed_dependencies']), names - {layer['name']}, (kind['id'], layer['name']))
                self.assertTrue(layer['paths'], (kind['id'], layer['name']))

    def test_the_most_specific_pattern_places_a_file(self):
        reference = by_id('react-tanstack-start-supabase')
        self.assertEqual(layer_of('src/components/ui/button.tsx', reference)[0], 'ui')
        self.assertEqual(layer_of('src/components/accounts/Card.tsx', reference)[0], 'features')
        self.assertEqual(layer_of('src/lib/market.server.ts', reference)[0], 'server')
        self.assertEqual(layer_of('vite.config.ts', reference), (None, None))


class ChooserTests(Workspace):
    def project(self, packages=None, pyproject=None, files=()):
        root = Path(self.tmp) / f'p{len(list(Path(self.tmp).iterdir()))}'
        root.mkdir()
        if packages is not None: (root / 'package.json').write_text(json.dumps({'dependencies': {p: '1' for p in packages}}))
        if pyproject: (root / 'pyproject.toml').write_text(pyproject)
        for name in files: (root / name).write_text('x = 1\n')
        return root

    def test_each_kind_of_project_gets_its_own_type(self):
        self.assertEqual(choose(self.project(['next', 'react'])), 'nextjs-app')
        self.assertEqual(choose(self.project(['react', 'vite', '@supabase/supabase-js'])), 'react-vite-supabase')

    def test_a_python_web_app_without_packaging_is_web_and_a_script_is_a_cli(self):
        self.assertEqual(choose(self.project(pyproject='[project]\nname="x"\ndependencies=["flask>=3"]\n', files=['app.py'])), 'python-web')
        self.assertEqual(choose(self.project(files=['tool.py'])), 'python-cli')

    def test_packaging_into_an_executable_makes_a_desktop_app(self):
        self.assertEqual(choose(self.project(pyproject='[project]\nname="x"\ndependencies=["streamlit"]\n', files=['App.spec', 'app.py'])),
                         'python-desktop')

    def test_nothing_recognisable_is_no_type(self):
        self.assertIsNone(choose(self.project()))
