"""The SARIF reader drops nothing silently and lets a rule raise severity, never lower it."""
import json
from pathlib import Path

from shared_fixture import Workspace
from eaos.engines.sarif import read

SARIF = {'version': '2.1.0', 'runs': [{'tool': {'driver': {'name': 'x', 'rules': []}}, 'results': [
    {'ruleId': 'KNOWN-1', 'level': 'error', 'message': {'text': 'known'},
     'locations': [{'physicalLocation': {'artifactLocation': {'uri': 'a.py'}, 'region': {'startLine': 3}}}]},
    {'ruleId': 'OTHER-9', 'level': 'note', 'message': {'text': 'other'}}]}]}


class SarifTests(Workspace):
    def sarif(self):
        path = Path(self.tmp) / 'r.sarif'
        path.write_text(json.dumps(SARIF))
        return path

    def test_an_unmatched_result_is_counted_and_a_severity_floor_only_raises(self):
        findings, unmapped = read(self.sarif(), 'x', '1', [{'match': 'KNOWN-*', 'kind': 'vulnerability'}])
        self.assertEqual((len(findings), unmapped), (1, {'OTHER-9': 1}))
        severity = lambda floor: read(self.sarif(), 'x', '1', [{'match': 'KNOWN-*', 'kind': 'vulnerability', 'severity_floor': floor}])[0][0]['measurements'][0]['value']
        self.assertEqual((severity('critical'), severity('low')), ('critical', 'high'))

    def test_a_result_without_a_level_takes_its_rules_and_carries_the_rules_cwe_and_confidence(self):
        # Semgrep writes the level on the rule, not the result: every one of its findings on EAOS was read as low.
        rule = {'id': 'python.audit.subprocess', 'defaultConfiguration': {'level': 'error'},
                'properties': {'precision': 'very-high', 'tags': ["CWE-78: OS Command Injection", 'LOW CONFIDENCE']}}
        bandit = {'id': 'B608', 'properties': {'tags': ['security', 'external/cwe/cwe-089']}}
        path = Path(self.tmp) / 'levels.sarif'
        path.write_text(json.dumps({'version': '2.1.0', 'runs': [{'tool': {'driver': {'name': 'x', 'rules': [rule, bandit]}}, 'results': [
            {'ruleId': rule['id'], 'message': {'text': 'run'}, 'locations': [{'physicalLocation': {'artifactLocation': {'uri': 'a.py'}}}]},
            {'ruleId': 'B608', 'message': {'text': 'sql'}, 'properties': {'issue_confidence': 'MEDIUM'},
             'locations': [{'physicalLocation': {'artifactLocation': {'uri': 'b.py'}}}]}]}]}))
        found = read(path, 'x', '1', [{'match': '*', 'kind': 'vulnerability'}])[0]
        self.assertEqual([(f['measurements'][0]['value'], f['engine_confidence'], f['cwe']) for f in found],
                         [('high', 'low', ['CWE-78']), ('medium', 'medium', ['CWE-89'])])
