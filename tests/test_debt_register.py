"""The debt register: severity from the evidence, witnesses named, one register behind RISK-REGISTER.md."""
import json
from pathlib import Path

from shared_fixture import Workspace

from eaos.artifact_contracts import contracts, validate
from eaos.debt_register import build, hotspots


def finding(fid, engine, kind, path, method='heuristic', **value):
    return {'id': fid, 'kind': 'engine_finding', 'location': {'path': path},
            'value': {'engine': engine, 'kind': kind, 'method': method, 'message': value.pop('message', ''), 'sites': [], **value}}


def cluster(cid, kind, fact_ids):
    return {'id': cid, 'statement': f'{kind} at a place', 'claim_type': 'risk', 'confidence': 'LIKELY', 'fact_ids': fact_ids,
            'render': {'key': 'engine_cluster'}, 'probe_spec': {'specification': {'query': 'engine_cluster_present', 'kind': kind}},
            'impact': {'scenario': 'it hurts'}}


class RegisterTests(Workspace):
    def register(self, facts, claims, measurements=None, probes=None):
        out = Path(self.tmp)
        (out / 'facts').mkdir(exist_ok=True)
        (out / 'facts/all.json').write_text(json.dumps({'facts': facts}))
        if measurements: (out / 'measurements.json').write_text(json.dumps(measurements))
        if probes: (out / 'probes.json').write_text(json.dumps(probes))
        return build(out, {'claims': claims})

    def item(self, record, claim_id):
        return next(i for i in record['items'] if i['claim_id'] == claim_id)

    def test_high_on_one_heuristic_witness_is_written_medium_and_asks_for_a_probe(self):
        record = self.register([finding('F1', 'semgrep', 'secret', 'src/a.ts')], [cluster('CLM-1', 'secret', ['F1'])])
        item = self.item(record, 'CLM-1')
        self.assertEqual(item['severity'], 'medium')
        self.assertIn('probe must decide', item['probe_needed'])
        self.assertEqual(validate(record, contracts()['debt-register']), [])

    def test_two_tools_or_one_deterministic_witness_keep_high(self):
        facts = [finding('F1', 'semgrep', 'secret', 'src/a.ts'), finding('F2', 'trivy', 'secret', 'src/a.ts'),
                 finding('F3', 'osv-scanner', 'vulnerability', 'package-lock.json', method='deterministic')]
        vulnerable = {'id': 'CLM-2', 'statement': 'axios@1 is vulnerable', 'claim_type': 'risk', 'confidence': 'CONFIRMED',
                      'fact_ids': ['F3'], 'render': {'key': 'vulnerable_dependency', 'params': {'severity': 'critical'}}}
        record = self.register(facts, [cluster('CLM-1', 'secret', ['F1', 'F2']), vulnerable])
        self.assertEqual(self.item(record, 'CLM-1')['severity'], 'high')
        self.assertEqual(self.item(record, 'CLM-2')['severity'], 'critical')
        self.assertNotIn('probe_needed', self.item(record, 'CLM-2'))

    def test_a_cluster_is_witnessed_only_by_findings_of_its_own_kind(self):
        facts = [finding('F1', 'semgrep', 'secret', 'x.ts'), finding('F2', 'trivy', 'secret', 'x.ts'),
                 finding('F3', 'eaos', 'dead_code', 'x.ts', method='deterministic')]
        item = self.item(self.register(facts, [cluster('CLM-1', 'secret', ['F1', 'F2', 'F3'])]), 'CLM-1')
        self.assertEqual({w['finding_id'] for w in item['witnesses']}, {'F1', 'F2'})

    def test_a_public_key_is_low_whatever_the_scanners_pattern_says_and_is_one_item(self):
        credential = {'id': 'C1', 'kind': 'committed_credential', 'extractor': 'secrets', 'location': {'path': '.env'},
                      'value': {'severity': 'public', 'key_family': 'env_file'}}
        facts = [credential, finding('F1', 'semgrep', 'secret', '.env'), finding('F2', 'trivy', 'secret', '.env')]
        record = self.register(facts, [cluster('CLM-1', 'secret', ['F1', 'F2'])])
        self.assertEqual([i['severity'] for i in record['items']], ['low'])
        self.assertIn(('eaos.secrets', 'deterministic'), {(w['tool'], w['kind']) for w in record['items'][0]['witnesses']})

    def test_a_secret_key_alone_is_a_critical_item(self):
        credential = {'id': 'C1', 'kind': 'committed_credential', 'extractor': 'secrets', 'location': {'path': 'src/admin.ts'},
                      'value': {'severity': 'service_role', 'key_family': 'jwt'}}
        [item] = self.register([credential], [])['items']
        self.assertEqual((item['severity'], item['category'], item['claim_id']), ('critical', 'security', None))

    def test_a_confirmed_probe_is_a_witness(self):
        record = self.register([finding('F1', 'enola', 'coupling', 'a.ts')], [cluster('CLM-1', 'coupling', ['F1'])],
                               probes=[{'id': 'PRB-1', 'claim_id': 'CLM-1', 'status': 'CONFIRMED'}])
        self.assertIn({'tool': 'eaos.probe', 'finding_id': 'PRB-1', 'kind': 'probe'}, self.item(record, 'CLM-1')['witnesses'])

    def test_the_hotspot_keeps_its_three_ranks(self):
        rows = [{'path': p, 'complexity_max': c, 'churn': h, 'fan_in': f}
                for p, c, h, f in (('a.ts', 1, 1, 0), ('b.ts', 5, 3, 2), ('c.ts', 9, 9, 9))]
        heat = hotspots({'files': rows})
        self.assertEqual(heat['c.ts'], {'file': 'c.ts', 'complexity_pct': 1.0, 'churn_pct': 1.0, 'fan_in_pct': 1.0, 'score': 2.0})
        self.assertEqual(heat['a.ts']['score'], 0.0)
        record = self.register([finding('F1', 'enola', 'coupling', 'c.ts')], [cluster('CLM-1', 'coupling', ['F1'])],
                               measurements={'files': rows})
        self.assertEqual(self.item(record, 'CLM-1')['hotspot']['file'], 'c.ts')

    def test_the_risk_register_document_is_rendered_from_the_record(self):
        from eaos.dossier import write_register
        facts = [finding('F1', 'enola', 'coupling', 'a.ts')]
        out = Path(self.tmp)
        (out / 'facts').mkdir()
        (out / 'facts/all.json').write_text(json.dumps({'facts': facts}))
        write_register(out, {'claims': [cluster('CLM-7', 'coupling', ['F1'])]}, 'en')
        record = json.loads((out / 'debt-register.json').read_text())
        text = (out / 'RISK-REGISTER.md').read_text()
        self.assertIn(record['items'][0]['id'], text)
        self.assertIn(record['formula'], text)
