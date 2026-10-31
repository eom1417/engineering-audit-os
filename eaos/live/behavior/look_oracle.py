"""The style oracle (M18.7): whether a batch changed how the app looks, read element by element and state by state from what the
lock's specs saved (eaos/templates/screens/look.cjs): pixels cannot see #333 become #343434, and these values can.

    compare(before, after, allowed)   every difference between two saved pages, what `allowed` declares aside
    judged(original, now, allowed)    the sentence of what a batch changed that it did not declare, '' when nothing
    declared(cards)                   what a batch's cards say of the look: None the pictures judge, [] a zero change
    look_changed(runtime, name, look) a lock pass's readings judged, then removed: only the recording stays

`allowed` empty is a zero change: nothing may differ. A consolidation the person agreed lists its changes,
[{'property': name or None, 'from': value, 'to': value}]: those alone may differ. An element gone or new is always a difference."""
import json
import shutil
from pathlib import Path

SHOWN = 12


def _looks(page, row):
    return {state: page['sigs'][index] for state, index in row.items()}


def _permitted(allowed, prop, old, new):
    return any(rule.get('from') == old and rule.get('to') == new and rule.get('property') in (None, prop) for rule in allowed or ())


def _differences(key, before, after, allowed):
    found = []
    for state in sorted(set(before) | set(after)):
        old, new = before.get(state), after.get(state)
        if old is None or new is None: found.append({'key': key, 'state': state, 'property': None, 'from': bool(old), 'to': bool(new)})
        else: found += [{'key': key, 'state': state, 'property': prop, 'from': old.get(prop), 'to': new.get(prop)} for prop in sorted(set(old) | set(new))
                        if old.get(prop) != new.get(prop) and not _permitted(allowed, prop, old.get(prop), new.get(prop))]
    return found


def compare(before, after, allowed=None):
    """The differences of one page: an element's property in a state, or `property` None for a state or element gone or new."""
    found = []
    for key in sorted(set(before['els']) | set(after['els'])):
        old, new = before['els'].get(key), after['els'].get(key)
        if old is None or new is None: found.append({'key': key, 'state': None, 'property': None, 'from': old is not None, 'to': new is not None})
        else: found += _differences(key, _looks(before, old), _looks(after, new), allowed)
    return found


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _said(name, row):
    if row['property'] is None: return f"{name}: {row['key']} {'is gone' if row['from'] else 'is new'}"
    return f"{name}: {row['key']} ({row['state']}) {row['property']} {row['from']} -> {row['to']}"


def _noisy(original, control):
    """{(page, element)} that differ with no change at all, read on the code as it was: what moves by itself on those pages (a live value, a late part)."""
    names = {path.name for path in Path(control).glob('*.json')}
    return {(name[:-5], row['key']) for name in names if (Path(original) / name).is_file()
            for row in compare(_read(Path(original) / name), _read(Path(control) / name))}


def _beyond(original, now, name, allowed, noisy):
    return [_said(name[:-5], row) for row in compare(_read(original / name), _read(now / name), allowed) if (name[:-5], row['key']) not in noisy]


def judged(original, now, allowed=None, control=None):
    """What the pages saved in `now` changed against `original` beyond `allowed`, in words; '' when nothing did. A page with no
    recording or no second reading proves nothing and is said. `control`: a reading of the unchanged code, whose differences are the pages' own."""
    noisy = _noisy(original, control) if control else set()
    original, now = Path(original), Path(now)
    names, read = {path.name for path in original.glob('*.json')}, {path.name for path in now.glob('*.json')}
    if not names: return 'nothing recorded to compare with: check the project again'
    readable = {path.name for path in Path(control).glob('*.json')} if control else names      # a page that fails on the unchanged code too proves nothing either way
    said = [f'{name}: not read again' for name in sorted((names & readable) - read)]
    for name in sorted(names & read): said += _beyond(original, now, name, allowed, noisy)
    return '' if not said else f"{len(said)} undeclared change(s) of the look: " + '; '.join(said[:SHOWN])


def declared(cards):
    """What the cards of a batch say of the look: None when none speaks of it, [] a zero change, else what the person agreed to,
    each card's `look` a list of {property, from, to}."""
    told = [card['look'] for card in cards if card.get('look') is not None]
    return None if not told else [rule for rules in told for rule in rules]


def look_changed(runtime, name, look, control=None):
    """What a pass `name` changed beyond `look`, in words, '' when it did not, or when the batch says nothing of the look. The
    reading is kept when it fails with no control read yet: a control pass may clear it; `control`: that pass, then removed too."""
    saved = Path(runtime) / 'behavior-lock' / 'look'
    said = judged(saved / 'original', saved / name, look, saved / control if control else None) if look is not None else ''
    if not said or control:
        shutil.rmtree(saved / name, ignore_errors=True)
        if control: shutil.rmtree(saved / control, ignore_errors=True)
    return said
