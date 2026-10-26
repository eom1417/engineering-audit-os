"""A stage may fail, be absent, or be skipped. All three must be visible, and none may be silent."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos import pipeline
from eaos.pipeline import STAGES, SkipStage, again, check, execute, resume
from eaos.pipeline.run import MANIFEST
from eaos.pipeline import loops, stages as module
from eaos.pipeline.stages import OPTIONAL, REQUIRED, Stage
from eaos.pipeline.run import CHECKPOINT, FAILED, NOT_REACHED, OK, SKIPPED, UNAVAILABLE
from shared_fixture import scratch

# The stages of the optional loops a check runs only when the person switches them on (`try_layers`: the `layers` path).
OFF = loops.switched_off(['complete'])
RUN = len(STAGES) - len(OFF)


def fake_runners(**behaviour):
    """Every declared stage gets a runner that writes its artifacts; named ones misbehave."""
    runners = {}
    for stage in STAGES:
        def make(stage=stage):
            def run(context):
                problem = behaviour.get(stage.name)
                if problem is not None:
                    raise problem
                for artifact in stage.produces:
                    path = context.out / artifact
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('{}' if path.suffix == '.json' else 'x', encoding='utf-8')
                return {'stage': stage.name}
            return run
        runners[stage.name] = make()
    return runners


def recording(ran):
    runners = fake_runners()
    for name, runner in list(runners.items()):
        runners[name] = lambda context, name=name, runner=runner: ran.append(name) or runner(context)
    return runners


class DeclarationTests(unittest.TestCase):
    """The pipeline declaration must be sane before anything executes it."""

    def test_the_declared_pipeline_is_sane(self):
        self.assertEqual(pipeline.errors(), [])
        self.assertEqual(STAGES[0].requires, ())
        self.assertEqual(set(pipeline.dependents(STAGES[0].name)), {stage.name for stage in STAGES[1:]})
        for stage in STAGES:
            self.assertNotIn(stage.name, pipeline.dependents(stage.name))

    def test_the_checker_rejects_a_bad_declaration(self):
        def errors(stages):
            original, module.STAGES = module.STAGES, stages
            declared, loops.LOOPS = loops.LOOPS, (loops.Loop('all', tuple(stage.name for stage in stages)),)
            try:
                return module.errors()
            finally:
                module.STAGES, loops.LOOPS = original, declared
        cases = [((Stage('a', produces=('x',), requires=('b',)), Stage('b', produces=('y',))),
                  'a: requires b, which no earlier stage provides'),
                 ((Stage('a', produces=('x',)), Stage('b', produces=('x',))), 'b: x is already produced by a'),
                 ((Stage('a', produces=('x',), necessity=OPTIONAL),), 'a: optional without saying when it may be absent'),
                 ((Stage('a', produces=()),), 'a: produces nothing, so nothing can depend on it')]
        for stages, problem in cases:
            with self.subTest(problem):
                self.assertIn(problem, errors(stages))
        self.assertEqual(errors((Stage('a', produces=('x',)), Stage('b', produces=('y',), requires=('a',), necessity=REQUIRED))), [])


class ExecutionTests(unittest.TestCase):
    def _run(self, **options):
        directory = scratch()
        manifest = execute('.', directory, **options)
        return manifest, Path(directory)

    def test_a_clean_run_marks_every_stage_ok_with_its_necessity(self):
        manifest, out = self._run(runners=fake_runners())
        self.assertEqual(manifest['status'], 'COMPLETE')
        self.assertEqual(manifest['counts'][OK], RUN)
        self.assertTrue((out / MANIFEST).is_file())
        for name, row in manifest['stages'].items():
            self.assertIn(row['necessity'], ('required', 'optional'), name)

    def test_a_failure_is_contained_and_its_dependents_say_why_they_did_not_run(self):
        manifest, _ = self._run(runners=fake_runners(probe=RuntimeError('boom')))
        self.assertEqual(manifest['stages']['probe']['status'], FAILED)
        self.assertIn('boom', manifest['stages']['probe']['reason'])
        self.assertEqual(manifest['stages']['measure']['status'], OK)
        self.assertEqual(manifest['status'], 'INCOMPLETE')
        for name in ('plan', 'target', 'reports'):
            self.assertEqual(manifest['stages'][name]['status'], NOT_REACHED, name)
            self.assertIn('probe', manifest['stages'][name]['reason'])
        runners = fake_runners()
        runners['policy'] = lambda context: {}
        manifest, _ = self._run(runners=runners)
        self.assertEqual(manifest['stages']['policy']['status'], FAILED)
        self.assertIn('declared artifacts were not written', manifest['stages']['policy']['reason'])

    def test_an_absent_or_skipped_stage_says_so_and_a_bad_request_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = execute('.', directory, runners=fake_runners(semantic=SkipStage('no provider')))
            written = json.loads((Path(directory) / MANIFEST).read_text(encoding='utf-8'))
        self.assertEqual((manifest['stages']['semantic']['status'], manifest['stages']['semantic']['reason']),
                         (UNAVAILABLE, 'no provider'))
        self.assertEqual(manifest['status'], 'COMPLETE')
        self.assertIn('did not run', written['limits'])
        # the assistant the check was given stopped midway (its limit, 2026-10-18): the stages after it still run, but
        # the check is PARTIAL, never COMPLETE, and the lost stage says when the assistant comes back
        lost = SkipStage('during the check Claude Code stopped answering (claude_limit)', code='claude_limit',
                         lost={'assistant': 'claude', 'resets': '7:10pm (UTC)'})
        with tempfile.TemporaryDirectory() as directory:
            manifest = execute('.', directory, runners=fake_runners(ideal=lost))
        row = manifest['stages']['ideal']
        self.assertEqual((row['status'], row['reason_code'], row['detail']['assistant_lost']['resets']), (UNAVAILABLE, 'claude_limit', '7:10pm (UTC)'))
        self.assertEqual(manifest['status'], 'PARTIAL')
        self.assertEqual(manifest['stages']['order']['status'], OK, 'what comes after a lost stage still runs')
        with tempfile.TemporaryDirectory() as directory:     # the lost stage keeps its earlier time for the estimate
            execute('.', directory, runners=fake_runners())
            execute('.', directory, runners=fake_runners(ideal=lost))
            from eaos.core.progress.log import previous_seconds
            self.assertIn('ideal', previous_seconds(directory))
        manifest, _ = self._run(only=['facts'], runners=fake_runners())
        self.assertEqual(manifest['stages']['facts']['status'], OK)
        self.assertEqual((manifest['stages']['claims']['status'], manifest['stages']['claims']['reason']),
                         (SKIPPED, 'not requested in this run'))
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            execute('.', directory, only=['nonexistent'], runners=fake_runners())
        with self.assertRaises(ValueError):
            execute('.', 'eaos/pipeline', runners=fake_runners())


class ResumeTests(unittest.TestCase):
    def test_a_tool_that_failed_is_said_and_run_again_alone_with_what_reads_it(self):
        # CodeQL failed in a 1 h 46 min check while the engines stage said ok: the check is partial and says which,
        # then the engines and the stages reading them run again, and the screens, the app and the rest are kept.
        runners = fake_runners()
        engines = runners['engines']
        runners['engines'] = lambda context: {**engines(context), 'tools_failed': {'codeql': 'autobuild exit 1'}}
        with tempfile.TemporaryDirectory() as directory:
            first = execute('.', directory, runners=runners)
            self.assertEqual(first['status'], 'PARTIAL')
            self.assertEqual(first['stages']['engines']['reason_code'], 'tools_failed')
            self.assertIn('codeql', first['stages']['engines']['reason'])
            ran = []
            second = again('.', directory, 'engines', runners=recording(ran))
        self.assertEqual(set(ran), {'engines', *pipeline.dependents('engines', reading=True)} - OFF)
        self.assertIn('triage', ran)
        self.assertNotIn('screens', ran)
        self.assertEqual(second['status'], 'COMPLETE')
        self.assertEqual(second['counts'][OK], RUN)

    def test_a_failed_or_stopped_run_resumes_where_it_did_not_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            execute('.', directory, runners=fake_runners(probe=RuntimeError('boom')))
            ran = []
            second = resume('.', directory, runners=recording(ran))
        self.assertNotIn('facts', ran)
        self.assertIn('probe', ran)
        self.assertEqual(second['counts'][OK], RUN)
        self.assertIn('resumed_from', second)
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(resume('.', directory, runners=fake_runners())['counts'][OK], RUN)
        # A run stopped midway resumes from where it stopped.
        order = [stage.name for stage in STAGES]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(KeyboardInterrupt):
                execute('.', directory, runners=fake_runners(probe=KeyboardInterrupt()))
            self.assertFalse((Path(directory) / MANIFEST).exists())
            stages = json.loads((Path(directory) / CHECKPOINT).read_text(encoding='utf-8'))['stages']
            ran = []
            second = resume('.', directory, runners=recording(ran))
            # only what did not end ok runs again, once each, in the declared order of what waits for what
            self.assertEqual(sorted(ran), sorted(n for n in order if stages.get(n, {}).get('status') != OK and n not in OFF))
            self.assertIn('probe', ran)
            self.assertEqual(second['counts'][OK], RUN)
            self.assertFalse((Path(directory) / CHECKPOINT).exists())
        # Stopped in an AI stage: going on (Retry) resumes at it and never asks a finished one again.
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(KeyboardInterrupt):
                execute('.', directory, runners=fake_runners(ideal=KeyboardInterrupt()))
            ran = []
            second = check('.', directory, go_on=True, runners=recording(ran))
        self.assertEqual(ran[0], 'ideal')
        self.assertFalse({'semantic', 'triage'} & set(ran), 'a finished AI stage was asked again')
        self.assertEqual(second['counts'][OK], RUN)
        # A new check after one stopped starts from nothing (a full-stack app, 2026-10-21: it went on at 31 of 37 stages).
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(KeyboardInterrupt):
                execute('.', directory, runners=fake_runners(ideal=KeyboardInterrupt()))
            ran = []
            check('.', directory, runners=recording(ran))
        self.assertEqual(sorted(ran), sorted(set(order) - OFF), 'every stage ran again')

    def test_one_stage_reruns_alone_when_its_inputs_are_on_disk_and_not_otherwise(self):
        with tempfile.TemporaryDirectory() as directory:
            execute('.', directory, runners=fake_runners())
            ran = []
            manifest = execute('.', directory, only=['plan'], runners=recording(ran))
        self.assertEqual(ran, ['plan'])
        self.assertEqual((manifest['stages']['plan']['status'], manifest['status']), (OK, 'PARTIAL'))
        with tempfile.TemporaryDirectory() as directory:
            manifest = execute('.', directory, only=['plan'], runners=fake_runners())
        self.assertEqual(manifest['stages']['plan']['status'], NOT_REACHED)
        self.assertIn('Prerequisites not completed', manifest['stages']['plan']['reason'])


class LoopTests(unittest.TestCase):
    """The check runs as loops (eaos/pipeline/loops.py): a loop judges its exit when its stages ended, runs what it broke
    again while its rounds last, and an optional loop runs only when the check switches it on."""

    def test_a_broken_app_stage_runs_again_and_no_other_loop_builds_on_the_broken_round(self):
        tries, runners = [], fake_runners()
        def screens(context, first=runners['screens']):
            tries.append('screens')
            if len(tries) == 1: raise RuntimeError('the browser timed out')
            return first(context)
        runners['screens'] = screens
        manifest = execute('.', scratch(), runners=runners, mode='normal')
        self.assertEqual(len(tries), 2)
        self.assertEqual(manifest['stages']['screens']['status'], OK)
        self.assertEqual(manifest['stages']['visual']['status'], OK)      # it requires screens: it waited for the round
        self.assertEqual(manifest['loops']['run_and_see'], {'state': 'met', 'stages': [], 'rounds': 2})
        self.assertEqual(manifest['status'], 'COMPLETE')

    def test_a_loop_says_what_its_goal_lacked_and_one_not_met_stops_the_check_when_declared(self):
        directory = scratch()
        manifest = execute('.', directory, runners=fake_runners(setup=SkipStage('the app did not start', code='app_not_running')))
        self.assertEqual(manifest['loops']['run_and_see']['state'], 'explained')
        self.assertEqual(manifest['loops']['run_and_see']['stages'], ['setup'])
        # the coverage ledger: a gap the person did not choose is big, and RUN.md says it in red at its top
        self.assertEqual([entry['loop'] for entry in manifest['coverage'] if entry['big']], ['run_and_see'])
        self.assertIn('🔴', (Path(directory) / 'RUN.md').read_text(encoding='utf-8').split('##')[0])
        manifest = execute('.', scratch(), runners=fake_runners(setup=SkipStage('no consent', code='no_run_consent')))
        self.assertEqual([entry['loop'] for entry in manifest['coverage'] if entry['big']], [])     # the person's choice
        manifest = execute('.', scratch(), runners=fake_runners(facts=RuntimeError('boom')))
        self.assertEqual(manifest['loops']['understand'], {'state': 'not_met', 'stages': ['facts'], 'rounds': 1, 'on_fail': 'stop'})

    def test_an_optional_loop_runs_only_when_the_check_switches_it_on(self):
        from eaos.pipeline.path_choice import resolve
        declared, loops.LOOPS = loops.LOOPS, (*loops.LOOPS, loops.Loop('try', ('visual',), switch='look'))
        try:
            self.assertEqual(resolve(['complete', 'look'])['paths'], ['complete', 'look'])
            manifest = execute('.', scratch(), runners=fake_runners())
            self.assertEqual(manifest['stages']['visual']['reason_code'], 'loop_off')
            manifest = execute('.', scratch(), runners=fake_runners(), paths=['complete', 'look'])
            self.assertEqual(manifest['stages']['visual']['status'], OK)
            # asked for by the person (`eaos check --path complete layers`): the option reached the run (M6, 2026-10-25)
            from eaos.pipeline.run import check
            manifest = check('.', scratch(), runners=fake_runners(), paths=['complete', 'look'])
            self.assertEqual(manifest['stages']['visual']['status'], OK)
        finally:
            loops.LOOPS = declared
