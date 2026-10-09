"""The real command-centre trial harness (tools/studio_trial.py and studio/scripts/trial.mjs): what it picks, how it
judges, the guards it probes against a real server, and that both halves agree on what each phase reports. The trial
itself drives a real assistant and is run by hand (NS46.T11, NS46.T17); these tests never count as its evidence."""
import importlib.util
import json
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))


def load():
    spec = importlib.util.spec_from_file_location('studio_trial', ROOT / 'tools/studio_trial.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


trial = load()
DRIVER = (ROOT / 'studio/scripts/trial.mjs').read_text(encoding='utf-8')
SOURCE = (ROOT / 'tools/studio_trial.py').read_text(encoding='utf-8')


def decision(id_, options=('a', 'b'), recommendation='', recommended_option=None, labels=None):
    labels = labels or {o: o.upper() for o in options}
    return {'id': id_, 'scope': f'scope-{id_}', 'response': None,
            'question': {'id': id_, 'state': 'waiting', 'recommendation': recommendation, 'recommended_option': recommended_option,
                         'options': [{'id': o, 'label': labels[o]} for o in options]}}


class Picking(unittest.TestCase):
    def test_the_recommended_option_is_the_explicit_id_else_one_unambiguous_label(self):
        self.assertEqual(trial.recommended_option(decision('d', recommended_option='b')['question'])['id'], 'b')
        self.assertEqual(trial.recommended_option(decision('d', recommendation='A: because it is safer')['question'])['id'], 'a')
        self.assertIsNone(trial.recommended_option(decision('d', recommendation='Ask later')['question']))
        both = decision('d', recommendation='Keep it', labels={'a': 'Keep', 'b': 'Keep it'})['question']
        self.assertIsNone(trial.recommended_option(both), 'both labels open the recommendation: no guess, as the Studio')
        same = decision('d', recommendation='Keep: yes', labels={'a': 'Keep', 'b': 'Keep'})['question']
        self.assertIsNone(trial.recommended_option(same), 'two options with the same label: no guess')

    def test_each_live_case_gets_its_own_waiting_question(self):
        rows = [decision('one'), decision('two', recommendation='B is right'), decision('three'), decision('four'),
                decision('five'), decision('single', options=('a',)), {**decision('done'), 'response': {'option': 'a'}}]
        picked = trial.pick_decisions(rows)
        self.assertEqual(picked['recommended']['id'], 'two')
        self.assertEqual([picked[k]['id'] for k in ('custom', 'keyboard', 'draft', 'concurrent')], ['one', 'three', 'four', 'five'])
        self.assertEqual(len({row['id'] for row in picked.values()}), 5)
        self.assertNotIn('concurrent', trial.pick_decisions(rows[:3]))

    def test_the_group_is_the_smallest_whole_group_of_fixable_cards(self):
        cards = [{'id': 'T1', 'category': 'security', 'severity': 'high', 'milestone': 'M1', 'fixable': True},
                 {'id': 'T2', 'category': 'security', 'severity': 'high', 'milestone': 'M1', 'fixable': True},
                 {'id': 'T3', 'category': 'security', 'severity': 'low', 'milestone': 'M2', 'fixable': True},
                 {'id': 'T4', 'category': 'docs', 'severity': 'low', 'milestone': 'M2', 'fixable': False},
                 {'id': 'T5', 'category': 'docs', 'severity': 'medium', 'milestone': 'M3', 'fixable': True, 'needs_decision': True}]
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'cards.json').write_text(json.dumps({'cards': cards}), encoding='utf-8')
            group = trial.choose_group(folder)
            self.assertIn(group['kind'], ('group', 'step'))
            self.assertEqual(group['cards'], ['T1', 'T2'], 'two fixable cards, whole; never the one that needs a decision')
            (Path(folder) / 'cards.json').write_text(json.dumps({'cards': [dict(c, milestone=None, category=c['id'], severity=None) for c in cards]}), encoding='utf-8')
            group = trial.choose_group(folder)
            self.assertEqual(group['kind'], 'cards')
            self.assertEqual(group['cards'], ['T1', 'T2'])

    def test_project_code_runs_only_for_eaos_or_an_authorized_live_corpus_project(self):
        record = {'live_corpus': [{'name': 'chief-ops', 'authorization': 'the owner said so', 'commit': 'abc'}, {'name': 'other'}]}
        self.assertTrue(trial.authorization('EAOS', record)['run_code'])
        self.assertTrue(trial.authorization('chief-ops', record)['run_code'])
        self.assertFalse(trial.authorization('other', record)['run_code'])
        self.assertFalse(trial.authorization('FleetManageWeb', record)['run_code'])
        self.assertIn('live_corpus', trial.authorization('FleetManageWeb', record)['why'])


class Judging(unittest.TestCase):
    def test_a_state_is_understood_only_in_the_contracts_words_for_the_language(self):
        words = trial.state_words()
        seen = {'running': words['running']['ar'], 'done': words['done']['en'], 'failed': ''}
        self.assertEqual(trial.understood(seen, 'ar'), {'running': True, 'done': False, 'failed': False})

    def test_steps_per_task_counts_only_the_tasks_done(self):
        self.assertEqual(trial.steps_per_task({'scan': 3, 'fix': 5, 'answers': 3, 'accept': 2}), 3.25)
        self.assertEqual(trial.steps_per_task({'scan': 4, 'fix': 0}), 4.0)
        self.assertIsNone(trial.steps_per_task({}))

    def test_a_case_is_always_live_and_says_whether_it_passed(self):
        row = trial.case('auth_origin_csrf', 1, {'x': 1})
        self.assertEqual((row['pass'], row['kind']), (True, 'live'))

    def test_the_record_it_writes_is_the_one_f15_and_the_acceptance_judge(self):
        import north_star_studio as judge
        record = {'assistant': 'Claude Code', 'audited': True, 'selection': {'kind': 'step', 'cards': ['T1', 'T2']}, 'cards_fixed': ['T1'],
                  'questions_answered_in_inbox': 2, 'accepted': True, 'typed_to_assistant': 0, 'understood': {'running': True}}
        self.assertEqual(judge.trial_passed(record), (True, ''))
        for key in record:
            self.assertIn(f"'{key}'", SOURCE, f'{key} is never written by tools/studio_trial.py')
        for case in judge.OWNER_CONTROL_CASES:
            self.assertIn(f"'{case}'", SOURCE, f'the owner-control case {case} is never judged')


class BothHalves(unittest.TestCase):
    """What tools/studio_trial.py reads from a phase's result is what studio/scripts/trial.mjs writes."""

    def test_every_phase_key_read_is_written_by_the_browser(self):
        read = set()
        for name in ('scan', 'decided', 'persisted', 'fixed', 'controls', 'rec', 'keyboard', 'draft', 'retry', 'queue', 'custom', 'consent',
                     'guards', 'undo', 'lang_rows'):
            read |= set(re.findall(rf"\b{name}\.get\('([a-z_]+)'\)", SOURCE))
        python_only = {'errors', 'exit', 'seconds'}
        server_side = {'exact', 'consent', 'accept_without_confirm', 'accept_forged_confirm', 'undo_without_confirm', 'accept_with_undo_token',
                       'outcome', 'reused_token_status'}
        for key in sorted(read - python_only - server_side):
            self.assertRegex(DRIVER, rf'\b{key}\b', f'{key} is read by the Python half but never written by trial.mjs')
        for key in sorted(server_side):
            self.assertRegex(SOURCE, rf"'{key}'", f'{key} is not answered by `check`')

    def test_every_phase_and_check_the_driver_uses_exists(self):
        phases = set(re.findall(r"browser\('([a-z]+)'", SOURCE))
        self.assertEqual(phases, {'scan', 'decisions', 'persist', 'fix', 'controls'})
        for phase in phases: self.assertRegex(DRIVER, rf'\b{phase}\b')
        for what in set(re.findall(r"check\('([a-z-]+)'", DRIVER)):
            self.assertIn(f"what == '{what}'", SOURCE)

    def test_the_hooks_the_driver_clicks_are_in_the_studio_source(self):
        source = '\n'.join(p.read_text(encoding='utf-8') for p in (ROOT / 'studio/src').rglob('*.tsx'))
        for hook in ('data-start-action', 'data-confirm', 'data-write-answer', 'data-send-answer', 'data-option', 'data-recommended',
                     'data-decide', 'data-control', 'data-run-state', 'data-verb', 'data-saved'):
            self.assertIn(hook, source)
        for hook in ('select-group', 'group-kind:', 'group:', 'queue-up:', 'decision-status', 'decision:', 'question:'):
            self.assertIn(hook, source)

    def test_the_typed_answers_say_yes_in_words_and_keep_their_spaces(self):
        self.assertIn('yes', trial.RUN_ANSWER)
        self.assertNotEqual(trial.RUN_ANSWER, trial.RUN_ANSWER.strip())
        self.assertIn('\n', trial.DECISION_ANSWER)
        self.assertTrue(all(len(a) <= 4000 for a in (trial.RUN_ANSWER, trial.DECISION_ANSWER, trial.KEYBOARD_ANSWER, trial.DRAFT_ANSWER)))


class AgainstARealServer(unittest.TestCase):
    """The API probes against the real server app (eaos/api/server.py), read-only, on 127.0.0.1."""

    def test_the_auth_origin_and_csrf_probes_get_the_refusals_they_expect(self):
        try:
            from eaos.api.server import bind, create_app, serve
        except ImportError as missing:
            self.skipTest(f'the Studio server needs {missing}')
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'studio').mkdir()
            app = create_app(Path(folder), name='trial-test', watch=False)
            sock = bind(0)
            app.state.ctx.keys.port = sock.getsockname()[1]
            servers = []
            threading.Thread(target=serve, args=(app, sock, servers.append), daemon=True).start()
            info = {'port': app.state.ctx.keys.port, 'token': app.state.ctx.keys.token}
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline and trial.http(info['port'], 'GET', '/api/session', {'X-EAOS-Token': info['token']})[0] != 200:
                    time.sleep(0.1)
                row = trial.auth_case(trial.Api(info), info['port'])
                self.assertTrue(row['pass'], row['evidence'])
            finally:
                if servers: servers[0].should_exit = True

    def test_a_runs_events_are_read_from_its_store_not_the_live_stream(self):
        with tempfile.TemporaryDirectory() as folder:
            runs = Path(folder) / 'runs' / 'r1'
            runs.mkdir(parents=True)
            (runs / 'events.jsonl').write_text('{"seq": 1, "kind": "action"}\nnot json\n{"seq": 2, "kind": "answer"}\n', encoding='utf-8')
            original = trial._runs_folder
            trial._runs_folder = lambda home, project: Path(folder) / 'runs'
            try:
                self.assertEqual([e['kind'] for e in trial._events(None, None, 'r1')], ['action', 'answer'])
                self.assertEqual(trial._events(None, None, 'missing'), [])
            finally:
                trial._runs_folder = original


if __name__ == '__main__':
    unittest.main()
