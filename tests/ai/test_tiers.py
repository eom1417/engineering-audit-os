"""Model tiers (M9.1, eaos/ai/assistant/tiers.py): each stage asks on its tier, a cheaper tier that fails or would close
something is asked again a tier up, and each assistant is told its tier's model or effort."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eaos.ai import nodes
from eaos.ai.assistant import headless as adapters, tiers
from eaos.ai.ideal import prompts as ideal_prompts
from tests.ai.test_ai_nodes import Answer, _nodes_report, decision


class Tiered(Answer):
    """The person's assistant on a tier: `make(tier)` answers, or raises, for the tier it is asked on."""
    tier = None

    def __init__(self, make):
        super().__init__(lambda name, schema: make(self.tier))
        self.tiers = []

    def __call__(self, name, prompt, schema):
        self.tiers.append(self.tier)
        return super().__call__(name, prompt, schema)


class Stages(unittest.TestCase):
    def test_each_stage_has_its_tier_and_the_speed_mode_lowers_only_the_standard_ones(self):
        self.assertEqual([tiers.tier_of(s) for s in ('card_triage', 'plan_orderer', 'ideal_planner', 'a_new_stage')],
                         ['light', 'standard', 'deep', 'deep'])
        self.assertEqual([tiers.tier_of(s, 'speed') for s in ('plan_orderer', 'ideal_planner')], ['light', 'deep'])
        with mock.patch.dict(os.environ, {'EAOS_TIER_IDEAL_PLANNER': 'standard'}):
            self.assertEqual(tiers.tier_of('ideal_planner'), 'standard')
        with mock.patch.dict(os.environ, {'EAOS_TIER_IDEAL_PLANNER': 'cheap'}), self.assertRaises(ValueError):
            tiers.tier_of('ideal_planner')
        self.assertEqual([tiers.up(t) for t in tiers.TIERS], ['standard', 'deep', None])

    def test_each_assistant_is_told_its_tiers_model_or_effort(self):
        with mock.patch.dict(os.environ, {}, clear=False) as env:
            env.pop('EAOS_CLAUDE_MODEL', None)
            claude = adapters.ClaudeCode(command=['claude'])
            self.assertEqual(claude.ask_argv({}, Path('.'), (), 'light')[-4:-2], ['--model', 'haiku'])
            self.assertNotIn('--model', claude.ask_argv({}, Path('.'), (), 'deep'), "the deep tier is the person's own model")
            with mock.patch.dict(os.environ, {'EAOS_CLAUDE_MODEL_STANDARD': 'opus'}):
                self.assertIn('opus', claude.ask_argv({}, Path('.'), (), 'standard'))
        with tempfile.TemporaryDirectory() as folder:
            argv = adapters.Codex(command=['codex']).ask_argv({}, Path(folder), (), 'light')
            self.assertIn('model_reasoning_effort="low"', argv)

    def test_the_ideal_critique_is_held_short_so_its_answer_parses_the_first_time(self):
        # EAOS on itself (2026-10-22): an unbounded critique wrote 60 KB that broke as JSON twice, three minutes lost.
        missed = ideal_prompts.CRITIQUE_SCHEMA['properties']['critique']['properties']['missed']
        self.assertEqual(missed['maxItems'], ideal_prompts.NOTES)
        self.assertIn(f'under {ideal_prompts.NOTE_CHARS} characters', ideal_prompts.prompt_critique({'project': {'language': 'en'}}, {}))


class Escalation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.report, _ = _nodes_report(Path(self.tmp.name))

    def triage(self, launcher):
        return nodes.run(self.report, names=['card_triage'], launcher=launcher, fresh=True)['card_triage']

    def test_a_card_the_light_tier_would_set_aside_is_judged_again_on_the_deep_tier(self):
        def make(tier):
            if tier == 'light': return {'summary': '', 'decisions': [decision('TASK-001', 'reject', ['TASK-001'])]}
            return {'summary': '', 'decisions': [decision('TASK-001', 'confirm', ['TASK-001'], detail={'harmed': 'the app users'})]}
        launcher = Tiered(make)
        record = self.triage(launcher)
        self.assertEqual(launcher.tiers[0], 'light')
        self.assertEqual((record['tier'], record['escalated']['to']), ('deep', 'deep'))
        self.assertEqual(next(d for d in record['decisions'] if d['subject'] == 'TASK-001')['decision'], 'confirm',
                         'a cheaper model never closes a card alone')

    def test_a_tier_that_fails_is_asked_again_one_tier_up_before_the_rules_decide(self):
        def make(tier):
            if tier == 'light': raise ValueError('not the asked JSON')
            return {'summary': '', 'decisions': [decision('TASK-001', 'confirm', ['TASK-001'], detail={'harmed': 'the app users'})]}
        record = self.triage(Tiered(make))
        self.assertEqual((record['method'], record['tier'], record['escalated']['from']), ('model', 'standard', 'light'))

    def test_a_tier_reached_after_a_failure_still_never_closes_alone(self):
        # the review of M9.1: light failed, standard answered "reject", and the reject stood without the deep tier
        def make(tier):
            if tier == 'light': raise ValueError('not the asked JSON')
            choice = 'confirm' if tier == 'deep' else 'reject'
            return {'summary': '', 'decisions': [decision('TASK-001', choice, ['TASK-001'], detail={'harmed': 'the app users'})]}
        launcher = Tiered(make)
        record = self.triage(launcher)
        self.assertEqual((launcher.tiers[:3], record['tier']), (['light', 'standard', 'deep'], 'deep'))
        self.assertEqual(next(d for d in record['decisions'] if d['subject'] == 'TASK-001')['decision'], 'confirm')


if __name__ == '__main__':
    unittest.main()
