"""The dossier: one ledger, derived artifacts, and an output contract that can fail the build."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from eaos import cli
from eaos.compose.rules import validate
from eaos.dossier import assemble

FIXTURE = Path(__file__).resolve().parent / 'fixtures/polyglot'


class DossierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'out'
        cls.result = assemble(FIXTURE, cls.out)
        cls.dossier = json.loads((cls.out / 'dossier.json').read_text())

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_facts_only_run_produces_a_clean_decision_artifact(self):
        self.assertEqual(self.result['status'], 'READY')
        self.assertEqual(self.result['output_spec_violations'], [])
        self.assertEqual(self.result['model_calls'], 0)
        self.assertTrue((self.out / 'DECISION-BRIEF.md').is_file())
        self.assertTrue((self.out / 'PROVENANCE.md').is_file())

    def test_the_brief_states_coverage_and_the_unexamined_scope(self):
        brief = (self.out / 'DECISION-BRIEF.md').read_text()
        self.assertIn('التغطية', brief)
        self.assertIn('ما لم يُفحص', brief)
        self.assertIn('semantic review: not performed', brief)

    def test_nothing_is_asserted_without_a_source_and_a_refutation(self):
        for claim in self.dossier['claims']:
            self.assertTrue(claim['falsifier'])
            self.assertTrue(claim.get('evidence_ids') or claim.get('fact_ids'))
            self.assertIn(claim['confidence'], ['CONFIRMED', 'LIKELY', 'HYPOTHESIS', 'REFUTED'])

    def test_shallow_history_produces_a_question_instead_of_a_coupling_claim(self):
        questions = ' '.join(question['question'] for question in self.dossier['questions'])
        self.assertTrue('too shallow' in questions or 'unavailable' in questions)

    def test_the_whole_human_output_stays_readable(self):
        total = sum(path.read_text().count('\n') for path in self.out.glob('*.md'))
        self.assertLess(total, 900)

    def test_a_claim_that_is_not_in_the_ledger_fails_the_output_contract(self):
        (self.out / 'DECISION-BRIEF.md').write_text((self.out / 'DECISION-BRIEF.md').read_text() + '\nSee CLM-999.\n')
        problems = validate(self.out, self.dossier)
        self.assertTrue(any('CLM-999' in problem for problem in problems))

    def test_a_raw_record_dump_fails_the_output_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'; out.mkdir()
            (out / 'DECISION-BRIEF.md').write_text('# brief\n\nالتغطية: 1/1\n\n⬤ claim\n\n## ما لم يُفحص\n\n- none\n\n```json\n{}\n```\n')
            problems = validate(out, {'claims': [], 'tasks': []})
            self.assertTrue(any(problem.startswith('R8') for problem in problems))

    def test_a_live_risk_without_a_disposition_fails_the_output_contract(self):
        dossier = {'claims': [{'id': 'CLM-001', 'claim_type': 'risk', 'confidence': 'LIKELY', 'statement': 'x'}], 'tasks': []}
        self.assertTrue(any(problem.startswith('R5') for problem in validate(self.out, dossier)))

    def test_a_task_without_a_runnable_acceptance_command_fails_the_output_contract(self):
        dossier = {'claims': [], 'tasks': [{'id': 'T1', 'title': 'x'}]}
        self.assertTrue(any(problem.startswith('R7') for problem in validate(self.out, dossier)))

    def test_cli_reports_violations_with_a_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as printed:
            code = cli.main(['dossier', str(FIXTURE), '--out', str(Path(tmp) / 'cli')])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(printed.getvalue())['status'], 'READY')

    def test_duplicate_records_become_one_claim_with_both_sources(self):
        from eaos import claims as ledger
        rows = ledger.merge([
            ledger.make(1, 'Totals must match between screens', 'contract', 'HYPOTHESIS', ['model_inference'], ['SRC-1'], 'a', legacy_id='C-1'),
            ledger.make(2, 'Totals must match between screens', 'business_rule', 'HYPOTHESIS', ['model_inference'], ['SRC-2'], 'a', legacy_id='RULE-1'),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['claim_type'], 'business_rule')
        self.assertEqual(rows[0]['evidence_ids'], ['SRC-1', 'SRC-2'])
        self.assertEqual(rows[0]['legacy_id'], 'C-1, RULE-1')


class DispositionTests(unittest.TestCase):
    """Regression: the code that assigns a disposition sat after a return and nothing noticed."""

    def test_every_claim_stating_a_consequence_gets_a_disposition(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'out'
            assemble(FIXTURE, out)
            claims = json.loads((out / 'dossier.json').read_text())['claims']
            self.assertTrue(claims)
            for claim in claims:
                if (claim.get('impact') or {}).get('scenario'):
                    self.assertIn((claim.get('disposition') or {}).get('kind'),
                                  {'task', 'accepted', 'investigate'}, claim['id'])
                self.assertTrue(claim.get('artifacts'), claim['id'])

    def test_the_contract_rejects_a_structural_finding_with_no_disposition(self):
        dossier = {'claims': [{'id': 'CLM-001', 'claim_type': 'business_rule', 'confidence': 'CONFIRMED',
                               'statement': 'A rule lives in two modules'}], 'tasks': []}
        self.assertTrue(any(problem.startswith('R5') for problem in validate(Path('.'), dossier)))


class UnreachableCodeTests(unittest.TestCase):
    """A statement after a return is silently dead; the last one disabled a product rule."""

    def test_no_statement_follows_a_return_in_the_package(self):
        import ast
        root = Path(__file__).resolve().parents[1] / 'eaos'
        offenders = []
        for path in sorted(root.rglob('*.py')):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                for field in ('body', 'orelse', 'finalbody'):
                    block = getattr(node, field, None)
                    if not isinstance(block, list): continue
                    for index, statement in enumerate(block[:-1]):
                        if isinstance(statement, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
                            offenders.append(f'{path.relative_to(root.parent)}:{block[index + 1].lineno}')
        self.assertEqual(offenders, [], 'unreachable statements found')


class DecisionContractRuleTests(unittest.TestCase):
    """The output contract must reject a task that carries no typed decision."""

    def test_a_contract_task_without_a_decision_is_rejected(self):
        dossier = {'claims': [], 'tasks': [{'id': 'TASK-001', 'contract_version': 1, 'decision': {}}]}
        problems = validate(Path('.'), dossier)
        self.assertTrue(any(problem.startswith('R7') and 'typed decision' in problem for problem in problems))

    def test_a_ready_repair_without_checks_is_rejected(self):
        dossier = {'claims': [], 'tasks': [{'id': 'TASK-002', 'contract_version': 1,
                                            'decision': {'kind': 'repair', 'readiness': 'ready', 'checks': []}}]}
        problems = validate(Path('.'), dossier)
        self.assertTrue(any(problem.startswith('R7') for problem in problems))

    def test_a_well_formed_investigation_passes(self):
        dossier = {'claims': [], 'tasks': [{'id': 'TASK-003', 'contract_version': 1,
                                            'decision': {'kind': 'investigate', 'readiness': 'needs_review',
                                                         'checks': [], 'blockers': []}}]}
        self.assertEqual([p for p in validate(Path('.'), dossier) if p.startswith('R7')], [])
