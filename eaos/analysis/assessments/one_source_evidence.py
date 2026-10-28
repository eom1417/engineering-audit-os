"""Whether a cluster of near copies or a screen pattern earns a card (the owner, 2026-10-28: likeness alone is never a
card). All three or it is a note, said in the report, never a card nor a breach of the law:

1. the copies carry one responsibility: the rules propose it (they sit in one part of the system, M6's layer and side
   when the check read them, else their folder; or they changed together in the history, mass commits left out by the
   history extractor; or one of them was fixed and its twin was not), and the judge (the card triage) rules on it;
2. the repetition costs upkeep or risks drift: the copies already differ, or their files keep changing;
3. one source is simpler and safer: its home sits in the part the copies share, so no new coupling is made.

These are signs to sort by, not proof of one contract: a card is a proposal, kept aside while its detector is under its
measured bar, never a gate's refusal (eaos/analysis/repair/one_source_gate.py), and its repair proves itself by the
behaviour lock and the project's tests. Known limit (M17): the third condition asks for one shared part, which the
first already gives, so the history and a fix made apart decide no card today; they are said as reasons only.
"""
from pathlib import Path, PurePosixPath

from ...core.system.files import read_json

CHANGING = 2          # commits of a file past which a copy in it is upkeep, not a file left alone


def layers_of(out):
    """{path: its layer and side} from the layers the check read (M6), {} when it read none."""
    record = read_json(Path(out) / 'layers.json', {}) if out else {}
    return {row['path']: f"{row.get('layer')}/{row.get('side')}" for row in record.get('map') or [] if row.get('layer')}


def history_of(sets):
    """({path: (commits, fix commits)}, {frozenset of two paths changed together})."""
    facts = (sets.get('history') or {}).get('facts') or []
    churn = {f['location']['path']: (f['value'].get('commits') or 0, f['value'].get('fix_commits') or 0)
             for f in facts if f['kind'] == 'history_churn'}
    together = {frozenset((f['location']['path'], f['location'].get('paired_path'))) for f in facts if f['kind'] == 'history_cochange'}
    return churn, together


def _part(path, layers):
    """A file's part of the system: its layer and side, else its folder two levels deep ('' at the root)."""
    return layers.get(path) or '/'.join(PurePosixPath(path).parent.parts[:2])


def _belongs(files, parts, history):
    """Why the rules propose the copies carry one responsibility, or None."""
    churn, together = history
    if len(parts) == 1: return f'they sit in one part of the system ({next(iter(parts))})'
    if any(frozenset((a, b)) in together for a in files for b in files if a < b): return 'they changed together in the history'
    fixes = [churn.get(path, (0, 0))[1] for path in files]
    if any(fixes) and not all(fixes): return 'one was fixed and its twin was not'
    return None


def _upkeep(finding, files, history):
    """Why keeping the copies costs upkeep or risks drift, or None."""
    evidence = finding['evidence']
    if set(evidence.get('kinds') or ()) & {'similar', 'gap'} or (evidence.get('similarity') or 1.0) < 1.0:
        return 'the copies already differ'
    changing = [path for path in files if history[0].get(path, (0, 0))[0] >= CHANGING]
    return f"{', '.join(changing[:3])} keep changing" if changing else None


def gate(finding, layers, history):
    """(a card or not, the evidence of each condition, or what is missing)."""
    files = sorted({place['path'] for place in finding['evidence'].get('places') or []})
    parts = {_part(path, layers) for path in files}
    reasons = {'belongs': _belongs(files, parts, history), 'upkeep': _upkeep(finding, files, history),
               'simpler': 'its home is in the part the copies share' if len(parts) == 1 else None}
    return all(reasons.values()), reasons
