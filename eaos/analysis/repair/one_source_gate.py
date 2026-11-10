"""The gate of one source per pattern: what a change adds against it, from the facts before and after it
(eaos/analysis/repair/gates.py `debt`), refused with the sentence the assistant reads: where, and the one home to use.

What refuses a change is code copied word for word (EAOS's own metrics, eaos/facts/code/metrics.py: six lines alike,
a copy kept on purpose inside jscpd's ignore markers, its reason beside it, aside). The detectors (near copies, the
ways of working) refuse only when named in REFUSES and shown (eaos/data/detector-verdicts.json):
one under its measured bar never refuses, and one over it refuses only once its refusals themselves are measured safe
on independent samples. REFUSES is empty, so a likeness alone never refuses a sound change.

Each row is keyed by what is written, not where: a copy by its code's digest, a way of working by its form and its
count over the changed files. Code moved between the changed files keeps its
rows; one more of the same is a new row, and so is a different one where another left. What the check before the change
did not measure (jscpd or ast-grep did not run, or near copies lack their digest) holds nothing against it.
"""
from ..assessments.one_source import findings
from ..assessments.weaknesses import observed

REFUSES = frozenset()       # the detectors whose refusals are measured safe; a detector's precision alone is not


def detector(finding):
    """The detector a finding is judged as (eaos/analysis/claims/ledger.py detector_of on its card)."""
    form = finding['evidence'].get('form')
    return f"one_source:{finding['kind']}" + (f':{form}' if finding['kind'] == 'idiom' else '')


def refusing():
    """The detectors that may refuse a change: named in REFUSES and not under their measured bar."""
    from ..claims.ledger import hidden_detectors
    hidden = hidden_detectors()
    return {name for name in REFUSES if name not in hidden}


def measured(record):
    """The kinds of row a check measured (`record(name)`: its fact set, None when it has none)."""
    external = record('external') or {}
    ran = observed({'external': external})
    near = [f for f in external.get('facts') or [] if f['value'].get('record') == 'near_copy']
    kinds = {'clone'} | ({'idiom'} if 'ast-grep' in ran else set())
    return kinds | ({'near_copy'} if 'jscpd' in ran and all(f['value'].get('digest') for f in near) else set())


def _counted(kind, key, places, paths, what):
    """{(kind, key, n): its row} for each place in the changed files, numbered over all of them: a move keeps the
    count."""
    mine = sorted((p for p in places if p['path'] in paths), key=lambda p: (p['path'], p.get('line') or 0))
    where = ', '.join(f"{p['path']}:{p.get('line') or 1}" for p in mine[:4])
    return {(kind, key, n): {'gate': 'copy', 'where': where, 'what': what.replace('{where}', where)} for n in range(1, len(mine) + 1)}


def _copy(finding, paths):
    """The rows of a cluster of near copies, one per copy in the changed files, keyed by the copied code."""
    evidence = finding['evidence']
    key = tuple(evidence.get('digests') or sorted({p['path'] for p in evidence['places']}))
    return _counted('near_copy', key, evidence['places'], paths, 'the same code is written again at {where}: give it one home and call it')


def _again(finding, paths):
    """The rows of an idiom written again in the changed files."""
    evidence = finding['evidence']
    key, what = evidence.get('form'), f"{evidence.get('form', '').replace('_', ' ')} is written by hand again at {{where}}"
    return _counted(finding['kind'], key, evidence['places'], paths, f"{what}: use the one in {evidence.get('home')}")


def _found(found, paths):
    rows = {}
    for finding in found:
        if finding['kind'] == 'near_copy': rows.update(_copy(finding, paths))
        else: rows.update(_again(finding, paths))
    return rows


def _clones(record, paths):
    """The lines copied word for word that EAOS's own metrics find without any tool, counted over the changed files: a
    row per window of copied lines there, numbered, so only more copied code is new. Never keyed by a copy's digest: a
    split moved a file's existing copies into new files, their six-line windows fell differently, every digest changed,
    and a sound split was refused."""
    covered, window, last = set(), 6, None
    for fact, mine in _copies_in(record, paths):
        window, last = fact['value'].get('window_lines') or window, fact['value']['occurrences']
        covered |= {(p['path'], line) for p in mine for line in _lines(p, window)}
    return {('clone', n): _copied(last) for n in range(1, -(-len(covered) // window) + 1)}


def _copies_in(record, paths):
    """(clone cluster, its copies in `paths`) of every cluster of two copies or more with one there."""
    for fact in (record('metrics') or {}).get('facts') or []:
        places = (fact['value'].get('occurrences') or []) if fact['kind'] == 'clone_cluster' else []
        mine = [p for p in places if p['path'] in paths]
        if len(places) >= 2 and mine: yield fact, mine


def _lines(place, window):
    """The lines a copy covers: from its start to its end, a window at least."""
    start = place.get('start_line') or 1
    return range(start, max(place.get('end_line') or 0, start + window - 1) + 1)


def _copied(places):
    return {'gate': 'copy', 'where': places[0]['path'], 'what': 'the same code is written in '
            + ', '.join(f"{p['path']}:{p.get('start_line') or 1}" for p in places[:4]) + ': give it one home and call it'}


def rows(record, paths, kinds=None):
    """The rows of the gate over one check (`record(name)`: its fact set, None when it has none) at the files `paths`;
    `kinds`: those the check before the change measured (None: every kind, nothing was there before)."""
    live, paths = refusing(), set(paths)
    found = [f for f in findings(None, {'external': record('external') or {}})[0] if detector(f) in live] if live else []
    out = {**_found(found, paths), **_clones(record, paths)}
    return {key: row for key, row in out.items() if kinds is None or key[0] in kinds}
