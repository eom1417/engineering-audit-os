"""SARIF 2.1.0, read once for every tool that writes it: Semgrep, Trivy, Checkov, OSV-Scanner, Spectral, ZAP.

A tool adapter builds its command, runs it, and hands the SARIF file here. Which EAOS kind a rule becomes is
data, in eaos/rules/sarif-rules.json, not code: the first row whose `match` (fnmatch on the ruleId) fits wins.
A result no row matches is counted in `unmapped` by ruleId, never dropped silently.

Severity: properties.security-severity (the CVSS-like score SARIF producers publish) decides when present:
>= 9 critical, >= 7 high, >= 4 medium, else low. Without it the SARIF level decides: error high, warning
medium, note or none low. A row's severity_floor raises it and never lowers it.
"""
import json
from fnmatch import fnmatch
from pathlib import Path

from .contract import finding, measurement, subject

RULES = Path(__file__).resolve().parent.parent / 'rules/sarif-rules.json'
ORDER = ['low', 'medium', 'high', 'critical']


def _severity(result, rule_properties):
    raw = (result.get('properties') or {}).get('security-severity') or rule_properties.get('security-severity')
    if raw is not None:
        try: score = float(raw)
        except (TypeError, ValueError): score = None
        if score is not None:
            return 'critical' if score >= 9 else 'high' if score >= 7 else 'medium' if score >= 4 else 'low'
    return {'error': 'high', 'warning': 'medium'}.get(result.get('level'), 'low')


def _sites(result):
    sites = []
    for location in result.get('locations') or []:
        physical = location.get('physicalLocation') or {}
        path = (physical.get('artifactLocation') or {}).get('uri')
        if path: sites.append({'path': path.removeprefix('file://'), 'line': (physical.get('region') or {}).get('startLine')})
    return sites


def read(path, engine, version, rules=None):
    """(findings, unmapped) from one SARIF file; see the module docstring for the mapping and severity."""
    if rules is None:
        rules = json.loads(RULES.read_text(encoding='utf-8')).get(engine, [])
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    findings, unmapped = [], {}
    for run in data.get('runs') or []:
        driver = (run.get('tool') or {}).get('driver') or {}
        properties = {rule.get('id'): rule.get('properties') or {} for rule in driver.get('rules') or []}
        for result in run.get('results') or []:
            rule_id = result.get('ruleId') or ''
            row = next((row for row in rules if fnmatch(rule_id, row['match'])), None)
            if row is None:
                unmapped[rule_id] = unmapped.get(rule_id, 0) + 1
                continue
            severity = _severity(result, properties.get(rule_id, {}))
            floor = row.get('severity_floor')
            if floor and ORDER.index(floor) > ORDER.index(severity): severity = floor
            sites = _sites(result) or [{'path': None, 'line': None}]
            findings.append(finding(engine, version, rule_id, row['kind'],
                                    subject('file', sites[0]['path'], sites[0]['path'], sites[0]['line']),
                                    ((result.get('message') or {}).get('text') or rule_id)[:500],
                                    measurements=[measurement('severity', severity)], sites=sites))
    return findings, unmapped
