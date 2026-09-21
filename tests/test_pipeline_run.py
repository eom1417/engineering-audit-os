"""A stage may fail, be absent, or be skipped. All three must be visible, and none may be silent."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.pipeline import MANIFEST, STAGES, SkipStage, execute, resume
from eaos.pipeline.run import FAILED, NOT_REACHED, OK, SKIPPED, UNAVAILABLE


def writer(*, raises=None, writes=True):
    """A fake runner that writes the artifacts its stage declares, unless told otherwise."""
    def run(context, _stage=None):
        if raises is not None:
            raise raises
        return {}
    return run


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
                    path.write_text('x', encoding='utf-8')
                return {'stage': stage.name}
            return run
        runners[stage.name] = make()
    return runners


class ExecutionTests(unittest.TestCase):
    def _run(self, **options):
        directory = tempfile.mkdtemp()
        manifest = execute('.', directory, **options)
        return manifest, Path(directory)

    def test_a_clean_run_marks_every_stage_ok(self):
        manifest, out = self._run(runners=fake_runners())
        self.assertEqual(manifest['status'], 'COMPLETE')
        self.assertEqual(manifest['counts'][OK], len(STAGES))
        self.assertTrue((out / MANIFEST).is_file())

    def test_a_failing_stage_does_not_take_the_independent_stages_with_it(self):
        manifest, _ = self._run(runners=fake_runners(probe=RuntimeError('boom')))
        self.assertEqual(manifest['stages']['probe']['status'], FAILED)
        self.assertIn('boom', manifest['stages']['probe']['reason'])
        self.assertEqual(manifest['stages']['sustainability']['status'], OK)
        self.assertEqual(manifest['status'], 'INCOMPLETE')

    def test_the_dependents_of_a_failed_stage_are_recorded_not_left_blank(self):
        manifest, _ = self._run(runners=fake_runners(probe=RuntimeError('boom')))
        for name in ('plan', 'compose', 'site', 'validate'):
            self.assertEqual(manifest['stages'][name]['status'], NOT_REACHED, name)
            self.assertIn('probe', manifest['stages'][name]['reason'])

    def test_a_stage_that_does_not_apply_is_unavailable_with_its_reason(self):
        manifest, _ = self._run(runners=fake_runners(semantic=SkipStage('no provider')))
        self.assertEqual(manifest['stages']['semantic']['status'], UNAVAILABLE)
        self.assertEqual(manifest['stages']['semantic']['reason'], 'no provider')
        self.assertEqual(manifest['status'], 'COMPLETE')

    def test_a_runner_that_writes_nothing_fails_even_when_it_returns_cleanly(self):
        runners = fake_runners()
        runners['policy'] = lambda context: {}
        manifest, _ = self._run(runners=runners)
        self.assertEqual(manifest['stages']['policy']['status'], FAILED)
        self.assertIn('declared artifacts were not written', manifest['stages']['policy']['reason'])

    def test_a_stage_left_out_of_the_run_says_so(self):
        manifest, _ = self._run(only=['facts'], runners=fake_runners())
        self.assertEqual(manifest['stages']['facts']['status'], OK)
        self.assertEqual(manifest['stages']['claims']['status'], SKIPPED)
        self.assertEqual(manifest['stages']['claims']['reason'], 'not requested in this run')

    def test_an_unknown_stage_name_is_refused_rather_than_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                execute('.', directory, only=['nonexistent'], runners=fake_runners())

    def test_output_inside_the_target_is_refused(self):
        with self.assertRaises(ValueError):
            execute('.', 'eaos/pipeline', runners=fake_runners())

    def test_every_row_carries_the_stage_necessity_so_absence_can_be_judged(self):
        manifest, _ = self._run(runners=fake_runners())
        for name, row in manifest['stages'].items():
            self.assertIn(row['necessity'], ('required', 'optional'), name)


class ResumeTests(unittest.TestCase):
    def test_resume_reruns_only_what_did_not_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            first = execute('.', directory, runners=fake_runners(probe=RuntimeError('boom')))
            self.assertEqual(first['stages']['probe']['status'], FAILED)
            ran = []
            runners = fake_runners()
            for name, runner in list(runners.items()):
                def wrap(context, name=name, runner=runner):
                    ran.append(name)
                    return runner(context)
                runners[name] = wrap
            second = resume('.', directory, runners=runners)
            self.assertNotIn('facts', ran)
            self.assertIn('probe', ran)
            self.assertEqual(second['stages']['facts']['status'], OK)
            self.assertEqual(second['stages']['probe']['status'], OK)
            self.assertEqual(second['counts'][OK], len(STAGES))
            self.assertIn('resumed_from', second)

    def test_resume_without_a_previous_manifest_runs_everything(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = resume('.', directory, runners=fake_runners())
            self.assertEqual(manifest['counts'][OK], len(STAGES))


class ManifestTests(unittest.TestCase):
    def test_the_manifest_states_what_a_run_could_not_see(self):
        with tempfile.TemporaryDirectory() as directory:
            execute('.', directory, runners=fake_runners(semantic=SkipStage('no provider')))
            manifest = json.loads((Path(directory) / MANIFEST).read_text(encoding='utf-8'))
        self.assertIn('limits', manifest)
        self.assertIn('did not run', manifest['limits'])
