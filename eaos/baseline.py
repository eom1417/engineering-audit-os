"""The debt a project already had, frozen, so a gate can fail only on what a change added.

A tool that reports several hundred pre-existing findings and fails the first pull request gets
switched off, and then it reports nothing at all. A pinned baseline separates the debt that was
already there from the debt this change created; only the second can fail a build.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from .delta import compare, key_of
from .workspace import read, write

DIRECTORY = 'baseline'
RECORD = 'baseline.json'
DOCUMENT = 'BASELINE.md'
LIMITATIONS = [
    'A baseline freezes claims, not code: a finding that reappears under a different statement '
    'reads as new, and one that disappears because a file was deleted reads as closed.',
    'Growth is measured by the sites a claim names and the facts behind it. A claim that gets '
    'worse without touching either reads as unchanged.',
    'Pinning records what was accepted, never that it was safe. Nothing here is a waiver.',
    'A gate over a baseline can only judge what the run examined; read RUN.md beside it.',
]


def _home(out):
    return Path(out) / DIRECTORY


def magnitude(claim):
    """How big a finding is, so growth in place is not mistaken for no change.

    Adding a third copy of a duplicated rule keeps the cluster's identity and changes only its
    size. Comparing identities alone let exactly that regression through the gate.
    """
    params = (claim.get('render') or {}).get('params') or {}
    counted = params.get('count')
    sites = params.get('where')
    return {'facts': len(claim.get('fact_ids', [])),
            'count': counted if isinstance(counted, int) else None,
            'sites': len([part for part in str(sites).split(',') if part.strip()]) if sites else None}


def _worse(before, after):
    """True when any measured dimension of the same finding grew."""
    for key in ('facts', 'count', 'sites'):
        old, new = before.get(key), after.get(key)
        if isinstance(old, int) and isinstance(new, int) and new > old:
            return True
    return False


def pin(out, note=''):
    """Freeze the current dossier as the accepted debt. Refuses to overwrite silently."""
    out = Path(out)
    dossier_path = out / 'dossier.json'
    if not dossier_path.is_file():
        raise ValueError('Run an audit before pinning a baseline: there is no dossier to freeze')
    home = _home(out)
    if (home / RECORD).is_file():
        raise ValueError(f'A baseline is already pinned at {home / RECORD}; clear it before pinning another')
    home.mkdir(parents=True, exist_ok=True)
    dossier = read(dossier_path)
    manifest = read(out / 'run-manifest.json') if (out / 'run-manifest.json').is_file() else {}
    record = {
        'schema_version': 1,
        'pinned_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'note': note,
        'target': (dossier.get('provenance') or {}).get('target') or manifest.get('target'),
        'commit': (dossier.get('provenance') or {}).get('commit'),
        'source_fingerprint': manifest.get('source_fingerprint'),
        'stages': {name: row['status'] for name, row in (manifest.get('stages') or {}).items()},
        'claims': len(dossier.get('claims', [])),
        # Two claims can share an identity; the count of claims and the count of accepted
        # identities are different numbers and reporting one as the other misleads.
        'accepted': sorted({'|'.join(key_of(claim)) for claim in dossier.get('claims', [])}),
        'magnitudes': {'|'.join(key_of(claim)): magnitude(claim) for claim in dossier.get('claims', [])},
        'limitations': LIMITATIONS,
    }
    write(home / RECORD, record)
    write(home / 'dossier.json', dossier)
    return {'baseline': str(home / RECORD), 'claims': record['claims'], 'pinned_at': record['pinned_at'],
            'limits': ' '.join(LIMITATIONS)}


def show(out, language='ar'):
    """What the pinned baseline describes, and how much of it is still open."""
    out = Path(out)
    home = _home(out)
    if not (home / RECORD).is_file():
        return {'pinned': False, 'reason': 'no baseline is pinned in this report directory',
                'limits': ' '.join(LIMITATIONS)}
    record = read(home / RECORD)
    current = read(out / 'dossier.json') if (out / 'dossier.json').is_file() else {'claims': []}
    still_open = {'|'.join(key_of(claim)) for claim in current.get('claims', [])} & set(record['accepted'])
    closed = sorted(set(record['accepted']) - still_open)
    result = {'pinned': True, 'pinned_at': record['pinned_at'], 'note': record.get('note', ''),
              'commit': record.get('commit'), 'claims': record['claims'],
              'accepted_identities': len(record['accepted']),
              'still_open': len(still_open), 'closed_since': len(closed),
              'artifact': str(out / DOCUMENT), 'limits': ' '.join(LIMITATIONS)}
    (out / DOCUMENT).write_text(document(record, result, closed, language), encoding='utf-8')
    return result


def clear(out):
    home = _home(out)
    if not (home / RECORD).is_file():
        return {'cleared': False, 'reason': 'no baseline is pinned'}
    for path in sorted(home.iterdir()):
        path.unlink()
    home.rmdir()
    return {'cleared': True, 'limits': ' '.join(LIMITATIONS)}


def gate(out, mode='new'):
    """Compare the current dossier against the baseline and say what a build should do.

    mode 'new'  — only claims absent from the baseline can fail.
    mode 'all'  — every live severe claim fails, baseline or not.
    """
    out = Path(out)
    if mode not in ('new', 'all'):
        raise ValueError("Gate mode must be 'new' or 'all'")
    current = read(out / 'dossier.json')
    home = _home(out)
    if mode == 'all':
        failing = [claim for claim in current.get('claims', [])
                   if claim.get('confidence') in {'CONFIRMED', 'LIKELY'}
                   and claim.get('claim_type') in {'risk', 'cause', 'business_rule', 'structure'}]
        return _verdict(out, mode, failing, baseline=None, comparison='every live finding')
    if not (home / RECORD).is_file():
        return {'status': 'NO_BASELINE', 'mode': mode, 'failing': [],
                'reason': 'nothing is pinned, so nothing can be called new',
                'limits': ' '.join(LIMITATIONS)}
    record = read(home / RECORD)
    # Reuse the one comparison the product already has rather than writing a second one.
    result = compare(read(home / 'dossier.json'), current)
    failing = list(result['new_severe_claims'])
    grew = []
    accepted = record.get('magnitudes') or {}
    for claim in current.get('claims', []):
        key = '|'.join(key_of(claim))
        if key in accepted and _worse(accepted[key], magnitude(claim)):
            grew.append(claim)
    failing += [claim for claim in grew if claim not in failing]
    return _verdict(out, mode, failing, baseline=record, comparison=result['comparison_status'],
                    grew=[claim['id'] for claim in grew])


def _verdict(out, mode, failing, baseline, comparison, grew=()):
    return {'status': 'FAIL' if failing else 'PASS', 'mode': mode,
            'failing': [{'id': claim['id'], 'confidence': claim['confidence'],
                         'statement': claim['statement'][:200],
                         'reason': 'grew beyond the baseline' if claim['id'] in set(grew) else 'not in the baseline'}
                        for claim in failing],
            'accepted_debt': baseline['claims'] if baseline else 0,
            'grew_in_place': sorted(grew),
            'comparison': comparison,
            'limits': ' '.join(LIMITATIONS)}


def document(record, summary, closed, language):
    ar = language == 'ar'
    lines = ['# ' + ('خط الأساس المقبول' if ar else 'Accepted baseline'), '',
             '> ' + ('الدين المثبَّت وقت التثبيت. البوابة تفشل على الجديد فقط، والقديم يُتابَع ولا يُخفى.'
                     if ar else
                     'The debt as it stood when it was pinned. The gate fails on new findings only; the '
                     'old ones are tracked, not hidden.'), '',
             f"- {'ثُبّت في' if ar else 'pinned at'}: {record['pinned_at']}",
             f"- {'الالتزام' if ar else 'commit'}: {record.get('commit') or '—'}",
             f"- {'ادعاءات مقبولة' if ar else 'accepted claims'}: {record['claims']} "
             f"({len(record['accepted'])} {'هوية مميزة' if ar else 'distinct identities'})",
             f"- {'ما زال مفتوحًا' if ar else 'still open'}: {summary['still_open']}",
             f"- {'أُغلق منذ التثبيت' if ar else 'closed since pinning'}: {summary['closed_since']}", '']
    if record.get('note'):
        lines += [f"> {record['note']}", '']
    lines += ['## ' + ('الحدود' if ar else 'Limits'), '']
    lines += [f'- {line}' for line in LIMITATIONS]
    return '\n'.join(lines) + '\n'
