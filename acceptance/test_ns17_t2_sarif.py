"""NS17.T2 — one SARIF reader for every tool that writes SARIF.

Interface this task must provide:
    from eaos.engines.sarif import read
    findings, unmapped = read(path, engine, version, rules=None)
      path     a SARIF 2.1.0 file
      rules    [{"match": fnmatch pattern on ruleId, "kind": a KINDS value, "severity_floor": optional}];
               None loads eaos/rules/sarif-rules.json[engine]
      findings a list of eaos.engines.contract.finding() dicts, one per SARIF result that a rule matches;
               every location of the result is a site; measurements hold {"name": "severity", "value": ...}
      unmapped {ruleId: count} for results no rule matches; never silently dropped
    severity: properties.security-severity >= 9 critical, >= 7 high, >= 4 medium, else low; without it,
              level error -> high, warning -> medium, note or none -> low; never below severity_floor.
"""
import json
import unittest
from pathlib import Path

SAMPLE = Path(__file__).parent / 'fixtures/sample.sarif'
RULES = [{'match': 'eaos.supabase-*', 'kind': 'dataflow'},
         {'match': 'eaos.string-built-sql', 'kind': 'vulnerability'}]


class SarifReader(unittest.TestCase):
    def read(self, rules=RULES):
        from eaos.engines.sarif import read
        return read(SAMPLE, 'semgrep', '1.90.0', rules)

    def test_matched_results_become_findings_and_the_rest_are_counted(self):
        findings, unmapped = self.read()
        self.assertEqual(sorted(f['kind'] for f in findings), ['dataflow', 'vulnerability'])
        self.assertEqual(unmapped, {'vendor.unknown-rule': 1})

    def test_every_location_is_a_site(self):
        findings, _ = self.read()
        sql = next(f for f in findings if f['kind'] == 'vulnerability')
        self.assertEqual(sorted(sql['sites']), [('src/db/query.ts', 40), ('src/db/report.ts', 7)])
        self.assertEqual(sql['rule'], 'eaos.string-built-sql')
        self.assertEqual(sql['engine'], 'semgrep')

    def test_severity_follows_security_severity_then_level(self):
        findings, _ = self.read()
        severity = {f['kind']: next(m['value'] for m in f['measurements'] if m['name'] == 'severity') for f in findings}
        self.assertEqual(severity, {'vulnerability': 'high', 'dataflow': 'medium'})

    def test_a_severity_floor_raises_but_never_lowers(self):
        rules = [dict(RULES[0], severity_floor='critical'), dict(RULES[1], severity_floor='low')]
        findings, _ = self.read(rules)
        severity = {f['kind']: next(m['value'] for m in f['measurements'] if m['name'] == 'severity') for f in findings}
        self.assertEqual(severity, {'vulnerability': 'high', 'dataflow': 'critical'})

    def test_ids_are_stable_across_reads(self):
        self.assertEqual([f['id'] for f in self.read()[0]], [f['id'] for f in self.read()[0]])

    def test_the_rules_file_covers_every_sarif_tool(self):
        path = Path(__file__).resolve().parent.parent / 'eaos/rules/sarif-rules.json'
        rules = json.loads(path.read_text(encoding='utf-8'))
        for engine in ('semgrep', 'trivy', 'checkov', 'osv-scanner', 'spectral', 'zap'):
            self.assertTrue(rules.get(engine), f'{engine} has no rows in eaos/rules/sarif-rules.json')
            for row in rules[engine]:
                self.assertEqual(set(row) - {'match', 'kind', 'severity_floor'}, set(), row)

    def test_the_default_rules_are_used_when_none_are_given(self):
        from eaos.engines.sarif import read
        findings, unmapped = read(SAMPLE, 'semgrep', '1.90.0')
        self.assertEqual(len(findings) + sum(unmapped.values()), 3)


if __name__ == '__main__':
    unittest.main()
