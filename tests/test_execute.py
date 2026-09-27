"""NS9: a card executed behind its own gates; the model's edits are held to the card's files and to exact text."""
import json
from pathlib import Path

from shared_fixture import Workspace

from eaos.execute import apply_edits, model_messages
from eaos.runtime.claude_adapter import parse, render


class EditTests(Workspace):
    def setUp(self):
        super().setUp()
        (Path(self.tmp) / 'a.ts').write_text('export const DAYS = ["Mon"];\nexport const x = 1;\n')
        (Path(self.tmp) / 'b.ts').write_text('export const DAYS = ["Mon"];\n')

    def test_an_edit_outside_the_card_is_refused_and_nothing_is_written(self):
        with self.assertRaises(ValueError):
            apply_edits(self.tmp, [{'path': 'a.ts', 'find': 'x = 1', 'replace': 'x = 2'},
                                   {'path': 'c.ts', 'find': 'a', 'replace': 'b'}], {'a.ts', 'b.ts'})
        self.assertIn('x = 1', (Path(self.tmp) / 'a.ts').read_text())

    def test_text_to_find_must_occur_exactly_once(self):
        with self.assertRaises(ValueError):
            apply_edits(self.tmp, [{'path': 'a.ts', 'find': 'export', 'replace': 'const'}], {'a.ts'})

    def test_edits_apply_in_order(self):
        changed = apply_edits(self.tmp, [
            {'path': 'b.ts', 'find': 'export const DAYS = ["Mon"];', 'replace': 'export { DAYS } from "./a";'}], {'a.ts', 'b.ts'})
        self.assertEqual(changed, ['b.ts'])
        self.assertEqual((Path(self.tmp) / 'b.ts').read_text(), 'export { DAYS } from "./a";\n')

    def test_the_model_sees_the_card_and_the_whole_of_its_files(self):
        card = {'id': 'TASK-1', 'title': 't', 'pattern': 'duplicated_rule', 'paths': ['a.ts', 'b.ts'], 'change': 'one home',
                'acceptance': [{'expect': 'the probe refutes it'}]}
        messages = model_messages(card, self.tmp)
        self.assertIn('=== a.ts\nexport const DAYS', messages[1]['content'])
        self.assertIn('the probe refutes it', messages[1]['content'])


class AdapterTests(Workspace):
    def test_system_turns_become_the_system_prompt(self):
        system, conversation = render([{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': 'U'}])
        self.assertTrue(system.startswith('S'))
        self.assertEqual(conversation, '### USER\nU')

    def test_a_fenced_or_wrapped_object_is_read_and_prose_alone_is_refused(self):
        self.assertEqual(parse('```json\n{"action": "final"}\n```'), {'action': 'final'})
        self.assertEqual(parse('Here: {"a": 1}'), {'a': 1})
        with self.assertRaises(ValueError): parse('no object here')


class BreakageTests(Workspace):
    def test_an_import_the_change_leaves_dangling_is_new_breakage_and_an_old_one_is_not(self):
        from eaos.execute import new_breakage
        from eaos.facts.run import collect
        repo, report = Path(self.tmp) / 'repo', Path(self.tmp) / 'report'
        (repo / 'src').mkdir(parents=True)
        (repo / 'package.json').write_text('{"name": "x"}')
        (repo / 'src/a.ts').write_text('import { b } from "./b";\nimport { gone } from "./gone";\nexport const a = b + gone;\n')
        (repo / 'src/b.ts').write_text('export const b = 1;\n')
        collect(repo, report, ['syntax', 'resolve', 'broken'])
        self.assertEqual(new_breakage(report, repo), [], 'what the report already had is not the change\'s doing')
        (repo / 'src/b.ts').unlink()
        broke = new_breakage(report, repo)
        self.assertEqual(len(broke), 1)
        self.assertIn('./b', broke[0])


class CheckGateTests(Workspace):
    def test_only_a_check_that_passed_before_can_fail_the_change(self):
        from eaos.execute import regressions
        before = [{'argv': ['npm', 'run', 'lint'], 'exit': 0}, {'argv': ['npm', 'test'], 'exit': 1}]
        self.assertEqual(regressions(before, [{'argv': ['npm', 'run', 'lint'], 'exit': 0}, {'argv': ['npm', 'test'], 'exit': 1}]), [],
                         'a check already failing on the original says nothing about the change')
        self.assertEqual(regressions(before, [{'argv': ['npm', 'run', 'lint'], 'exit': 1}, {'argv': ['npm', 'test'], 'exit': 0}]),
                         ['npm run lint'])


    def test_a_suite_already_failing_gates_on_its_tests_by_name(self):
        from eaos.execute import failing, regressions
        tap = 'ok 1 - keeps\nnot ok 2 - needs a database\nnot ok 3 - flaky # TODO\n'
        self.assertEqual(failing(tap), ['flaky', 'needs a database'])
        before = [{'argv': ['npm', 'test'], 'exit': 1, 'failing': ['needs a database']}]
        same = [{'argv': ['npm', 'test'], 'exit': 1, 'failing': ['needs a database']}]
        worse = [{'argv': ['npm', 'test'], 'exit': 1, 'failing': ['keeps', 'needs a database']}]
        self.assertEqual(regressions(before, same), [])
        self.assertEqual(regressions(before, worse), ['npm test (1 new failing: keeps)'])

class CandidateTests(Workspace):
    def test_the_candidate_is_a_branch_on_the_authorised_commit_and_its_change_a_descendant(self):
        import subprocess
        from eaos.execute import candidate, git
        repo, runtime = Path(self.tmp) / 'repo', Path(self.tmp) / 'runtime'
        repo.mkdir(); runtime.mkdir()
        (repo / 'a.ts').write_text('export const a = 1;\n')
        for args in (('init', '--quiet'), ('add', '-A'), ('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '--quiet', '-m', 'one')):
            git(repo, *args)
        granted = git(repo, 'rev-parse', 'HEAD').stdout.strip()
        (runtime / 'authorization.json').write_text(json.dumps({'commit': granted}))
        where = candidate(repo, runtime, 'TASK-7')
        self.assertEqual(git(where, 'rev-parse', 'HEAD').stdout.strip(), granted)
        self.assertEqual(git(where, 'branch', '--show-current').stdout.strip(), 'eaos/task-7')
        (where / 'a.ts').write_text('export const a = 2;\n')
        git(where, 'add', '-A'); git(where, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '--quiet', '-m', 'change')
        self.assertEqual(git(where, 'merge-base', '--is-ancestor', granted, 'HEAD').returncode, 0)
        self.assertEqual((repo / 'a.ts').read_text(), 'export const a = 1;\n', 'the original is never written')


class VerifyLockTests(Workspace):
    def test_verifying_never_updates_a_snapshot(self):
        from unittest import mock
        from eaos import behavior_lock
        runtime = Path(self.tmp)
        (runtime / 'behavior-lock/snapshots').mkdir(parents=True)
        with mock.patch('eaos.live_run.LiveRun'), mock.patch.object(behavior_lock, '_prepare'), \
                mock.patch.object(behavior_lock, '_start'), mock.patch.object(behavior_lock, '_pass') as passed, \
                mock.patch.object(behavior_lock, 'spec_statuses'), mock.patch.object(behavior_lock, '_results', return_value=[]), \
                mock.patch.object(behavior_lock, '_write'):
            behavior_lock.verify_lock(self.tmp, self.tmp, runtime)
        self.assertIs(passed.call_args.kwargs['update'], False)


class AdapterIsolationTests(Workspace):
    def test_the_model_runs_with_every_tool_off_no_session_and_the_cli_s_own_sign_in(self):
        from unittest import mock
        from eaos.runtime import claude_adapter
        done = mock.Mock(returncode=0, stdout=json.dumps({'result': '{"action": "final"}', 'total_cost_usd': 0.01}))
        with mock.patch.object(claude_adapter.subprocess, 'run', return_value=done) as run:
            self.assertEqual(claude_adapter.call([{'role': 'user', 'content': 'hi'}]), {'action': 'final'})
        argv, kwargs = run.call_args.args[0], run.call_args.kwargs
        self.assertEqual(argv[argv.index('--tools') + 1], '')
        self.assertIn('--no-session-persistence', argv)
        self.assertNotIn('env', kwargs, 'no key is put in the environment: the CLI uses the sign-in it has')
        self.assertFalse(any('key' in a.lower() for a in argv if a.startswith('--')))


class EndpointGuardTests(Workspace):
    def test_a_fix_that_deletes_an_endpoint_is_breakage_even_when_it_compiles(self):
        from eaos.execute import new_breakage
        from eaos.facts.run import collect
        repo, report = Path(self.tmp) / 'repo', Path(self.tmp) / 'report'
        (repo / 'server').mkdir(parents=True)
        (repo / 'package.json').write_text('{"name": "x"}')
        (repo / 'server/admin.ts').write_text('export const admin = 1;\n')
        (repo / 'server/index.ts').write_text("import { admin } from './admin';\nconst app = new Hono();\n"
                                              "app.get('/api/me', me);\napp.route('/api/admin/secrets', admin);\n")
        collect(repo, report, ['syntax', 'resolve', 'broken', 'entrypoints'])
        self.assertEqual(new_breakage(report, repo), [])
        (repo / 'server/index.ts').write_text("const app = new Hono();\napp.get('/api/me', me);\n")
        self.assertEqual(new_breakage(report, repo), ['the endpoint MOUNT /api/admin/secrets is gone'])
