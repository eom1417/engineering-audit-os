"""Findings from pinned external engines, normalised into facts.

This set is the one place where evidence we did not compute ourselves enters the system. It is
opt-in, it records which engines were absent as plainly as what the present ones found, and it
carries no timing or path from the run, so two runs of the same engine versions over the same
tree produce the same bytes.
"""
from . import digest, make
from .source import LANGUAGE_BY_SUFFIX

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


def run(target, source, out=None, only=None):
    from ..engines import analyze, missing, observed
    workdir = str(out) if out else None
    if workdir is None:
        return {'facts': [], 'input_sha': digest(b'external:no-workdir'), 'summary': {}, 'available': False,
                'reason': 'external engines need a report directory to write their raw artifacts into'}
    manifest = analyze(target, workdir + '/engines', exclude=source.exclude, only=only, formats=source_formats())
    versions = ''.join(f"{name}={detail.get('version')};" for name, detail in sorted(manifest['coverage'].items()))
    input_sha = digest((source.fingerprint + '|' + versions).encode('utf-8'))
    facts = []
    for item in manifest['findings']:
        subject = item['subject']
        facts.append(make('engine_finding', NAME, VERSION, input_sha,
                          {'path': subject.get('path'), 'line': subject.get('line'), 'symbol': subject.get('key')},
                          {'engine': item['engine'], 'engine_version': item['engine_version'], 'rule': item['rule'],
                           'kind': item['kind'], 'method': item['method'], 'message': item['message'],
                           'measurements': item['measurements'], 'engine_confidence': item['engine_confidence'],
                           'subject_kind': subject.get('kind'),
                           'sites': [{'path': path, 'line': line} for path, line in item.get('sites', [])]},
                          limitations=LIMITATIONS[:1]))
    present, absent = observed(manifest), missing(manifest)
    summary = {'engines_observed': present, 'engines_unavailable': absent,
               # What each engine actually looked for, so silence can be told from absence.
               'evaluated_kinds': {name: manifest['coverage'][name]['evaluated_kinds'] for name in present},
               'findings': len(facts), 'target_unchanged': manifest['target_unchanged'],
               'by_engine': {name: len([f for f in facts if f['value']['engine'] == name]) for name in present},
               'by_kind': {kind: len([f for f in facts if f['value']['kind'] == kind])
                           for kind in sorted({f['value']['kind'] for f in facts})},
               'unmapped_rules': {name: manifest['engines'][name].get('unmapped_rules', {}) for name in present}}
    return {'facts': facts, 'input_sha': input_sha, 'summary': summary, 'available': bool(present),
            'reason': None if present else 'no external engine is installed'}
