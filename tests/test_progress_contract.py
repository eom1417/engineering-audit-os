"""The progress contract (live scan map v2, phase 1): eaos/progress/ and eaos/data/schemas/progress.json.

What every flow's progress file promises its readers, each promise a test:
- every event written validates against the versioned schema;
- every declared stage ends exactly once, also when the run is stopped or breaks (I1);
- a counted step never says more done than total, and one that ends ok ends with done == total (I5);
- a loop that counts fast is written at most 4 times a second per step, and its last value is always written;
- the running external programs are read from `ps` on Linux and on macOS, and a `ps` that fails turns the sampler off
  with one line;
- `run.alive` after 10 s of silence, and a reader calls a run `stalled` after 30 s without a line;
- the single Python fold of each recorded real run equals its committed expected JSON (I4, Python half).
Fake runners and an injected clock stand in for the real stages and for time, so every case runs in a moment; the
recorded runs in tests/fixtures/progress/ are real checks.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'tools'))

import jsonschema  # noqa: E402

from eaos import progress  # noqa: E402
from eaos.pipeline import STAGES, SkipStage, execute, resume  # noqa: E402
from eaos.pipeline.stages import ORDER  # noqa: E402
from eaos.progress import log as writer, sampler  # noqa: E402
from test_live_scan_map import project, stepping_runners  # noqa: E402

FIXTURES = ROOT / 'tests/fixtures/progress'
SCHEMA = json.loads((ROOT / 'eaos/data/schemas/progress.json').read_text(encoding='utf-8'))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
GOLDEN = sorted(FIXTURES.glob('*.jsonl'))


class Clock:
    """Monotonic seconds that move only when the test says so."""

    def __init__(self): self.at = 1000.0
    def __call__(self): return self.at
    def move(self, seconds): self.at += seconds


def invalid(rows):
    return [(row.get('seq'), row.get('event'), error.message) for row in rows for error in VALIDATOR.iter_errors(row)]


def counting_runners(**behaviour):
    """The stepping runners, with `plan` counting a loop through progress.count() the way deep code does."""
    runners = stepping_runners(**behaviour)
    plain = runners['plan']

    def plan(context):
        for done in range(0, 157): progress.count('codemod trial', done, 156)
        progress.count('debt items', 500, 454)             # more than declared: held at total
        progress.count('homes', -3, 642)                   # less than nothing: held at 0
        return plain(context)

    runners['plan'] = plan
    return runners


def check_rows(**options):
    out = Path(tempfile.mkdtemp(prefix='progress-out-'))
    try: execute(project(), out, **options)
    except BaseException as problem: options['raised'] = problem
    return progress.read(out), options.get('raised'), out


def ends(rows):
    return [r['stage'] for r in rows if r['event'] == 'stage.ended']


class Schema(unittest.TestCase):
    def test_the_schema_is_a_valid_versioned_json_schema_shipped_with_the_package(self):
        jsonschema.Draft202012Validator.check_schema(SCHEMA)
        self.assertEqual((SCHEMA['x-version'], SCHEMA['$defs']['run.started']['properties']['schema']), (1, {'const': writer.SCHEMA}))
        self.assertEqual((ROOT / 'schemas/progress.json').read_bytes(), (ROOT / 'eaos/data/schemas/progress.json').read_bytes(),
                         'the packaged copy is the canonical one')

    def test_every_event_a_check_writes_validates_against_the_schema(self):
        for behaviour in ({}, {'probe': RuntimeError('boom'), 'semantic': SkipStage('no provider')},
                          {'claims': KeyboardInterrupt()}, {'features': SystemExit(3)}):
            rows, _, _ = check_rows(runners=counting_runners(**behaviour))
            self.assertGreater(len(rows), len(STAGES))
            self.assertEqual(invalid(rows), [], behaviour)

    def test_every_event_the_writer_can_write_validates_including_activity_and_heartbeats(self):
        clock = Clock()
        found = [[{'name': 'semgrep-core', 'pid': 42, 'since': '2026-10-09T20:00:00+00:00'}], None]
        stub = type('Stub', (), {'off': False, 'reason': 'the running programs cannot be seen: FileNotFoundError: ps',
                                 'sample': lambda self: found.pop(0)})()
        out = Path(tempfile.mkdtemp())
        log = progress.ProgressLog(out, 'setup', clock=clock, pulse=False, sampler=stub)
        log.started(STAGES[:3], ['facts'], {'facts': 3.0}, steps={'facts': {'syntax': 1.5}})
        log.stage_started('facts')
        log.stepper('facts')('syntax', 1, 19, 'unavailable', 0.4, reason='no parser', reason_code='parser_missing', kind='item')
        for _ in range(3): clock.move(writer.SAMPLE_EVERY); log.tick()
        clock.move(progress.ALIVE_EVERY); log.tick()
        log.finish('ERROR', reason='RuntimeError: x', seconds=12.5)
        rows = progress.read(out, 'setup')
        self.assertEqual({r['event'] for r in rows}, {'run.started', 'stage.started', 'stage.step', 'stage.activity',
                                                       'run.alive', 'stage.ended', 'run.ended'})
        self.assertEqual(invalid(rows), [])

    def test_every_line_of_every_recorded_real_run_validates(self):
        self.assertTrue(GOLDEN, 'the recorded runs are committed')
        for path in GOLDEN:
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(invalid(rows), [], path.name)

    def test_a_line_that_breaks_the_contract_is_refused(self):
        good = {'seq': 3, 'at': '2026-10-09T20:00:00.000+00:00', 'event': 'stage.step', 'run': '20261009T200000-abcdef',
                'stage': 'facts', 'step': 'syntax', 'done': 1, 'total': 19, 'status': 'running'}
        self.assertEqual(invalid([good]), [])
        for broken in ({'done': -1}, {'surprise': 1}, {'event': 'stage.stepped'}, {'stage': ''}):
            self.assertTrue(invalid([{**good, **broken}]), broken)
        self.assertTrue(invalid([{**good, 'event': 'stage.ended', 'status': 'done'}]), 'an end is one of the five fates')


class OneEndPerStage(unittest.TestCase):
    """I1: every declared stage gets exactly one stage.ended, whatever happens to the run."""

    def assert_one_end_each(self, rows):
        self.assertEqual(sorted(ends(rows)), sorted(ORDER))
        self.assertEqual(rows[-1]['event'], 'run.ended')
        self.assertEqual([r['seq'] for r in rows], list(range(1, len(rows) + 1)))

    def test_a_whole_run_a_partial_run_and_a_run_with_failures(self):
        for options in ({}, {'only': ['facts', 'features']},
                        {'runners': counting_runners(probe=RuntimeError('x'), semantic=SkipStage('no provider'))}):
            options.setdefault('runners', counting_runners())
            rows, raised, _ = check_rows(**options)
            self.assertIsNone(raised)
            self.assert_one_end_each(rows)

    def test_a_resumed_run(self):
        folder, out = project(), Path(tempfile.mkdtemp())
        execute(folder, out, runners=counting_runners(probe=RuntimeError('x')))
        resume(folder, out, runners=counting_runners())
        rows = progress.read(out)
        self.assert_one_end_each(rows)
        self.assertTrue(all(r.get('resumed') for r in rows if r['event'] == 'stage.ended' and r['stage'] == 'facts'))

    def test_a_stopped_run_ends_the_stage_it_was_in_and_every_stage_it_did_not_reach(self):
        rows, raised, _ = check_rows(runners=counting_runners(claims=KeyboardInterrupt()))
        self.assertIsInstance(raised, KeyboardInterrupt, 'the stop still reaches the caller')
        self.assert_one_end_each(rows)
        ended = {r['stage']: r for r in rows if r['event'] == 'stage.ended'}
        self.assertEqual(ended['claims']['status'], 'failed')
        self.assertIn('while this stage ran', ended['claims']['reason'])
        after = [n for n in ORDER if 'claims' in progress.fold(rows)['stages'][ORDER.index(n)]['requires']]
        self.assertTrue(after and all(ended[n]['status'] == 'not_reached' for n in after))
        self.assertEqual((rows[-1]['status'], progress.fold(rows)['reason']), ('STOPPED', 'KeyboardInterrupt: '))
        self.assertEqual(ended['facts']['status'], 'ok', 'what ended before the stop keeps its own end')

    def test_a_run_that_crashes_inside_a_stage_or_after_the_stages(self):
        rows, raised, _ = check_rows(runners=counting_runners(features=SystemExit(3)))
        self.assertIsInstance(raised, SystemExit)
        self.assert_one_end_each(rows)
        self.assertEqual(rows[-1]['status'], 'ERROR')
        self.assertEqual({r['stage']: r['status'] for r in rows if r['event'] == 'stage.ended'}['features'], 'failed')
        from unittest import mock
        with mock.patch('eaos.pipeline.run._manifest', side_effect=RuntimeError('disk full')):
            rows, raised, _ = check_rows(runners=counting_runners())
        self.assertIsInstance(raised, RuntimeError)
        self.assert_one_end_each(rows)

    def test_the_writer_refuses_a_second_end_and_a_second_finish(self):
        out = Path(tempfile.mkdtemp())
        log = progress.ProgressLog(out, pulse=False, sampler=None)
        log.started(STAGES, list(ORDER), {})
        row = {'stage': 'facts', 'status': 'ok', 'reason': '', 'seconds': 1.0, 'necessity': 'required', 'artifacts': []}
        self.assertIsNotNone(log.ended(row))
        self.assertIsNone(log.ended({**row, 'status': 'failed'}))
        log.finish('COMPLETE')
        self.assertIsNone(log.finish('ERROR'))
        rows = progress.read(out)
        self.assertEqual(sorted(ends(rows)), sorted(ORDER))
        self.assertEqual([r['status'] for r in rows if r['event'] == 'run.ended'], ['COMPLETE'])

    def test_every_recorded_run_that_reached_an_end_ended_each_stage_once(self):
        for path in GOLDEN:
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            names = [s['name'] for s in rows[0]['stages']]
            if rows[-1]['event'] == 'run.ended':
                self.assertEqual(sorted(ends(rows)), sorted(names), path.name)
            else:
                self.assertEqual(len(ends(rows)), len(set(ends(rows))), f'{path.name}: no stage ended twice')


class CountedSteps(unittest.TestCase):
    """I5: done <= total on every step line; a counted step that ends ok ends with done == total."""

    def assert_bounded(self, rows, where):
        steps = [r for r in rows if r['event'] == 'stage.step']
        self.assertTrue(all(0 <= r['done'] <= r['total'] for r in steps), where)
        self.assertTrue(all(r['done'] == r['total'] for r in steps if r.get('kind') == 'count' and r['status'] == 'ok'), where)
        for stage in progress.fold(rows)['stages']:
            items = [s for s in stage['steps'] if s['kind'] == 'item']
            if stage['state'] == 'ok' and items:
                self.assertEqual(max(s['done'] for s in items), items[0]['total'], f'{where}: {stage["name"]} accounted for every item')

    def test_counts_inside_a_stage_are_bounded_and_end_at_their_total(self):
        rows, _, _ = check_rows(runners=counting_runners())
        self.assert_bounded(rows, 'fake run')
        plan = {s['name']: s for s in progress.fold(rows)['stages']}['plan']['steps']
        self.assertEqual([(s['name'], s['kind'], s['status'], s['done'], s['total']) for s in plan],
                         [('codemod trial', 'count', 'ok', 156, 156), ('debt items', 'count', 'ok', 454, 454),
                          ('homes', 'count', 'running', 0, 642)])

    def test_every_recorded_real_run_keeps_its_counts_bounded(self):
        for path in GOLDEN:
            self.assert_bounded([json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()], path.name)

    def test_count_and_step_do_nothing_outside_a_run_and_never_raise(self):
        self.assertIsNone(progress.current())
        progress.count('anything', 3, 10)
        progress.step('anything', 3, 10)

        def broken(*args, **kwargs): raise RuntimeError('the stepper broke')
        with progress.using(broken):
            progress.count('anything', 3, 10)
            progress.step('anything', 3, 10)
            self.assertIs(progress.current(), broken)
        self.assertIsNone(progress.current(), 'the block restores what was there')

    def test_the_real_facts_and_engines_report_through_the_current_stage(self):
        heard = []
        with progress.using(lambda *args, **kwargs: heard.append(args)):
            from eaos.engines import analyze
            analyze(project(), tempfile.mkdtemp(), only=['lizard'])
        self.assertEqual([(a[0], a[3]) for a in heard][:2], [('lizard', 'waiting'), ('lizard', 'running')])
        self.assertEqual(heard[-1][1:3], (1, 1))


class Coalescer(unittest.TestCase):
    def setUp(self):
        self.clock, self.out = Clock(), Path(tempfile.mkdtemp())
        self.log = progress.ProgressLog(self.out, clock=self.clock, pulse=False, sampler=None)
        self.log.started(STAGES, list(ORDER), {})
        self.log.stage_started('plan')

    def lines_of(self, name):
        return [r for r in progress.read(self.out) if r['event'] == 'stage.step' and r['step'] == name]

    def test_a_fast_loop_writes_at_most_four_lines_a_second_and_always_its_last_value(self):
        with progress.using(self.log.stepper('plan')):
            for done in range(1, 643):                       # 642 items, one every 15 ms: about 9.6 s
                self.clock.move(0.015)
                progress.count('homes', done, 642)
        lines = self.lines_of('homes')
        seconds = 642 * 0.015
        self.assertLessEqual(len(lines), int(seconds * 4) + 2, f'{len(lines)} lines in {seconds:.1f} s')
        self.assertGreater(len(lines), 10, 'it still moves visibly')
        self.assertEqual((lines[-1]['done'], lines[-1]['status']), (642, 'ok'))
        moments = [i for i, r in enumerate(lines) if r['status'] == 'running']
        self.assertEqual(len(moments), len(lines) - 1)

    def test_a_coalesced_value_is_written_when_its_window_passes_and_at_the_latest_when_the_stage_ends(self):
        with progress.using(self.log.stepper('plan')):
            for done in range(1, 100): progress.count('cards', done, 156)            # all within one instant
        self.assertEqual([r['done'] for r in self.lines_of('cards')], [1])
        self.clock.move(writer.COALESCE)
        self.log.tick()
        self.assertEqual([r['done'] for r in self.lines_of('cards')], [1, 99], 'the beat writes the newest value')
        with progress.using(self.log.stepper('plan')):
            progress.count('cards', 120, 156)
        self.log.ended({'stage': 'plan', 'status': 'ok', 'reason': '', 'seconds': 1.0, 'necessity': 'required', 'artifacts': []})
        rows = progress.read(self.out)
        self.assertEqual([r['done'] for r in self.lines_of('cards')], [1, 99, 120])
        last_step = max(i for i, r in enumerate(rows) if r['event'] == 'stage.step')
        self.assertLess(last_step, next(i for i, r in enumerate(rows) if r['event'] == 'stage.ended'))

    def test_each_step_name_has_its_own_window_and_a_change_of_status_is_written_at_once(self):
        step = self.log.stepper('plan')
        step('a', 0, 2, 'running')
        step('b', 0, 2, 'running')
        step('a', 1, 2, 'running')                          # coalesced
        step('a', 2, 2, 'ok')                               # a new status: written now, the coalesced value dropped
        self.assertEqual([(r['step'], r['done'], r['status']) for r in progress.read(self.out) if r['event'] == 'stage.step'],
                         [('a', 0, 'running'), ('b', 0, 'running'), ('a', 2, 'ok')])


class Sampling(unittest.TestCase):
    def test_the_linux_process_table_recorded_during_a_real_check(self):
        rows = sampler.parse((FIXTURES / 'ps/linux.txt').read_text(encoding='utf-8'))
        self.assertEqual(len(rows), 38)
        self.assertIn((1, 0, 3 * 3600 + 50 * 60 + 4, 'systemd'), rows)
        self.assertIn('run-assistant.s', {r[3] for r in rows}, 'procps cuts comm at 15 characters')
        eaos = next(r[0] for r in rows if r[3] == 'eaos' and r[1] != 1)
        found = sampler.programs(rows, eaos, leave={next(r[0] for r in rows if r[3] == 'ps')})
        self.assertEqual([p['name'] for p in found], ['pysemgrep'] + ['semgrep-core'] * 6)
        self.assertTrue(all(p['since'].endswith('+00:00') for p in found))

    def test_the_macos_process_table(self):
        rows = sampler.parse((FIXTURES / 'ps/macos.txt').read_text(encoding='utf-8'))
        self.assertEqual(len(rows), 14)
        by = {r[0]: r for r in rows}
        self.assertEqual(by[1], (1, 0, 3 * 86400 + 4 * 3600 + 12 * 60 + 55, 'launchd'), 'dd-hh:mm:ss, a full path')
        self.assertEqual(by[807][3], '-zsh')
        self.assertEqual(by[2231][3], 'Google Chrome Helper (Renderer)', 'spaces and parentheses in the path')
        self.assertEqual(by[2210][2], 45 * 60 + 10)
        found = sampler.programs(rows, 9001, leave={9080})
        self.assertEqual([(p['name'], p['pid']) for p in found],
                         [('python3.12', 9050), ('semgrep-core', 9061), ('semgrep-core', 9062), ('trivy', 9077)])

    def test_elapsed_times_in_every_ps_form(self):
        self.assertEqual([sampler.elapsed(t) for t in ('00:07', '59:59', '01:02:03', '2-00:00:01', '12-03:04:05')],
                         [7, 3599, 3723, 172801, 12 * 86400 + 3 * 3600 + 4 * 60 + 5])
        self.assertEqual([sampler.elapsed(t) for t in ('', 'abc', '7', '1:2:3:4', '-1:00')], [None] * 5)

    def test_the_real_ps_here_sees_a_program_this_process_started_and_not_itself(self):
        child = subprocess.Popen(['sleep', '20'])
        self.addCleanup(lambda: (child.kill(), child.wait()))
        found = sampler.Sampler().sample()
        self.assertIsNotNone(found)
        self.assertIn(('sleep', child.pid), [(p['name'], p['pid']) for p in found])
        self.assertNotIn('ps', [p['name'] for p in found], 'the ps that looked is left out')

    def test_a_ps_that_is_missing_fails_or_prints_nonsense_turns_the_sampler_off_with_one_line(self):
        for command in (['no-such-ps-anywhere'], ['false'], ['echo', 'nothing useful']):
            looker = sampler.Sampler(command=command)
            self.assertIsNone(looker.sample())
            self.assertTrue(looker.off and looker.reason.startswith('the running programs cannot be seen'), command)
            self.assertIsNone(looker.sample())
        clock, out = Clock(), Path(tempfile.mkdtemp())
        log = progress.ProgressLog(out, clock=clock, pulse=False, sampler=sampler.Sampler(command=['false']))
        log.started(STAGES, list(ORDER), {})
        for stage in ('facts', 'engines'):
            log.stage_started(stage)
            for _ in range(5): clock.move(writer.SAMPLE_EVERY); log.tick()
            log.ended({'stage': stage, 'status': 'ok', 'reason': '', 'seconds': 1.0, 'necessity': 'required', 'artifacts': []})
        activity = [r for r in progress.read(out) if r['event'] == 'stage.activity']
        self.assertEqual(len(activity), 1, 'said once, then quiet')
        self.assertEqual((activity[0]['programs'], activity[0]['stage']), ([], 'facts'))
        self.assertIn('ps exited with 1', activity[0]['reason'])
        self.assertEqual(progress.fold(progress.read(out))['stages'][0]['activity_note'], activity[0]['reason'])

    def test_activity_is_written_only_when_the_set_of_programs_changes(self):
        semgrep = {'name': 'semgrep-core', 'pid': 7, 'since': '2026-10-09T20:00:00+00:00'}
        seen = [[semgrep], [semgrep], [semgrep, {'name': 'trivy', 'pid': 9, 'since': '2026-10-09T20:00:02+00:00'}], []]
        stub = type('Stub', (), {'off': False, 'reason': '', 'sample': lambda self: seen.pop(0)})()
        clock, out = Clock(), Path(tempfile.mkdtemp())
        log = progress.ProgressLog(out, clock=clock, pulse=False, sampler=stub)
        log.started(STAGES, list(ORDER), {})
        log.stage_started('engines')
        log.tick()
        self.assertEqual(len(seen), 4, 'not before SAMPLE_EVERY seconds of the stage')
        for _ in range(4): clock.move(writer.SAMPLE_EVERY); log.tick()
        activity = [[p['name'] for p in r['programs']] for r in progress.read(out) if r['event'] == 'stage.activity']
        self.assertEqual(activity, [['semgrep-core'], ['semgrep-core', 'trivy'], []])
        log.ended({'stage': 'engines', 'status': 'ok', 'reason': '', 'seconds': 8.0, 'necessity': 'optional', 'artifacts': []})
        self.assertEqual({s['name']: s for s in progress.fold(progress.read(out))['stages']}['engines']['programs'], [])


class Liveness(unittest.TestCase):
    def test_a_quiet_run_says_it_is_alive_every_ten_seconds_and_a_busy_one_does_not_need_to(self):
        clock, out = Clock(), Path(tempfile.mkdtemp())
        log = progress.ProgressLog(out, clock=clock, pulse=False, sampler=None)
        log.started(STAGES, list(ORDER), {})
        log.stage_started('plan')
        for _ in range(30): clock.move(1.0); log.tick()
        rows = progress.read(out)
        self.assertEqual(rows[0]['alive_every'], progress.ALIVE_EVERY)
        self.assertEqual(len([r for r in rows if r['event'] == 'run.alive']), 3, '30 quiet seconds: three beats')
        step = log.stepper('plan')
        for done in range(30):
            clock.move(1.0); step('x', done, 30, 'running'); log.tick()
        self.assertEqual(len([r for r in progress.read(out) if r['event'] == 'run.alive']), 3, 'lines are proof enough')
        log.finish('COMPLETE')
        clock.move(60)
        self.assertFalse(log.tick(), 'the beat stops with the run')
        self.assertEqual(progress.read(out)[-1]['event'], 'run.ended')

    def test_the_real_heartbeat_thread_beats_and_stops_with_the_run(self):
        out = Path(tempfile.mkdtemp())
        log = progress.ProgressLog(out, sampler=None, alive_every=0.2)
        log.started(STAGES, list(ORDER), {})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not any(r['event'] == 'run.alive' for r in progress.read(out)): time.sleep(0.1)
        self.assertTrue(any(r['event'] == 'run.alive' for r in progress.read(out)))
        log.finish('STOPPED')
        log.thread.join(3)
        self.assertFalse(log.thread.is_alive())

    def test_the_beat_stops_when_the_file_cannot_be_written(self):
        out = Path(tempfile.mkdtemp())
        progress.path_for(out).mkdir()                    # the path cannot be written as a file
        log = progress.ProgressLog(out, clock=Clock(), sampler=None)
        log.started(STAGES, list(ORDER), {})
        self.assertTrue(log.broken)
        self.assertIsNone(log.thread, 'no beat for a file nobody can read')
        self.assertFalse(log.tick())

    def test_stalled_after_thirty_seconds_of_silence_with_an_injected_clock(self):
        state = {'state': 'running', 'alive_every': 10.0}
        self.assertEqual(progress.judge(state, heard=1000.0, now=1029.9), 'running')
        self.assertEqual(progress.judge(state, heard=1000.0, now=1030.0), 'running')
        self.assertEqual(progress.judge(state, heard=1000.0, now=1030.1), 'stalled')
        self.assertEqual(progress.judge(state, heard=1000.0, now=1030.1, living=False), 'interrupted', 'a known death wins')
        self.assertEqual(progress.judge({'state': 'running'}, heard=1000.0, now=2000.0), 'running',
                         'a run that promised no heartbeat is not judged by its silence')
        self.assertEqual(progress.judge({**state, 'state': 'done'}, heard=1000.0, now=9999.0), 'done')
        self.assertEqual(progress.judge(state, heard=None, now=9999.0), 'running')

    def test_the_server_shows_a_silent_run_as_stalled(self):
        from test_studio_api import report_with_data
        from eaos.api.read import scan_state
        report = report_with_data(tempfile.mkdtemp())
        log = progress.ProgressLog(report, pulse=False, sampler=None)
        log.started(STAGES, list(ORDER), {})
        log.stage_started('facts')
        self.assertEqual(scan_state(report)['state'], 'running')
        then = time.time() - progress.STALLED_AFTER - 5
        os.utime(progress.path_for(report), (then, then))
        self.assertEqual(scan_state(report)['state'], 'stalled')


class Flows(unittest.TestCase):
    def test_each_flow_has_its_own_file_and_the_check_keeps_its_v1_place(self):
        folder = Path(tempfile.mkdtemp())
        self.assertEqual(progress.path_for(folder), folder / 'run-progress.jsonl')
        self.assertEqual(progress.path_for(folder, 'setup'), folder / 'progress' / 'setup.jsonl')
        log = progress.ProgressLog(folder, 'safety', pulse=False, sampler=None)
        log.started(STAGES[:2], ['facts'], {})
        log.finish('COMPLETE')
        state = progress.fold(progress.read(folder, 'safety'))
        self.assertEqual((state['flow'], state['state'], progress.read(folder)), ('safety', 'done', []))

    def test_the_last_runs_step_seconds_are_carried_into_the_next_run(self):
        out = Path(tempfile.mkdtemp())
        execute(project(), out, runners=stepping_runners())
        execute(project(), out, runners=stepping_runners())
        first = progress.read(out)[0]
        self.assertEqual(first['previous_steps']['facts'], {'syntax': 0.01, 'resolve': 0.01, 'graph': 0.01})
        self.assertEqual(progress.fold(progress.read(out))['previous_steps']['facts']['graph'], 0.01)


class GoldenFold(unittest.TestCase):
    """I4, the Python half: the fold of each recorded real run is the committed expected JSON."""

    def test_the_recorded_runs_cover_an_end_a_stop_and_a_kill(self):
        self.assertEqual({p.stem for p in GOLDEN}, {'complete', 'stopped', 'killed'})

    def test_the_fold_of_every_recorded_run_equals_its_expected_json(self):
        for path in GOLDEN:
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            expected = json.loads(path.with_suffix('.fold.json').read_text(encoding='utf-8'))
            self.assertEqual(progress.fold(rows), expected, path.name)

    def test_what_each_recorded_run_folds_to(self):
        folds = {p.stem: json.loads(p.with_suffix('.fold.json').read_text(encoding='utf-8')) for p in GOLDEN}
        complete, stopped, killed = folds['complete'], folds['stopped'], folds['killed']
        self.assertEqual((complete['state'], complete['status']), ('done', 'COMPLETE'))
        self.assertTrue(all(s['state'] in progress.ENDED for s in complete['stages']))
        engines = {s['name']: s for s in complete['stages']}['engines']
        self.assertEqual(len(engines['steps']), 21, 'every tool of the engine registry')
        self.assertEqual((stopped['state'], stopped['status']), ('done', 'STOPPED'))
        self.assertTrue(all(s['state'] in progress.ENDED for s in stopped['stages']))
        self.assertEqual({s['name']: s['state'] for s in stopped['stages']}['engines'], 'failed')
        self.assertEqual(killed['state'], 'running', 'a killed run never wrote its end')
        self.assertEqual(progress.judge(killed, heard=0.0, now=progress.STALLED_AFTER + 1), 'stalled')
        running = [s['name'] for s in killed['stages'] if s['state'] == 'running']
        self.assertEqual(running, ['engines'])

    def test_the_tool_that_writes_the_expected_json_agrees(self):
        import progress_golden
        self.assertEqual(progress_golden.main(['check']), 0)


if __name__ == '__main__':
    unittest.main()
