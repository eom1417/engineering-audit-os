"""A check can follow some paths only (eaos/pipeline/paths.py): it runs what they need, keeps or leaves the rest, and
says so."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.engines import ADAPTERS
from eaos.check_paths import PATHS, SPINE
from eaos.pipeline.paths import resolve
from eaos.pipeline.run import check
from eaos.pipeline.stages import OPTIONAL, STAGES
from eaos.remediation_patterns import PATTERNS

FIXTURE = Path(__file__).parent / 'fixtures/polyglot'
LIVE = {stage.name for stage in STAGES if 'app' in stage.uses}


def _commit(project, message):
    subprocess.run(['git', 'add', '-A'], cwd=project, check=True)
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', message], cwd=project, check=True)


class PathsTests(unittest.TestCase):
    def test_each_path_runs_what_it_needs_and_together_they_cover_everything(self):
        security = resolve(['security'])
        self.assertFalse(LIVE & set(security['stages']), 'the security path never runs the app')
        self.assertIn('engines', security['stages'])
        vulnerable = {name for name, adapter in ADAPTERS.items() if 'vulnerability' in {c.kind for c in adapter.capabilities()}}
        self.assertTrue(vulnerable and vulnerable <= set(security['engines']), 'an engine joins its path by what it finds')
        both = resolve(['look', 'security'])
        self.assertEqual(set(both['stages']), set(security['stages']) | set(resolve(['look'])['stages']))
        self.assertEqual(resolve(['security', 'complete'])['stages'], None)
        with self.assertRaises(ValueError): resolve(['speedy'])
        # every optional stage, card pattern and engine capability belongs to a path
        chosen = [p for name, p in PATHS.items() if name != 'complete']
        optional = {s.name for s in STAGES if s.necessity == OPTIONAL} - set(SPINE)
        self.assertEqual(optional - {n for p in chosen for n in p.get('stages', ())}, set())
        self.assertEqual(set(PATTERNS) - {n for p in chosen for n in p.get('patterns', ())}, set())
        kinds = {c.kind for adapter in ADAPTERS.values() for c in adapter.capabilities()}
        self.assertEqual(kinds - {k for p in chosen for k in p.get('kinds', ())}, set())
        actions = json.loads((Path(__file__).parent.parent / 'eaos/data/studio-actions.json').read_text(encoding='utf-8'))['actions']
        audit = next(a for a in actions if a['id'] == 'audit')['inputs']['properties']
        self.assertEqual(audit['paths']['items']['enum'], list(PATHS), 'the Studio offers every path, in their order')
        named = {n for p in chosen for n in p.get('engines', ())}
        self.assertEqual({n for n, a in ADAPTERS.items() if not a.capabilities()} - named, set(), 'an engine that names no capability')


    def test_a_redo_from_a_stage_is_timed_as_that_stage_and_its_readers_only(self):
        from eaos import check_choices
        from eaos.pipeline.stages import ORDER, dependents
        with mock.patch.object(check_choices, 'previous_seconds', return_value={name: 60.0 for name in ORDER}):
            whole, redo = check_choices.estimate('report'), check_choices.estimate('report', again_from='reports')
        self.assertLess(redo['minutes_high'], whole['minutes_low'])
        self.assertLessEqual(redo['minutes_low'], 1 + len(dependents('reports', reading=True)))


    def test_a_redo_from_a_check_made_without_the_assistant_runs_without_it_unless_one_is_chosen_now(self):
        from eaos import check_choices
        with tempfile.TemporaryDirectory() as report:
            Path(report, 'run-manifest.json').write_text(json.dumps({'stages': {'triage': {'reason_code': 'ai_skipped'}}}))
            self.assertTrue(check_choices.without_ai_kept(report, False, 'reports', False))
            self.assertFalse(check_choices.without_ai_kept(report, False, 'reports', True), 'an assistant chosen now is used')
            self.assertFalse(check_choices.without_ai_kept(report, False, None, False), 'a new check asks as always')
            Path(report, 'run-manifest.json').write_text(json.dumps({'stages': {'triage': {'status': 'ok'}}}))
            self.assertFalse(check_choices.without_ai_kept(report, False, 'reports', False))


class FocusedCheckTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.project, self.out = Path(self.directory.name) / 'project', Path(self.directory.name) / 'out'
        shutil.copytree(FIXTURE, self.project)
        subprocess.run(['git', 'init', '-q'], cwd=self.project, check=True)
        _commit(self.project, 'fixture')

    def tearDown(self):
        self.directory.cleanup()

    def test_on_the_same_code_a_path_refreshes_its_part_and_keeps_the_rest_with_its_date(self):
        first = check(self.project, self.out, language='en')
        self.assertNotIn("This check's path", (self.out / 'START-HERE.md').read_text(encoding='utf-8'))
        tasks = json.loads((self.out / 'plan.json').read_text(encoding='utf-8'))['tasks']
        picture = self.out / 'live/screens/screenshots/home.png'
        picture.parent.mkdir(parents=True)
        picture.write_bytes(b'png')
        with mock.patch.dict(os.environ, {'EAOS_ENGINE_TOOLS': self.directory.name}):     # no engine installed: quick
            second = check(self.project, self.out, language='en', paths=['security'])
        self.assertEqual(second['paths'], ['security'])
        self.assertTrue(picture.is_file(), "a focused check deletes nothing of the last one")
        self.assertEqual(second['stages']['lock'].get('checked_at'), first['started_at'])
        page = (self.out / 'START-HERE.md').read_text(encoding='utf-8')
        self.assertIn('This check followed: Security. It did not look at: Look and screens, Code, Speed and scale', page)
        self.assertIn(f"the check of {first['started_at'][:10]}", page)
        self.assertEqual([t['id'] for t in json.loads((self.out / 'plan.json').read_text(encoding='utf-8'))['tasks']],
                         [t['id'] for t in tasks], 'the cards of the other paths stay')

    def test_on_other_code_a_path_keeps_only_its_cards_and_runs_only_its_stages(self):
        check(self.project, self.out, language='en')
        (self.project / 'core' / 'added.py').write_text('def added():\n    return 1\n', encoding='utf-8')
        _commit(self.project, 'more')
        manifest = check(self.project, self.out, language='en', paths=['look'])
        ran = {name for name, row in manifest['stages'].items() if row.get('reason_code') != 'outside_paths'}
        self.assertEqual(ran, set(resolve(['look'])['stages']))
        patterns = {t['pattern'] for t in json.loads((self.out / 'plan.json').read_text(encoding='utf-8'))['tasks']}
        self.assertLessEqual(patterns, set(PATHS['look']['patterns']))
        self.assertEqual(manifest['stages']['engines']['reason_code'], 'outside_paths')
        self.assertIn('they were not checked this time', (self.out / 'START-HERE.md').read_text(encoding='utf-8'))
