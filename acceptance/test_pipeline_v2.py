"""NS46.T24 owner-request acceptance (owner, 2026-10-11: the evidence first, the assistant decides with the tools before
the target, the gaps and the plan, the reports last), planned 2026-10-11.

The evidence is $EAOS_MEASURE/pipeline-v2/, copied as written by real checks of a fresh clone of each project:
    identity.json             the findings of develop and of this order without an assistant, compared by id
    joint/<project>/          run-manifest.json, target-proposal.json, target-architecture.json, cards.json and
                              plan.json of a check with the person's assistant (Claude Code)
    live/<project>/           run-manifest.json, live/*.json and gallery/index.html of a check that ran the app
A fake assistant never counts: each AI stage must have ended ok with its own calls to a named assistant.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import north_star_measure as measure

EVIDENCE = measure.REPORTS / 'pipeline-v2'
# What a check compares by id (night2 u4 compare.py); facts/external.json is the engines' own output, and
# EXECUTIVE.md gains the one line that says who decided.
FINDINGS = ('claims', 'cards', 'plan tasks', 'transform stages')
WHO_DECIDED_ALONE = 'ما حكم مساعد على هذا المستهدف: القواعد قررت كل جزء فيه.'


def load(*parts):
    return json.loads(EVIDENCE.joinpath(*parts).read_text(encoding='utf-8'))


def projects(kind):
    folder = EVIDENCE / kind
    return sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []


class PipelineV2(unittest.TestCase):
    def test_without_an_assistant_the_findings_are_those_of_develop(self):
        identity = load('identity.json')
        self.assertGreaterEqual(len([name for name in identity if name != 'explained']), 3)
        for name, row in identity.items():
            if name == 'explained': continue
            rows = row['rows']
            internal = {k: v for k, v in rows.items() if k.startswith('facts/') and k != 'facts/external.json'}
            self.assertTrue(internal, name)
            self.assertEqual({k: v for k, v in {**internal, **{k: rows[k] for k in FINDINGS}}.items() if v != 'same'}, {}, name)
            self.assertEqual((row['executive_added'], row['executive_removed']), ([WHO_DECIDED_ALONE], []), name)

    def test_with_the_assistant_the_target_the_gaps_and_the_plan_follow_its_decisions(self):
        names = projects('joint')
        self.assertGreaterEqual(len(names), 2, names)
        for name in names:
            manifest = load('joint', name, 'run-manifest.json')
            self.assertEqual(manifest['status'], 'COMPLETE', name)
            for stage in ('triage', 'ideal', 'order'):
                row = manifest['stages'][stage]
                self.assertEqual(row['status'], 'ok', f"{name} {stage}: {row.get('reason')}")
                self.assertGreaterEqual(row['detail'].get('calls') or 0, 1, f'{name} {stage}')
                self.assertTrue(row['detail'].get('assistant'), f'{name} {stage}')
            order = list(manifest['stages'])
            self.assertLess(max(order.index(s) for s in ('cards', 'reconcile', 'steps')), order.index('reports'), name)
            proposal = {c['id']: c['relation'] for c in load('joint', name, 'target-proposal.json')['current_components']}
            target = load('joint', name, 'target-architecture.json')
            self.assertEqual(target['decided']['by'], 'assistant', name)
            for component in target['current_components']:
                label = component['decided_by']['label']
                self.assertEqual(component['decided_by']['rule'], proposal[component['id']], f"{name} {component['id']}")
                changed = component['relation'] != proposal[component['id']]
                self.assertEqual(changed, label == 'ai_modified', f"{name} {component['id']} {label}")
            plan = load('joint', name, 'plan.json')
            aside = {row['card'] for row in load('joint', name, 'cards.json')['set_aside']}
            self.assertFalse(aside & {t['id'] for t in plan['tasks']}, name)
            gaps = {card for row in target['gap_matrix'] for card in row['blocking_tasks']}
            self.assertFalse(aside & gaps, name)
            self.assertIn(plan['order']['source'], ('assistant', 'rules'), name)

    def test_the_app_ran_inside_the_check_and_its_screens_were_judged(self):
        names = projects('live')
        self.assertTrue(names)
        for name in names:
            manifest = load('live', name, 'run-manifest.json')
            for stage in ('setup', 'record', 'screens'):
                self.assertEqual(manifest['stages'][stage]['status'], 'ok', f"{name} {stage}: {manifest['stages'][stage].get('reason')}")
            lock = load('live', name, 'live', 'lock.json')
            self.assertGreaterEqual(lock['passed'], 1, name)
            screens = load('live', name, 'live', 'screens.json')['rows']
            self.assertGreaterEqual(sum(1 for row in screens if row.get('screenshot')), 2, name)
            visual = manifest['stages']['visual']
            self.assertEqual(visual['status'], 'ok', f"{name} visual: {visual.get('reason')}")
            self.assertGreaterEqual(visual['detail'].get('calls') or 0, 1, name)
            self.assertIn('<img', (EVIDENCE / 'live' / name / 'gallery/index.html').read_text(encoding='utf-8'), name)


if __name__ == '__main__':
    unittest.main()
