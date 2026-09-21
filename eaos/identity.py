"""Whether two findings from two runs are the same finding, and what evidence settles it.

Matching on a similar sentence is how two distinct problems become one and a renamed file becomes
a fresh problem. Identity here is derived from what a finding is about — its probe, its symbol,
its path — and a rename is only followed when something records the rename.
"""
import json
from difflib import SequenceMatcher

VERSION = 1
# How a match was established, strongest first. Anything weaker than these is not a match.
BY_UID, BY_ALIAS, BY_RENAME, BY_LOCATION = 'uid', 'alias', 'rename_evidence', 'symbol_and_path'
UNMATCHED = 'unmatched'
# Two different findings often read alike. A sentence alone never establishes identity.
SENTENCE_IS_NOT_EVIDENCE = 'statement_similarity'


def anchors(claim):
    """The things a claim is about, used to recognise it again."""
    factors = claim.get('priority_factors') or {}
    probe = (claim.get('probe_spec') or {}).get('specification') or {}
    symbols = sorted({value for key, value in probe.items() if key == 'symbol' and isinstance(value, str)})
    paths = sorted(set(factors.get('paths') or []) | {value for key, value in probe.items()
                                                      if key in ('path', 'left', 'right', 'place')
                                                      and isinstance(value, str)})
    return {'uid': claim.get('uid'), 'claim_type': claim.get('claim_type'), 'symbols': symbols, 'paths': paths}


def migrate(previous, current, renames=None):
    """Match claims across two runs. Returns matched pairs, and what stayed unmatched on each side.

    `renames` is a mapping of old path to new path that something else established — a git rename
    record, a declared move. It is never inferred from how alike two statements look.
    """
    renames = dict(renames or {})
    remaining = list(current)
    pairs, unmatched_before = [], []
    by_uid = {claim.get('uid'): claim for claim in remaining if claim.get('uid')}
    aliases = {alias: claim for claim in remaining for alias in (claim.get('aliases') or [])}
    for claim in previous:
        match, how = None, UNMATCHED
        if claim.get('uid') and claim['uid'] in by_uid:
            match, how = by_uid[claim['uid']], BY_UID
        elif claim.get('uid') and claim['uid'] in aliases:
            match, how = aliases[claim['uid']], BY_ALIAS
        else:
            before = anchors(claim)
            moved = {renames.get(path, path) for path in before['paths']}
            for candidate in remaining:
                after = anchors(candidate)
                if after['claim_type'] != before['claim_type']:
                    continue
                if before['symbols'] and after['symbols'] == before['symbols'] and moved & set(after['paths']):
                    match, how = candidate, BY_RENAME if moved != set(before['paths']) else BY_LOCATION
                    break
                if not before['symbols'] and moved and moved == set(after['paths']):
                    match, how = candidate, BY_RENAME if moved != set(before['paths']) else BY_LOCATION
                    break
        if match is None:
            unmatched_before.append(claim)
            continue
        remaining.remove(match)
        pairs.append({'before': claim['id'], 'after': match['id'], 'matched_by': how})
    return {'contract_version': VERSION, 'matched': pairs,
            'unmatched_before': [claim['id'] for claim in unmatched_before],
            'unmatched_after': [claim['id'] for claim in remaining],
            'limits': 'Identity follows evidence: a uid, a recorded alias, a recorded rename, or the same '
                      'symbol in the same place. Similar wording is not evidence and is never used.'}


def similarity(left, right):
    """How alike two statements read. Reported for a human to judge, never used to match."""
    return round(SequenceMatcher(None, ' '.join(left.split()).lower(),
                                 ' '.join(right.split()).lower()).ratio(), 3)


def look_alikes(claims, threshold=0.9):
    """Distinct findings that read almost the same, so a reader can tell them apart deliberately."""
    rows = []
    for index, left in enumerate(claims):
        for right in claims[index + 1:]:
            if left.get('uid') and left.get('uid') == right.get('uid'):
                continue
            score = similarity(left.get('statement', ''), right.get('statement', ''))
            if score >= threshold:
                rows.append({'left': left['id'], 'right': right['id'], 'similarity': score,
                             'kept_separate_because': SENTENCE_IS_NOT_EVIDENCE})
    return sorted(rows, key=lambda row: (-row['similarity'], row['left']))
