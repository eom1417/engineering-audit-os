"""The gate of one source per pattern (M15.9): what a change adds against it, from the facts before and after it
(eaos/analysis/repair/gates.py `debt`), refused with the sentence the assistant reads: where, and the one home to use.

What refuses a change is code copied word for word (EAOS's own metrics, eaos/facts/code/metrics.py: six lines alike,
a copy kept on purpose inside jscpd's ignore markers, its reason beside it, aside). M15's detectors (near copies, the
look, screen patterns, ways of working) refuse only when named in REFUSES and shown (eaos/data/detector-verdicts.json):
one under its measured bar never refuses, and one over it refuses only once its refusals themselves are measured safe
on independent samples (M17). None is yet: a likeness alone never refuses a sound change.

Each row is keyed by what is written, not where: a copy by its code's digest, a way of working, a value of the look or
a screen pattern by its form and its count over the changed files. Code moved between the changed files keeps its
rows; one more of the same is a new row, and so is a different one where another left. What the check before the change
did not measure (jscpd or ast-grep did not run, the patterns were not read, near copies without their digest: a check
before M15's closure) holds nothing against it.
"""
from ..assessments.one_source import findings
from ..assessments.weaknesses import observed

REFUSES = frozenset()       # the detectors whose refusals are measured safe (M17); a detector's precision alone is not


def detector(finding):
    """The detector a finding is judged as (eaos/analysis/claims/ledger.py detector_of on its card)."""
    form = finding['evidence'].get('form')
    return f"one_source:{finding['kind']}" + (f':{form}' if finding['kind'] == 'idiom' else '')


def refusing():
    """The detectors of M15 that may refuse a change now: named in REFUSES and not under their measured bar."""
    from ..claims.ledger import hidden_detectors
    hidden = hidden_detectors()
    return {name for name in REFUSES if name not in hidden}


def measured(record):
    """The kinds of row a check measured (`record(name)`: its fact set, None when it has none)."""
    external = record('external') or {}
    ran = observed({'external': external})
    near = [f for f in external.get('facts') or [] if f['value'].get('record') == 'near_copy']
    kinds = {'clone'} | ({'idiom'} if 'ast-grep' in ran else set()) | ({'look', 'ui_pattern'} if record('patterns') is not None else set())
    return kinds | ({'near_copy'} if 'jscpd' in ran and all(f['value'].get('digest') for f in near) else set())


def _counted(kind, key, places, paths, what):
    """{(kind, key, n): its row} for each place in the changed files, numbered over all of them: a move keeps the count."""
    mine = sorted((p for p in places if p['path'] in paths), key=lambda p: (p['path'], p.get('line') or 0))
    where = ', '.join(f"{p['path']}:{p.get('line') or 1}" for p in mine[:4])
    return {(kind, key, n): {'gate': 'copy', 'where': where, 'what': what.replace('{where}', where)} for n in range(1, len(mine) + 1)}


def _look(record, paths):
    rows = {}
    for fact in (record('patterns') or {}).get('facts') or []:
        if fact['kind'] != 'look_value': continue
        value = fact['value']
        rows.update(_counted('look', f"{value['kind']}:{value['value']}", value['places'], paths,
                             f"{value['kind'].replace('_', ' ')} {value['value']} is written at {{where}}, outside the tokens file: name it there and use its name"))
    return rows


def _copy(finding, paths):
    """The rows of a cluster of near copies, one per copy in the changed files, keyed by the copied code."""
    evidence = finding['evidence']
    key = tuple(evidence.get('digests') or sorted({p['path'] for p in evidence['places']}))
    return _counted('near_copy', key, evidence['places'], paths, 'the same code is written again at {where}: give it one home and call it')


def _again(finding, paths):
    """The rows of an idiom or a screen pattern written again in the changed files."""
    evidence = finding['evidence']
    if finding['kind'] == 'idiom':
        key, what = evidence.get('form'), f"{evidence.get('form', '').replace('_', ' ')} is written by hand again at {{where}}"
    else:
        key, what = f"{evidence.get('tag')}:{evidence.get('elements')}", f"the <{evidence.get('tag')}> structure is written again at {{where}}"
    return _counted(finding['kind'], key, evidence['places'], paths, f"{what}: use the one in {evidence.get('home')}")


def _found(found, paths):
    rows = {}
    for finding in found:
        if finding['kind'] == 'near_copy': rows.update(_copy(finding, paths))
        elif finding['kind'] != 'look': rows.update(_again(finding, paths))
    return rows


def _clones(record, paths):
    """The lines copied word for word that EAOS's own metrics find without any tool: one row per copy in the changed
    files, keyed by their digest and numbered, so a third copy is new and a copy moved between them is not."""
    rows = {}
    for fact in (record('metrics') or {}).get('facts') or []:
        places = fact['value'].get('occurrences') or [] if fact['kind'] == 'clone_cluster' else []
        mine = sum(p['path'] in paths for p in places)
        if len(places) >= 2: rows.update({('clone', fact['input_sha'], n): _copied(places) for n in range(1, mine + 1)})
    return rows


def _copied(places):
    return {'gate': 'copy', 'where': places[0]['path'], 'what': 'the same code is written in '
            + ', '.join(f"{p['path']}:{p.get('start_line') or 1}" for p in places[:4]) + ': give it one home and call it'}


def rows(record, paths, kinds=None):
    """The rows of the gate over one check (`record(name)`: its fact set, None when it has none) at the files `paths`;
    `kinds`: those the check before the change measured (None: every kind, nothing was there before)."""
    live, paths = refusing(), set(paths)
    found = [f for f in findings(None, {name: record(name) or {} for name in ('external', 'patterns')})[0]
             if detector(f) in live] if live else []
    out = {**_found(found, paths), **(_look(record, paths) if 'one_source:look' in live else {}), **_clones(record, paths)}
    return {key: row for key, row in out.items() if kinds is None or key[0] in kinds}
