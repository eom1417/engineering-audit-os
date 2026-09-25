"""The SARIF reader drops nothing silently and lets a rule raise severity, never lower it."""
import json
import unittest
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

    def test_a_result_no_row_matches_is_counted_not_dropped(self):
        findings, unmapped = read(self.sarif(), 'x', '1', [{'match': 'KNOWN-*', 'kind': 'vulnerability'}])
        self.assertEqual((len(findings), unmapped), (1, {'OTHER-9': 1}))

    def test_a_severity_floor_raises_and_never_lowers(self):
        severity = lambda floor: read(self.sarif(), 'x', '1', [{'match': 'KNOWN-*', 'kind': 'vulnerability', 'severity_floor': floor}])[0][0]['measurements'][0]['value']
        self.assertEqual((severity('critical'), severity('low')), ('critical', 'high'))
