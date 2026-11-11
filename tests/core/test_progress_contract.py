"""The progress contract: eaos/kernel/progress/ and eaos/data/schemas/progress.json.

What every flow's progress file promises its readers, each promise a test:
- every event written validates against the versioned schema;
- every declared stage ends exactly once, also when the run is stopped or breaks (I1);
- a counted step never says more done than total, and one that ends ok ends with done == total (I5);
- a loop that counts fast is written at most 4 times a second per step, and its last value is always written.
The sampler, the liveness and the recorded runs are in test_progress_sampling.py."""
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'tools'))
import jsonschema  # noqa: E402
from eaos.kernel import progress  # noqa: E402
from eaos.features.check.journey import STAGES, SkipStage, execute, resume  # noqa: E402
from eaos.features.check.journey.stages import ORDER  # noqa: E402
from eaos.kernel.progress import log as writer  # noqa: E402
from shared_fixture import scratch  # noqa: E402
from tests.core._progress_fixture import Clock, GOLDEN, SCHEMA, check_rows, counting_runners, ends, invalid, project


class Schema(unittest.TestCase):
    def test_every_event_written_validates_and_a_line_that_breaks_the_contract_is_refused(self):
        jsonschema.Draft202012Validator.check_schema(SCHEMA)
        self.assertEqual((SCHEMA['x-version'], SCHEMA['$defs']['run.started']['properties']['schema']),
                         (1, {'const': writer.SCHEMA}))
        good = {'seq': 3, 'at': '2026-10-09T20:00:00.000+00:00', 'event': 'stage.step', 'run': '20261009T200000-abcdef',
                'stage': 'facts', 'step': 'syntax', 'done': 1, 'total': 19, 'status': 'running'}
        self.assertEqual(invalid([good]), [])
        for broken in ({'done': -1}, {'surprise': 1}, {'event': 'stage.stepped'}, {'stage': ''}):
            self.assertTrue(invalid([{**good, **broken}]), broken)
        self.assertTrue(invalid([{**good, 'event': 'stage.ended', 'status': 'done'}]),
                        'an end is one of the five fates')
        # Every event a check, the writer or a recorded run writes validates.
        for behaviour in ({}, {'probe': RuntimeError('boom'), 'semantic': SkipStage('no provider')},
                          {'claims': KeyboardInterrupt()}, {'features': SystemExit(3)}):
            rows, _, _ = check_rows(runners=counting_runners(**behaviour))
            self.assertGreater(len(rows), len(STAGES))
            self.assertEqual(invalid(rows), [], behaviour)
        clock = Clock()
        found = [[{'name': 'semgrep-core', 'pid': 42, 'since': '2026-10-09T20:00:00+00:00'}], None]
        stub = type('Stub', (), {'off': False, 'reason': 'the running programs cannot be seen: FileNotFoundError: ps',
                                 'sample': lambda self: found.pop(0)})()
        out = Path(scratch())
        log = progress.ProgressLog(out, 'setup', clock=clock, pulse=False, sampler=stub)
        log.started(STAGES[:3], ['facts'], {'facts': 3.0}, steps={'facts': {'syntax': 1.5}})
        log.stage_started('facts')
        log.stepper('facts')('syntax', 1, 19, 'unavailable', 0.4, reason='no parser', reason_code='parser_missing',
                             kind='item')
        for _ in range(3): clock.move(writer.SAMPLE_EVERY); log.tick()
        clock.move(progress.ALIVE_EVERY); log.tick()
        log.finish('ERROR', reason='RuntimeError: x', seconds=12.5)
        rows = progress.read(out, 'setup')
        self.assertEqual({r['event'] for r in rows}, {'run.started', 'stage.started', 'stage.step', 'stage.activity',
                                                       'run.alive', 'stage.ended', 'run.ended'})
        self.assertEqual(invalid(rows), [])
        self.assertTrue(GOLDEN, 'the recorded runs are committed')
        for path in GOLDEN:
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(invalid(rows), [], path.name)


class OneEndPerStage(unittest.TestCase):
    """I1: every declared stage gets exactly one stage.ended, whatever happens to the run."""

    def assert_one_end_each(self, rows):
        self.assertEqual(sorted(ends(rows)), sorted(ORDER))
        self.assertEqual(rows[-1]['event'], 'run.ended')
        self.assertEqual([r['seq'] for r in rows], list(range(1, len(rows) + 1)))

    def test_whole_partial_failed_and_resumed_runs_end_each_stage_once(self):
        for options in ({}, {'only': ['facts', 'features']},
                        {'runners': counting_runners(probe=RuntimeError('x'), semantic=SkipStage('no provider'))}):
            options.setdefault('runners', counting_runners())
            rows, raised, _ = check_rows(**options)
            self.assertIsNone(raised)
            self.assert_one_end_each(rows)
        folder, out = project(), Path(scratch())
        execute(folder, out, runners=counting_runners(probe=RuntimeError('x')))
        resume(folder, out, runners=counting_runners())
        rows = progress.read(out)
        self.assert_one_end_each(rows)
        self.assertTrue(all(r.get('resumed') for r in rows if r['event'] == 'stage.ended' and r['stage'] == 'facts'))
        out = Path(scratch())
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
        for path in GOLDEN:
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            names = [s['name'] for s in rows[0]['stages']]
            if rows[-1]['event'] == 'run.ended':
                self.assertEqual(sorted(ends(rows)), sorted(names), path.name)
            else:
                self.assertEqual(len(ends(rows)), len(set(ends(rows))), f'{path.name}: no stage ended twice')

    def test_a_stopped_or_crashed_run_still_ends_every_stage(self):
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
        rows, raised, _ = check_rows(runners=counting_runners(features=SystemExit(3)))
        self.assertIsInstance(raised, SystemExit)
        self.assert_one_end_each(rows)
        self.assertEqual(rows[-1]['status'], 'ERROR')
        self.assertEqual({r['stage']: r['status'] for r in rows if r['event'] == 'stage.ended'}['features'], 'failed')
        from unittest import mock
        with mock.patch('eaos.features.check.journey.run._manifest', side_effect=RuntimeError('disk full')):
            rows, raised, _ = check_rows(runners=counting_runners())
        self.assertIsInstance(raised, RuntimeError)
        self.assert_one_end_each(rows)


class CountedSteps(unittest.TestCase):
    """I5: done <= total on every step line; a counted step that ends ok ends with done == total."""

    def assert_bounded(self, rows, where):
        steps = [r for r in rows if r['event'] == 'stage.step']
        self.assertTrue(all(0 <= r['done'] <= r['total'] for r in steps), where)
        self.assertTrue(all(r['done'] == r['total'] for r in steps if r.get('kind') == 'count' and r['status'] == 'ok'),
                        where)
        for stage in progress.fold(rows)['stages']:
            items = [s for s in stage['steps'] if s['kind'] == 'item']
            if stage['state'] == 'ok' and items:
                self.assertEqual(max(s['done'] for s in items), items[0]['total'],
                                 f'{where}: {stage["name"]} accounted for every item')

    def test_counts_are_bounded_end_at_their_total_and_do_nothing_outside_a_run(self):
        rows, _, _ = check_rows(runners=counting_runners())
        self.assert_bounded(rows, 'fake run')
        plan = {s['name']: s for s in progress.fold(rows)['stages']}['plan']['steps']
        self.assertEqual([(s['name'], s['kind'], s['status'], s['done'], s['total']) for s in plan],
                         [('codemod trial', 'count', 'ok', 156, 156), ('debt items', 'count', 'ok', 454, 454),
                          ('homes', 'count', 'running', 0, 642)])
        for path in GOLDEN:
            self.assert_bounded([json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()], path.name)
        self.assertIsNone(progress.current())
        progress.count('anything', 3, 10)
        progress.step('anything', 3, 10)

        def broken(*args, **kwargs): raise RuntimeError('the stepper broke')
        with progress.using(broken):
            progress.count('anything', 3, 10)
            progress.step('anything', 3, 10)
            self.assertIs(progress.current(), broken)
        self.assertIsNone(progress.current(), 'the block restores what was there')


class Coalescer(unittest.TestCase):
    def setUp(self):
        self.clock, self.out = Clock(), Path(scratch())
        self.log = progress.ProgressLog(self.out, clock=self.clock, pulse=False, sampler=None)
        self.log.started(STAGES, list(ORDER), {})
        self.log.stage_started('plan')

    def lines_of(self, name):
        return [r for r in progress.read(self.out) if r['event'] == 'stage.step' and r['step'] == name]

    def test_a_fast_loop_is_coalesced_per_step_and_its_newest_value_is_always_written(self):
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
        step = self.log.stepper('plan')
        step('a', 0, 2, 'running')
        step('b', 0, 2, 'running')
        step('a', 1, 2, 'running')                          # coalesced
        step('a', 2, 2, 'ok')                               # a new status: written now, the coalesced value dropped
        self.assertEqual([(r['step'], r['done'], r['status']) for r in progress.read(self.out)
                          if r['event'] == 'stage.step' and r['step'] in ('a', 'b')],
                         [('a', 0, 'running'), ('b', 0, 'running'), ('a', 2, 'ok')])
        # A coalesced value is written when its window passes, and at the latest when the stage ends.
        with progress.using(self.log.stepper('plan')):
            for done in range(1, 100): progress.count('cards', done, 156)            # all within one instant
        self.assertEqual([r['done'] for r in self.lines_of('cards')], [1])
        self.clock.move(writer.COALESCE)
        self.log.tick()
        self.assertEqual([r['done'] for r in self.lines_of('cards')], [1, 99], 'the beat writes the newest value')
        with progress.using(self.log.stepper('plan')):
            progress.count('cards', 120, 156)
        self.log.ended({'stage': 'plan', 'status': 'ok', 'reason': '', 'seconds': 1.0, 'necessity': 'required',
                        'artifacts': []})
        rows = progress.read(self.out)
        self.assertEqual([r['done'] for r in self.lines_of('cards')], [1, 99, 120])
        last_step = max(i for i, r in enumerate(rows) if r['event'] == 'stage.step')
        self.assertLess(last_step, next(i for i, r in enumerate(rows) if r['event'] == 'stage.ended'))


if __name__ == '__main__':
    unittest.main()
