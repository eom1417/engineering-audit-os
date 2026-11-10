"""The progress contract: eaos/core/progress/ and eaos/data/schemas/progress.json.

- the running external programs are read from `ps` on Linux and on macOS, and a `ps` that fails turns the sampler off
  with one line;
- `run.alive` after 10 s of silence, and a reader calls a run `stalled` after 30 s without a line;
- the single Python fold of each recorded real run equals its committed expected JSON (I4, Python half).
Fake runners and an injected clock stand in for the real stages and for time; the recorded runs in
tests/fixtures/progress/ are real checks."""
import json
import subprocess
import sys
import time
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'tools'))
from eaos.core import progress  # noqa: E402
from eaos.pipeline import STAGES, execute  # noqa: E402
from eaos.pipeline.stages import ORDER  # noqa: E402
from eaos.core.progress import log as writer, sampler  # noqa: E402
from shared_fixture import scratch  # noqa: E402
from tests.core._progress_fixture import Clock, FIXTURES, GOLDEN, project, stepping_runners


class Sampling(unittest.TestCase):
    def test_stages_side_by_side_each_show_the_programs_they_started(self):
        # engines and setup ran together, and every analyzer was shown under setup, the stage started last
        sampler.watch()
        step = lambda *args, **kwargs: None    # noqa: E731 - a stepper names its stage
        step.stage = 'engines'
        with progress.using(step): mine = subprocess.Popen(['sleep', '20'])
        other = subprocess.Popen(['sleep', '20'])
        self.addCleanup(lambda: [(p.kill(), p.wait()) for p in (mine, other)])
        found = {p['pid']: p.get('stage') for p in sampler.Sampler().sample()}
        self.assertEqual((found[mine.pid], found[other.pid]), ('engines', None))

        class Seen:
            def sample(self): return [{'name': 'codeql', 'pid': 7, 'since': '2026-10-18T00:00:00+00:00',
                                       'stage': 'engines'},
                                      {'name': 'npm', 'pid': 8, 'since': '2026-10-18T00:00:00+00:00'}]
        log = progress.ProgressLog(Path(scratch()), pulse=False, sampler=None)
        log.sampler = Seen()
        log.started(STAGES, list(ORDER), {})
        log.stage_started('engines')
        log.stage_started('setup')
        log._look('setup')
        shown = {r['stage']: [p['name'] for p in r['programs']] for r in progress.read(log.folder)
                 if r['event'] == 'stage.activity'}
        self.assertEqual(shown, {'engines': ['codeql'], 'setup': ['npm']},
                         'a program of no known stage is on the one started last')

    def test_the_running_programs_are_read_from_ps_on_linux_and_macos_and_a_failing_ps_is_said_once(self):
        rows = sampler.parse((FIXTURES / 'ps/linux.txt').read_text(encoding='utf-8'))
        self.assertEqual(len(rows), 38)
        self.assertIn((1, 0, 3 * 3600 + 50 * 60 + 4, 'systemd'), rows)
        self.assertIn('run-assistant.s', {r[3] for r in rows}, 'procps cuts comm at 15 characters')
        eaos = next(r[0] for r in rows if r[3] == 'eaos' and r[1] != 1)
        found = sampler.programs(rows, eaos, leave={next(r[0] for r in rows if r[3] == 'ps')})
        self.assertEqual([p['name'] for p in found], ['pysemgrep'] + ['semgrep-core'] * 6)
        self.assertTrue(all(p['since'].endswith('+00:00') for p in found))
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
        self.assertEqual([sampler.elapsed(t) for t in ('00:07', '59:59', '01:02:03', '2-00:00:01', '12-03:04:05')],
                         [7, 3599, 3723, 172801, 12 * 86400 + 3 * 3600 + 4 * 60 + 5])
        self.assertEqual([sampler.elapsed(t) for t in ('', 'abc', '7', '1:2:3:4', '-1:00')], [None] * 5)
        # The running programs are seen, and a ps that fails is said once.
        child = subprocess.Popen(['sleep', '20'])
        self.addCleanup(lambda: (child.kill(), child.wait()))
        found = sampler.Sampler().sample()
        self.assertIsNotNone(found)
        self.assertIn(('sleep', child.pid), [(p['name'], p['pid']) for p in found])
        self.assertNotIn('ps', [p['name'] for p in found], 'the ps that looked is left out')
        for command in (['no-such-ps-anywhere'], ['false'], ['echo', 'nothing useful']):
            looker = sampler.Sampler(command=command)
            self.assertIsNone(looker.sample())
            self.assertTrue(looker.off and looker.reason.startswith('the running programs cannot be seen'), command)
            self.assertIsNone(looker.sample())
        clock, out = Clock(), Path(scratch())
        log = progress.ProgressLog(out, clock=clock, pulse=False, sampler=sampler.Sampler(command=['false']))
        log.started(STAGES, list(ORDER), {})
        for stage in ('facts', 'engines'):
            log.stage_started(stage)
            for _ in range(5): clock.move(writer.SAMPLE_EVERY); log.tick()
            log.ended({'stage': stage, 'status': 'ok', 'reason': '', 'seconds': 1.0, 'necessity': 'required',
                       'artifacts': []})
        activity = [r for r in progress.read(out) if r['event'] == 'stage.activity']
        self.assertEqual(len(activity), 1, 'said once, then quiet')
        self.assertEqual((activity[0]['programs'], activity[0]['stage']), ([], 'facts'))
        self.assertIn('ps exited with 1', activity[0]['reason'])
        self.assertEqual(progress.fold(progress.read(out))['stages'][0]['activity_note'], activity[0]['reason'])
        semgrep = {'name': 'semgrep-core', 'pid': 7, 'since': '2026-10-09T20:00:00+00:00'}
        seen = [[semgrep], [semgrep], [semgrep, {'name': 'trivy', 'pid': 9, 'since': '2026-10-09T20:00:02+00:00'}], []]
        stub = type('Stub', (), {'off': False, 'reason': '', 'sample': lambda self: seen.pop(0)})()
        clock, out = Clock(), Path(scratch())
        log = progress.ProgressLog(out, clock=clock, pulse=False, sampler=stub)
        log.started(STAGES, list(ORDER), {})
        log.stage_started('engines')
        log.tick()
        self.assertEqual(len(seen), 4, 'not before SAMPLE_EVERY seconds of the stage')
        for _ in range(4): clock.move(writer.SAMPLE_EVERY); log.tick()
        activity = [[p['name'] for p in r['programs']] for r in progress.read(out) if r['event'] == 'stage.activity']
        self.assertEqual(activity, [['semgrep-core'], ['semgrep-core', 'trivy'], []])
        log.ended({'stage': 'engines', 'status': 'ok', 'reason': '', 'seconds': 8.0, 'necessity': 'optional',
                   'artifacts': []})
        self.assertEqual({s['name']: s for s in progress.fold(progress.read(out))['stages']}['engines']['programs'], [])


class Liveness(unittest.TestCase):
    def test_a_quiet_run_beats_and_a_silent_one_is_judged_stalled(self):
        clock, out = Clock(), Path(scratch())
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
        out = Path(scratch())
        log = progress.ProgressLog(out, sampler=None, alive_every=0.2)
        log.started(STAGES, list(ORDER), {})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not any(r['event'] == 'run.alive'
                                                      for r in progress.read(out)): time.sleep(0.1)
        self.assertTrue(any(r['event'] == 'run.alive' for r in progress.read(out)))
        log.finish('STOPPED')
        log.thread.join(3)
        self.assertFalse(log.thread.is_alive())
        out = Path(scratch())
        progress.path_for(out).mkdir()                    # the path cannot be written as a file
        log = progress.ProgressLog(out, clock=Clock(), sampler=None)
        log.started(STAGES, list(ORDER), {})
        self.assertTrue(log.broken)
        self.assertIsNone(log.thread, 'no beat for a file nobody can read')
        self.assertFalse(log.tick())
        state = {'state': 'running', 'alive_every': 10.0}
        self.assertEqual(progress.judge(state, heard=1000.0, now=1029.9), 'running')
        self.assertEqual(progress.judge(state, heard=1000.0, now=1030.0), 'running')
        self.assertEqual(progress.judge(state, heard=1000.0, now=1030.1), 'stalled')
        self.assertEqual(progress.judge(state, heard=1000.0, now=1030.1, living=False), 'interrupted',
                         'a known death wins')
        self.assertEqual(progress.judge({'state': 'running'}, heard=1000.0, now=2000.0), 'running',
                         'a run that promised no heartbeat is not judged by its silence')
        self.assertEqual(progress.judge({**state, 'state': 'done'}, heard=1000.0, now=9999.0), 'done')
        self.assertEqual(progress.judge(state, heard=None, now=9999.0), 'running')


class Flows(unittest.TestCase):
    def test_each_flow_has_its_own_file_and_carries_the_last_runs_step_seconds(self):
        folder = Path(scratch())
        self.assertEqual(progress.path_for(folder), folder / 'run-progress.jsonl')
        self.assertEqual(progress.path_for(folder, 'setup'), folder / 'progress' / 'setup.jsonl')
        log = progress.ProgressLog(folder, 'safety', pulse=False, sampler=None)
        log.started(STAGES[:2], ['facts'], {})
        log.finish('COMPLETE')
        state = progress.fold(progress.read(folder, 'safety'))
        self.assertEqual((state['flow'], state['state'], progress.read(folder)), ('safety', 'done', []))
        out = Path(scratch())
        execute(project(), out, runners=stepping_runners())
        execute(project(), out, runners=stepping_runners())
        first = progress.read(out)[0]
        self.assertEqual(first['previous_steps']['facts'], {'syntax': 0.01, 'resolve': 0.01, 'graph': 0.01})
        self.assertEqual(progress.fold(progress.read(out))['previous_steps']['facts']['graph'], 0.01)


class GoldenFold(unittest.TestCase):
    """I4, the Python half: the fold of each recorded real run is the committed expected JSON."""

    def test_the_fold_of_every_recorded_run_equals_its_expected_json(self):
        self.assertEqual({p.stem for p in GOLDEN}, {'complete', 'stopped', 'killed'})
        for path in GOLDEN:
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            expected = json.loads(path.with_suffix('.fold.json').read_text(encoding='utf-8'))
            self.assertEqual(progress.fold(rows), expected, path.name)
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
        import progress_golden
        self.assertEqual(progress_golden.main(['check']), 0)


if __name__ == '__main__':
    unittest.main()
