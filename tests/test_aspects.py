"""Every aspect of the program reaches the person's assistant and gets a verdict (eaos/aspects.py), with the evidence
stages restored in 0.0.9: production readiness (eaos/production_readiness.py), the architecture map's digest
(eaos/engines/architecture.py) and the capped journeys (eaos/behavior_lock.py)."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import shared_fixture  # noqa: F401  (runs without measured detector verdicts)
from shared_fixture import Workspace


def _write(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record) if not isinstance(record, str) else record)


class Readiness(Workspace):
    def report(self, baseline=None):
        out = Path(self.tmp)
        _write(out / 'features.json', {'features': [{'name': 'quotes', 'surfaces': ['/quotes', '/api/health'], 'files': ['src/market.ts']}]})
        _write(out / 'facts/entrypoints.json', {'facts': [
            {'kind': 'entry_point', 'location': {'path': 'src/r.tsx'}, 'value': {'route': r, 'surface': 'page'}} for r in ('/quotes', '/api/health')]})
        _write(out / 'facts/runtime.json', {'facts': [
            {'id': 'FACT-int', 'kind': 'integration_target', 'location': {'path': 'src/market.ts'}, 'value': {'host': 'brapi.dev'}},
            {'id': 'FACT-res', 'kind': 'resilience_policy', 'location': {'path': 'src/market.ts'},
             'value': {'host': 'brapi.dev', 'has_timeout': False, 'has_retry': True, 'has_circuit_breaker': False}}]})
        _write(out / 'intake.json', {'scenarios': [
            {'id': 'QS-001', 'kind': 'load', 'stimulus': '250 users use quotes', 'response': 'r', 'source': 'answer',
             'measure': {'metric': 'p95_ms', 'threshold': 800, 'unit': 'ms'}}]})
        if baseline: _write(out / 'live/baseline.json', baseline)
        return out

    def test_faults_scans_health_telemetry_and_the_load_baseline_become_findings_with_evidence(self):
        from eaos.production_readiness import build
        record = build(self.report())
        rows = {f['id']: f for f in record['findings']}
        self.assertEqual(rows['RDY-resilience-brapi.dev']['status'], 'gap')
        self.assertIn('no circuit breaker, timeout', rows['RDY-resilience-brapi.dev']['detail'])
        self.assertEqual(rows['RDY-resilience-brapi.dev']['evidence'], ['FACT-res'])
        self.assertIn('/quotes', rows['RDY-security-scan']['detail'])
        self.assertEqual(rows['RDY-security-authentication']['status'], 'gap')
        self.assertEqual((rows['RDY-observability-health']['status'], rows['RDY-observability-telemetry']['status']), ('ok', 'gap'))
        self.assertEqual(rows['RDY-performance-QS-001']['status'], 'unmeasured')
        measured = build(self.report({'conditions': {}, 'scenarios': [{'id': 'QS-001', 'threshold': 800, 'before': {'p95_ms': 1250.0, 'error_rate': 0}}]}),
                         measured=True)
        self.assertEqual(next(f for f in measured['findings'] if f['id'] == 'RDY-performance-QS-001')['status'], 'gap')

    def test_the_city_and_the_clusters_are_read_into_hotspots_and_clusters(self):
        from eaos.engines.architecture import digest
        folder = Path(self.tmp) / 'architecture'
        _write(folder / 'city.cc.json', {'files': [{'id': 'r', 'name': 'root', 'type': 'Folder', 'children': [
            {'id': 'a', 'name': 'app', 'type': 'Folder', 'children': [{'id': 'm', 'name': 'main.py', 'type': 'File'},
                                                                     {'id': 'p', 'name': 'prices.py', 'type': 'File'}]}]}],
            'lenses': {'metrics': {'attributes': {'m': {'complexity': 2, 'rloc': 10}, 'p': {'complexity': 9, 'rloc': 40}}},
                       'git': {'attributes': {'m': {'number_of_commits': 1}, 'p': {'number_of_commits': 7}}}}})
        _write(folder / 'emerge/python/emerge-statistics-and-metrics.json', {
            'overall-metrics': {'louvain-modularity-dependency-graph': 0.4},
            'local-metrics': {'shop/app/main.py': {'fan-in-dependency-graph': 0, 'file_result_dependency_graph_louvain-modularity-in-file': 0},
                              'shop/app/prices.py': {'fan-in-dependency-graph': 3, 'file_result_dependency_graph_louvain-modularity-in-file': 0}}})
        found = digest(folder)
        self.assertEqual([h['path'] for h in found['hotspots']], ['app/prices.py', 'app/main.py'])
        self.assertEqual(found['clusters'], [{'id': 'python-0', 'files': 2, 'members': ['app/prices.py', 'app/main.py'],
                                              'most_depended_on': 'app/prices.py'}])
        self.assertEqual(found['modularity'], 0.4)

    def test_journeys_stay_light_on_disk(self):
        from eaos import behavior_lock
        folder = Path(self.tmp)
        (folder / 'rrweb').mkdir()
        (folder / 'traces').mkdir()
        (folder / 'rrweb/big.rrweb.json').write_bytes(b'x' * 50)
        for n in range(3): (folder / f'rrweb/{n}.rrweb.json').write_bytes(b'x')
        for n in range(2): (folder / f'traces/{n}.zip').write_bytes(b'x')
        with mock.patch.multiple(behavior_lock, RECORDING_BYTES=10, JOURNEYS=2, TRACE_BYTES=10, TRACES=1):
            kept = behavior_lock.cap_journeys(folder)
        self.assertEqual((kept['recordings'], kept['traces']), (['0.rrweb.json', '1.rrweb.json'], ['0.zip']))
        self.assertEqual(sorted(p.name for p in folder.glob('*/*')), ['0.rrweb.json', '0.zip', '1.rrweb.json'])
        self.assertEqual([d['why'] for d in kept['recordings_dropped']], ['more than 2 kept', 'larger than 10 bytes'])


FILES = {'app/__init__.py': '',
         'app/main.py': 'from app.prices import price\nfrom app.tax import tax\n\n\ndef run():\n    return price(3) + tax(3)\n',
         'app/prices.py': 'def price(n, rate=2, floor=1):\n    if n > 10:\n        return n * rate\n    return max(n, floor) * rate\n',
         'app/tax.py': 'def tax(n, rate=2, floor=1):\n    if n > 10:\n        return n * rate\n    return max(n, floor) * rate\n'}


class Planner:
    """The person's assistant, faked: it reads the bundle, keeps one aspect and improves another with a card."""
    assistant, model = 'Claude Code', 'fake-model'

    def __init__(self): self.bundles = []

    def __call__(self, name, prompt, schema):
        bundle = json.loads(prompt[prompt.rindex('The bundle:\n') + len('The bundle:\n'):])
        self.bundles.append(bundle)
        card = bundle['cards'][0]['id']
        answer = {'views': {}, 'departures': [], 'open_questions': [], 'confidence': 0.7, 'aspects': [
            {'aspect': 'sustainability', 'verdict': 'keep', 'why': 'Every measured indicator meets its target.', 'plan': '', 'cards': [], 'cites': []},
            {'aspect': 'canonical_homes', 'verdict': 'improve', 'why': 'The rule is written twice.', 'plan': 'Move it to one module.',
             'cards': [card, 'TASK-invented'], 'cites': []}]}
        return answer if name == 'plan' else {'critique': {'missed': [], 'risks': [], 'order': []}, 'ideal': answer}


class EveryAspectReachesTheAssistant(unittest.TestCase):
    def test_every_restored_aspect_is_in_the_planners_bundle_and_its_verdicts_reach_the_gap_report(self):
        from eaos.compose.four_reports import write as reports
        from eaos.pipeline.run import execute
        from eaos.studio import ideal
        from eaos.target_architecture import reconcile, render
        with tempfile.TemporaryDirectory() as tmp:
            project, out = Path(tmp) / 'shop', Path(tmp) / 'out'
            for name, text in FILES.items():
                (project / name).parent.mkdir(parents=True, exist_ok=True)
                (project / name).write_text(text)
            for argv in (['init', '-q'], ['add', '-A'], ['commit', '-qm', 'first']):
                subprocess.run(['git', '-C', str(project), '-c', 'user.name=t', '-c', 'user.email=t@t', *argv], check=True)
            with mock.patch.dict(os.environ, {'EAOS_ASSISTANT': 'none'}):
                manifest = execute(project, out, language='en')
            for stage in ('verify', 'readiness', 'sustainability', 'transform'):
                self.assertIn(manifest['stages'][stage]['status'], ('ok', 'unavailable'), stage)
            # The live stages and the map, as a check that ran them leaves them.
            _write(out / 'architecture/map.json', {'digest': {'hotspots': [{'path': 'app/prices.py', 'complexity': 3}], 'clusters': []}})
            _write(out / 'live/journeys.json', {'walked': [{'spec': 'quotes.spec.ts', 'pages': ['/quotes'], 'status': 'failed',
                                                            'reason': 'the page threw'}]})
            manifest['stages']['architecture']['status'] = manifest['stages']['journeys']['status'] = 'ok'
            _write(out / 'run-manifest.json', manifest)

            planner = Planner()
            self.assertEqual(ideal.plan(out, launcher=planner, lang='en')['state'], 'planned')
            seen = planner.bundles[0]['aspects']
            self.assertEqual(set(seen), {'structure', 'sustainability', 'canonical_homes', 'tests', 'journeys', 'performance',
                                         'resilience', 'security', 'observability', 'screens', 'findings'})
            self.assertEqual(seen['structure']['city_hotspots'][0]['path'], 'app/prices.py')
            self.assertEqual(seen['journeys']['failures'], [{'spec': 'quotes.spec.ts', 'reason': 'the page threw'}])
            self.assertEqual(len(seen['sustainability']['indicators']), 6)
            self.assertTrue(seen['canonical_homes']['homes'])
            self.assertEqual(seen['tests']['rules_verdict'], 'improve')
            self.assertIn('findings', seen['resilience'])
            self.assertTrue(seen['performance']['findings'])

            render(out, reconcile(out, planned=True), language='en')
            reports(out, 'en')
            gap = ' '.join((out / 'GAP-AND-STRATEGY.md').read_text().split())
            target = (out / 'TARGET-STATE.md').read_text()
        self.assertIn('Sustainability indicators: keep: already right, nothing changes. Every measured indicator meets its '
                      'target. (your assistant)', gap)
        self.assertIn('One home per repeated definition: improve. The rule is written twice. Plan: Move it to one module. '
                      '(TASK-001) (your assistant)', gap)
        self.assertNotIn('TASK-invented', gap)
        self.assertIn('Tests and coverage: improve. the project has no test file (the rules)', gap)
        self.assertIn('Every aspect of the program: keep or improve', target)


if __name__ == '__main__':
    unittest.main()
