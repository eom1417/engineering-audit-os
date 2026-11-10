"""A batch handed over as branches a reviewer can merge one by one.

The batch's own branch stays whole: every check passed on all of it together. When its kept cards are of more than one
kind (KINDS), each kind also gets a branch of its own, `<batch branch>-<kind>`, made from the base with only that kind's
commits (rebuilt as leaving a card out rebuilds the copy, waves.rebuild), and kept only when those commits apply alone
and that kind's cards still pass their acceptance there. A kind that does not stand alone is named, not made. Accept and
undo of the batch delete these branches with its own (drop): what EAOS makes, EAOS removes.

Why: a branch mixing dependency upgrades, refactors and visual fixes in many files cannot be merged in pieces.
"""
from pathlib import Path

from .execute import git
from .waves import apply, plan, rebuild
from .waves.acceptance import batch_acceptance

# The kinds a batch is split by, each named by its cards' remediation patterns (eaos/analysis/repair/remediation.py
# PATTERNS, eaos/analysis/repair/review.py design cards); a card of none of them is of the kind `other`.
KINDS = {
    'deps': ('upgrade_dependency',),
    'refactor': ('split_module', 'hotspot', 'import_cycle', 'hidden_coupling', 'canonicalize', 'duplicated_rule',
                 'mutable_state', 'dead_code', 'remove_dead', 'one_source', 'old_engine', 'layer_boundary'),
    'look': ('design_review',),
}


def kind_of(card):
    return next((kind for kind, patterns in KINDS.items() if card.get('pattern') in patterns), 'other')


def split(where, wave, summary):
    """{'split': [{kind, cards, branch}], 'not_split': [{kind, cards, why}]} of the batch `wave` handed over as
    summary['branch'] in the project; `where`: (report, runtime, project). {} when it kept cards of one kind only,
    lands on its base directly, or continues an earlier batch's branch (its base is then that batch, not the
    person's code)."""
    report, runtime, project = where
    cards = {card['id']: card for card in plan(Path(report))['tasks'] if card['id'] in summary['kept']}
    kinds = {}
    for card_id in summary['kept']: kinds.setdefault(kind_of(cards[card_id]), []).append(card_id)
    if len(kinds) < 2 or wave.get('direct') or wave.get('continues'): return {}
    tip = git(wave['root'], 'rev-parse', 'HEAD').stdout.strip()
    made = {'split': [], 'not_split': []}
    try:
        for kind, ids in kinds.items():
            why = _alone((report, runtime), wave, [cards[c] for c in ids])
            if why: made['not_split'].append({'kind': kind, 'cards': ids, 'why': why})
            else: made['split'].append({'kind': kind, 'cards': ids, 'branch': apply(
                project, {'kept': ids, 'branch': f"{summary['branch']}-{kind}", 'root': wave['root']})})
    finally:
        git(wave['root'], 'reset', '--hard', '--quiet', tip)
    return made


def _alone(where, wave, cards):
    """'' once the copy is the base plus only `cards`' commits and their acceptances pass there, else why not."""
    report, runtime = where
    ids = {card['id'] for card in cards}
    if rebuild(wave['root'], wave['base'], [sha for card_id, sha in wave['kept'].items() if card_id in ids]):
        return 'its changes do not apply without the other kinds'
    try: exits = batch_acceptance(Path(report), cards, Path(wave['root']), runtime=Path(runtime))
    except Exception as problem:     # noqa: BLE001 - the whole branch is handed over still; this kind is only not split
        return f'its acceptance could not run alone: {problem}'[:300]
    failing = sorted(card_id for card_id, code in exits.items() if code not in (0, None))
    return f"{', '.join(failing)} still fail without the other kinds" if failing else ''


def drop(project, wave):
    """Delete the branches the batch `wave` was split into, with its own branch at accept or undo."""
    names = [each['branch'] for each in wave.get('split') or []]
    if names: git(project, 'branch', '-D', *names)


def said(record):
    """({answer keys}, the words for the assistant) of the branches of each kind the batch's `record` was split into."""
    if 'split' not in record: return {}, ''
    return {'split_branches': record['split'], 'not_split': record['not_split']}, (
        (" The fixes are also on one branch per kind (split_branches: each with its cards), so a reviewer can merge them "
         "one by one with git; only the whole branch went through every check, each kind's branch through its cards' "
         "acceptance. Accept or undo still takes the whole batch and removes these branches too." if record['split'] else '')
        + (" Name the kinds that could not stand alone (not_split) and why." if record['not_split'] else ''))
