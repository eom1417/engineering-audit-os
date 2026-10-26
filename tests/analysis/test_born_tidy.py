"""Born tidy (M8.7): the gates every change passes hold the repository's craft and its assistants' context, so a project
built from its plan or extended with a feature ends with no such finding, and a fix is held only for what it made worse."""
from pathlib import Path

from shared_fixture import Workspace

from eaos.analysis.repair.gates import debt, tidy
from eaos.facts.run import collect

APP = {**{f'src/part{n}.py': f'PART = {n}\n' for n in range(4)}, 'src/main.py': 'from src import part0\n'}
FAMILY = {f'src/pipeline_{name}.py': f'STEP = "{name}"\n' for name in ('read', 'clean', 'load', 'save')}


class BornTidyTests(Workspace):
    def facts(self, name, files):
        root = Path(self.tmp) / name
        for path, text in files.items():
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_text(text, encoding='utf-8')
        out = Path(self.tmp) / f'{name}-facts'
        collect(root, out, ['syntax', 'resolve', 'repository'])
        return out

    def test_a_new_project_is_held_for_every_finding_and_a_change_only_for_what_it_made_worse(self):
        built = self.facts('built', {**APP, **FAMILY})
        found = tidy(None, built, [*APP, *FAMILY])
        self.assertEqual([(p['gate'], p['where']) for p in found], [('tidy', 'src/pipeline_*')])
        self.assertIn('Move them into src/pipeline/', found[0]['what'])
        before = self.facts('before', APP)
        self.assertEqual([p['where'] for p in debt(before, built, list(FAMILY)) if p['gate'] == 'tidy'], ['src/pipeline_*'],
                         'the change that added the family is held for it')
        self.assertEqual(tidy(built, built, list(FAMILY)), [], 'a finding the project already had is not the change\'s')
        self.assertEqual(tidy(None, built, ['src/main.py']), [], 'a change elsewhere is not held for it')
