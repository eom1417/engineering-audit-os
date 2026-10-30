"""Findings from pinned external engines, normalised into facts.

This set is the one place where evidence we did not compute ourselves enters the system. It is
opt-in, it records which engines were absent as plainly as what the present ones found, and it
carries no timing or path from the run, so two runs of the same engine versions over the same
tree produce the same bytes.
"""
from . import digest, make
from .source import LANGUAGE_BY_SUFFIX
from ..engines.contract import ERROR, SCHEMA_MISMATCH
from pathlib import Path

NAME = 'external'
VERSION = '1'
LIMITATIONS = [
    'Every finding here comes from an engine whose rules we did not implement and cannot vouch for; '
    'it is heuristic evidence, and one engine agreeing with itself is not corroboration.',
    'An engine that is not installed produces no findings and no silence: its absence is recorded as '
    'reduced coverage, never as a clean result.',
    'Engine versions are pinned. A version that does not match its pin is still recorded, and marked.',
]


def source_formats():
    """The languages our own extraction understands, so an engine is asked the same question we ask."""
    return sorted(set(LANGUAGE_BY_SUFFIX.values()))


def _copy_artifacts(manifest, out):
    # What an engine produced for the report itself (Syft's SBOM) is copied in under its declared name.
    import shutil
    for report in manifest['engines'].values():
        for artifact, path in (report.get('artifacts') or {}).items():
            if Path(path).is_file(): shutil.copyfile(path, Path(out) / artifact)


def metric_facts(manifest, input_sha):
    return [make('symbol_metric_external', NAME, VERSION, input_sha,
                 {'path': row['path'], 'line': row.get('line'), 'symbol': row.get('symbol')},
                 {'engine': name, 'engine_version': report.get('version'),
                  'granularity': row.get('granularity', 'file'), **row['measurements']},
                 limitations=LIMITATIONS[:1])
            for name, report in sorted(manifest['engines'].items()) for row in report.get('metrics') or []]


def _finding_fact(item, input_sha):
    """The fact of one finding; one the project justified on its line is an `engine_finding_justified`, with its
    reason: shown apart, never a card, and still held against a change by the gates (assessments/weaknesses.py new)."""
    subject = item['subject']
    return make('engine_finding_justified' if item.get('justified') else 'engine_finding', NAME, VERSION, input_sha,
                {'path': subject.get('path'), 'line': subject.get('line'), 'symbol': subject.get('key')},
                {'engine': item['engine'], 'engine_version': item['engine_version'], 'rule': item['rule'],
                 'kind': item['kind'], 'method': item['method'], 'message': item['message'],
                 'measurements': item['measurements'], 'engine_confidence': item['engine_confidence'],
                 'subject_kind': subject.get('kind'), 'cwe': item.get('cwe') or [],
                 'sites': [{'path': path, 'line': line} for path, line in item.get('sites', [])],
                 **({'justified': item['justified']} if item.get('justified') else {})},
                limitations=LIMITATIONS[:1])


def _evaluated_kinds(manifest, present):
    if not isinstance(manifest.get('coverage'), dict): return {}
    return {name: manifest['coverage'][name]['evaluated_kinds'] for name in present}


def _kind_counts(facts):
    kinds = sorted({f['value'].get('kind') for f in facts if f['value'].get('kind')})
    return {kind: len([f for f in facts if f['value'].get('kind') == kind]) for kind in kinds}


def _apart(facts):
    """(the facts, what the project justified on its line with its reason): the second reported apart, not hidden."""
    justified = [f for f in facts if f['kind'] == 'engine_finding_justified']
    return [f for f in facts if f['kind'] != 'engine_finding_justified'], [
        {'engine': f['value']['engine'], 'rule': f['value']['rule'], 'path': f['location']['path'],
         'line': f['location'].get('line'), 'why': f['value']['justified']} for f in justified][:100]


def _summary(manifest, facts, present, absent):
    from ..engines import not_applicable
    facts, justified = _apart(facts)
    counts = {name: len([f for f in facts if f['value'].get('engine') == name]) for name in present}
    return {'engines_observed': present, 'engines_unavailable': absent,
            'justified': justified,
            'engines_failed': _failed(manifest),
            'engines_not_applicable': not_applicable(manifest),
            # Candidate boundaries of today's components (GitNexus communities), for the map and the target.
            'communities': _communities(manifest),
            # GitNexus's area skills read: each area's key files, for the project's extension guide.
            'areas': _detail(manifest).get('areas') or [],
            # What each engine actually looked for, so silence can be told from absence.
            'evaluated_kinds': _evaluated_kinds(manifest, present),
            'findings': len(facts), 'target_unchanged': manifest['target_unchanged'],
            'by_engine': counts,
            'zero_findings': {name: 'engine completed but normalized zero facts'
                              for name, count in counts.items() if count == 0},
            'by_kind': _kind_counts(facts),
            'unmapped_rules': {name: manifest['engines'][name].get('unmapped_rules', {}) for name in present}}


def _failed(manifest):
    """{engine: why} of each engine that ran and broke: the check says so instead of reading its silence as clean."""
    return {name: detail.get('reason') or detail['status'] for name, detail in manifest['coverage'].items()
            if detail['status'] in (ERROR, SCHEMA_MISMATCH)}


def _communities(manifest):
    """GitNexus's communities: candidate boundaries of today's components."""
    return _detail(manifest).get('communities') or []


def _detail(manifest):
    return (manifest['coverage'].get('gitnexus') or {}).get('detail') or {}


def run(target, source, out=None, only=None, keep=False):
    from ..engines import analyze, missing, observed
    workdir = str(out) if out else None
    if workdir is None:
        return {'facts': [], 'input_sha': digest(b'external:no-workdir'), 'summary': {}, 'available': False,
                'reason': 'external engines need a report directory to write their raw artifacts into'}
    manifest = analyze(target, workdir + '/engines', exclude=source.exclude, only=only, formats=source_formats(), keep=keep)
    _copy_artifacts(manifest, out)
    versions = ''.join(f"{name}={detail.get('version')};" for name, detail in sorted(manifest['coverage'].items()))
    input_sha = digest((source.content_fingerprint + '|' + versions).encode('utf-8'))
    facts = []
    present, absent = observed(manifest), missing(manifest)
    facts += metric_facts(manifest, input_sha)
    facts += [_finding_fact(item, input_sha) for item in manifest['findings'] + manifest.get('justified', [])]
    summary = _summary(manifest, facts, present, absent)
    _drop_scratch(Path(workdir) / 'engines')
    return {'facts': facts, 'input_sha': input_sha, 'summary': summary, 'available': bool(present),
            'reason': None if present else 'no external engine is installed'}


# The engines' working folders: their indexes, caches, copies of the project and raw outputs. Once their findings are
# normalised above (engines.json keeps them, once, for an engine run again within the check) nothing reads them: the
# code index alone is 130 MB on a five-file project, and reforge's and semgrep's raw reports were 10 MB on EAOS.
SCRATCH = ('*/',)


def _drop_scratch(engines):
    import shutil
    for folder in Path(engines).glob('*/'):
        shutil.rmtree(folder, ignore_errors=True)


def engine_records(sets, record):
    """The engines' records of one kind (`record` in a symbol_metric_external fact: Presidio's personal values,
    ast-grep's tables and switches) among the read fact sets."""
    return [f for f in (sets.get('external') or {}).get('facts', [])
            if f['kind'] == 'symbol_metric_external' and f['value'].get('record') == record]
