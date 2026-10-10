"""NS46.T21 owner-request acceptance (owner, 2026-10-10: AI in every step where the outcome is better with it),
planned 2026-10-10: one real `eaos start --yes` check with the person's assistant.

The evidence is $EAOS_MEASURE/ai-in-the-pipeline/run-manifest.json, the manifest of that check copied as written. A
fake provider never counts: each AI stage must have ended ok with its own calls to a named assistant.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import north_star_measure as measure

AI_STAGES = ('semantic', 'triage', 'ideal', 'order')


class AiInThePipeline(unittest.TestCase):
    def test_every_ai_stage_ran_on_a_real_check_with_the_assistant(self):
        path = measure.REPORTS / 'ai-in-the-pipeline/run-manifest.json'
        self.assertTrue(path.is_file(), f'no evidence at {path}')
        manifest = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(manifest.get('status'), 'COMPLETE')
        for name in AI_STAGES:
            stage = manifest['stages'].get(name) or {}
            detail = stage.get('detail') or {}
            self.assertEqual(stage.get('status'), 'ok', f'{name}: {stage.get("reason")}')
            self.assertGreaterEqual(detail.get('calls') or 0, 1, name)
            if name != 'semantic': self.assertTrue(detail.get('assistant'), name)
