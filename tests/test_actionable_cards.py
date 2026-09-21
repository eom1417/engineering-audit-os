"""A card says what must stay true, what it would cost, and what it is waiting on — separately."""
import json
import tempfile
import unittest
from pathlib import Path

from eaos.dossier import assemble
from eaos.facts.run import collect
from eaos.plan import UNKNOWN, build, harm_of, invariants_of, waves

FIXTURE = Path(__file__).resolve().parent / 'fixtures/sustainability'


def claim(**overrides):
    row = {'id': 'CLM-001', 'statement': 'a duplicated rule', 'claim_type': 'business_rule',
           'confidence': 'CONFIRMED', 'falsifier': 'the two occurrences compute different rules',
           'assessment': {}, 'impact': {}}
    row.update(overrides)
    return row


def radius(total=3, dependents=2, flows=1):
    return {'blast_radius': total, 'direct_dependents': ['a'] * dependents, 'flows': ['f'] * flows,
            'transitive_dependents': [], 'entry_points': [], 'covering_tests': [], 'coverage': {},
            'change_partners': []}


class InvariantTests(unittest.TestCase):
    def test_a_card_always_states_what_must_hold_after_the_change(self):
        rows = invariants_of(claim())
        self.assertTrue(rows)
        self.assertTrue(all(row['invariant'] for row in rows))
        self.assertIn('falsifier', [row['source'] for row in rows])

    def test_a_stated_invariant_is_carried_through_rather_than_paraphrased(self):
        stated = 'a price is computed in exactly one place'
        rows = invariants_of(claim(assessment={'violated_invariant': stated}))
        self.assertEqual(rows[0]['invariant'], stated)
        self.assertTrue(rows[0]['must_hold_after'])


class HarmTests(unittest.TestCase):
    """Business harm, reach and effort answer three different questions."""

    def test_unevidenced_business_harm_stays_unknown(self):
        harm = harm_of(claim(), radius(), 'medium', 'estimated')
        self.assertEqual(harm['business']['value'], UNKNOWN)
        self.assertIn('not established', harm['business']['basis'])

    def test_measured_reach_is_never_presented_as_business_harm(self):
        harm = harm_of(claim(), radius(total=99), 'medium', 'estimated')
        self.assertEqual(harm['business']['value'], UNKNOWN)
        self.assertEqual(harm['reach']['value'], 99)
        self.assertIn('measured', harm['reach']['basis'])

    def test_evidenced_business_harm_is_reported_with_its_basis(self):
        harm = harm_of(claim(assessment={'business_harm': 'duplicate invoices were issued'}),
                       radius(), 'small', 'estimated')
        self.assertEqual(harm['business']['value'], 'duplicate invoices were issued')
        self.assertIn('evidenced', harm['business']['basis'])

    def test_effort_carries_the_confidence_of_its_estimate(self):
        harm = harm_of(claim(), radius(), 'large', 'low confidence')
        self.assertEqual(harm['effort']['value'], 'large')
        self.assertEqual(harm['effort']['basis'], 'low confidence')

    def test_the_three_are_never_collapsed_into_one_number(self):
        harm = harm_of(claim(), radius(), 'medium', 'estimated')
        self.assertEqual(sorted(harm), ['business', 'effort', 'reach'])
        for key in harm:
            self.assertIn('basis', harm[key], key)


class SchedulingTests(unittest.TestCase):
    """An investigation holds up the task that consumes it, and nothing else."""

    def _task(self, identifier, paths, prerequisites=(), kind='remediate'):
        return {'id': identifier, 'paths': list(paths), 'kind': kind, 'priority': 1,
                'prerequisites': [{'task_id': ref, 'reason': 'needs the outcome'} for ref in prerequisites],
                'claim_id': 'CLM-' + identifier}

    def test_an_investigation_only_precedes_the_task_that_needs_it(self):
        tasks = [self._task('TASK-001', ['a.py'], kind='investigate'),
                 self._task('TASK-002', ['b.py'], prerequisites=['TASK-001']),
                 self._task('TASK-003', ['c.py'])]
        plan = waves(tasks)
        first = next(wave for wave in plan if 'TASK-001' in wave['tasks'])
        third = next(wave for wave in plan if 'TASK-003' in wave['tasks'])
        second = next(wave for wave in plan if 'TASK-002' in wave['tasks'])
        self.assertEqual(first['wave'], third['wave'],
                         'an unrelated task was held up by an investigation it does not consume')
        self.assertGreater(second['wave'], first['wave'])

    def test_a_file_conflict_separates_tasks_without_implying_a_dependency(self):
        tasks = [self._task('TASK-001', ['a.py']), self._task('TASK-002', ['a.py'])]
        plan = waves(tasks)
        self.assertNotEqual(next(w['wave'] for w in plan if 'TASK-001' in w['tasks']),
                            next(w['wave'] for w in plan if 'TASK-002' in w['tasks']))
        for task in tasks:
            self.assertEqual(task['prerequisites'], [], 'a file conflict must not become a causal claim')

    def test_a_prerequisite_without_a_reason_is_refused(self):
        tasks = [self._task('TASK-001', ['a.py'])]
        tasks.append({'id': 'TASK-002', 'paths': ['b.py'], 'kind': 'remediate', 'priority': 1,
                      'prerequisites': [{'task_id': 'TASK-001'}], 'claim_id': 'X'})
        with self.assertRaises(ValueError):
            waves(tasks)


class OnePlanTests(unittest.TestCase):
    """Sustainability moves and the transform plan answer to the same decisions, not a second plan."""

    def test_every_transform_stage_traces_to_a_finding_the_ledger_holds(self):
        with tempfile.TemporaryDirectory() as out:
            collect(FIXTURE, out)
            assemble(FIXTURE, out, language='en')
            from eaos.sustainability import render as dashboard
            from eaos.transform_plan import build as transform, render as write_plan
            dashboard(out, language='en')
            plan = transform(out)
            write_plan(out, plan, language='en')
            record = json.loads(Path(out, 'transform-plan.json').read_text(encoding='utf-8'))
            facts = {fact['id'] for name in ('fingerprint', 'redundancy')
                     if Path(out, 'facts', f'{name}.json').is_file()
                     for fact in json.loads(Path(out, 'facts', f'{name}.json').read_text(encoding='utf-8'))['facts']}
        for stage in record.get('stages', []):
            sites = stage.get('sites') or []
            self.assertTrue(sites or stage.get('rule'), f"stage {stage.get('stage')} names nothing to act on")

    def test_a_card_and_its_claim_share_one_decision(self):
        with tempfile.TemporaryDirectory() as out:
            collect(FIXTURE, out)
            assemble(FIXTURE, out, language='en')
            build(FIXTURE, out, 'en')
            dossier = json.loads(Path(out, 'dossier.json').read_text(encoding='utf-8'))
        by_claim = {claim['id']: claim for claim in dossier['claims']}
        for task in dossier['tasks']:
            decision = task['decision']
            self.assertEqual(decision['observation_uid'],
                             by_claim[task['claim_id']].get('uid') or decision['observation_uid'])
            self.assertIn(decision['kind'], ('repair', 'investigate', 'retain'))

    def test_a_card_carries_its_invariants_and_its_separated_harm(self):
        with tempfile.TemporaryDirectory() as out:
            collect(FIXTURE, out)
            assemble(FIXTURE, out, language='en')
            build(FIXTURE, out, 'en')
            dossier = json.loads(Path(out, 'dossier.json').read_text(encoding='utf-8'))
        self.assertTrue(dossier['tasks'])
        for task in dossier['tasks']:
            self.assertTrue(task['invariants'], task['id'])
            self.assertEqual(sorted(task['harm']), ['business', 'effort', 'reach'], task['id'])
