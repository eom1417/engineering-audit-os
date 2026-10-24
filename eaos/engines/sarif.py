"""SARIF 2.1.0, read once for every tool that writes it: Semgrep, Trivy, Checkov, OSV-Scanner, Spectral, ZAP.

A tool adapter builds its command, runs it, and hands the SARIF file here. Which EAOS kind a rule becomes is
data, in eaos/rules/sarif-rules.json, not code: the first row whose `match` (fnmatch on the ruleId) fits wins.
A result no row matches is counted in `unmapped` by ruleId, never dropped silently.

Severity: properties.security-severity (the CVSS-like score SARIF producers publish) decides when present:
>= 9 critical, >= 7 high, >= 4 medium, else low. Without it the SARIF level decides: error high, warning medium,
note or none low; a result that names no level has its rule's (defaultConfiguration, as Semgrep writes it), else
SARIF's default, warning. A row's severity_floor raises it and never lowers it.

Confidence, how sure the engine is of its own rule (engine_confidence: high, medium or low; None when it does not
say): the result's issue_confidence (Bandit), else a `LOW CONFIDENCE` tag (Semgrep, whose precision property says
very-high on every rule), else the rule's precision (CodeQL).

The weaknesses a rule names (CWE-78, ...) are read from its tags and the result's, in whichever spelling the tool
writes them (Semgrep `CWE-78: ...`, Bandit `external/cwe/cwe-78`, CodeQL `external/cwe/cwe-078`), so two engines
reporting the same weakness can be told apart from two reporting different ones at the same file.
"""
import json
import re
from fnmatch import fnmatch
from pathlib import Path

from .contract import finding, measurement, subject

RULES = Path(__file__).resolve().parent.parent / 'rules/sarif-rules.json'
ORDER = ['low', 'medium', 'high', 'critical']
CWE = re.compile(r'\bcwe[-/:]?0*(\d+)', re.IGNORECASE)


def _results(data):
    """(rules by id, result) for every result of every run."""
    for run in data.get('runs') or []:
        driver = (run.get('tool') or {}).get('driver') or {}
        rules = {rule.get('id'): rule for rule in driver.get('rules') or []}
        for result in run.get('results') or []:
            yield rules, result


def _artifacts(result):
    """(physicalLocation, artifactLocation) for every location of a result."""
    for location in result.get('locations') or []:
        physical = location.get('physicalLocation') or {}
        yield physical, physical.get('artifactLocation') or {}


def _score(raw):
    try: return float(raw)
    except (TypeError, ValueError): return None


def _severity(result, rule, floor):
    score = _score((result.get('properties') or {}).get('security-severity') or (rule.get('properties') or {}).get('security-severity'))
    if score is not None:
        severity = 'critical' if score >= 9 else 'high' if score >= 7 else 'medium' if score >= 4 else 'low'
    else: severity = {'error': 'high', 'warning': 'medium'}.get(_level(result, rule), 'low')
    return floor if floor and ORDER.index(floor) > ORDER.index(severity) else severity


def _level(result, rule):
    """A result's SARIF level: its own, else its rule's default, else SARIF's default, warning."""
    return result.get('level') or (rule.get('defaultConfiguration') or {}).get('level') or 'warning'


def _tags(result, rule):
    return [tag for tag in ((rule.get('properties') or {}).get('tags') or []) + ((result.get('properties') or {}).get('tags') or [])
            if isinstance(tag, str)]


def _cwe(result, rule):
    return {f'CWE-{int(found)}' for tag in _tags(result, rule) for found in CWE.findall(tag)}


def _confidence(result, rule):
    said = ((result.get('properties') or {}).get('issue_confidence')
            or next((tag.split()[0] for tag in _tags(result, rule) if tag.upper().endswith(' CONFIDENCE')), None)
            or (rule.get('properties') or {}).get('precision'))
    said = str(said or '').lower().replace('very-', '')
    return said if said in ('high', 'medium', 'low') else None


def _sites(result):
    return [{'path': artifact['uri'].removeprefix('file://'), 'line': (physical.get('region') or {}).get('startLine')}
            for physical, artifact in _artifacts(result) if artifact.get('uri')]


def read(path, engine, version, rules=None):
    """(findings, unmapped) from one SARIF file; see the module docstring for the mapping and severity."""
    if rules is None:
        rules = json.loads(RULES.read_text(encoding='utf-8')).get(engine, [])
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    findings, unmapped = [], {}
    for known, result in _results(data):
        rule_id = result.get('ruleId') or ''
        row = _row(rules, rule_id)
        if row is None:
            unmapped[rule_id] = unmapped.get(rule_id, 0) + 1
            continue
        rule = known.get(rule_id) or {}
        severity = _severity(result, rule, row.get('severity_floor'))
        sites = _sites(result) or [{'path': None, 'line': None}]
        findings.append(finding(engine, version, rule_id, row['kind'],
                                subject('file', sites[0]['path'], sites[0]['path'], sites[0]['line']),
                                ((result.get('message') or {}).get('text') or rule_id)[:500],
                                measurements=[measurement('severity', severity)], sites=sites,
                                engine_confidence=_confidence(result, rule), cwe=_cwe(result, rule)))
    return findings, unmapped


def _row(rules, rule_id):
    """The first row of the rules whose `match` fits the ruleId, or None."""
    return next((row for row in rules if fnmatch(rule_id, row['match'])), None)


def relative(uri, target):
    """A SARIF location as a project-relative path. Tools differ: absolute, file://, or relative to the
    target's parent (Checkov writes `project/Dockerfile`); the last is stripped only when the file exists."""
    text, root = str(uri or ''), Path(target).resolve()
    for prefix in ('file://' + str(root) + '/', str(root) + '/'):
        if text.startswith(prefix): return text[len(prefix):]
    head, _, rest = text.partition('/')
    if head == root.name and rest and (root / rest).exists(): return rest
    return text


def relativise(path, target):
    """Rewrite every result location in a SARIF file to a project-relative path, in place, before any
    finding id is derived from it, so an id never depends on where the project was checked out."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    for _, result in _results(data):
        for _, artifact in _artifacts(result):
            if 'uri' in artifact: artifact['uri'] = relative(artifact['uri'], target)
    Path(path).write_text(json.dumps(data), encoding='utf-8')


class Declared:
    """An engine a person added (eaos/core/tools_catalog.py): its `engine` entry says how to run it ({target} and {output} in
    its args) and that it writes SARIF; its findings read like every SARIF engine's, every rule a `risk` unless mapped."""

    def __init__(self, entry):
        self.NAME, self.PINNED, self.entry = entry['name'], entry['version'], entry

    def capabilities(self):
        return []

    def version(self):
        from . import tool
        return tool.version(self.entry['binary'])

    def analyze(self, target, workdir, exclude=(), formats=None):
        from . import tool
        from .contract import ERROR, OBSERVED, Report
        from .process import run, which
        if declined := tool.declined(self.NAME, self.entry['binary'], target): return declined
        output = Path(workdir) / self.NAME / 'out.sarif'
        output.parent.mkdir(parents=True, exist_ok=True)
        args = [str(a).replace('{target}', str(Path(target).resolve())).replace('{output}', str(output)) for a in self.entry['engine']['args']]
        code, _, error, seconds = run([which(self.entry['binary']), *args], cwd=output.parent)
        if not output.is_file(): return Report(self.NAME, self.version(), self.PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
        findings, unmapped = read(output, self.NAME, self.version(), self.entry['engine'].get('rules') or [{'match': '*', 'kind': 'risk'}])
        return Report(self.NAME, self.version(), self.PINNED, OBSERVED, seconds=seconds, findings=findings, unmapped=unmapped, raw=str(output))


def declared():
    """{name: engine} of every added tool that declares an `engine`."""
    from ..core.toolchain import registry
    return {t['name']: Declared(t) for t in registry()['tools'] if t.get('engine')}

