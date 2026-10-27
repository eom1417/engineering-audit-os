"""The behaviour lock knows an intended change (M9.7): a card that changes screens on purpose declares them, and the
lock judges those screens against its declaration instead of refusing them.

A card's `changes_screens` is {screens: [a route, or 'all' for a part every page shows], adds: [the words it adds]}
(a link in the shared navigation shows on every page: flaskr's nav link was refused on every screen, M9.3). On a
declared screen only, a difference that is ONLY the declared addition passes (judged): every recorded word still there
and in its order, every new word one the card declared, the picture changed in at most PICTURE of its pixels and not
in its size. Anything else still fails: a word removed or changed, a layout broken, a screen nobody declared, a page's
errors. A card without the declaration is judged exactly as before.

The words a pass saw are written by the page specs (eaos/live/behavior/specs.py) to EAOS_LOCK_WORDS, the pass's
`words-<name>` folder, removed once judged. Once a batch with such a change is kept (eaos/journeys/fix/waves/batch.py),
its declared screens are recorded again on its code (record_intended) into behavior-lock/intended/<commit>/, and every
later run on code that holds that commit compares with them (restore_intended): the next card meets the new truth.
At most KEPT such recordings are kept, the oldest removed.
"""
import difflib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

PICTURE = 0.05           # the most of a declared screen's pixels its addition may change
KEPT = 20
RATIO = re.compile(r'ratio ([\d.]+) of all image pixels')
RESIZED = re.compile(r'Expected an image \d+px by \d+px, received')
FOLDER, INDEX = 'intended', 'intended/index.json'


class Intended(NamedTuple):
    """One pass's view of the declared changes: {screen's snapshot name, or '*': the words it may add}, where the
    recording's words of the pass's screens are, and where the words it saw were written."""
    screens: dict
    recorded: Path
    received: Path


def screen_name(route):
    """The snapshot name of a route's screen (as specs.py names it), '*' for 'all'."""
    from .specs import path_of, slug
    route = str(route).strip()
    return '*' if route in ('all', '*') else slug(path_of(route) or route)


def screens_of(cards):
    """{screen name or '*': frozenset of the words its cards add} of every card that declares `changes_screens`."""
    found = {}
    for card in cards:
        declared = card.get('changes_screens') or {}
        words = set(_words(' '.join(str(w) for w in declared.get('adds') or [])))
        for route in declared.get('screens') or []:
            found[screen_name(route)] = found.get(screen_name(route), frozenset()) | words
    return found


def for_pass(screens, lock, words, kind):
    """The Intended of one pass (as kind of user `kind`, or the run's one session), None without a declaration."""
    if not screens: return None
    mark = f'@{kind}' if kind else ''
    return Intended(dict(screens), Path(lock) / '__screenshots__' / mark, Path(words) / mark)


def judged(where, name, message, intended):
    """Whether a failed test of spec file `where` on screen `name` (its failure `message`) is only the declared addition."""
    allowed = _allowed(intended, name)
    if allowed is None or RESIZED.search(message): return False
    ratio = RATIO.search(message)
    if ratio and float(ratio.group(1)) > PICTURE: return False
    before, after = (folder / where / f'{name}.text.txt' for folder in (intended.recorded, intended.received))
    if not (before.is_file() and after.is_file()): return False     # the words not seen, or never recorded: not judged
    return only_added(before.read_text(encoding='utf-8'), after.read_text(encoding='utf-8'), allowed)


def _allowed(intended, name):
    if not intended or not ({name, '*'} & set(intended.screens)): return None
    return intended.screens.get(name, frozenset()) | intended.screens.get('*', frozenset())


def only_added(before, after, allowed):
    """Whether `after` is `before` with only words of `allowed` added: nothing removed, changed or moved."""
    old, new, allowed = _words(before), _words(after), {w.casefold() for w in allowed}
    for op, _, _, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if op == 'insert' and all(w.casefold() in allowed for w in new[j1:j2]): continue
        if op != 'equal': return False
    return True


def _words(text):
    return re.findall(r'\w+', str(text))


# ── the new truth, once a batch with an intended change is kept ──────────────────────────────────────────

def restore_intended(recorded, lock, target):
    """The screens recorded again after each kept intended change whose commit `target` holds, laid over the lock's
    recording in the order they were kept."""
    for row in _index(recorded):
        if _holds(target, row['commit']) and (Path(recorded) / FOLDER / row['commit']).is_dir():
            shutil.copytree(Path(recorded) / FOLDER / row['commit'], Path(lock) / '__screenshots__', dirs_exist_ok=True)


def record_intended(report, target, runtime, screens):
    """The declared `screens` recorded again on `target` (a kept batch's copy, at its commit), kept for every later run on
    code that holds the commit: behavior-lock/intended/<commit>/, and the screens recorded."""
    from ..app.run import LiveRun
    from .folder import _prepare, lend_kinds
    from .lock import LockPass, _run_specs, _start
    recorded = Path(runtime) / 'behavior-lock'
    commit = subprocess.run(['git', '-C', str(target), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    live = LiveRun(target, runtime, 'S09')
    lock = _prepare(live, report, recorded)
    restore_intended(recorded, lock, target)
    try:
        base = _start(live, lock)
        lend_kinds(report, lock, lock / '.auth/user.json')
        _run_specs(live, lock, base, recorded, LockPass('intended', update=True))
    finally:
        live.stop()
        live.record('behavior-lock/run-log-intended.json')
    kept = _keep_screens(lock / '__screenshots__', recorded / FOLDER / commit, screens)
    _remember(recorded, commit, kept)
    return kept


def _keep_screens(shots, into, screens):
    """The pictures and words of the declared screens (all when '*') copied from `shots` into `into`."""
    shutil.rmtree(into, ignore_errors=True)
    kept = []
    for path in sorted(shots.rglob('*')) if shots.is_dir() else []:
        name = path.name.removesuffix('.text.txt').removesuffix('.png')
        if path.name == name or not ('*' in screens or name in screens): continue
        (into / path.relative_to(shots)).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, into / path.relative_to(shots))
        kept.append(str(path.relative_to(shots)))
    return kept


def _remember(recorded, commit, kept):
    """The index of the new truths, the oldest past KEPT removed."""
    rows = [r for r in _index(recorded) if r['commit'] != commit] + [{'commit': commit, 'screens': kept}]
    for old in rows[:-KEPT]: shutil.rmtree(Path(recorded) / FOLDER / old['commit'], ignore_errors=True)
    (Path(recorded) / INDEX).write_text(json.dumps(rows[-KEPT:], indent=1) + '\n', encoding='utf-8')


def _index(recorded):
    try: return json.loads((Path(recorded) / INDEX).read_text(encoding='utf-8'))
    except (OSError, ValueError): return []


def _holds(target, commit):
    done = subprocess.run(['git', '-C', str(target), 'merge-base', '--is-ancestor', commit, 'HEAD'], capture_output=True)
    return done.returncode == 0
