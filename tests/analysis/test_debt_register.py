"""The debt register: severity from the evidence, witnesses named, one register (debt-register.json)."""
import json
from pathlib import Path

from shared_fixture import Workspace

from eaos.core.contracts.artifact_rules import contracts, validate
from eaos.analysis.assessments.debt_register import build, hotspots


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

    def test_severity_follows_the_witnesses_and_a_committed_key_what_it_unlocks(self):
        facts = [finding('F1', 'semgrep', 'secret', 'src/a.ts'), finding('F2', 'trivy', 'secret', 'src/a.ts'),
                 finding('F3', 'osv-scanner', 'vulnerability', 'package-lock.json', method='deterministic'),
                 finding('F4', 'semgrep', 'secret', 'src/b.ts')]
        vulnerable = {'id': 'CLM-2', 'statement': 'axios@1 is vulnerable', 'claim_type': 'risk', 'confidence': 'CONFIRMED',
                      'fact_ids': ['F3'], 'render': {'key': 'vulnerable_dependency', 'params': {'severity': 'critical'}}}
        record = self.register(facts, [cluster('CLM-1', 'secret', ['F1', 'F2']), vulnerable,
                                       cluster('CLM-3', 'secret', ['F4'])])
        self.assertEqual(validate(record, contracts()['debt-register']), [])
        self.assertEqual(self.item(record, 'CLM-1')['severity'], 'high')
        self.assertEqual(self.item(record, 'CLM-2')['severity'], 'critical')
        self.assertNotIn('probe_needed', self.item(record, 'CLM-2'))
        # High on one heuristic witness is written medium and asks for a probe.
        self.assertEqual(self.item(record, 'CLM-3')['severity'], 'medium')
        self.assertIn('probe must decide', self.item(record, 'CLM-3')['probe_needed'])
        # A committed key is rated by what it unlocks.
        public = {'id': 'C1', 'kind': 'committed_credential', 'extractor': 'secrets', 'location': {'path': '.env'},
                  'value': {'severity': 'public', 'key_family': 'env_file'}}
        record = self.register([public, finding('F1', 'semgrep', 'secret', '.env'), finding('F2', 'trivy', 'secret', '.env')],
                               [cluster('CLM-1', 'secret', ['F1', 'F2'])])
        self.assertEqual([i['severity'] for i in record['items']], ['low'])
        self.assertIn(('eaos.secrets', 'deterministic'), {(w['tool'], w['kind']) for w in record['items'][0]['witnesses']})
        secret = {'id': 'C1', 'kind': 'committed_credential', 'extractor': 'secrets', 'location': {'path': 'src/admin.ts'},
                  'value': {'severity': 'service_role', 'key_family': 'jwt'}}
        [item] = self.register([secret], [])['items']
        self.assertEqual((item['severity'], item['category'], item['claim_id']), ('critical', 'security', None))

    def test_witnesses_are_findings_of_the_claims_kind_and_its_confirmed_probe(self):
        facts = [finding('F1', 'semgrep', 'secret', 'x.ts'), finding('F2', 'trivy', 'secret', 'x.ts'),
                 finding('F3', 'eaos', 'dead_code', 'x.ts', method='deterministic')]
        item = self.item(self.register(facts, [cluster('CLM-1', 'secret', ['F1', 'F2', 'F3'])]), 'CLM-1')
        self.assertEqual({w['finding_id'] for w in item['witnesses']}, {'F1', 'F2'})
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
