"""Mechanical repairs: ready under their family's rule, and their check is the claim's own probe on the changed copy."""
import json
import subprocess
import sys
from pathlib import Path

from shared_fixture import Workspace

from eaos.core.decisions import decide
from eaos.analysis.engagement import DEFAULT_RULES
from eaos.analysis.mechanical_assessment import FAMILIES, build_assessment, family
from eaos.pipeline import execute

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
    def test_a_mechanical_claim_is_ready_under_its_rule_and_what_needs_a_person_never_is(self):
        built = build_assessment(claim(), SAME, self.tmp)
        self.assertTrue(built['assessment']['reviewed_by'].startswith('engagement rule consolidate_duplicates'))
        self.assertEqual(built['checks'][0]['argv'][1:4], ['-m', 'eaos', 'recheck'])
        self.assertEqual(decide({**claim(), **built})['readiness'], 'ready')
        for name, (rule, invariant, after) in FAMILIES.items():
            self.assertIn(rule, DEFAULT_RULES, name)
            self.assertTrue(invariant and after, name)
        self.assertEqual(family({'probe_spec': {'specification': {'query': 'cycle_present'}}}), 'cycle')
        # What needs a person never becomes a repair.
        def broken(rule):
            return {**claim('broken_code'), 'probe_spec': {'probe_type': 'graph_query', 'specification': {
                'query': 'broken_code_present', 'path': 'server/index.ts', 'symbol': './env.js', 'rule': rule}}}
        cases = {'test code': (claim(origin='test'), SAME), 'unconfirmed': (claim(confidence='LIKELY'), SAME),
                 'two different values': (claim(), DIFFERENT), 'across languages': (claim(), ACROSS),
                 # Restore the file, or remove what uses it: removing it once deleted two admin routes.
                 'missing file': (broken('missing-import'), {})}
        for case, (row, sets) in cases.items():
            with self.subTest(case):
                self.assertIsNone(build_assessment(row, sets, self.tmp))
        self.assertIsNotNone(build_assessment(broken('stale-instruction'), {}, self.tmp))
        (Path(self.tmp) / 'eaos.engagement.json').write_text(json.dumps({'rules': {'consolidate_duplicates': False}}))
        self.assertIsNone(build_assessment(claim(), SAME, self.tmp))

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


APP = {'app/__main__.py': 'from app import core\ncore.run()\n',
       'app/core.py': 'def run():\n    return 1\n\n\ndef forgotten():\n    return 2\n'}


class RemoveDeadTests(Workspace):
    """Confirmed dead code, under the engagement rule, becomes a ready removal card whose check really decides."""

    def cards(self, repo, out):
        execute(repo, out, skip=('engines',), language='en')
        return json.loads((out / 'plan.json').read_text())['tasks']

    def test_a_confirmed_dead_function_gets_a_ready_card_unless_the_rule_is_off(self):
        repo = Path(self.tmp) / 'repo'
        for name, text in APP.items():
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text(text)
        cards = [t for t in self.cards(repo, Path(self.tmp) / 'out') if t['pattern'] == 'remove_dead']
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual((card['kind'], card['decision']['readiness']), ('remediate', 'ready'))
        self.assertNotIn('human review', json.dumps(card['acceptance']))
        argv = card['decision']['checks'][0]['argv']
        run = lambda: subprocess.run(argv, cwd=repo, capture_output=True, text=True,
                                     env={'PYTHONPATH': str(ROOT), 'PATH': '/usr/bin:/bin'}).returncode
        self.assertEqual(run(), 1, 'the check must fail while the dead function is still there')
        (repo / 'app/core.py').write_text('def run():\n    return 1\n')
        self.assertEqual(run(), 0, 'the check must pass once it is removed')
        (repo / 'app/core.py').write_text(APP['app/core.py'])
        (repo / 'eaos.engagement.json').write_text(json.dumps({'rules': {'remove_dead_code': False}}))
        self.assertFalse([t for t in self.cards(repo, Path(self.tmp) / 'off') if t['decision']['readiness'] == 'ready'])
