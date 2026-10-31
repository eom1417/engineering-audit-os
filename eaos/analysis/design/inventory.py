"""The design inventory (M18.10-M18.12, M18.15): every value, component look and format the project's screens really show, from what the lock's
specs saved of each page (eaos/templates/screens/look.cjs). Facts, always shown: a card waits for its bar (tools/judging/precision.py).

    inventory(pages, project)   {pages, values, near_colours, components, motion, formats, libraries}
    write(folder, out, project) design/inventory.json, the crops beside it; None when no page was saved
"""
import base64
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from ..assessments.one_source_look import colour_groups
from ...core.system.files import read_json

DATA = Path(__file__).resolve().parents[2] / 'data'
CATALOG = json.loads((DATA / 'design-catalog.json').read_text(encoding='utf-8'))
LIBRARIES = json.loads((DATA / 'ui-libraries.json').read_text(encoding='utf-8'))
TOP_VALUES, LOOKS_KEPT, PLACES = 40, 24, 5
CROP_MOST = 60_000           # bytes of one picture a report carries


def read_pages(folder):
    """{page name: what its spec saved}, one file per page and kind of user."""
    return {path.stem: json.loads(path.read_text(encoding='utf-8')) for path in sorted(Path(folder).glob('*.json'))}


def _elements(pages):
    """Each element of each page with its default look: (page, key, row of states, look)."""
    for name, page in pages.items():
        for key, row in page['els'].items():
            yield name, key, row, page['sigs'][row['default']]


def _values(pages):
    """{kind: [{value, uses, pages, where}]}: the values the screens show, the most used first; what means "nothing" left out."""
    ignored, found = set(CATALOG['ignored_values']), defaultdict(lambda: defaultdict(lambda: {'uses': 0, 'pages': set(), 'where': []}))
    for name, key, _, look in _elements(pages):
        for kind, spec in CATALOG['values'].items():
            for prop in spec['properties']:
                value = look.get(prop)
                if not value or value in ignored: continue
                row = found[kind][value]
                row['uses'] += 1
                row['pages'].add(name)
                if len(row['where']) < PLACES: row['where'].append({'page': name, 'element': key})
    return {kind: sorted(({'value': value, 'uses': row['uses'], 'pages': len(row['pages']), 'where': row['where']} for value, row in rows.items()),
                         key=lambda row: (-row['uses'], row['value'])) for kind, rows in found.items()}


def _signature(look):
    return tuple((prop, look.get(prop)) for prop in CATALOG['component_look'])


def _components(pages):
    """{role: {count, looks: [{look, count, pages, where, crop}]}}: the same part drawn how many ways, the most used first."""
    groups = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'pages': set(), 'where': [], 'crop': None}))
    for name, key, _, look in _elements(pages):
        role = (pages[name].get('roles') or {}).get(key)
        if role not in CATALOG['components']: continue
        row = groups[role][_signature(look)]
        row['count'] += 1
        row['pages'].add(name)
        if len(row['where']) < PLACES: row['where'].append({'page': name, 'element': key})
        row['crop'] = row['crop'] or (pages[name].get('crops') or {}).get(key)
    return {role: {'count': sum(r['count'] for r in looks.values()), 'looks': _looks(looks)} for role, looks in sorted(groups.items())}


def _looks(looks):
    ordered = sorted(looks.items(), key=lambda item: -item[1]['count'])[:LOOKS_KEPT]
    return [{'look': dict(sig), 'count': row['count'], 'pages': len(row['pages']), 'where': row['where'], 'crop': row['crop']} for sig, row in ordered]


def _formats(pages):
    """{kind: [{form, count, pages}]} of what the pages' words show; a kind shown in two forms is the finding."""
    found = {}
    for kind, spec in CATALOG['formats'].items():
        rows = []
        for form, pattern in spec['forms'].items():
            hits = {name: len(re.findall(pattern, page.get('text') or '')) for name, page in pages.items()}
            if any(hits.values()): rows.append({'form': form, 'count': sum(hits.values()), 'pages': sum(1 for n in hits.values() if n)})
        if rows: found[kind] = sorted(rows, key=lambda row: -row['count'])
    return found


def _motion(pages):
    durations, easings = Counter(), Counter()
    for page in pages.values():
        durations.update((page.get('motion') or {}).get('durations') or {})
        easings.update((page.get('motion') or {}).get('easings') or {})
    return {'durations': durations.most_common(TOP_VALUES), 'easings': easings.most_common(TOP_VALUES)}


def _manifests(project):
    """The package names of the project's package.json files, its own folders only."""
    names = set()
    for path in Path(project).rglob('package.json'):
        if 'node_modules' in path.parts: continue
        data = read_json(path, {}) or {}
        names |= set(data.get('dependencies') or ()) | set(data.get('devDependencies') or ())
    return names


def libraries(project):
    """{job: its packages} of each job two or more packages of the project do."""
    names = _manifests(project)
    found = {job: sorted(names & set(spec['packages'])) for job, spec in LIBRARIES['jobs'].items()}
    return {job: packages for job, packages in found.items() if len(packages) > 1}


def _near(values):
    counts = {row['value']: row['uses'] for row in values.get('color') or ()}
    return [members for _, members, _ in colour_groups(counts) if len(members) > 1]


def inventory(pages, project):
    values = _values(pages)
    return {'schema_version': 1, 'pages': len(pages), 'values': {kind: {'distinct': len(rows), 'rows': rows[:TOP_VALUES]} for kind, rows in values.items()},
            'near_colours': _near(values), 'components': _components(pages), 'motion': _motion(pages), 'formats': _formats(pages), 'libraries': libraries(project)}


def with_pictures(report):
    """The inventory of a report with its pictures inside, small ones only: REPORT.html is one file."""
    drawn = read_json(Path(report) / 'design' / 'inventory.json')
    if not drawn: return None
    for look in (look for part in drawn['components'].values() for look in part['looks'] if look.get('crop')):
        path = Path(report) / 'design' / 'crops' / look['crop']
        if path.is_file() and path.stat().st_size <= CROP_MOST: look['crop_data'] = base64.b64encode(path.read_bytes()).decode()
    return drawn


def write(folder, out, project):
    """The inventory of the pages saved in `folder`, in `out`/design; None when no page was saved (the app did not run)."""
    pages = read_pages(folder)
    if not pages: return None
    drawn = inventory(pages, project)
    target = Path(out) / 'design'
    (target / 'crops').mkdir(parents=True, exist_ok=True)
    for row in (look for part in drawn['components'].values() for look in part['looks'] if look['crop']):
        if (Path(folder) / 'crops' / row['crop']).is_file(): shutil.copyfile(Path(folder) / 'crops' / row['crop'], target / 'crops' / row['crop'])
    (target / 'inventory.json').write_text(json.dumps(drawn, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return drawn
