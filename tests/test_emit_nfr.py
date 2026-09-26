"""Load, fault and scan plans in their tools' formats, from the intake and the facts, with no host written."""
import json
from pathlib import Path

from shared_fixture import Workspace

from eaos.emit import nfr
from eaos.emit.shape import problems


class NfrTests(Workspace):
    def report(self):
        out = Path(self.tmp)
        (out / 'facts').mkdir()
        (out / 'features.json').write_text(json.dumps({'features': [
            {'name': 'contas', 'surfaces': ['/_authenticated/contas', '/_authenticated/contas_/$id'], 'tables': ['accounts'], 'files': ['src/a.ts']},
            {'name': 'cotacoes', 'surfaces': ['/cotacoes'], 'files': ['src/market.ts']}]}))
        (out / 'facts/entrypoints.json').write_text(json.dumps({'facts': [
            {'kind': 'entry_point', 'location': {'path': 'src/r.tsx'}, 'value': {'route': r, 'surface': 'page'}}
            for r in ('/_authenticated/contas', '/_authenticated/contas_/$id', '/cotacoes')] + [
            {'kind': 'data_access', 'location': {'path': 'src/a.ts'}, 'value': {'client': 'supabase'}}]}))
        (out / 'facts/domain.json').write_text(json.dumps({'facts': [
            {'kind': 'integration_target', 'location': {'path': 'src/market.ts'}, 'value': {'host': 'brapi.dev'}},
            {'kind': 'integration_target', 'location': {'path': 'tests/x.ts'}, 'value': {'host': 'mock.dev'}},
            {'kind': 'integration_target', 'location': {'path': 'src/ns.ts'}, 'value': {'host': 'www.w3.org'}},
            {'kind': 'integration_target', 'location': {'path': 'old/client.ts'}, 'value': {'host': 'abc.supabase.co'}}]}))
        (out / 'facts/deadcode.json').write_text(json.dumps({'facts': [
            {'kind': 'engine_finding', 'location': {'path': 'old/client.ts'}, 'value': {'rule': 'unreachable-module'}}]}))
        (out / 'intake.json').write_text(json.dumps({'scenarios': [
            {'id': 'QS-001', 'kind': 'load', 'stimulus': '250 users at the same time use contas', 'response': 'r', 'source': 'answer',
             'measure': {'metric': 'p95_ms', 'threshold': 800, 'unit': 'ms'}, 'question_id': 'concurrent_users'},
            {'id': 'QS-002', 'kind': 'latency', 'stimulus': 's', 'response': 'r', 'source': 'default',
             'measure': {'metric': 'error_rate', 'threshold': 0.02, 'unit': 'ratio'}, 'question_id': 'concurrent_users'}]}))
        return out, nfr.write(out)

    def test_k6_runs_the_scenario_over_the_routes_that_need_no_fixture(self):
        out, _ = self.report()
        script = (out / 'nfr/k6/qs-001.js').read_text()
        self.assertIn("target: 250", script)
        self.assertIn("'p(95)<800'", script)
        self.assertIn("'rate<0.02'", script)
        self.assertIn('["/contas", "/cotacoes"]', script)
        self.assertIn('__ENV.BASE_URL', script)
        self.assertNotIn('http://', script)

    def test_every_dependency_is_a_proxy_whose_upstream_is_a_variable(self):
        out, _ = self.report()
        proxies = json.loads((out / 'nfr/toxiproxy.json').read_text())
        self.assertEqual([(p['name'], p['upstream']) for p in proxies],
                         [('supabase', '${SUPABASE_UPSTREAM}'), ('brapi.dev', '${BRAPI_DEV_UPSTREAM}')])
        self.assertEqual(problems('toxiproxy', proxies), [])

    def test_each_proxy_gets_three_faults_with_the_expected_behaviour_and_features(self):
        out, _ = self.report()
        record = json.loads((out / 'nfr/experiments.json').read_text())
        self.assertEqual(problems('experiments', record), [])
        brapi = [e for e in record['experiments'] if e['dependency'] == 'brapi.dev']
        self.assertEqual([e['toxic'] for e in brapi], ['latency', 'timeout', 'down'])
        self.assertEqual(brapi[0]['features'], ['cotacoes'])
        self.assertIn('within 5 seconds', brapi[1]['expected'])

    def test_the_zap_plan_has_its_automation_shape(self):
        out, _ = self.report()
        plan = json.loads((out / 'nfr/zap.yaml').read_text())
        self.assertEqual(problems('zap', plan), [])
        self.assertEqual([job['type'] for job in plan['jobs']], ['spider', 'requestor', 'passiveScan-wait', 'report'])

    def test_every_file_is_put_to_its_tool_and_k6_accepts_its_script(self):
        from eaos.emit import emit
        from eaos.engines.process import which
        out, written = self.report()
        self.assertEqual(sorted(e.tool for e in written), ['k6', 'schema', 'schema', 'schema'])
        if not which('k6'): self.skipTest('k6 is not installed')
        _, rows = emit(out, only=['nfr'], validate=True)
        self.assertTrue(all(row['ok'] for row in rows), rows)
