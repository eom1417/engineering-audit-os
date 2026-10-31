"""The coverage ledger (M4.3): for each loop of the check (eaos/pipeline/loops.py), what it covered, what it could not,
and why. The checkpoint and the manifest keep it (`coverage`); START-HERE.md and RUN.md show its big gaps in red at the
top (eaos/report/documents/start_here.py, eaos/report/documents/run.py).

A gap is big when the loop's goal is not reached for a reason the person did not choose: a stage of it broke, or a
stage its goal stands on is absent (the app did not start, a tool not installed). A stage left out because the
check followed other paths, did not switch its optional loop on, or the person did not allow (running the app, signing
in), is said but is not a big gap.
"""
from ..core.language.words import catalog
from .loops import LOOPS, NOT_MET, outcome

# what the person chose, or what does not apply to the project: said, never a big gap
CHOSEN = ('outside_paths', 'loop_off', 'not_requested', 'no_run_consent', 'engines_not_requested', 'sign_in_declined',
          'not_applicable')


def ledger(rows, settled=None):
    """[{loop, name: {ar, en}, state, rounds, covered, missed: [{stage, status, reason_code, reason}], behind, big}] for
    every loop with a stage in `rows`; a loop whose stages have not all ended is 'running' (the checkpoint's view)."""
    return [_entry(loop, rows, (settled or {}).get(loop.name) or {}) for loop in LOOPS if any(name in rows for name in loop.stages)]


def _entry(loop, rows, settled):
    state, behind = _state(loop, rows)
    codes = [rows[name].get('reason_code') for name in behind]
    return {'loop': loop.name, 'name': _name(loop.name), 'state': state, 'rounds': settled.get('rounds', 1),
            'covered': [name for name in loop.stages if (rows.get(name) or {}).get('status') == 'ok'],
            'missed': _missed(loop, rows), 'behind': behind,
            'big': state == NOT_MET or any(code not in CHOSEN for code in codes)}


def _state(loop, rows):
    """(the loop's state, the stages behind it: those its outcome names, then those that could not measure their ground)."""
    state, behind = outcome(loop, rows) if all(name in rows for name in loop.stages) else ('running', [])
    return state, behind + [name for name in _unmeasured(loop, rows) if name not in behind]


def _unmeasured(loop, rows):
    """The stages of `loop` that ran and said what they could not read (M15.0): a gap, never taken for clean."""
    return [name for name in loop.stages if (rows.get(name) or {}).get('reason_code') in ('unmeasured', 'unread_names')]


def _missed(loop, rows):
    """The stages of `loop` that ended but not ok, or ok with ground they could not measure, with why."""
    return [{'stage': name, **{key: rows[name].get(key) for key in ('status', 'reason_code', 'reason')}}
            for name in loop.stages if name in rows and (rows[name].get('status') != 'ok' or name in _unmeasured(loop, rows))]


def _name(loop):
    """{ar, en} of a loop's name (eaos/data/words.json `loops`), else its id."""
    name = (catalog().get('loops') or {}).get(loop, {}).get('name') or [loop, loop]
    return {'ar': name[0], 'en': name[1]}
