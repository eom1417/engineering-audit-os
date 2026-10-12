"""A stage may fail, be absent, or be skipped. All three must be visible, and none may be silent."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos import pipeline
from eaos.pipeline import MANIFEST, STAGES, SkipStage, check, execute, resume
from eaos.pipeline import stages as module
from eaos.pipeline.stages import OPTIONAL, REQUIRED, Stage
from eaos.pipeline.run import CHECKPOINT, FAILED, NOT_REACHED, OK, SKIPPED, UNAVAILABLE


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
            try:
                return module.errors()
            finally:
                module.STAGES = original
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
        directory = tempfile.mkdtemp()
        manifest = execute('.', directory, **options)
        return manifest, Path(directory)

    def test_a_clean_run_marks_every_stage_ok_with_its_necessity(self):
        manifest, out = self._run(runners=fake_runners())
        self.assertEqual(manifest['status'], 'COMPLETE')
        self.assertEqual(manifest['counts'][OK], len(STAGES))
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
        manifest, _ = self._run(only=['facts'], runners=fake_runners())
        self.assertEqual(manifest['stages']['facts']['status'], OK)
        self.assertEqual((manifest['stages']['claims']['status'], manifest['stages']['claims']['reason']),
                         (SKIPPED, 'not requested in this run'))
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            execute('.', directory, only=['nonexistent'], runners=fake_runners())
        with self.assertRaises(ValueError):
            execute('.', 'eaos/pipeline', runners=fake_runners())


class ResumeTests(unittest.TestCase):
    def test_a_failed_or_stopped_run_resumes_where_it_did_not_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            execute('.', directory, runners=fake_runners(probe=RuntimeError('boom')))
            ran = []
            second = resume('.', directory, runners=recording(ran))
        self.assertNotIn('facts', ran)
        self.assertIn('probe', ran)
        self.assertEqual(second['counts'][OK], len(STAGES))
        self.assertIn('resumed_from', second)
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(resume('.', directory, runners=fake_runners())['counts'][OK], len(STAGES))
        # A run stopped midway resumes from where it stopped.
        order = [stage.name for stage in STAGES]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(KeyboardInterrupt):
                execute('.', directory, runners=fake_runners(probe=KeyboardInterrupt()))
            self.assertFalse((Path(directory) / MANIFEST).exists())
            ran = []
            second = resume('.', directory, runners=recording(ran))
            self.assertEqual(ran, order[order.index('probe'):])
            self.assertEqual(second['counts'][OK], len(STAGES))
            self.assertFalse((Path(directory) / CHECKPOINT).exists())
        # Stopped in an AI stage: it resumes at it and never asks a finished one again.
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(KeyboardInterrupt):
                execute('.', directory, runners=fake_runners(ideal=KeyboardInterrupt()))
            ran = []
            second = check('.', directory, runners=recording(ran))
        self.assertEqual(ran[0], 'ideal')
        self.assertFalse({'semantic', 'triage'} & set(ran), 'a finished AI stage was asked again')
        self.assertEqual(second['counts'][OK], len(STAGES))

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
