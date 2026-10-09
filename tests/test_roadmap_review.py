"""tools/roadmap_review.py (NS46.T16): the roadmap's proposals stand on ids of the plan, are decisions for the owner,
and never change docs/north-star.json."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import roadmap_review  # noqa: E402


def proposal(pid, cites, kind='merge'):
    return {'id': pid, 'kind': kind, 'title': f'Proposal {pid}', 'detail': 'what changes', 'cites': cites,
            'recommendation': 'approve: it saves a step', 'risk': 'none known', 'confidence': 0.6}


class FakeLauncher:
    assistant, model, seconds, cost_usd = 'Claude Code', 'test-model', 1.0, None

    def __init__(self, *args, **kwargs):
        self.passes = []

    def __call__(self, name, prompt, schema):
        self.passes.append(name)
        assert 'NS46' in prompt
        rows = [proposal('P1', ['NS46', 'NS-invented']), proposal('P2', ['NS-invented']), proposal('P1', ['NS30'])]
        if name == 'plan': return {'summary': 'draft', 'proposals': rows}
        return {'critique': {'missed': ['m'], 'risks': ['r']}, 'summary': 'revised', 'proposals': rows + [proposal('P3', ['C1'], 'gate')]}


class Available:
    name = 'Claude Code'

    def available(self): return True


class RoadmapReview(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(self.tmp))
        patches = [mock.patch.object(roadmap_review, 'OUT_JSON', self.tmp / 'roadmap-proposals.json'),
                   mock.patch.object(roadmap_review, 'OUT_MD', self.tmp / 'roadmap-proposals.md'),
                   mock.patch.object(roadmap_review.dev_paths, 'MEASURE', self.tmp / 'measure'),
                   mock.patch.object(roadmap_review, 'AdapterLauncher', FakeLauncher),
                   mock.patch.object(roadmap_review.assistants, 'installed', lambda: {'claude': Available()})]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_a_proposal_keeps_only_resolving_cites_and_one_without_any_is_dropped(self):
        known = roadmap_review.known_ids(json.loads(roadmap_review.PLAN.read_text(encoding='utf-8')))
        self.assertLessEqual({'NS46', 'NS46.T16', 'C1'}, known)
        kept, dropped = roadmap_review.check([proposal('P1', ['NS46', 'NS-invented']), proposal('P2', ['NS-invented']),
                                              proposal('P1', ['NS30']), proposal('P4', ['NS30'], kind='apply-now')], known)
        self.assertEqual([(row['id'], row['cites']) for row in kept], [('P1', ['NS46'])])
        self.assertEqual([(row['id'], row['why']) for row in dropped],
                         [('P2', 'no citation resolves'), ('P1', 'repeated id'), ('P4', 'outside the schema')])

    def test_every_proposal_waits_for_the_owner_and_the_plan_is_not_touched(self):
        before = roadmap_review.PLAN.read_bytes()
        self.assertEqual(roadmap_review.main([]), 0)
        self.assertEqual(roadmap_review.PLAN.read_bytes(), before)
        data = json.loads(roadmap_review.OUT_JSON.read_text(encoding='utf-8'))
        self.assertEqual([row['id'] for row in data['proposals']], ['P1', 'P3'])
        for row in data['proposals']:
            self.assertEqual(row['decision'], {'state': 'waiting', 'options': ['approve', 'reject'], 'owner_verdict': None})
            self.assertIs(row['applied'], False)
        self.assertEqual((data['run']['passes'], data['run']['share_with_evidence'], data['run']['raw_share']),
                         (['plan', 'critique'], 1.0, 0.75))
        text = roadmap_review.OUT_MD.read_text(encoding='utf-8')
        self.assertIn('None has been applied', text)
        self.assertTrue(all(row['id'] in text for row in data['proposals']))

    def test_an_owner_verdict_survives_a_new_run(self):
        roadmap_review.main([])
        data = json.loads(roadmap_review.OUT_JSON.read_text(encoding='utf-8'))
        data['proposals'][0]['decision'].update(state='rejected', owner_verdict={'date': '2026-10-09', 'verdict': 'reject'})
        roadmap_review.OUT_JSON.write_text(json.dumps(data), encoding='utf-8')
        roadmap_review.main([])
        again = {row['id']: row for row in json.loads(roadmap_review.OUT_JSON.read_text(encoding='utf-8'))['proposals']}
        self.assertEqual(again['P1']['decision']['state'], 'rejected')
        self.assertEqual(again['P3']['decision']['state'], 'waiting')


if __name__ == '__main__':
    unittest.main()
