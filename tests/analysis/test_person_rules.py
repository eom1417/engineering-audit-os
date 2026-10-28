"""The person's own rules (M16): kept in their words with their scope, guarded by a machine, one card with every place,
held at a fix's gate and at the commit, a change checked on what it brought, unpinned without leaving a copy behind."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from tests.shared_fixture import Workspace

from eaos.analysis.rules import changed, context, guards, held
from eaos.core.project import rules as registry

ROOT = Path(__file__).resolve().parents[2]
DATA_IN_CODE = {'kind': 'pattern', 'language': 'javascript', 'rule': {'pattern': 'const $X = [$$$ITEMS]', 'has': {'kind': 'object', 'stopBy': 'end'}},
                'message': 'records written in the code', 'examples': {'broken': ['const users = [{name: "Sara"}]'],
                                                                      'kept': ['const steps = [1, 2, 3]', 'const users = await db.all()']}}


def git(folder, *args):
    return subprocess.run(['git', '-C', str(folder), *args], capture_output=True, text=True, check=True)


class Rules(Workspace):
    def setUp(self):
        super().setUp()
        self.home = Path(self.tmp) / 'home'
        patcher = mock.patch.dict(os.environ, {'EAOS_HOME': str(self.home), 'EAOS_OUTPUT': str(Path(self.tmp) / 'out')})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.project = Path(self.tmp) / 'app'
        (self.project / 'src').mkdir(parents=True)
        (self.project / 'src/db.js').write_text('export const db = { all: async () => [] };\n')
        (self.project / 'src/users.js').write_text('import { db } from "./db.js";\nexport const users = () => db.all();\n')
        (self.project / 'src/page.js').write_text('import { users } from "./users.js";\nexport const page = () => users();\n')
        git(self.tmp, 'init', '-q', str(self.project))
        for key, value in (('user.name', 't'), ('user.email', 't@t')): git(self.project, 'config', key, value)
        git(self.project, 'add', '-A')
        git(self.project, 'commit', '-qm', 'init')

    def commit(self, message='change'):
        git(self.project, 'add', '-A')
        git(self.project, 'commit', '-qm', message)


class Kept(Rules):
    def test_a_rule_said_again_in_other_forms_is_the_same_rule_and_its_scope_ends_with_its_batch(self):
        rule, before = registry.add(self.project, 'البيانات تعيش في قاعدة البيانات بس', 'chat', scope={'kind': 'batch', 'ref': 2})
        self.assertEqual((rule['id'], before, rule['lang'], rule['said'][0]['door']), ('R1', 0, 'ar', 'chat'))
        again, before = registry.add(self.project, 'البيانات تعيش في قاعدة البيانات، بس!', 'studio', scope={'kind': 'batch', 'ref': 2})
        self.assertEqual((again['id'], before, len(registry.load(self.project)['rules'])), ('R1', 1, 1), 'said again, never a second rule')
        pinned, _ = registry.add(self.project, 'Never send the whole state on every save', 'mcp', scope={'kind': 'pinned'})
        state = {'waves': [{'number': 2, 'status': 'accepted', 'kept': {}}]}
        ended = registry.settle(self.project, state)
        self.assertEqual([r['id'] for r in ended], ['R1'], 'a rule left unpinned stops at its scope\'s end')
        self.assertEqual([r['id'] for r in registry.holding(self.project, state)], [pinned['id']])
        self.assertEqual(registry.find(registry.load(self.project), 'R1')['history'][-1]['why'], 'its batch 2 is over')

    def test_every_change_keeps_who_when_and_what_it_was_and_a_break_after_a_hold_is_a_return(self):
        registry.add(self.project, 'Prices come from one table', 'terminal')
        registry.change(self.project, 'R1', 'person', 'studio', 'it holds everywhere', scope={'kind': 'pinned', 'ref': None})
        registry.change(self.project, 'R1', 'person', 'terminal', words='Prices come from the prices table only')
        history = registry.find(registry.load(self.project), 'R1')['history']
        self.assertEqual([h['what'] for h in history], ['said', 'pinned', 'changed'])
        self.assertEqual(history[2]['was']['words'], 'Prices come from one table')
        registry.broke(self.project, 'R1', 'check:a', ['src/a.js:1'])
        registry.broke(self.project, 'R1', 'check:a', ['src/a.js:1'])          # the same check read again
        registry.held(self.project, 'R1', 'check:b')
        registry.broke(self.project, 'R1', 'gate', ['src/b.js:3'])
        rule = registry.find(registry.load(self.project), 'R1')
        self.assertEqual((rule['broken'], registry.came_back(rule)), (2, 1))


class Guarded(Rules):
    def test_a_pattern_is_proved_on_its_examples_and_one_that_would_refuse_sound_code_is_refused(self):
        guard = guards.checked(DATA_IN_CODE)
        (self.project / 'src/seed.js').write_text('export const users = [{ name: "Sara" }];\nconst steps = [1, 2];\n')
        self.assertEqual(guards.run(guard, self.project)['places'], ['src/seed.js:1'])
        with self.assertRaisesRegex(ValueError, 'finds kept example 1'):
            guards.checked({**DATA_IN_CODE, 'rule': {'pattern': 'const $X = $Y'}})
        with self.assertRaisesRegex(ValueError, 'does not find broken example 1'):
            guards.checked({**DATA_IN_CODE, 'rule': {'pattern': 'let $X = [$$$I]'}})
        self.assertEqual(guards.run(guards.checked({'kind': 'none', 'why': 'a matter of taste'}), self.project)['status'], 'unguarded')

    def test_a_test_guard_names_the_places_its_output_points_at_and_a_detector_guard_reads_what_was_found(self):
        failing = guards.checked({'kind': 'test', 'command': [sys.executable, '-c', 'print("src/db.js:1: no"); raise SystemExit(1)']})
        self.assertEqual(guards.run(failing, self.project)['places'], ['src/db.js:1'])
        detector = guards.checked({'kind': 'detector', 'detectors': ['real_data']})
        found = [{'detector': 'real_data:personal', 'places': ['src/seed.js'], 'said': 'names in the code'}]
        self.assertEqual(guards.run(detector, self.project, None, found)['status'], 'broken')
        self.assertEqual(guards.run(detector, self.project, None, [])['status'], 'held')


class HeldOnAChange(Rules):
    def test_a_change_is_refused_only_for_what_it_brought_never_for_a_break_already_there(self):
        rule, _ = registry.add(self.project, 'No records in the code', 'terminal', scope={'kind': 'pinned'})
        registry.guard(self.project, rule['id'], guards.checked(DATA_IN_CODE), 'person', 'terminal')
        (self.project / 'src/seed.js').write_text('export const users = [{ name: "Sara" }];\n')
        self.commit('a break already there')
        rules = registry.holding(self.project, {})
        (self.project / 'src/seed.js').write_text('export const users = [{ name: "Sara" }];\nexport const x = 1;\n')
        git(self.project, 'add', '-A')
        result = changed.check(self.project, rules, staged=True, gates=False)
        self.assertFalse(result['refused'], result['rules'])
        (self.project / 'src/more.js').write_text('export const cities = [{ name: "Riyadh" }];\n')
        git(self.project, 'add', '-A')
        result = changed.check(self.project, rules, staged=True, gates=False)
        self.assertEqual([(r['id'], r['places']) for r in result['rules']], [('R1', ['src/more.js:1'])])
        self.assertIn('No records in the code', held.refusal(result['rules'])[0])

    def test_the_check_reaches_the_files_that_depend_on_the_change(self):
        (self.project / 'src/db.js').write_text('export const db = { all: async () => [1] };\n')
        files, wide = changed.reached(self.project, changed.changed(self.project))
        self.assertEqual((sorted(files), wide), (['src/db.js', 'src/page.js', 'src/users.js'], False))

    def test_a_test_that_failed_before_the_change_never_refuses_it(self):
        rule, _ = registry.add(self.project, 'The tests pass', 'terminal', scope={'kind': 'pinned'})
        always = {'kind': 'test', 'command': [sys.executable, '-c', 'raise SystemExit(1)']}
        registry.guard(self.project, rule['id'], guards.checked(always), 'person', 'terminal')
        (self.project / 'src/db.js').write_text('export const db = {};\n')
        result = changed.check(self.project, registry.holding(self.project, {}), gates=False)
        self.assertFalse(result['refused'])


class AtTheGate(Rules):
    def test_a_fix_that_breaks_a_rule_is_refused_with_its_words_and_how_often_it_came_back(self):
        rule, _ = registry.add(self.project, 'No records in the code', 'card', scope={'kind': 'card', 'ref': 'CLM-001'})
        registry.guard(self.project, rule['id'], guards.checked(DATA_IN_CODE), 'person', 'card')
        registry.broke(self.project, rule['id'], 'check:a', ['src/old.js:1'])
        registry.held(self.project, rule['id'], 'check:b')
        rules = registry.holding(self.project, {}, card='CLM-001')
        (self.project / 'src/seed.js').write_text('export const users = [{ name: "Sara" }];\n')
        self.commit('the fix')
        said = held.gate(self.project, rules, self.project, ['src/seed.js'], [])
        self.assertEqual(len(said), 1)
        self.assertIn('"No records in the code" at src/seed.js:1; this change brought it back (1 time(s) it came back)', said[0])
        self.assertIn('pin it', said[0], 'pinning is offered for a rule not pinned')
        self.assertEqual(registry.came_back(registry.find(registry.load(self.project), 'R1')), 1)
        self.assertEqual(registry.holding(self.project, {}, card='CLM-002'), [], 'a card\'s rule holds for that card only')


class ThroughTheTools(Rules):
    def test_saying_a_rule_is_the_assistants_to_do_and_pinning_it_the_persons_never_inside_a_studio_run(self):
        from eaos.interfaces.mcp_server import rules as tools
        added = tools.rule('add', words='Never send the whole state on every save', project=str(self.project))
        self.assertEqual((added['rule']['id'], added['rule']['doors']), ('R1', ['mcp']))
        self.assertEqual(tools.rule('pin', id='R1', project=str(self.project))['status'], 'needs_the_person')
        with mock.patch.dict(os.environ, {'EAOS_STUDIO_RUN': 'r1'}), self.assertRaises(PermissionError):
            tools.rule('pin', id='R1', person_agreed=True, project=str(self.project))
        pinned = tools.rule('pin', id='R1', person_agreed=True, project=str(self.project))
        self.assertIn('AGENTS.md', pinned['written_into'])
        listed = tools.rules(project=str(self.project))
        self.assertEqual((listed['pinned'], listed['rules'][0]['history'][-1]['what']), (1, 'pinned'))


class Written(Rules):
    def test_pinned_rules_go_between_the_markers_and_unpinning_leaves_nothing_behind(self):
        (self.project / 'CLAUDE.md').write_text('# Mine\n@AGENTS.md\n')
        (self.project / 'AGENTS.md').write_text('# How we work\n')
        rule = {'id': 'R1', 'words': 'Data lives only in the database', 'guard': DATA_IN_CODE}
        files, made = context.write(self.project, [rule], [])
        self.assertEqual((files, made), (['AGENTS.md'], []), 'CLAUDE.md imports AGENTS.md: the block is read once')
        self.assertIn('- Data lives only in the database (R1, guarded by a code pattern)', (self.project / 'AGENTS.md').read_text())
        context.write(self.project, [], made)
        self.assertEqual((self.project / 'AGENTS.md').read_text(), '# How we work\n')
        hook = self.project / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\necho mine\nexit 0\n')
        context.hook(self.project, ['eaos'], True)
        self.assertTrue(context.hooked(self.project))
        self.assertLess(hook.read_text().index('check --changed'), hook.read_text().index('exit 0'), 'never skipped by an exit below it')
        context.hook(self.project, ['eaos'], False)
        self.assertEqual(hook.read_text(), '#!/bin/sh\necho mine\nexit 0\n')

    def test_the_commit_hook_refuses_a_commit_that_breaks_a_pinned_rule_with_the_persons_words(self):
        env = {**os.environ, 'PYTHONPATH': str(ROOT)}
        eaos = lambda *argv: subprocess.run([sys.executable, '-m', 'eaos', *argv, '--project', str(self.project), '--lang', 'en'],
                                            cwd=self.project, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(eaos('rules', 'add', 'No records written in the code', '--pin').returncode, 0)
        guard = eaos('rules', 'guard', 'R1', '--language', 'javascript', '--pattern', json.dumps(DATA_IN_CODE['rule']),
                     '--broken', DATA_IN_CODE['examples']['broken'][0], '--kept', DATA_IN_CODE['examples']['kept'][0])
        self.assertEqual(guard.returncode, 0, guard.stdout)
        self.assertEqual(eaos('rules', 'hook', 'on', '--yes').returncode, 0)
        (self.project / 'src/seed.js').write_text('export const users = [{ name: "Sara" }];\n')
        git(self.project, 'add', '-A')
        refused = subprocess.run(['git', '-C', str(self.project), 'commit', '-qm', 'records'], capture_output=True, text=True, env=env)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('No records written in the code', refused.stdout + refused.stderr)
        self.assertIn('src/seed.js:1', refused.stdout + refused.stderr)
        unpinned = eaos('rules', 'unpin', 'R1')
        self.assertEqual(unpinned.returncode, 0, unpinned.stdout)
        self.assertFalse(context.hooked(self.project), 'the last pinned rule took its hook block with it')
        self.assertFalse((self.project / 'AGENTS.md').exists(), 'a file EAOS made for the rules alone goes with them')
        self.assertEqual(subprocess.run(['git', '-C', str(self.project), 'commit', '-qm', 'records'], env=env).returncode, 0)



class InACheck(Rules):
    def test_a_broken_rule_is_one_card_with_every_place_that_closes_only_when_its_guard_finds_none(self):
        from eaos.analysis.claims.recheck import recheck
        from eaos.core.project.places import workspace
        from eaos.pipeline import execute
        rule, _ = registry.add(self.project, 'No records written in the code', 'studio', scope={'kind': 'pinned'})
        registry.guard(self.project, rule['id'], guards.checked(DATA_IN_CODE), 'person', 'studio')
        (self.project / 'src/seed.js').write_text('export const users = [{ name: "Sara" }];\nexport const cities = [{ name: "Riyadh" }];\n')
        (self.project / 'src/more.js').write_text('export const rows = [{ id: 1 }];\n')
        out = Path(self.tmp) / 'report'
        execute(self.project, out, language='en', sign_in={'folder': str(workspace(self.project))})
        cards = [c for c in json.loads((out / 'dossier.json').read_text())['claims'] if (c.get('render') or {}).get('key') == 'person_rule']
        self.assertEqual(len(cards), 1, 'one card per rule, every place in it')
        params = cards[0]['render']['params']
        self.assertEqual(params['places'], ['src/more.js:1', 'src/seed.js:1', 'src/seed.js:2'])
        self.assertIn('No records written in the code', cards[0]['statement'])
        self.assertEqual(registry.find(registry.load(self.project), 'R1')['broken'], 1)
        self.assertIn("'recheck'", str(cards[0].get('checks')), 'a ready repair: its check runs the guard again on the fixed copy')
        task = next(t for t in json.loads((out / 'plan.json').read_text())['tasks'] if t.get('pattern') == 'person_rule')
        self.assertEqual((task['decision']['kind'], task['decision']['readiness']), ('repair', 'ready'))
        spec = cards[0]['probe_spec']
        self.assertEqual(recheck(self.project, spec)[0], 'CONFIRMED')
        for name in ('seed.js', 'more.js'): (self.project / 'src' / name).write_text('export const rows = async (db) => db.all();\n')
        self.assertEqual(recheck(self.project, spec)[0], 'REFUTED', 'closed only when the guard finds none')


if __name__ == '__main__':
    unittest.main()
