"""Backend coverage of the live map (live scan map v2, phase 2): every long piece of work says where it is.

- the slow loops of the check count into the running stage (codemod trials, debt items, canonical homes,
  simulations, indicators, claim steps, artifacts, bundles, emitters), so a long stage never glows empty (G2);
- the programs a stage starts are sampled during every stage of every flow (G3);
- the steps after the check are flows with declared stages (setup, safety, fix), each stage ended exactly once
  whatever happens (I1), the screens reported one by one by EAOS's Playwright stream reporter (G1, G13), and the
  journey is guided.STEPS as data;
- every skipped stage and every refusal carries a stable reason_code whose words, Arabic and English, are in
  eaos/data/errors.json (G5);
- a stage added in a test appears in the folded state with no other change (I3, API half);
- time left is a range from the last run only, and the last five runs of each flow are kept (G10, G11);
- progress can be switched off, and then writes and hears nothing (the switch tools/progress_determinism.py uses).
"""
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tests'))

import jsonschema  # noqa: E402

from eaos import behavior_lock, guided, live_setup, progress, waves  # noqa: E402
from eaos.api.read import scan_state  # noqa: E402
from eaos.pipeline import STAGES, SkipStage, execute  # noqa: E402
from eaos.pipeline import run as pipeline_run  # noqa: E402
from eaos.pipeline.stages import Stage as CheckStage  # noqa: E402
from eaos.progress import flow as flows, log as writer  # noqa: E402
from eaos.progress.estimate import estimate  # noqa: E402
from eaos.progress.history import path_of, runs  # noqa: E402
from test_live_scan_map import project, stepping_runners  # noqa: E402
from test_pipeline_run import fake_runners  # noqa: E402

SCHEMA = json.loads((ROOT / 'eaos/data/schemas/progress.json').read_text(encoding='utf-8'))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
REASONS = json.loads((ROOT / 'eaos/data/errors.json').read_text(encoding='utf-8'))['reasons']
FLOWS = {'setup': live_setup.FLOW, 'safety': behavior_lock.FLOW, 'fix': waves.FLOW}


def invalid(rows):
    return [(row.get('seq'), row.get('event'), error.message) for row in rows for error in VALIDATOR.iter_errors(row)]


def ends(rows):
    return [r['stage'] for r in rows if r['event'] == 'stage.ended']


class Recorder:
    """A stepper that keeps every call, standing in for a running stage."""

    def __init__(self): self.calls = []

    def __call__(self, name, done, total, status='running', seconds=None, reason='', reason_code='', kind='', artifact=''):
        self.calls.append({'name': name, 'done': done, 'total': total, 'status': status, 'kind': kind,
                           'reason_code': reason_code, 'artifact': artifact})

    def of(self, name): return [c for c in self.calls if c['name'] == name]


class Clock:
    def __init__(self): self.at = 1000.0
    def __call__(self): return self.at
    def move(self, seconds): self.at += seconds


def small_project():
    """A real git project with a repeated definition: enough for every stage of the real check to run."""
    root = Path(tempfile.mkdtemp(prefix='coverage-src-'))
    body = 'RATE = 3\n\n\ndef total(items):\n    out = 0\n    for item in items:\n        out += item * RATE\n    return out\n'
    (root / 'src').mkdir()
    (root / 'src/a.py').write_text(body + '\n\ndef unused():\n    return total([1, 2])\n', encoding='utf-8')
    (root / 'src/b.py').write_text(body, encoding='utf-8')
    for argv in (['init', '-q'], ['add', '-A'], ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'first']):
        subprocess.run(['git', '-C', str(root), *argv], check=True, capture_output=True)
    return root


def assert_counted_ends_at_total(test, steps):
    for step in steps:
        test.assertLessEqual(step['done'], step['total'], step)
        if step['status'] == 'ok': test.assertEqual(step['done'], step['total'], step)


class MarkPoints(unittest.TestCase):
    """G2: the loops section 2 of the plan profiled count into the running stage."""

    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp(prefix='coverage-out-'))
        cls.manifest = execute(small_project(), cls.out, language='en')
        cls.state = progress.fold(progress.read(cls.out))

    def counted(self, stage):
        return {s['name']: s for s in next(x for x in self.state['stages'] if x['name'] == stage)['steps'] if s['kind'] == 'count'}

    def test_a_real_check_shows_counted_steps_in_each_long_stage(self):
        expected = {'claims': {'claim steps', 'debt items'}, 'sustainability': {'indicators'},
                    'transform': {'indicators', 'canonical homes', 'simulations'}, 'plan': {'debt items'},
                    'executive': {'canonical homes'}, 'compose': {'artifacts'}, 'bundles': {'artifacts', 'bundles'},
                    'emit': {'emitters', 'files judged'}}
        self.assertEqual(self.manifest['status'], 'COMPLETE')
        for stage, names in expected.items():
            self.assertLessEqual(names, set(self.counted(stage)), stage)
            for step in self.counted(stage).values():
                self.assertEqual((step['status'], step['done']), ('ok', step['total']), (stage, step))

    def test_every_counted_step_that_ran_has_its_seconds_for_the_next_estimate(self):
        steps = [s for stage in self.state['stages'] for s in stage['steps'] if s['kind'] == 'count' and s['total']]
        self.assertTrue(steps)
        self.assertTrue(all(isinstance(s['seconds'], (int, float)) for s in steps), steps)

    def test_codemod_trials_count_one_card_at_a_time(self):
        from eaos import codemods
        tasks = [{'id': f'T{n}', 'pattern': 'remove_dead'} for n in range(7)] + [{'id': 'X', 'pattern': 'other'}]
        record = Recorder()
        with mock.patch.object(codemods, 'card_for', return_value={'kind': 'jscodeshift'}), \
                mock.patch.object(codemods, 'dry_run', return_value=({'ok': True}, ['cmd'])), \
                mock.patch('eaos.verify.isolated_copy', return_value=Path('/nowhere')), progress.using(record):
            self.assertEqual(codemods.attach(tasks, tempfile.mkdtemp(), tempfile.mkdtemp()), 7)
        trials = record.of('codemod trials')
        self.assertEqual([c['done'] for c in trials], list(range(8)))
        self.assertEqual((trials[-1]['status'], trials[-1]['total'], trials[-1]['kind']), ('ok', 7, 'count'))

    def test_canonical_homes_simulations_and_debt_items_count_their_loops(self):
        from eaos import debt_register, guarantee, transform_plan
        moves = [{'move': 'canonicalize', 'rule': f'r{n}', 'occurrences': [], 'falsifier': '', 'predicted': {},
                  'indicator': 'single_source'} for n in range(40)]
        sets = {'fingerprint': {'facts': [{'kind': 'duplicate_cluster', 'value': {'shape_sha': f'r{n}'}} for n in range(40)]}}
        record = Recorder()
        with mock.patch.object(transform_plan, '_gather', return_value=sets), \
                mock.patch.object(transform_plan, 'compute', return_value={}), \
                mock.patch.object(transform_plan, '_transformations', return_value=moves), \
                mock.patch.object(transform_plan, '_canonical_home_for', return_value={'candidates': []}), \
                mock.patch.object(transform_plan, '_stage_acceptance', return_value={}), progress.using(record):
            plan = transform_plan.build(tempfile.mkdtemp())
        homes = record.of('canonical homes')
        self.assertEqual((len(plan['stages']), homes[0]['done'], homes[-1]['done'], homes[-1]['status']), (40, 0, 40, 'ok'))
        record = Recorder()
        with mock.patch('eaos.simulator.simulate', return_value={}), mock.patch.object(guarantee, 'snapshot', return_value={}), \
                progress.using(record):
            guarantee.record_predictions(tempfile.mkdtemp(), {'stages': [{'stage': n} for n in range(25)]})
        self.assertEqual([(c['done'], c['total']) for c in record.of('simulations')][-1], (20, 20), 'the budget is the total')
        record = Recorder()
        claims = [{'id': f'C{n}', 'fact_ids': []} for n in range(30)]
        with mock.patch.object(debt_register, '_item', side_effect=lambda claim, *a: {'title': claim['id'], 'severity': 'low',
                                                                                     'witnesses': [], 'files': []}), \
                progress.using(record):
            debt_register.build(tempfile.mkdtemp(), {'claims': claims})
        items = record.of('debt items')
        self.assertEqual((items[0]['done'], items[-1]['done'], items[-1]['total'], items[-1]['status']), (0, 30, 30, 'ok'))
        assert_counted_ends_at_total(self, record.calls)

    def test_marking_where_a_loop_is_changes_nothing_outside_a_run(self):
        from eaos import sustainability
        with mock.patch.object(sustainability, '_read_sets', return_value={}):
            try: sustainability.compute(tempfile.mkdtemp())
            except Exception: pass                      # the indicators need facts; the count itself must be silent
        self.assertIsNone(progress.current())


class Sampling(unittest.TestCase):
    """G3: the running programs are looked at during every stage, of the check and of every flow."""

    def stub(self):
        seen = []
        sampler = type('Stub', (), {'reason': '', 'sample': lambda me: seen.append(1) or
                                    [{'name': f'tool-{len(seen)}', 'pid': 100 + len(seen), 'since': '2026-10-09T20:00:00+00:00'}]})()
        return sampler, seen

    def test_a_check_writer_and_a_flow_writer_sample_by_default(self):
        self.assertIsNotNone(progress.ProgressLog(tempfile.mkdtemp()).sampler)
        flow = progress.Flow(tempfile.mkdtemp(), 'setup', live_setup.FLOW, pulse=False)
        self.assertIsNotNone(flow.log.sampler)

    def test_every_stage_of_every_flow_is_sampled_while_it_runs(self):
        for name, declared in FLOWS.items():
            clock, (sampler, _) = Clock(), self.stub()
            folder = Path(tempfile.mkdtemp())
            with progress.Flow(folder, name, declared, clock=clock, pulse=False, sampler=sampler) as flow:
                for stage in declared:
                    flow.begin(stage.name)
                    clock.move(writer.SAMPLE_EVERY)
                    flow.log.tick()
            rows = progress.read(folder, name)
            sampled = [r['stage'] for r in rows if r['event'] == 'stage.activity']
            self.assertEqual(sampled, [s.name for s in declared], name)
            self.assertEqual(invalid(rows), [])

    def test_every_stage_of_the_check_is_sampled_while_it_runs(self):
        clock, (sampler, _) = Clock(), self.stub()
        out = Path(tempfile.mkdtemp())
        log = progress.ProgressLog(out, clock=clock, pulse=False, sampler=sampler)
        log.started(STAGES, [s.name for s in STAGES], {})
        for stage in STAGES:
            log.stage_started(stage.name)
            clock.move(writer.SAMPLE_EVERY)
            log.tick()
            log.ended({'stage': stage.name, 'status': 'ok', 'reason': '', 'seconds': 2.0, 'necessity': stage.necessity, 'artifacts': []})
        log.finish('COMPLETE')
        self.assertEqual([r['stage'] for r in progress.read(out) if r['event'] == 'stage.activity'], [s.name for s in STAGES])


class FlowDeclarations(unittest.TestCase):
    """G13 and I1 for every flow: declared as data, every declared stage ended exactly once."""

    def test_each_flow_is_declared_soundly_and_the_journey_names_a_flow_for_each_step(self):
        for name, declared in FLOWS.items():
            self.assertEqual(flows.errors(declared), [], name)
            self.assertTrue(all(isinstance(s, flows.Stage) for s in declared))
        self.assertEqual([step[0] for step in guided.STEPS], list(guided.FLOWS))
        self.assertEqual(set(guided.FLOWS.values()), {'check', *FLOWS})

    def run_flow(self, body, name='setup', declared=None):
        folder = Path(tempfile.mkdtemp())
        raised = None
        try:
            with progress.Flow(folder, name, declared or FLOWS[name]) as flow: body(flow)
        except BaseException as problem:
            raised = problem
        rows = progress.read(folder, name)
        self.assertEqual(sorted(ends(rows)), sorted(s.name for s in (declared or FLOWS[name])))
        self.assertEqual(rows[-1]['event'], 'run.ended')
        self.assertEqual(invalid(rows), [])
        return rows, raised, folder

    def test_a_whole_flow_a_flow_that_stops_early_one_that_breaks_and_one_that_is_stopped(self):
        rows, _, _ = self.run_flow(lambda f: [f.begin(s.name) for s in live_setup.FLOW])
        self.assertEqual((rows[-1]['status'], {r['status'] for r in rows if r['event'] == 'stage.ended'}), ('COMPLETE', {'ok'}))
        rows, _, _ = self.run_flow(lambda f: f.begin('detect'))
        ended = {r['stage']: r for r in rows if r['event'] == 'stage.ended'}
        self.assertEqual((ended['detect']['status'], ended['attempt']['status'], ended['attempt']['reason_code'], rows[-1]['status']),
                         ('ok', 'not_reached', 'run_ended', 'INCOMPLETE'))

        def breaks(flow):
            flow.begin('detect'); flow.begin('attempt')
            raise RuntimeError('boom')
        rows, raised, _ = self.run_flow(breaks)
        ended = {r['stage']: r for r in rows if r['event'] == 'stage.ended'}
        self.assertIsInstance(raised, RuntimeError)
        self.assertEqual((ended['attempt']['status'], ended['baseline']['status'], rows[-1]['status']), ('failed', 'not_reached', 'ERROR'))

        def stopped(flow):
            flow.begin('detect')
            raise KeyboardInterrupt()
        rows, raised, _ = self.run_flow(stopped)
        self.assertIsInstance(raised, KeyboardInterrupt)
        self.assertEqual(rows[-1]['status'], 'STOPPED')

    def test_marks_are_ignored_outside_a_flow_and_for_a_stage_the_flow_does_not_declare(self):
        progress.begin('detect'); progress.end('detect'); progress.skip('detect', 'x', 'no_build')
        with progress.stage('detect'): pass
        rows, _, _ = self.run_flow(lambda f: (progress.begin('verify'), progress.begin('detect'), progress.end('detect'),
                                              progress.end('detect', 'failed')))
        self.assertEqual({r['stage']: r['status'] for r in rows if r['event'] == 'stage.ended'}['detect'], 'ok')

    def test_setup_writes_its_flow_when_there_is_no_app_to_start(self):
        runtime = Path(tempfile.mkdtemp())
        result = live_setup.setup(Path(tempfile.mkdtemp()), runtime, say=lambda n: None)
        self.assertFalse(result['ok'])
        rows = progress.read(runtime, 'setup')
        ended = {r['stage']: (r['status'], r.get('reason_code')) for r in rows if r['event'] == 'stage.ended'}
        self.assertEqual(ended, {'detect': ('unavailable', 'no_app_profile'), 'attempt': ('skipped', 'no_app_profile'),
                                 'baseline': ('skipped', 'no_app_profile')})
        self.assertEqual((rows[-1]['status'], invalid(rows)), ('INCOMPLETE', []))

    def test_setup_reports_each_attempt_and_the_baseline(self):
        from test_live_setup import VITE_APP, project as app
        runtime = Path(tempfile.mkdtemp())
        outcomes = iter([{'ok': False, 'failure': 'GET / answered 500', 'fixtures': {}}, {'ok': True, 'page': {}, 'fixtures': {}}])
        assistant = mock.Mock()
        assistant.complete.return_value = ({'result': {'reason': 'set the env'}}, {})
        with mock.patch.object(live_setup, 'verify', side_effect=lambda *a, **k: next(outcomes)), \
                mock.patch.object(live_setup, 'assist_messages', return_value=[]), \
                mock.patch.object(live_setup, 'apply'), \
                mock.patch.object(live_setup, 'setup_baseline', return_value={'ok': True}):
            self.assertTrue(live_setup.setup(app(VITE_APP), runtime, provider=assistant, say=lambda n: None)['ok'])
        state = progress.fold(progress.read(runtime, 'setup'))
        stages = {s['name']: s for s in state['stages']}
        self.assertEqual([(s['name'], s['status'], s['reason_code']) for s in stages['attempt']['steps']],
                         [('attempt 1', 'failed', 'app_not_answering'), ('attempt 2', 'ok', '')])
        self.assertEqual([stages[n]['state'] for n in ('detect', 'attempt', 'baseline')], ['ok', 'ok', 'ok'])
        self.assertEqual(state['status'], 'COMPLETE')

    def test_setup_stopped_mid_attempt_ends_every_stage(self):
        from test_live_setup import VITE_APP, project as app
        runtime = Path(tempfile.mkdtemp())
        with mock.patch.object(live_setup, 'verify', side_effect=KeyboardInterrupt()), self.assertRaises(KeyboardInterrupt):
            live_setup.setup(app(VITE_APP), runtime, say=lambda n: None)
        rows = progress.read(runtime, 'setup')
        self.assertEqual(sorted(ends(rows)), ['attempt', 'baseline', 'detect'])
        self.assertEqual(rows[-1]['status'], 'STOPPED')

    def fix_batch(self, gates_say=''):
        from test_waves import git, repository
        project, runtime, report = repository(), Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        cards = [{'id': f'T{n}', 'title': f't{n}', 'kind': 'remediate', 'decision': {'readiness': 'ready'}, 'paths': [f'{n}.txt'],
                  'verify_command': ['true']} for n in (1, 2, 3)]
        (report / 'plan.json').write_text(json.dumps({'tasks': cards}))
        (runtime / 'authorization.json').write_text(json.dumps({'commit': git(project, 'rev-parse', 'HEAD')}))

        def change(card, root, report, provider):
            (Path(root) / card['paths'][0]).write_text(card['id'])
            return 'model', ''
        verdicts = iter([gates_say, '', ''])
        with mock.patch('eaos.sandbox.refusal', return_value=''), mock.patch.object(waves, 'change', side_effect=change), \
                mock.patch.object(waves, 'new_breakage', side_effect=lambda report, root: ['boom'] if (Path(root) / '2.txt').exists() else []), \
                mock.patch.object(waves, 'batch_acceptance', side_effect=lambda report, cards, root: {c['id']: 0 for c in cards}), \
                mock.patch.object(waves, 'original_checks', return_value=[]), \
                mock.patch.object(waves, 'gates', side_effect=lambda *a, **k: next(verdicts, '')), \
                progress.Flow(runtime, 'fix', waves.FLOW):
            waves.run_batch(report, project, runtime, 1, ['T1', 'T2', 'T3'])
        rows = progress.read(runtime, 'fix')
        self.assertEqual(sorted(ends(rows)), sorted(s.name for s in waves.FLOW))
        self.assertEqual(invalid(rows), [])
        return {s['name']: s for s in progress.fold(rows)['stages']}

    def test_fix_reports_card_by_card_and_skips_the_halving_when_the_gates_pass(self):
        stages = self.fix_batch()
        self.assertEqual([(s['name'], s['status'], s['reason_code']) for s in stages['change']['steps']],
                         [('T1', 'ok', ''), ('T2', 'failed', 'card_broke_something'), ('T3', 'ok', '')])
        self.assertEqual([s['name'] for s in stages['acceptance']['steps']], ['T1', 'T3'])
        self.assertEqual((stages['culprit']['state'], stages['culprit']['reason_code']), ('skipped', 'gates_passed'))
        self.assertEqual({stages[n]['state'] for n in ('open', 'change', 'acceptance', 'gates', 'handover')}, {'ok'})

    def test_fix_runs_the_halving_when_the_gates_fail(self):
        stages = self.fix_batch(gates_say='a screen changed')
        self.assertEqual(stages['gates']['steps'][0]['reason_code'], 'gates_failed')
        self.assertEqual(stages['culprit']['state'], 'ok')

    def test_safety_marks_the_screens_and_skips_the_speed_without_a_build(self):
        runtime = Path(tempfile.mkdtemp())
        (runtime / 'run.json').write_text(json.dumps({'baseline': {}}))

        def lock(report, target, runtime):
            for name in ('prepare', 'start', 'record', 'verify'): progress.begin(name)
            progress.end('verify')
            return {'results': [{'path': 'a.spec.ts', 'status': 'passed'}]}
        state = {'setup': {'commit': 'c'}}
        with mock.patch.object(guided, 'runtime_of', return_value=runtime), mock.patch.object(guided, 'report_of', return_value=runtime), \
                mock.patch.object(guided, 'source', return_value=runtime), mock.patch.object(guided, 'save'), \
                mock.patch('eaos.behavior_lock.run_lock', side_effect=lock):
            outcome = guided.safety_run(state)
        self.assertEqual((outcome['speed'], outcome['passed']), ('no_build', 1))
        ended = {r['stage']: (r['status'], r.get('reason_code')) for r in progress.read(runtime, 'safety') if r['event'] == 'stage.ended'}
        self.assertEqual(ended['speed'], ('skipped', 'no_build'))
        self.assertEqual({ended[n][0] for n in ('prepare', 'start', 'record', 'verify')}, {'ok'})


class Screens(unittest.TestCase):
    """Section 3.6: one step per spec file as the stream reporter writes it, with its shot."""

    def lines(self, path, rows):
        with path.open('a', encoding='utf-8') as handle:
            for row in rows: handle.write(json.dumps(row) + '\n')

    def test_each_spec_file_is_one_step_with_its_verdict_and_shot(self):
        folder = Path(tempfile.mkdtemp())
        shots, kept = folder / 'lock/__screenshots__', folder / 'runtime/behavior-lock/snapshots'
        (shots / 'home.spec.ts').mkdir(parents=True)
        (shots / 'home.spec.ts/home.png').write_bytes(b'png')
        stream = folder / 'stream.jsonl'
        self.lines(stream, [{'event': 'plan', 'files': {'playwright/home.spec.ts': 2, 'playwright/broken.spec.ts': 1, 'playwright/skip.spec.ts': 1}},
                            {'event': 'test.begin', 'file': 'playwright/home.spec.ts', 'title': 'a'},
                            {'event': 'test.end', 'file': 'playwright/home.spec.ts', 'title': 'a', 'status': 'passed', 'duration': 500, 'shots': []}])
        record = Recorder()
        with progress.using(record):
            screens = behavior_lock.Screens(stream, shots, kept, keep=True)
            screens.read()
            self.assertEqual([(c['name'], c['status']) for c in record.calls][-1], ('playwright/home.spec.ts', 'running'))
            self.lines(stream, [{'event': 'test.end', 'file': 'playwright/home.spec.ts', 'title': 'b', 'status': 'passed', 'duration': 700,
                                 'shots': ['home.spec.ts/home.png']},
                                {'event': 'test.begin', 'file': 'playwright/broken.spec.ts', 'title': 'c'},
                                {'event': 'test.end', 'file': 'playwright/broken.spec.ts', 'title': 'c', 'status': 'timedOut', 'error': 'slow'},
                                {'event': 'test.end', 'file': 'playwright/skip.spec.ts', 'title': 'd', 'status': 'skipped'}])
            screens.read()
        done = [c for c in record.calls if c['status'] != 'running' and c['status'] != 'waiting']
        self.assertEqual([(c['name'], c['done'], c['total'], c['status'], c['reason_code'], c['artifact']) for c in done],
                         [('playwright/home.spec.ts', 1, 3, 'ok', '', 'behavior-lock/snapshots/home.spec.ts/home.png'),
                          ('playwright/broken.spec.ts', 2, 3, 'failed', 'screen_failed', ''),
                          ('playwright/skip.spec.ts', 3, 3, 'skipped', 'screen_needs_fixture', '')])
        self.assertEqual((kept / 'home.spec.ts/home.png').read_bytes(), b'png', 'the shot is kept as soon as it is taken')

    def test_following_never_raises_and_does_nothing_outside_a_flow(self):
        folder = Path(tempfile.mkdtemp())
        screens = behavior_lock.Screens(folder / 'missing.jsonl', folder, folder / 'kept').start()
        self.assertIsNone(screens.thread, 'outside a flow nobody follows the screens')
        screens.read()
        screens.handle({'event': 'test.end', 'file': 'unknown.spec.ts'})
        screens.stop()
        (folder / 'bad.jsonl').write_text('not json\n{"event": "plan", "files": {"a.spec.ts": 1}}\n')
        record = Recorder()
        with progress.using(record): behavior_lock.Screens(folder / 'bad.jsonl', folder, folder / 'kept').read()
        self.assertEqual([(c['name'], c['status']) for c in record.calls], [('a.spec.ts', 'waiting')])

    def test_the_lock_config_uses_the_stream_reporter_shipped_with_the_package(self):
        self.assertTrue(behavior_lock.REPORTER.is_file())
        self.assertIn("['./stream-reporter.mjs', { outputFile: process.env.EAOS_LOCK_STREAM }]", behavior_lock.LOCK_CONFIG)

    @unittest.skipUnless((Path.home() / '.eaos/tools/node/node_modules/.bin/playwright').exists()
                         and (Path.home() / '.eaos/tools/browsers').is_dir(), 'the pinned Playwright is not installed here')
    def test_the_real_reporter_under_the_pinned_playwright_reports_screen_by_screen(self):
        folder = Path(tempfile.mkdtemp())
        lock = folder / '.eaos-lock'
        (lock / 'playwright').mkdir(parents=True)
        (lock / 'node_modules').symlink_to(Path.home() / '.eaos/tools/node/node_modules', target_is_directory=True)
        shutil.copyfile(behavior_lock.REPORTER, lock / 'stream-reporter.mjs')
        (lock / 'package.json').write_text('{"private": true, "type": "commonjs"}\n')
        (lock / 'playwright.config.ts').write_text(behavior_lock.CONFIG.replace("storageState: path.join(__dirname, '.auth', 'user.json')", '')
                                                   .replace("dependencies: ['setup'], ", ''))
        (lock / 'lock.config.ts').write_text(behavior_lock.LOCK_CONFIG.replace('...offline ', '').replace("launchOptions: { args: ['--proxy-server=http://127.0.0.1:9', '--proxy-bypass-list=127.0.0.1;localhost;[::1]'] }", ''))
        (lock / 'playwright/home.spec.ts').write_text(
            "import { test, expect } from '@playwright/test';\n"
            "test('home', async ({ page }) => { await page.setContent('<h1>Hello</h1>'); await expect(page).toHaveScreenshot('home.png'); });\n")
        (lock / 'playwright/broken.spec.ts').write_text(
            "import { test, expect } from '@playwright/test';\ntest('broken', async () => { expect(1).toBe(2); });\n")
        stream = folder / 'runtime/behavior-lock' / behavior_lock.STREAM
        stream.parent.mkdir(parents=True)
        env = {**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': str(Path.home() / '.eaos/tools/browsers'),
               'EAOS_LOCK_REPORT': str(folder / 'report.json'), 'EAOS_LOCK_STREAM': str(stream)}
        with progress.Flow(folder / 'runtime', 'safety', behavior_lock.FLOW, pulse=False, sampler=None):
            progress.begin('record')
            screens = behavior_lock.Screens(stream, lock / '__screenshots__', stream.parent / 'snapshots', keep=True, every=0.1).start()
            subprocess.run([str(lock / 'node_modules/.bin/playwright'), 'test', '--config', 'lock.config.ts', '--project=lock',
                            '--workers=1', '--update-snapshots=all'], cwd=lock, env=env, capture_output=True, timeout=300)
            screens.stop()
        steps = {s['name']: s for s in next(s for s in progress.fold(progress.read(folder / 'runtime', 'safety'))['stages']
                                            if s['name'] == 'record')['steps']}
        self.assertEqual((steps['playwright/home.spec.ts']['status'], steps['playwright/home.spec.ts']['artifact']),
                         ('ok', 'behavior-lock/snapshots/home.spec.ts/home.png'))
        self.assertEqual((steps['playwright/broken.spec.ts']['status'], steps['playwright/broken.spec.ts']['reason_code']),
                         ('failed', 'screen_failed'))
        self.assertTrue((stream.parent / 'snapshots/home.spec.ts/home.png').is_file())


def outcomes(expression):
    """The strings an expression can give: a literal, or either side of `a if test else b`, nested."""
    if isinstance(expression, ast.Constant) and isinstance(expression.value, str) and expression.value: return {expression.value}
    if isinstance(expression, ast.IfExp): return outcomes(expression.body) | outcomes(expression.orelse)
    return set()


class ReasonCodes(unittest.TestCase):
    """G5: every skipped stage and refusal says why in a stable code, worded in Arabic and English."""

    # Codes not written as a literal argument: f'engine_{status}' (eaos/engines), outcome['speed'] (eaos/guided.py), the
    # default of a SkipStage without one, the blocked prerequisites' tuples (eaos/pipeline/run.py) and a screen's verdict
    # (eaos/behavior_lock.py Screens.verdict).
    ELSEWHERE = {'engine_unavailable', 'engine_not_applicable', 'engine_error', 'engine_partial', 'no_build',
                 'no_production_run', 'not_applicable', 'prerequisites_missing', 'prerequisite_failed', 'screen_failed',
                 'screen_needs_fixture'}

    def codes_in_the_code(self):
        found = set()
        for path in (ROOT / 'eaos').rglob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Dict):
                    found |= {v.value for k, v in zip(node.keys, node.values) if isinstance(k, ast.Constant)
                              and k.value == 'reason_code' and isinstance(v, ast.Constant) and v.value}
                if not isinstance(node, ast.Call): continue
                for keyword in node.keywords:
                    if keyword.arg in ('code', 'reason_code'):
                        found |= outcomes(keyword.value)
                name = getattr(node.func, 'attr', getattr(node.func, 'id', ''))
                position = {'skip': 2, 'end': 3}.get(name)
                owner = getattr(getattr(node.func, 'value', None), 'id', '')
                if position is not None and owner == 'progress' and len(node.args) > position:
                    found |= outcomes(node.args[position])
        return found

    def test_every_skip_stage_raised_by_a_runner_names_its_code(self):
        tree = ast.parse((ROOT / 'eaos/pipeline/runners.py').read_text(encoding='utf-8'))
        raised = [node.exc for node in ast.walk(tree) if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)
                  and getattr(node.exc.func, 'id', '') == 'SkipStage']
        self.assertGreaterEqual(len(raised), 11)
        self.assertTrue(all(any(k.arg == 'code' for k in call.keywords) for call in raised))

    def test_every_code_written_anywhere_has_its_words_in_both_languages(self):
        codes = self.codes_in_the_code() | self.ELSEWHERE
        self.assertGreaterEqual(len(self.codes_in_the_code()), 30)
        for code in self.ELSEWHERE - {'engine_unavailable', 'engine_not_applicable', 'engine_error', 'engine_partial'}:
            self.assertTrue(any(f"'{code}'" in p.read_text(encoding='utf-8') for p in (ROOT / 'eaos').rglob('*.py')), code)
        self.assertEqual(sorted(codes - set(REASONS)), [])
        for code, texts in REASONS.items():
            self.assertTrue(texts.get('ar') and texts.get('en'), code)
            self.assertTrue(any('؀' <= ch <= 'ۿ' for ch in texts['ar']), code)
        self.assertEqual(sorted(set(REASONS) - codes), [], 'no text for a code nothing writes')

    def test_a_skipped_stage_carries_its_code_into_the_manifest_the_file_and_the_fold(self):
        out = Path(tempfile.mkdtemp())
        manifest = execute(project(), out, runners=stepping_runners(semantic=SkipStage('no model', code='no_provider'),
                                                                     probe=RuntimeError('boom')),
                           only=[s.name for s in STAGES if s.name != 'site'])
        rows = manifest['stages']
        self.assertEqual((rows['semantic']['reason_code'], rows['probe']['reason_code'], rows['site']['reason_code']),
                         ('no_provider', 'stage_error', 'not_requested'))
        self.assertEqual(rows['plan']['reason_code'], 'prerequisite_failed')
        self.assertNotIn('reason_code', rows['facts'], 'a stage that ran has no reason')
        folded = {s['name']: s['reason_code'] for s in progress.fold(progress.read(out))['stages']}
        self.assertEqual({n: folded[n] for n in ('semantic', 'probe', 'site', 'plan', 'facts')},
                         {'semantic': 'no_provider', 'probe': 'stage_error', 'site': 'not_requested', 'plan': 'prerequisite_failed', 'facts': ''})
        self.assertEqual(progress.reason_text('no_provider', 'ar'), REASONS['no_provider']['ar'])
        self.assertEqual(progress.reason_text('no_provider', 'en'), REASONS['no_provider']['en'])
        self.assertIsNone(progress.reason_text('something_new'))

    def test_a_catalog_that_cannot_be_read_gives_no_words_and_no_error(self):
        from eaos.progress import reasons
        reasons.reasons.cache_clear()
        try:
            with mock.patch.object(reasons, 'CATALOG', Path(tempfile.mkdtemp()) / 'missing.json'):
                self.assertEqual((reasons.reasons(), reasons.reason_text('no_provider')), ({}, None))
        finally:
            reasons.reasons.cache_clear()

    def test_the_plain_errors_still_read_from_the_same_catalog(self):
        self.assertTrue(guided.explain(ValueError('not a project folder: /x'))['ar']['message'])


class FixtureStage(unittest.TestCase):
    """I3, API half: a stage declared in a test appears in the folded state and the API, nothing else changed."""

    def test_a_stage_added_to_the_check_appears_in_the_progress_and_the_api(self):
        added = CheckStage('fixture_stage', produces=('fixture.json',), requires=('facts',), description='A stage added by a test')
        stages = (*STAGES, added)
        runners = {**fake_runners(), 'fixture_stage': lambda context: (context.out / 'fixture.json').write_text('{}') and {}}
        out = Path(tempfile.mkdtemp())
        with mock.patch.object(pipeline_run, 'STAGES', stages), mock.patch.object(pipeline_run, 'ORDER', tuple(s.name for s in stages)), \
                mock.patch.object(pipeline_run, 'BY_NAME', {s.name: s for s in stages}):
            manifest = execute(project(), out, runners=runners)
        self.assertEqual(manifest['stages']['fixture_stage']['status'], 'ok')
        state = scan_state(out)
        row = next(s for s in state['stages'] if s['name'] == 'fixture_stage')
        self.assertEqual((row['state'], row['requires'], row['description'], row['layer']), ('ok', ['facts'], 'A stage added by a test', 1))
        self.assertEqual(len(state['stages']), len(STAGES) + 1)

    def test_a_stage_added_to_a_flow_appears_in_its_fold(self):
        folder = Path(tempfile.mkdtemp())
        declared = (*live_setup.FLOW, flows.Stage('fixture_stage', requires=('baseline',), description='A stage added by a test'))
        with progress.Flow(folder, 'setup', declared) as flow:
            flow.begin('fixture_stage')
        state = progress.fold(progress.read(folder, 'setup'))
        self.assertEqual([s['name'] for s in state['stages']], [s.name for s in declared])
        self.assertEqual(next(s for s in state['stages'] if s['name'] == 'fixture_stage')['state'], 'ok')


class Estimates(unittest.TestCase):
    """G10: time left as a range, from the last run only."""

    def state(self, previous, stages):
        return {'state': 'running', 'previous': previous, 'stages': [{'requested': True, 'steps': [], **s} for s in stages]}

    def test_a_first_run_says_so_and_a_finished_run_has_no_estimate(self):
        self.assertEqual(estimate(self.state({}, [{'name': 'facts', 'state': 'running'}]), time.time()), {'basis': 'first_run'})
        self.assertIsNone(estimate({'state': 'done', 'previous': {'facts': 3}}, time.time()))

    def test_the_range_scales_the_waiting_stages_by_this_runs_pace(self):
        now = time.time()
        started = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(now - 10))
        state = self.state({'facts': 100, 'engines': 200, 'plan': 300},
                           [{'name': 'facts', 'state': 'ok', 'seconds': 50},
                            {'name': 'engines', 'state': 'running', 'started_at': started},
                            {'name': 'plan', 'state': 'waiting'}, {'name': 'brand_new', 'state': 'waiting'}])
        found = estimate(state, now)
        centre = 300 * 0.5 + (200 * 0.5 - 10)
        self.assertEqual((found['pace'], found['unknown'], found['basis']), (0.5, ['brand_new'], 'previous_run'))
        self.assertLessEqual(found['low'], centre)
        self.assertGreaterEqual(found['high'], centre)
        self.assertLess(found['high'] - found['low'], centre * 0.31 + 1)

    def test_a_counted_step_gives_the_running_stage_its_own_pace(self):
        now = time.time()
        started = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(now - 40))
        state = self.state({'plan': 1000}, [{'name': 'plan', 'state': 'running', 'started_at': started,
                                             'steps': [{'name': 'codemod trials', 'kind': 'count', 'status': 'running', 'done': 40, 'total': 160}]}])
        found = estimate(state, now)
        self.assertTrue(found['low'] <= 120 <= found['high'], found)

    def test_the_api_carries_the_estimate_and_the_steps_of_the_last_run(self):
        out = Path(tempfile.mkdtemp())
        execute(project(), out, runners=stepping_runners())
        log = progress.ProgressLog(out, pulse=False, sampler=None)
        log.started(STAGES, [s.name for s in STAGES], progress.previous_seconds(out))
        log.stage_started('facts')
        state = scan_state(out)
        self.assertEqual(state['estimate']['basis'], 'previous_run')
        self.assertIn('syntax', state['previous_steps']['facts'])
        log.finish('STOPPED')


class History(unittest.TestCase):
    """G11: the last five runs of each flow are kept, a killed one too."""

    def test_five_runs_are_kept_newest_first_and_a_killed_run_is_kept_when_the_next_begins(self):
        folder = Path(tempfile.mkdtemp())
        made = []
        for n in range(7):
            log = progress.ProgressLog(folder, 'fix', pulse=False, sampler=None)
            log.run = f'20261009T2000{n:02d}-abcdef'
            log.started(waves.FLOW, [s.name for s in waves.FLOW], {})
            made.append(log.run)
            if n < 6: log.finish('COMPLETE')
        self.assertEqual([r['run'] for r in runs(folder, 'fix')], made[1:6][::-1], 'the running one is not history yet')
        log = progress.ProgressLog(folder, 'fix', pulse=False, sampler=None)
        log.started(waves.FLOW, [], {})
        kept = runs(folder, 'fix')
        self.assertEqual((kept[0]['run'], kept[0]['state'], len(kept)), (made[6], 'running', 5))
        self.assertEqual(progress.fold_file(path_of(folder, 'fix', made[6]))['run'], made[6])
        for bad in ('../x', '', '.hidden', 'a/b'): self.assertIsNone(path_of(folder, 'fix', bad))

    def test_keeping_a_run_never_fails_the_run(self):
        folder = Path(tempfile.mkdtemp())
        self.assertEqual(writer.first_row(folder / 'missing.jsonl'), {})
        self.assertIsNone(writer.keep(folder / 'missing.jsonl', folder, 'fix'))
        (folder / 'blank.jsonl').write_text('')
        self.assertIsNone(writer.keep(folder / 'blank.jsonl', folder, 'fix'), 'no run id: nothing to keep')
        log = progress.ProgressLog(folder, 'fix', pulse=False, sampler=None)
        log.started(waves.FLOW, [], {})
        (folder / 'progress').chmod(0o500)
        try: self.assertIsNotNone(log.finish('COMPLETE'))
        finally: (folder / 'progress').chmod(0o700)

    def test_the_checks_history_is_beside_its_report(self):
        out = Path(tempfile.mkdtemp())
        for _ in range(2): execute(project(), out, runners=fake_runners())
        kept = runs(out)
        self.assertEqual((len(kept), {r['status'] for r in kept}), (2, {'COMPLETE'}))
        self.assertTrue(all(Path(r['path']).parent == out / 'progress/history/check' for r in kept))


class Switch(unittest.TestCase):
    def test_progress_switched_off_writes_and_hears_nothing(self):
        out = Path(tempfile.mkdtemp())
        heard = []
        runners = fake_runners()
        plain = runners['plan']
        runners['plan'] = lambda context: heard.append(progress.current()) or plain(context)
        with mock.patch.dict(os.environ, {'EAOS_PROGRESS': 'off'}):
            manifest = execute(project(), out, runners=runners)
            folder = Path(tempfile.mkdtemp())
            with progress.Flow(folder, 'setup', live_setup.FLOW) as flow:
                flow.begin('detect')
                self.assertIsNone(progress.current())
        self.assertEqual((manifest['status'], heard), ('COMPLETE', [None]))
        self.assertFalse((out / 'run-progress.jsonl').exists() or (out / 'progress').exists())
        self.assertFalse((folder / 'progress').exists())


class Journey(unittest.TestCase):
    def test_the_journey_is_the_four_steps_each_with_its_flow_and_its_state(self):
        report, runtime = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        log = progress.ProgressLog(runtime, 'safety', pulse=False, sampler=None)
        log.started(behavior_lock.FLOW, [s.name for s in behavior_lock.FLOW], {})
        with mock.patch.object(guided, 'report_of', return_value=report), mock.patch.object(guided, 'runtime_of', return_value=runtime), \
                mock.patch.object(guided, 'scan_done', return_value=True):
            steps = guided.journey({})
        self.assertEqual([(s['id'], s['flow'], s['state']) for s in steps],
                         [('scan', 'check', 'none'), ('ready', 'setup', 'none'), ('safety', 'safety', 'running'), ('fix', 'fix', 'none')])
        self.assertEqual(steps[0]['title']['ar'], guided.STEPS[0][1])
        self.assertFalse(steps[1]['done'], 'no setup recorded: not ready')
        log.finish('STOPPED')

    def test_a_later_step_is_never_done_while_an_earlier_one_waits_or_runs(self):
        report, runtime = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        everything_done = [(name, ar, en, (lambda state: True), run) for name, ar, en, _, run in guided.STEPS]
        with mock.patch.object(guided, 'report_of', return_value=report), mock.patch.object(guided, 'runtime_of', return_value=runtime):
            self.assertEqual([s['done'] for s in guided.journey({})], [False] * 4,
                             'no report yet: no ready card is left, yet the fix has not run')
            with mock.patch.object(guided, 'STEPS', everything_done):
                self.assertEqual([s['done'] for s in guided.journey({})], [True] * 4)
                log = progress.ProgressLog(report, 'check', pulse=False, sampler=None)
                log.started(STAGES, [s.name for s in STAGES], {})
                self.assertEqual([s['done'] for s in guided.journey({})], [True, False, False, False],
                                 'the check runs again: the steps after it wait for it')
                log.finish('STOPPED')

    def test_a_step_whose_done_check_cannot_be_read_is_not_done(self):
        broken = [(name, ar, en, (lambda state: 1 / 0), run) for name, ar, en, _, run in guided.STEPS]
        folder = Path(tempfile.mkdtemp())
        with mock.patch.object(guided, 'STEPS', broken), mock.patch.object(guided, 'report_of', return_value=folder), \
                mock.patch.object(guided, 'runtime_of', return_value=folder):
            self.assertEqual([s['done'] for s in guided.journey({})], [False] * 4)


if __name__ == '__main__':
    unittest.main()
