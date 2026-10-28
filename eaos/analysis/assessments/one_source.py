"""One source per pattern (M15), sorted into findings: near copies of code (jscpd's pairs joined into clusters), the
ways of working written by hand (ast-grep's idiom records, eaos/rules/ast-grep/rules/idioms.yml), the element trees
repeated across the screens and the look written outside its tokens file (the patterns fact set,
eaos/facts/duplication/patterns.py; the style census of the pictured pages, one_source_look.py).

Each finding: {kind, place, line, severity, evidence: {...}} as in data_keeping.py, its evidence naming every place,
the source (the most complete copy, or the home the project's own layout gives: an existing components/ui, lib, hooks,
utils or middleware folder, else the layer's own) and what differs. `numbers(sets)` are the four numbers of the law
(eaos/core/contracts/code_laws.py), the same tools/quality.py records for EAOS.
"""
import re
from collections import Counter
from pathlib import PurePosixPath

from ...core.contracts.code_laws import PATTERN_REPEATS
from ...facts.engine_findings import engine_records
from . import one_source_look

TEST = re.compile(r'(^|/)(tests?|__tests__|spec|e2e)(/|$)|[._-](test|spec)\.[a-z]+$')
NEARBY = 10           # two records of one idiom this close in one file are one place
# The kind of home each idiom calls for, by the folders a project already names it with.
HOMES = {'hook': ('hooks', 'composables', 'lib', 'utils'), 'helper': ('lib', 'utils', 'helpers', 'shared', 'common', 'core'),
         'middleware': ('middleware', 'middlewares', 'lib', 'utils'), 'component': ('components/ui', 'components', 'ui')}
IDIOM_HOME = {'request_state': 'hook', 'popup_close': 'component', 'drag_drop': 'hook', 'route_guard': 'middleware'}


def _span(place):
    return place['path'], place['line'] or 0, place.get('end_line') or place['line'] or 0


def _clusters(pairs):
    """The pairs joined into clusters: two places of one file whose lines overlap are one member."""
    members, parent = [], []
    def member(place):
        path, start, end = _span(place)
        for i, (p, s, e) in enumerate(members):
            if p == path and s <= end and start <= e:
                members[i] = (p, min(s, start), max(e, end))
                return i
        members.append((path, start, end)); parent.append(len(parent))
        return len(members) - 1
    def root(i):
        while parent[i] != i: i = parent[i]
        return i
    links = []
    for pair in pairs:
        one, other = member(pair['first']), member(pair['second'])
        parent[root(one)] = root(other)
        links.append((one, pair))
    grouped = {}
    for i, pair in links: grouped.setdefault(root(i), []).append(pair)
    return [([members[i] for i in range(len(members)) if root(i) == top], rows) for top, rows in grouped.items()]


def _pairs(sets):
    for fact in engine_records(sets, 'near_copy'):
        value = fact['value']
        yield {'first': {'path': fact['location']['path'], 'line': fact['location'].get('line'), 'end_line': value.get('end_line')},
               'second': value.get('other') or {}, 'kind': value.get('kind'), 'similarity': value.get('similarity'),
               'lines': value.get('lines') or 0, 'fact_id': fact['id']}


def _cluster(members, pairs):
    """The finding of one cluster: its source the largest copy, the kinds of copy and the lowest likeness."""
    members.sort(key=lambda m: (-(m[2] - m[1]), m[0], m[1]))
    path, start, end = members[0]
    similar = [p['similarity'] for p in pairs if p['similarity']]
    return _finding('near_copy', path, start, 'medium' if len(members) >= 3 or end - start >= 15 else 'low',
                    copies=len(members), lines=end - start + 1, kinds=sorted({p['kind'] for p in pairs}),
                    similarity=min(similar, default=1.0), places=[{'path': p, 'line': s, 'end_line': e} for p, s, e in members],
                    home=f'{path}:{start}', fact_ids=[p['fact_id'] for p in pairs][:20])


def near_copies(sets):
    """One finding per cluster of near copies, not all in tests."""
    return [_cluster(members, pairs) for members, pairs in _clusters(list(_pairs(sets)))
            if not all(TEST.search(path) for path, _, _ in members)]


def _places(records):
    """The records of one idiom as places: two in one file NEARBY lines apart are one."""
    places = []
    for fact in sorted(records, key=lambda f: (f['location']['path'], f['location'].get('line') or 0)):
        path, line = fact['location']['path'], fact['location'].get('line') or 0
        if places and places[-1]['path'] == path and line - places[-1]['line'] <= NEARBY: continue
        places.append({'path': path, 'line': line, 'rule': fact['value'].get('rule'), 'fact_id': fact['id']})
    return [p for p in places if not TEST.search(p['path'])]


def home_for(kind, places, folders):
    """The central home of a pattern by the project's own layout: an existing folder of its kind nearest the places
    (their common folder or above), else a folder of that name in the common folder of the places."""
    common = PurePosixPath(*_common([PurePosixPath(p['path']).parent.parts for p in places]))
    names = HOMES[kind]
    for folder in [common, *common.parents]:
        for name in names:
            candidate = (folder / name).as_posix().lstrip('./')
            if candidate in folders: return candidate
    return (common / names[0]).as_posix().lstrip('./') or names[0]


def _common(parts):
    shared = []
    for level in zip(*parts):
        if len(set(level)) != 1: break
        shared.append(level[0])
    return shared


def idioms(sets, folders):
    """One finding per idiom written PATTERN_REPEATS times or more, with the ways it is written."""
    by_form = {}
    for fact in engine_records(sets, 'idiom'): by_form.setdefault(fact['value'].get('form'), []).append(fact)
    found = []
    for form, records in sorted(by_form.items()):
        places = _places(records)
        if len(places) < PATTERN_REPEATS: continue
        ways = sorted({p['rule'] for p in places})
        found.append(_finding('idiom', places[0]['path'], places[0]['line'], 'medium' if form == 'route_guard' else 'low',
                              form=form, count=len(places), ways=len(ways), places=places[:40],
                              home=home_for(IDIOM_HOME.get(form, 'helper'), places, folders), fact_ids=[p['fact_id'] for p in places][:20]))
    return found


def ui_patterns(facts, folders):
    """One finding per element tree repeated PATTERN_REPEATS times or more."""
    found = []
    for fact in facts:
        if fact['kind'] != 'ui_pattern': continue
        members = fact['value']['members']
        found.append(_finding('ui_pattern', members[0]['path'], members[0]['line'], 'low', tag=members[0]['tag'],
                              count=len(members), elements=members[0]['elements'], similarity=fact['value']['similarity'],
                              places=members[:40], home=home_for('component', members, folders), fact_id=fact['id']))
    return found


def _finding(kind, place, line, severity, **evidence):
    return {'kind': kind, 'place': place, 'line': line, 'severity': severity, 'evidence': evidence}


def folders_of(sets):
    """Every folder of the project the facts name a file in."""
    paths = {f['location'].get('path') for name in ('syntax', 'patterns') for f in (sets.get(name) or {}).get('facts', [])}
    return {parent.as_posix() for path in paths if path for parent in PurePosixPath(path).parents if parent.as_posix() != '.'}


def findings(out, sets, root=None):
    """Every finding of one source per pattern, and what was not read (a tool that did not run)."""
    patterns = (sets.get('patterns') or {}).get('facts') or []
    folders = folders_of(sets)
    look = one_source_look.finding(patterns, out)
    found = near_copies(sets) + idioms(sets, folders) + ui_patterns(patterns, folders) + ([look] if look else [])
    return found, unmeasured(sets)


def unmeasured(sets):
    """What could not be read: near copies without jscpd, the ways of working without ast-grep, the rest without the source."""
    from .weaknesses import observed
    ran = observed(sets)
    return [name for name, missing in (('near_copy', 'jscpd' not in ran), ('idiom', 'ast-grep' not in ran),
                                       ('ui_pattern', 'patterns' not in sets), ('look', 'patterns' not in sets)) if missing]


def numbers(sets, out=None):
    """The four numbers of the law: near copies (clusters), the look's values written outside the tokens file, UI
    patterns and idioms repeated; each counted as tools/quality.py records it for EAOS."""
    found, _ = findings(out, sets)
    count = Counter(f['kind'] for f in found)
    look = next((f for f in found if f['kind'] == 'look'), None)
    return {'near_copies': count['near_copy'], 'look': look['evidence']['written'] if look else 0,
            'ui_patterns': count['ui_pattern'], 'idioms': count['idiom']}
