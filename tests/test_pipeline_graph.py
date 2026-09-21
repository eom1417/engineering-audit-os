"""The pipeline declaration must be sane before anything executes it."""
import unittest

from eaos import pipeline
from eaos.pipeline.stages import OPTIONAL, REQUIRED, Stage


class DeclarationTests(unittest.TestCase):
    def test_the_declared_pipeline_has_no_structural_problems(self):
        self.assertEqual(pipeline.errors(), [])

    def test_no_stage_requires_something_declared_after_it(self):
        seen = set()
        for stage in pipeline.STAGES:
            for need in stage.requires:
                self.assertIn(need, seen, f'{stage.name} requires {need}, declared later')
            seen.add(stage.name)

    def test_the_order_is_acyclic_by_construction(self):
        for stage in pipeline.STAGES:
            self.assertNotIn(stage.name, pipeline.dependents(stage.name))

    def test_every_artifact_has_exactly_one_owner(self):
        owners = {}
        for stage in pipeline.STAGES:
            for artifact in stage.produces:
                self.assertNotIn(artifact, owners, f'{artifact} produced by two stages')
                owners[artifact] = stage.name

    def test_an_optional_stage_must_say_when_it_may_be_absent(self):
        for stage in pipeline.STAGES:
            if stage.necessity == OPTIONAL:
                self.assertTrue(stage.absent_when.strip(), f'{stage.name} is optional without a reason')

    def test_the_first_stage_depends_on_nothing_and_everything_else_reaches_it(self):
        self.assertEqual(pipeline.STAGES[0].requires, ())
        reachable = set(pipeline.dependents(pipeline.STAGES[0].name))
        self.assertEqual(reachable, {stage.name for stage in pipeline.STAGES[1:]})


class ValidatorTests(unittest.TestCase):
    """The declaration checker has to actually reject a bad declaration."""

    def _with(self, stages):
        from eaos.pipeline import stages as module
        original = module.STAGES
        module.STAGES = stages
        try:
            return module.errors()
        finally:
            module.STAGES = original

    def test_a_forward_reference_is_reported(self):
        problems = self._with((Stage('a', produces=('x',), requires=('b',)), Stage('b', produces=('y',))))
        self.assertIn('a: requires b, which no earlier stage provides', problems)

    def test_two_stages_producing_one_artifact_is_reported(self):
        problems = self._with((Stage('a', produces=('x',)), Stage('b', produces=('x',))))
        self.assertIn('b: x is already produced by a', problems)

    def test_an_optional_stage_without_a_reason_is_reported(self):
        problems = self._with((Stage('a', produces=('x',), necessity=OPTIONAL),))
        self.assertIn('a: optional without saying when it may be absent', problems)

    def test_a_stage_that_produces_nothing_is_reported(self):
        problems = self._with((Stage('a', produces=()),))
        self.assertIn('a: produces nothing, so nothing can depend on it', problems)

    def test_a_sane_declaration_produces_no_problems(self):
        self.assertEqual(self._with((Stage('a', produces=('x',)),
                                     Stage('b', produces=('y',), requires=('a',), necessity=REQUIRED))), [])
