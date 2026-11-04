"""The cards of a batch that have a codemod, fixed by it in the batch's copy as the batch opens (fix_start): each kept, or
taken back when it fails or breaks something; a lock file card that fails whole, kept for the packages that pass one at
a time."""
import subprocess

from ...analysis.assessments.dependencies import check_of
from .execute import codemod_by_member, git, new_breakage
from .waves import change, commit, drop_last


def automatic_fixes(wave, cards, root, report, progress):
    """The cards with a codemod, fixed by it in the copy: each kept, or taken back when it fails or breaks something; a
    lock file card that fails whole is kept for the packages that pass one at a time (_in_part)."""
    automatic = [c for c in cards if _dry(c).get('files_changed', 0) > 0]
    for index, card in enumerate(automatic, 1):
        progress(index, len(automatic) + 1, f"automatic fix of {card['id']}")
        why = _automatic_fix(wave, card, root, report)
        if why and not _in_part(wave, card, root, report): wave['failed'][card['id']] = why
    # A lock card whose dry run failed whole is tried one package at a time too; when none passes it stays the
    # assistant's (a uv.lock card of ten packages: one needed a newer Python than the project's, 2026-11-04).
    for card in [c for c in cards if c not in automatic and _dry(c).get('exit') not in (0, None)]:
        _in_part(wave, card, root, report)


def _dry(card):
    return (card.get('codemod') or {}).get('dry_run') or {}


def _automatic_fix(wave, card, root, report):
    """'' when the card's codemod is kept in the copy, else why not, the copy as before."""
    try:
        tool, _ = change(card, root, report)
        sha = commit(root, card)
        broke = new_breakage(report, root)
        if broke:
            drop_last(root)
            return f'its automatic fix broke something: {broke[0]}'
        wave['kept'][card['id']], wave['tools'][card['id']] = sha, tool
        return ''
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as problem:
        git(root, 'reset', '--hard', '--quiet', 'HEAD')
        git(root, 'clean', '-fdq')
        return f'{type(problem).__name__}: {problem}'[:300]


def _in_part(wave, card, root, report):
    """Whether a lock file card that failed whole is kept for the packages that pass one at a time (codemod_by_member).
    Its acceptance becomes theirs alone, so it claims no package it did not move: wave['partial'] holds that check and
    each package left with why; those stay vulnerable, and the next check finds them again."""
    facts, left = codemod_by_member(card, root, report)
    if not facts: return False
    said = '; '.join(f'{name} ({why})' for name, why in left.items())
    sha = commit(root, card, f"Upgrade {len(facts)} of the {len(facts) + len(left)} packages of the lock file\n"
                             + (f'Left as they were: {said}' if left else ''))
    if new_breakage(report, root):
        drop_last(root)
        return False
    wave['kept'][card['id']], wave['tools'][card['id']] = sha, 'codemod'
    if left: wave.setdefault('partial', {})[card['id']] = {'verify_command': check_of(facts), 'left': left}
    return True

