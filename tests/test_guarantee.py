"""Guarantee: simulator predictions vs. observed indicator deltas."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from shared_fixture import Workspace
from eaos.audit import run as run_audit
from eaos.guarantee import compare


class GuaranteeTests(Workspace):

    def test_identical_snapshots_produce_honest_results(self):
        a = Path(self.tmp) / 'a'; b = Path(self.tmp) / 'b'
        run_audit(Path('tests/fixtures/sustainability'), a, language='en')
        run_audit(Path('tests/fixtures/sustainability'), b, language='en')
        result = compare(a, b, language='en')
        for row in result['rows']:
            if row['verdict'] != 'HONEST':
                # With identical snapshots, predicted improvement is -current, observed is 0; overstatement is expected.
                self.assertEqual(row['verdict'], 'OVERSTATED')

    def test_tolerance_zeros_out_all_differences(self):
        a = Path(self.tmp) / 'a'; b = Path(self.tmp) / 'b'
        run_audit(Path('tests/fixtures/sustainability'), a, language='en')
        run_audit(Path('tests/fixtures/sustainability'), b, language='en')
        # Tolerance of 1.0 swallows everything
        result = compare(a, b, tolerance=1.0, language='en')
        for row in result['rows']:
            self.assertEqual(row['verdict'], 'HONEST')

    def test_returns_artifact_path(self):
        a = Path(self.tmp) / 'a'; b = Path(self.tmp) / 'b'
        run_audit(Path('tests/fixtures/sustainability'), a, language='en')
        run_audit(Path('tests/fixtures/sustainability'), b, language='en')
        result = compare(a, b, language='en')
        self.assertTrue(Path(result['artifact']).is_file())
        content = Path(result['artifact']).read_text()
        self.assertIn('Verification guarantee', content)


class GuaranteeLimitationsTests(Workspace):
    def test_guarantee_does_not_run_runtime_checks(self):
        from eaos import guarantee
        self.assertIn('structural indicator deltas', ' '.join(guarantee.LIMITATIONS))


class ExecutedStageTests(unittest.TestCase):
    """A prediction is only worth something once something actually happened and was measured.

    Every other test here compares a report with itself or with a tolerance wide enough to swallow
    the difference. This one takes a project with a real duplicate, records what the plan says
    removing it will do, removes it, audits again, and asks whether the plan was right.
    """

    SHARED = ('def normalise(value):\n'
              '    trimmed = str(value).strip().lower()\n'
              '    return trimmed.replace(" ", "-")\n')

    def _project(self, root, duplicated):
        root.mkdir(parents=True, exist_ok=True)
        (root / 'alpha').mkdir(exist_ok=True)
        (root / 'beta').mkdir(exist_ok=True)
        (root / 'alpha/__init__.py').write_text('', encoding='utf-8')
        (root / 'beta/__init__.py').write_text('', encoding='utf-8')
        (root / 'alpha/shared.py').write_text(self.SHARED, encoding='utf-8')
        if duplicated:
            # The same definition a second time: the duplicate the plan proposes to canonicalize.
            (root / 'beta/shared.py').write_text(self.SHARED, encoding='utf-8')
        else:
            (root / 'beta/shared.py').write_text('from alpha.shared import normalise\n', encoding='utf-8')
        (root / 'alpha/main.py').write_text(
            'from alpha.shared import normalise\n\n\ndef main():\n    return normalise("A B")\n',
            encoding='utf-8')
        (root / 'beta/main.py').write_text(
            'from beta.shared import normalise\n\n\ndef main():\n    return normalise("C D")\n',
            encoding='utf-8')
        return root

    def test_a_stage_that_was_really_executed_gets_a_verdict_per_indicator(self):
        from eaos.guarantee import predict
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            before_src = self._project(tmp / 'before', duplicated=True)
            after_src = self._project(tmp / 'after', duplicated=False)
            before_out, after_out = tmp / 'r-before', tmp / 'r-after'
            run_audit(before_src, before_out, language='en')
            run_audit(after_src, after_out, language='en')

            plan = json.loads((before_out / 'transform-plan.json').read_text(encoding='utf-8'))
            stages = plan.get('stages') or []
            if not stages:
                self.skipTest('the fixture produced no transform stage to predict about')
            prediction_path = tmp / 'prediction.json'
            predict(before_out, stages[0], prediction_path)

            result = compare(before_out, after_out, tolerance=0.0, prediction=prediction_path)
            # Asserted while the tree still exists: the artifacts are the point, not the return value.
            self.assertTrue((after_out / 'guarantee.json').is_file())
            self.assertTrue((after_out / 'GUARANTEE.md').is_file())
            written = json.loads((after_out / 'guarantee.json').read_text(encoding='utf-8'))
            self.assertEqual(written['rows'], result['rows'])

        self.assertEqual(result['status'], 'COMPARED', result['reasons'])
        self.assertTrue(result['rows'], 'an executed stage must produce at least one compared row')
        verdicts = {row['verdict'] for row in result['rows']}
        self.assertTrue(verdicts <= {'HONEST', 'OVERSTATED', 'UNDERSTATED'}, verdicts)
        for row in result['rows']:
            # Both sides are real measurements; neither may be carried over from the prediction.
            self.assertIsNotNone(row['observed'])
            self.assertEqual(row['difference'], round(row['predicted'] - row['observed'], 4))

    def test_a_prediction_from_another_snapshot_is_refused_rather_than_compared(self):
        # The cheapest way to fake a guarantee is to compare a prediction against a tree it was
        # never made about. The snapshot check is what makes the verdict mean anything.
        from eaos.guarantee import predict
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            first = self._project(tmp / 'first', duplicated=True)
            other = self._project(tmp / 'other', duplicated=False)
            first_out, other_out, after_out = tmp / 'r1', tmp / 'r2', tmp / 'r3'
            run_audit(first, first_out, language='en')
            run_audit(other, other_out, language='en')
            run_audit(other, after_out, language='en')
            stages = json.loads((first_out / 'transform-plan.json').read_text(encoding='utf-8')).get('stages') or []
            if not stages:
                self.skipTest('the fixture produced no transform stage to predict about')
            prediction_path = tmp / 'prediction.json'
            predict(first_out, stages[0], prediction_path)
            result = compare(other_out, after_out, prediction=prediction_path)
        self.assertEqual(result['status'], 'UNAVAILABLE')
        self.assertEqual(result['rows'], [])
        self.assertTrue(any('different source snapshot' in reason for reason in result['reasons']),
                        result['reasons'])


class RecordedPredictionTests(unittest.TestCase):
    """The transform stage writes down its claim before anything changes."""

    def test_predictions_are_recorded_with_a_budget_that_states_where_it_stopped(self):
        from eaos.guarantee import record_predictions
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            source = ExecutedStageTests()._project(tmp / 'src', duplicated=True)
            out = tmp / 'out'
            run_audit(source, out, language='en')
            plan = json.loads((out / 'transform-plan.json').read_text(encoding='utf-8'))
            fake = {'stages': [dict(plan['stages'][0]) for _ in range(3)] if plan.get('stages') else []}
            self.assertTrue(fake['stages'], 'the duplicate fixture must yield a transform stage')
            summary = record_predictions(out, fake, budget=2)
            record = json.loads((out / 'predictions.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['recorded'], 2)
        self.assertEqual(record['stages_in_plan'], 3)
        # Silence about the third stage would read as "nothing to predict".
        self.assertTrue(any('beyond the budget' in row['reason'] for row in record['skipped']),
                        record['skipped'])
        self.assertIn('before_snapshot', record)

    def test_recording_a_prediction_never_touches_the_analysed_repository(self):
        # The analysed tree is untrusted input. A stage that predicts by trying the change would
        # make the audit a writer, and this claim is the only thing standing between the two.
        from eaos.guarantee import record_predictions
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            source = ExecutedStageTests()._project(tmp / 'src', duplicated=True)
            out = tmp / 'out'
            run_audit(source, out, language='en')
            before = {path.relative_to(source): path.read_bytes()
                      for path in sorted(source.rglob('*')) if path.is_file()}
            plan = json.loads((out / 'transform-plan.json').read_text(encoding='utf-8'))
            record_predictions(out, plan)
            after = {path.relative_to(source): path.read_bytes()
                     for path in sorted(source.rglob('*')) if path.is_file()}
        self.assertEqual(before, after, 'predicting must not edit, add or delete a source file')
