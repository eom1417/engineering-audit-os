"""Mechanical repairs: ready under their family's rule, and their check is the claim's own probe on the changed copy."""
import json
import subprocess
import sys
from pathlib import Path

from shared_fixture import Workspace

from eaos.mechanical_assessment import FAMILIES, build_assessment, family

ROOT = Path(__file__).resolve().parents[1]
DEFINED = [{'path': 'app/prices.py', 'line': 1}, {'path': 'app/report.py', 'line': 1}]
SAME = {'domain': {'facts': [{'id': 'FACT-1', 'kind': 'domain_constant', 'value': {'distinct_values': 1, 'definitions': DEFINED}}]}}
DIFFERENT = {'domain': {'facts': [{'id': 'FACT-1', 'kind': 'domain_constant', 'value': {'distinct_values': 2, 'definitions': DEFINED}}]}}
ACROSS = {'domain': {'facts': [{'id': 'FACT-1', 'kind': 'domain_constant', 'value': {
    'distinct_values': 1, 'definitions': [{'path': 'api/orders.ts', 'line': 3}, {'path': 'core/pricing.py', 'line': 4}]}}]}}


def claim(key='duplicated_rule', origin='source', confidence='CONFIRMED'):
    return {'id': 'CLM-001', 'statement': 'RATE is defined in 2 places', 'confidence': confidence, 'origin': origin,
            'fact_ids': ['FACT-1'], 'render': {'key': key},
            'probe_spec': {'probe_type': 'absence_search', 'specification': {'patterns': [r'\bRATE\b'], 'search_scope': ['source']}}}


class AssessmentTests(Workspace):
    def test_a_confirmed_product_claim_of_a_mechanical_family_is_ready_under_its_rule(self):
        built = build_assessment(claim(), SAME, self.tmp)
        self.assertTrue(built['assessment']['reviewed_by'].startswith('engagement rule consolidate_duplicates'))
        self.assertEqual(built['checks'][0]['argv'][1:4], ['-m', 'eaos', 'recheck'])
        from eaos.decisions import decide
        self.assertEqual(decide({**claim(), **built})['readiness'], 'ready')

    def test_test_code_unconfirmed_claims_and_a_rule_turned_off_get_no_repair(self):
        self.assertIsNone(build_assessment(claim(origin='test'), SAME, self.tmp))
        self.assertIsNone(build_assessment(claim(confidence='LIKELY'), SAME, self.tmp))
        (Path(self.tmp) / 'eaos.engagement.json').write_text(json.dumps({'rules': {'consolidate_duplicates': False}}))
        self.assertIsNone(build_assessment(claim(), SAME, self.tmp))

    def test_a_rule_with_two_different_values_is_a_decision_for_a_person_not_a_repair(self):
        self.assertIsNone(build_assessment(claim(), DIFFERENT, self.tmp))

    def test_a_rule_repeated_across_languages_is_a_design_decision_not_a_repair(self):
        self.assertIsNone(build_assessment(claim(), ACROSS, self.tmp))

    def test_a_missing_file_is_a_decision_for_a_person_not_a_repair(self):
        # Restore the file, or remove what uses it: removing it once deleted two admin routes to make a server compile.
        def broken(rule):
            return {**claim('broken_code'), 'probe_spec': {'probe_type': 'graph_query', 'specification': {
                'query': 'broken_code_present', 'path': 'server/index.ts', 'symbol': './env.js', 'rule': rule}}}
        self.assertIsNone(build_assessment(broken('missing-import'), {}, self.tmp))
        self.assertIsNotNone(build_assessment(broken('stale-instruction'), {}, self.tmp))

    def test_every_family_names_a_rule_the_engagement_declares(self):
        from eaos.engagement import DEFAULT_RULES
        for name, (rule, invariant, after) in FAMILIES.items():
            self.assertIn(rule, DEFAULT_RULES, name)
            self.assertTrue(invariant and after, name)
        self.assertEqual(family({'probe_spec': {'specification': {'query': 'cycle_present'}}}), 'cycle')

    def test_a_load_blocker_is_rechecked_by_its_entry_path_and_route_not_by_a_fact_id(self):
        blocker = {**claim(key='load_blocker'), 'probe_spec': {'probe_type': 'graph_query', 'specification': {
            'query': 'load_blocker_present', 'entry_point': 'FACT-9', 'question': 'result_is_bounded'}}}
        sets = {'entrypoints': {'facts': [{'id': 'FACT-9', 'location': {'path': 'src/api.ts'}, 'value': {'route': '/items'}}]}}
        spec = json.loads(build_assessment(blocker, sets, self.tmp)['checks'][0]['argv'][5])
        self.assertEqual((spec['specification']['entry_path'], spec['specification']['entry_route']), ('src/api.ts', '/items'))


class RecheckTests(Workspace):
    def test_the_check_fails_while_the_rule_is_duplicated_and_passes_once_it_has_one_home(self):
        project = Path(self.tmp) / 'project'
        (project / 'app').mkdir(parents=True)
        (project / 'app/prices.py').write_text('RATE = 0.15\n\n\ndef price(x):\n    return x * RATE\n')
        (project / 'app/report.py').write_text('RATE = 0.15\n\n\ndef total(x):\n    return x * RATE\n')
        argv = build_assessment(claim(), SAME, project)['checks'][0]['argv']
        run = lambda: subprocess.run(argv, cwd=project, capture_output=True, text=True, timeout=600)
        before = run()
        self.assertEqual(before.returncode, 1, before.stdout + before.stderr)
        (project / 'app/report.py').write_text('from app.prices import RATE\n\n\ndef total(x):\n    return x * RATE\n')
        after = run()
        self.assertEqual(after.returncode, 0, after.stdout + after.stderr)


class UndecidedTests(Workspace):
    def test_a_probe_that_cannot_decide_exits_2_never_0(self):
        project = Path(self.tmp) / 'project'
        project.mkdir()
        (project / 'a.py').write_text('x = 1\n')
        spec = json.dumps({'probe_type': 'execution', 'specification': {}})
        done = subprocess.run([sys.executable, '-m', 'eaos', 'recheck', '--spec', spec, str(project)],
                              capture_output=True, text=True, cwd=ROOT, timeout=300)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
