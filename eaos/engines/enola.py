"""enola: a package-level architecture graph over 23 languages, in under a second.

It writes its output inside the repository it reads, so it reads a mirror. Its insights carry a
confidence the engine assigns itself; we record that number and still enter every finding as
heuristic, because one of them — the only cycle it reports here — is contradicted by its own facts.
"""
import json
import re
from pathlib import Path

from .contract import (Capability, Report, OBSERVED, UNAVAILABLE, ERROR, FILE, PACKAGE, SYMBOL,
                       finding, measurement, subject)
from .process import mirror, run, which

NAME, BINARY, PINNED = 'enola', 'enola', '0.4.21'

KIND_BY_SOURCE = {'cycles': 'cycle', 'god-class': 'coupling', 'hotspots': 'coupling',
                  'dependency-depth': 'coupling', 'import-closure': 'coupling',
                  'exported-surface': 'surface', 'complexity-outliers': 'complexity',
                  'performance': 'complexity', 'dead-code': 'dead_code', 'dead-methods': 'dead_code',
                  'unused-routes': 'dead_code', 'query-loops': 'dataflow', 'layers': 'boundary',
                  'constraints': 'boundary', 'vendored-candidates': 'duplication'}
COMPLEXITY = re.compile(r'cyclomatic complexity (\d+)')


# enola's cycle and coupling explainers work over package nodes; the rest name symbols.
GRANULARITY = {'cycle': PACKAGE, 'coupling': PACKAGE, 'boundary': PACKAGE}


def capabilities():
    return [Capability(kind, source, granularity=GRANULARITY.get(kind, SYMBOL))
            for source, kind in sorted(KIND_BY_SOURCE.items())]


def version():
    binary = which(BINARY)
    if not binary:
        return None
    code, out, _, _ = run([binary, '--version', '--json'], timeout=30)
    if code != 0:
        return None
    try:
        return json.loads(out).get('version')
    except ValueError:
        return None


def analyze(target, workdir, exclude=(), formats=None):
    found = version()
    if found is None:
        return Report(NAME, None, PINNED, UNAVAILABLE, reason='enola is not installed')
    workdir = Path(workdir)
    copy, mode = mirror(target, workdir)
    if exclude:
        (copy / 'mcp-arch.yaml').write_text(
            'repo: "."\nignore:\n' + ''.join(f'  - "{pattern}/**"\n' for pattern in exclude), encoding='utf-8')
    code, _, error, seconds = run([which(BINARY), '--generate', str(copy)], cwd=str(copy))
    produced = copy / '.enola'
    if code != 0 or not (produced / 'insights.json').is_file():
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or 'no insights written')
    insights = json.loads((produced / 'insights.json').read_text(encoding='utf-8'))
    receipt = json.loads((produced / 'receipt.json').read_text(encoding='utf-8'))
    kept = workdir / 'enola'
    kept.mkdir(parents=True, exist_ok=True)
    for name in ('insights.json', 'receipt.json'):
        (kept / name).write_text((produced / name).read_text(encoding='utf-8'), encoding='utf-8')
    findings, unmapped = [], {}
    for insight in insights:
        kind = KIND_BY_SOURCE.get(insight['source'])
        if kind is None:
            unmapped[insight['source']] = unmapped.get(insight['source'], 0) + 1
            continue
        evidence = (insight.get('evidence') or [{}])[0]
        key = evidence.get('symbol') or evidence.get('fact') or evidence.get('file')
        if not key:
            # A roll-up line ("127 more…") names nothing to act on; it is a summary, not a finding.
            unmapped[insight['source'] + ':summary'] = unmapped.get(insight['source'] + ':summary', 0) + 1
            continue
        detail = evidence.get('detail') or ''
        complexity = COMPLEXITY.search(detail)
        findings.append(finding(
            NAME, found, insight['source'], kind,
            subject('symbol' if evidence.get('symbol') else 'module', key, evidence.get('file'), evidence.get('line')),
            insight['title'],
            # The only number enola states structurally is in prose; parsed here, pinned by version.
            measurements=[measurement('cyclomatic_complexity', int(complexity.group(1)))] if complexity else (),
            engine_confidence=insight.get('confidence'), raw_ref='enola/insights.json'))
    evaluated = {KIND_BY_SOURCE[name]: {'status': 'observed', 'granularity': GRANULARITY.get(KIND_BY_SOURCE[name], SYMBOL)}
                 for name in receipt.get('explainers', []) if name in KIND_BY_SOURCE}
    coverage = {'status': 'observed', 'extractors': receipt.get('extractors', []),
                'explainers': receipt.get('explainers', []), 'mirror_mode': mode,
                'facts': receipt.get('fact_count'), 'insights': len(insights)}
    provenance = {'snapshot_id': receipt.get('snapshot_id'), 'extractor_version': receipt.get('extractor_version'),
                  'git': receipt.get('git'), 'generated_at': receipt.get('generated_at')}
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, coverage=coverage,
                  provenance=provenance, raw=str(kept), unmapped=unmapped, evaluated=evaluated)
