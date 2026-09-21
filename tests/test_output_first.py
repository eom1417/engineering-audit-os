"""Decision safety, real outcomes, source access and causal sequencing."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from eaos.acceptance import fingerprint, run
from eaos.decisions import decide, identity, task_errors
from eaos.delta import compare
from eaos.plan import waves


def observation(**extra):
    return {'id': 'CLM-001', 'claim_type': 'business_rule', 'statement': 'Two entry paths compute different totals',
            'confidence': 'CONFIRMED', 'origin': 'source', 'fact_ids': ['FACT-1'],
            'falsifier': 'Both entry paths return the required total', **extra}


class DecisionTests(unittest.TestCase):
    def test_confirmed_signal_and_likely_claim_do_not_authorize_repair(self):
        for confidence in ('CONFIRMED', 'LIKELY', 'HYPOTHESIS'):
            self.assertEqual(decide(observation(confidence=confidence))['kind'], 'investigate')

    def test_fixture_signal_and_refuted_claim_retain_without_repair(self):
        self.assertEqual(decide(observation(origin='test'))['kind'], 'retain')
        self.assertEqual(decide(observation(confidence='REFUTED'))['kind'], 'retain')

    def test_evidenced_violation_stays_blocked_without_check_and_review(self):
        claim = observation(assessment={'violated_invariant': 'premium total is 90',
                                        'requirement_refs': ['README:1'], 'evidence_refs': ['FACT-1']})
        decision = decide(claim)
        self.assertEqual(decision['kind'], 'repair')
        self.assertEqual(decision['readiness'], 'blocked')
        self.assertTrue(decision['blockers'])

    def test_serial_renumber_does_not_change_identity(self):
        self.assertEqual(identity(observation()), identity(observation(id='CLM-999')))

    def test_absence_and_scope_loss_never_mean_healed(self):
        previous = {'claims': [observation()], 'provenance': {'excluded_patterns': []}}
        current = {'claims': [], 'provenance': {'excluded_patterns': ['billing']}}
        result = compare(previous, current)
        self.assertEqual(result['resolved_claims'], [])
        self.assertEqual(len(result['unobserved_claims']), 1)
        self.assertEqual(result['comparison_status'], 'scope_changed')

    def test_no_ready_task_without_real_checks(self):
        self.assertTrue(task_errors({'contract_version': 1, 'kind': 'remediate',
                                    'decision': {'kind': 'repair', 'readiness': 'ready', 'checks': []}}))


class AcceptanceTests(unittest.TestCase):
    def check(self, root, code):
        return {'id': 'CHECK-1', 'kind': 'command', 'invariant': 'premium price is 90',
                'expected': 'assertion succeeds', 'expected_exit': 0, 'cwd': '.',
                'source_revision': fingerprint(root), 'argv': [sys.executable, '-B', '-c', code]}

    def test_defect_fails_corrected_copy_passes_and_stale_binding_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'app.py').write_text('def price(): return 95\n')
            check = self.check(root, 'from app import price; assert price() == 90')
            self.assertEqual(run(check, root)['status'], 'blocked')
            self.assertEqual(run(check, root, execute=True)['status'], 'fail')
            (root / 'app.py').write_text('def price(): return 90\n')
            self.assertEqual(run(check, root, execute=True)['status'], 'blocked')
            check['source_revision'] = fingerprint(root)
            self.assertEqual(run(check, root, execute=True)['status'], 'pass')

    def test_candidate_mutation_is_inconclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            check = self.check(tmp, "open('unplanned.py', 'w').write('surprise')")
            self.assertEqual(run(check, tmp, execute=True)['status'], 'inconclusive')

    def test_report_regeneration_cannot_be_a_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            check = self.check(tmp, '')
            check['argv'] = ['eaos', 'dossier', '.']
            self.assertEqual(run(check, tmp, execute=True)['status'], 'blocked')

    def test_missing_program_is_blocked_not_failed_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            check = self.check(tmp, '')
            check['argv'] = ['/definitely/missing/eaos-program']
            self.assertEqual(run(check, tmp, execute=True)['status'], 'blocked')


class CausalTests(unittest.TestCase):
    def task(self, id, path, prerequisites=()):
        return {'id': id, 'paths': [path], 'kind': 'remediate', 'priority': 1, 'prerequisites': list(prerequisites)}

    def test_prerequisites_on_different_files_are_sequential(self):
        tasks = [self.task('A', 'a.py'), self.task('B', 'b.py', [{'task_id': 'A', 'reason': 'uses the new contract'}])]
        self.assertEqual([w['tasks'] for w in waves(tasks)], [['A'], ['B']])

    def test_cycle_and_missing_dependency_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            waves([self.task('B', 'b.py', [{'task_id': 'A', 'reason': 'missing'}])])
        with self.assertRaisesRegex(ValueError, 'cycle'):
            waves([self.task('A', 'a.py', [{'task_id': 'A', 'reason': 'cycle'}])])


class SemanticSourceTests(unittest.TestCase):
    def test_can_read_component_beyond_summary_and_reject_escape(self):
        from eaos.dossier import assemble
        from eaos.semantic import run as interpret
        class Provider:
            calls = 0
            def identity(self): return {'kind': 'SCRIPTED_TEST_FIXTURE'}
            def complete(self, messages):
                self.calls += 1
                digest = json.loads(messages[1]['content'])['instructions']['digest']
                if self.calls == 1:
                    return {'claims': [], 'source_requests': [{'path': 'zz_last.py', 'start_line': 1, 'end_line': 1},
                                                             {'path': '../secret', 'start_line': 1, 'end_line': 1}]}
                assert 'answer = 42' in digest['source_ranges'][0]['source']
                assert digest['source_omissions']
                return {'claims': [{'statement': 'The last module defines the documented answer constant',
                        'claim_type': 'responsibility', 'fact_ids': [digest['source_ranges'][0]['fact_id']],
                        'falsifier': 'The source no longer defines the answer constant'}], 'questions': []}
        with tempfile.TemporaryDirectory() as tmp:
            root, out = Path(tmp) / 'repo', Path(tmp) / 'out'
            root.mkdir()
            for index in range(65): (root / f'm{index:03}.py').write_text('x = 1\n')
            (root / 'zz_last.py').write_text('answer = 42\n')
            assemble(root, out)
            result = interpret(root, out, Provider())
            self.assertEqual(result['claims'], 1)
            self.assertEqual(json.loads((out / 'dossier.json').read_text())['provenance']['model_calls'], 2)

class ProductIntegrationTests(unittest.TestCase):
    def test_one_command_generates_consistent_reports_and_refresh_removes_old_cards(self):
        from eaos.product_review import run as review
        from eaos.views import refresh
        from eaos.workspace import read, write
        with tempfile.TemporaryDirectory() as tmp:
            root, out = Path(tmp) / 'repo', Path(tmp) / 'out'
            root.mkdir()
            (root / 'a.py').write_text('RATE = 0.1\n')
            (root / 'b.py').write_text('RATE = 0.2\n')
            result = review(root, out, language='en')
            self.assertEqual(result['mode'], 'facts_only')
            self.assertEqual(result['executable_repairs'], 0)
            self.assertTrue((out / 'PRODUCT-REPORT.md').is_file())
            self.assertIn('PLAN/TASK-001', (out / 'index.html').read_text())
            dossier = read(out / 'dossier.json')
            for claim in dossier['claims']: claim['confidence'] = 'REFUTED'
            write(out / 'dossier.json', dossier)
            refresh(out, 'en')
            self.assertEqual(read(out / 'plan.json')['tasks'], [])
            self.assertFalse((out / 'PLAN/TASK-001.md').exists())
            self.assertNotIn('PLAN/TASK-001', (out / 'index.html').read_text())

    def test_review_rejects_fabricated_evidence_and_preserves_history(self):
        from eaos.product_review import run as review_project
        from eaos.decision_review import apply
        from eaos.workspace import read
        with tempfile.TemporaryDirectory() as tmp:
            root, out = Path(tmp) / 'repo', Path(tmp) / 'out'
            root.mkdir()
            (root / 'a.py').write_text('RATE = 0.1\n')
            (root / 'b.py').write_text('RATE = 0.2\n')
            review_project(root, out)
            claim = read(out / 'dossier.json')['claims'][0]
            assessment = {'reviewed_by': 'test reviewer', 'violated_invariant': 'same rate',
                          'before': 'rates differ', 'after': 'same rate', 'proposed_change': 'share one rule',
                          'requirement_refs': ['invented'], 'evidence_refs': claim['fact_ids']}
            with self.assertRaisesRegex(ValueError, 'known requirement_refs'):
                apply(out, {'claim_id': claim['id'], 'assessment': assessment})
            assessment['requirement_refs'] = claim['fact_ids']
            result = apply(out, {'claim_id': claim['id'], 'assessment': assessment})
            self.assertEqual(result['decision']['readiness'], 'blocked')
            self.assertEqual(len(list((out / 'decision-history').glob('*.json'))), 1)

    def test_html_links_are_navigable_and_script_schemes_are_rejected(self):
        from eaos.site import inline
        self.assertIn('href="#plan/task-001"', inline('[task](PLAN/TASK-001.md)'))
        self.assertNotIn('href', inline('[bad](javascript:alert)'))

class ContractEdgeTests(unittest.TestCase):
    def test_all_decision_types_validate_against_the_published_schema(self):
        from eaos.audit_records import schema_errors
        from eaos.workspace import DATA, read
        spec = read(DATA / 'schemas/decision.schema.json')
        for claim in (observation(), observation(origin='test'), observation(confidence='REFUTED')):
            self.assertEqual(schema_errors(decide(claim), spec), [])

    def test_duplicate_identity_is_reported_as_ambiguous_not_silently_collapsed(self):
        a = observation(uid='OBS-same')
        result = compare({'claims': [a, copy.deepcopy(a)]}, {'claims': []})
        self.assertTrue(result['ambiguous_identities'])
        self.assertEqual(result['unobserved_claims'], [])

    def test_source_retrieval_redacts_full_private_key_before_slicing(self):
        from eaos.dossier import assemble
        from eaos.semantic_source import SourceSession
        from eaos.facts.store import read_set
        with tempfile.TemporaryDirectory() as tmp:
            root, out = Path(tmp) / 'repo', Path(tmp) / 'out'
            root.mkdir()
            (root / 'main.py').write_text('answer = 42\n')
            (root / 'README.md').write_text('-----BEGIN PRIVATE KEY-----\nPRIVATE_PAYLOAD\n-----END PRIVATE KEY-----\n')
            assemble(root, out)
            sources = SourceSession(root, out, {'syntax': read_set(out, 'syntax')})
            blocks = sources.retrieve([{'path': 'README.md', 'start_line': 2, 'end_line': 2}])
            self.assertEqual(len(blocks), 1)
            self.assertNotIn('PRIVATE_PAYLOAD', json.dumps(blocks))

    def test_claim_rewording_does_not_rename_a_located_probe(self):
        probe = {'probe_type': 'graph_query', 'specification': {'query': 'cycle_present', 'members': ['a.py','b.py']}}
        self.assertEqual(identity(observation(probe_spec=probe)),
                         identity(observation(statement='A reworded observation about the same cycle', probe_spec=probe)))

class InvestigationOutcomeTests(unittest.TestCase):
    def test_investigation_can_end_in_no_change_and_repeated_review_keeps_history(self):
        from eaos.product_review import run as review
        from eaos.decision_review import apply
        from eaos.workspace import read
        with tempfile.TemporaryDirectory() as tmp:
            root, out = Path(tmp) / 'repo', Path(tmp) / 'out'
            root.mkdir()
            (root / 'a.py').write_text('LIMIT = 10\n')
            (root / 'b.py').write_text('LIMIT = 20\n')
            review(root, out)
            claim = read(out / 'dossier.json')['claims'][0]
            decision = apply(out, {'claim_id': claim['id'], 'outcome': 'retain',
                                   'reviewed_by': 'test owner', 'reason': 'Different domain limits are intentional.'})
            self.assertEqual(decision['decision']['kind'], 'retain')
            self.assertEqual(read(out / 'plan.json')['tasks'], [])
            self.assertFalse((out / 'PLAN/TASK-001.md').exists())
