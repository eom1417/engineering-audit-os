"""The gate of one source per pattern (M15.9): what a change adds against it, from the facts before and after it
(eaos/analysis/repair/gates.py `debt`). A near copy, a value of the look written outside the tokens file, a screen
pattern or a way of working written by hand once more, at a file the change touched, is refused with the sentence the
assistant reads: where, and the one home to use instead.

Each row is keyed by its place and its count in that file, so one more of the same in a file is a new row: a change
that adds a fifth copy is refused while the four it found are not held against it.
"""
from collections import Counter

from ..assessments.one_source import findings


def _sets(facts):
    return {'external': {'facts': facts('external')}, 'patterns': {'facts': facts('patterns')}}


def _counted(kind, key, places, paths):
    """{(kind, key, path, n): place} for each place of a changed file, numbered within its file."""
    seen, rows = Counter(), {}
    for place in places:
        if place['path'] not in paths: continue
        seen[place['path']] += 1
        rows[(kind, key, place['path'], seen[place['path']])] = place
    return rows


def _look(facts, paths):
    rows = {}
    for fact in facts('patterns'):
        if fact['kind'] != 'look_value': continue
        value = fact['value']
        for key, place in _counted('look', f"{value['kind']}:{value['value']}", value['places'], paths).items():
            rows[key] = {'gate': 'copy', 'where': f"{place['path']}:{place['line']}",
                         'what': f"{value['kind'].replace('_', ' ')} {value['value']} is written at {place['path']}:{place['line']}, "
                                 'outside the tokens file: name it in the tokens file and use its name'}
    return rows


def _found(found, paths):
    rows = {}
    for finding in found:
        evidence, kind = finding['evidence'], finding['kind']
        if kind == 'look': continue
        if kind == 'near_copy':
            files = tuple(sorted({p['path'] for p in evidence['places']}))
            if set(files) & paths:
                rows[('near_copy', files)] = {'gate': 'copy', 'where': finding['place'], 'what': 'the same code is written in '
                                              + ', '.join(f"{p['path']}:{p['line']}" for p in evidence['places'][:4]) + ': give it one home and call it'}
            continue
        what = (f"{evidence.get('form', '').replace('_', ' ')} is written by hand again" if kind == 'idiom' else
                f"the <{evidence.get('tag')}> structure is written again")
        for key, place in _counted(kind, evidence.get('form') or evidence.get('tag'), evidence['places'], paths).items():
            rows[key] = {'gate': 'copy', 'where': f"{place['path']}:{place.get('line') or 1}",
                         'what': f"{what} at {place['path']}:{place.get('line') or 1}: use the one in {evidence.get('home')}"}
    return rows


def rows(facts, paths):
    """The rows of the gate over one collection of facts (`facts(name)`: a fact set's facts) at the files `paths`."""
    found, _ = findings(None, _sets(facts))
    return {**_found(found, set(paths)), **_look(facts, set(paths))}
