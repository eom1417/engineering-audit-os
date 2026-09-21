"""One decision contract governs both planners, and the executor refuses what it refuses."""
import unittest

from eaos.decision_bridge import NEEDS_REVALIDATION, decision_of, executable, from_roadmap
from eaos.decisions import VERSION


def roadmap_task(**overrides):
    task = {'id': 'TASK-1', 'kind': 'remediate', 'status': 'planned', 'finding_ids': ['F-1'],
            'evidence_ids': ['E-1'], 'required_gate_ids': ['G-1'], 'depends_on': [], 'files': ['a.py']}
    task.update(overrides)
    return task


FINDINGS = [{'id': 'F-1', 'claim_status': 'CONFIRMED', 'status': 'open'}]
GATES = [{'id': 'G-1', 'status': 'pass'}]


class RoadmapAdapterTests(unittest.TestCase):
    def test_a_confirmed_remediation_adapts_to_a_ready_repair(self):
        decision = from_roadmap(roadmap_task(), FINDINGS, GATES)
        self.assertEqual((decision['kind'], decision['readiness']), ('repair', 'ready'))
        self.assertEqual(decision['blockers'], [])
        self.assertEqual(decision['contract_version'], VERSION)

    def test_a_repair_over_an_unconfirmed_finding_is_blocked(self):
        findings = [{'id': 'F-1', 'claim_status': 'HYPOTHESIS'}]
        decision = from_roadmap(roadmap_task(), findings, GATES)
        self.assertEqual(decision['readiness'], 'blocked')
        self.assertTrue(any('HYPOTHESIS' in reason for reason in decision['blockers']))

    def test_a_repair_with_no_evidence_is_blocked(self):
        decision = from_roadmap(roadmap_task(evidence_ids=[]), FINDINGS, GATES)
        self.assertIn('no evidence reference on a repair', decision['blockers'])

    def test_a_repair_with_no_gate_is_blocked(self):
        decision = from_roadmap(roadmap_task(required_gate_ids=[]), FINDINGS, GATES)
        self.assertIn('no acceptance gate declared', decision['blockers'])

    def test_a_gate_that_was_never_declared_is_named(self):
        decision = from_roadmap(roadmap_task(required_gate_ids=['G-9']), FINDINGS, GATES)
        self.assertTrue(any('G-9' in reason for reason in decision['blockers']))

    def test_an_investigation_needs_review_rather_than_execution(self):
        decision = from_roadmap(roadmap_task(kind='investigate'), FINDINGS, GATES)
        self.assertEqual((decision['kind'], decision['readiness']), ('investigate', 'needs_review'))
        self.assertIn('blocked_missing_requirement', decision['allowed_outcomes'])

    def test_a_task_of_an_unknown_kind_is_not_silently_treated_as_a_repair(self):
        decision = from_roadmap(roadmap_task(kind='refactor'), FINDINGS, GATES)
        self.assertNotEqual(decision['kind'], 'repair')
        self.assertTrue(decision['blockers'])


class ContractSelectionTests(unittest.TestCase):
    def test_a_current_plan_task_keeps_its_own_decision(self):
        task = {'contract_version': VERSION,
                'decision': {'kind': 'repair', 'readiness': 'ready', 'checks': [], 'blockers': []}}
        decision = decision_of(task)
        self.assertEqual(decision['source'], 'plan')
        self.assertEqual(decision['readiness'], 'ready')

    def test_a_plan_task_from_an_older_contract_needs_revalidation(self):
        task = {'decision': {'kind': 'repair', 'readiness': 'ready', 'checks': [], 'blockers': []}}
        decision = decision_of(task)
        self.assertEqual(decision['readiness'], NEEDS_REVALIDATION)
        self.assertTrue(any('revalidation' in reason for reason in decision['blockers']))


class ExecutabilityTests(unittest.TestCase):
    def test_a_ready_repair_is_executable(self):
        allowed, verdict = executable(roadmap_task(), FINDINGS, GATES)
        self.assertTrue(allowed, verdict['refusals'])

    def test_an_investigation_is_refused_with_the_reason(self):
        allowed, verdict = executable(roadmap_task(kind='investigate'), FINDINGS, GATES)
        self.assertFalse(allowed)
        self.assertIn('an investigation concludes with a decision, not with a code change',
                      verdict['refusals'])

    def test_a_blocked_repair_is_refused_and_every_blocker_is_listed(self):
        allowed, verdict = executable(roadmap_task(evidence_ids=[], required_gate_ids=[]), FINDINGS, GATES)
        self.assertFalse(allowed)
        self.assertIn('no evidence reference on a repair', verdict['refusals'])
        self.assertIn('no acceptance gate declared', verdict['refusals'])

    def test_a_retained_decision_has_nothing_to_execute(self):
        task = {'contract_version': VERSION, 'decision': {'kind': 'retain', 'readiness': 'no_change',
                                                          'checks': [], 'blockers': []}}
        allowed, verdict = executable(task)
        self.assertFalse(allowed)
        self.assertIn('the decision was to retain; there is nothing to execute', verdict['refusals'])

    def test_a_ready_repair_whose_check_is_malformed_is_refused(self):
        task = {'contract_version': VERSION,
                'decision': {'kind': 'repair', 'readiness': 'ready', 'blockers': [],
                             'checks': [{'id': 'C-1', 'kind': 'command', 'argv': ['eaos', 'dossier', '.'],
                                         'invariant': 'x', 'expected': 'y', 'source_revision': 'r',
                                         'expected_exit': 0}]}}
        allowed, verdict = executable(task)
        self.assertFalse(allowed)
        self.assertIn('report regeneration is not behavioral acceptance', verdict['refusals'])

    def test_a_malformed_task_is_refused_rather_than_crashing(self):
        allowed, verdict = executable({})
        self.assertFalse(allowed)
        self.assertTrue(verdict['refusals'])


class ExecutorTests(unittest.TestCase):
    """The executor asks the contract before it copies a single file."""

    def test_the_executor_calls_the_bridge_before_doing_any_work(self):
        import ast
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / 'eaos/runtime/remediate.py').read_text(encoding='utf-8')
        body = ast.parse(source)
        target = next(node for node in ast.walk(body)
                      if isinstance(node, ast.FunctionDef) and node.name == '_implement')
        statements = [ast.dump(node) for node in target.body]
        gate = next((index for index, text in enumerate(statements) if 'executable' in text), None)
        copy = next((index for index, text in enumerate(statements) if 'copy' in text.lower()), len(statements))
        self.assertIsNotNone(gate, 'the executor does not consult the decision contract at all')
        self.assertLess(gate, copy, 'the contract is consulted after work has already begun')
