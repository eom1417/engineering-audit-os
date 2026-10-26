"""A batch of moves (M8.5): drawn as one tree from the repository's findings, made on a branch of its own, and refused
whole when anything differs."""
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from shared_fixture import Workspace

from analysis.test_moves import FAMILY, SHOP
from eaos.facts.run import collect
from eaos.journeys.fix import move_batch

DYNAMIC = ('\n\nclass Dynamic(unittest.TestCase):\n    def test_by_name(self):\n        import importlib\n'
           "        self.assertTrue(importlib.import_module('shop.' + 'pipeline_run').go)\n")


def git(root, *argv):
    return subprocess.run(['git', '-C', str(root), *argv], check=True, capture_output=True, text=True).stdout.strip()


def unittest_checks(root, runtime, name):
    """The project's checks as the gate runs them: here its unittest suite, each test named."""
    done = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=root, capture_output=True,
                          text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    return [{'argv': ['python', '-m', 'unittest'], 'exit': done.returncode, 'output': done.stdout + done.stderr}]


class MoveBatchTests(Workspace):
    def project(self, files):
        root = Path(self.tmp) / 'project'
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text, encoding='utf-8')
        git(root, 'init', '-q')
        git(root, 'add', '-A')
        git(root, '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'one')
        return root

    def make(self, root, chosen, checks=unittest_checks):
        runtime, report = Path(self.tmp) / 'runtime', Path(self.tmp) / 'report'
        runtime.mkdir(exist_ok=True)
        report.mkdir(exist_ok=True)
        (runtime / 'authorization.json').write_text(json.dumps({'commit': git(root, 'rev-parse', 'HEAD')}))
        with mock.patch('eaos.live.isolation.sandbox.refusal', return_value=''), \
                mock.patch.object(move_batch, 'named_checks', checks), mock.patch.object(move_batch, 'new_breakage', return_value=[]):
            return move_batch.make({'report': report, 'target': root, 'runtime': runtime, 'number': 1, 'moves': chosen})

    def test_a_sound_batch_is_kept_on_its_own_branch_and_one_that_breaks_a_test_is_refused_whole(self):
        root = self.project(SHOP)
        summary = self.make(root, FAMILY)
        self.assertEqual((summary['kept'], summary['refused'], summary['branch']), (['shop/pipeline_run.py', 'shop/pipeline_load.py'], [], 'eaos/moves-1'))
        self.assertTrue((Path(summary['root']) / 'shop/pipeline/run.py').is_file())
        self.assertEqual(git(root, 'status', '--porcelain'), '', "the person's project is never written")

    def test_a_batch_that_breaks_what_the_tool_cannot_see_is_refused_whole_with_the_test_that_says_so(self):
        root = self.project({**SHOP, 'tests/test_shop.py': SHOP['tests/test_shop.py'] + DYNAMIC})
        summary = self.make(root, FAMILY)
        self.assertEqual(summary['kept'], [])
        self.assertIn('test_shop.Dynamic.test_by_name: passed before, not after', summary['refused'])
        self.assertEqual(git(Path(summary['root']), 'rev-parse', 'HEAD'), summary['base'], 'the copy is back at its base: nothing to hand over')

    def test_a_project_whose_tests_cannot_prove_it_gets_the_proposal_only(self):
        root = self.project({k: v for k, v in SHOP.items() if not k.startswith('tests/')})
        summary = self.make(root, FAMILY, checks=lambda *_: [])
        self.assertEqual(summary['kept'], [])
        self.assertEqual(summary['refused'], ['proposal only: the project has no check or test EAOS can run'])

    def test_the_proposal_draws_today_and_the_proposed_place_of_each_file_with_its_reason(self):
        files = {**SHOP, **{f'shop/pipeline_step{n}.py': f'STEP = {n}\n' for n in range(3)},
                 **{f'shop/part{n}.py': f'PART = {n}\n' for n in range(3)}}
        root = self.project(files)
        report = Path(self.tmp) / 'report'
        collect(root, report, ['syntax', 'resolve', 'repository'])
        drawn = move_batch.proposal(report, root)
        family = {m['from']: m['to'] for m in drawn['moves'] if m['rule'] == 'prefix-family'}
        self.assertEqual(family['shop/pipeline_run.py'], 'shop/pipeline/run.py')
        self.assertEqual(family['shop/pipeline_step2.py'], 'shop/pipeline/step2.py')
        self.assertIn('shop/', drawn['tree'])
        self.assertTrue(any(line.startswith('  pipeline_load.py  →  shop/pipeline/load.py') for line in drawn['tree']))
