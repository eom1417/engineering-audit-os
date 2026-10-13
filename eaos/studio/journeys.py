"""studio/journeys.json: the user's journeys, the screens of the app as frames and the links between them.

Read only from records the check already wrote; nothing is invented, every element names its evidence (`fact`, `file`,
`line`) and every count its source (`src`):

    screens     facts/entrypoints.json entry_point (surface page): one screen per full route; its component file is
                the file the router imports under the handler's name (facts/syntax.json import_edge names, resolved
                by facts/graph.json depends_on), else the one file defining that name
    links       facts/entrypoints.json navigation: a link, redirect, navigate() call or menu entry, at its file and
                line. A link belongs to the screens that render its file (the screen's component file and what it
                imports, three steps); a link in the router file belongs to the route on its line or to the screen
                whose handler holds it; a link in a file the router reaches without passing a screen (the sidebar,
                the header) belongs to the menu, shown on every screen nested under the layout route; a link in a
                file six or more screens render is the menu's too. A link no screen renders is counted, not drawn.
    flags       broken: a link whose target matches no screen (a parameter of the link, :id, $id or {id}, matches only
                a parameter of a route; catch-all routes match nothing); no way in: a page no link reaches from the
                start ("/", and the root layout drawn around every page);
                dead end: a page with no link out and no menu; duplicate: one route declared twice, or one
                component file on several routes
    tasks       what a person does, as a path from the start: a route that creates or edits (…/new, …/edit, a
                Create…Page), or a dialog or form file named for it (CreateWorkOrderDialog) that a screen renders;
                the path is the shortest chain of links from the start to the screen that holds it
    change      each screen's file is owned by the deepest component of target-architecture.json (the System map's
                component); its operation and target component are that component's. The target decides folders,
                not screens: a screen-level decision (keep, merge, delete) is a gap, counted in `missing`
    shots       media.json images of kind screen with this route (the screen gate's shots), when they exist

The layout is computed here, pinned: screens sit on a grid of columns (clicks from the start) and rows; a screen that
was on the previous journeys.json of this report keeps its cell, so a node keeps its place across scans and views.
"""
import json
import re
from collections import defaultdict, deque
from pathlib import Path

from .. import arch_map
from ..lock_specs import PARAM, path_of

DEPTH = 3
SHARED = 6
MAX_TASKS = 40
COL_W, ROW_H, BOX_W, BOX_H, PAD, MAX_ROWS = 212, 84, 168, 60, 24, 12
FORM_SEGMENTS = {'new': 'create', 'create': 'create', 'add': 'create', 'edit': 'edit', 'register': 'create', 'signup': 'create'}
FORM_NAME = re.compile(r'^(?P<verb>Create|New|Add|Edit|Update|Register)(?P<object>[A-Z]\w*?)(?:Dialog|Form|Modal|Sheet|Drawer|Wizard|Page)?$')
FORM_FILE = re.compile(r'(?:^|/)(?P<name>(?:Create|New|Add|Edit|Update|Register)[A-Z]\w*?(?:Dialog|Form|Modal|Sheet|Drawer|Wizard))\.[jt]sx?$')
VERBS = {'create': ('إنشاء', 'Create'), 'new': ('إنشاء', 'Create'), 'add': ('إضافة', 'Add'), 'edit': ('تعديل', 'Edit'),
         'update': ('تحديث', 'Update'), 'register': ('تسجيل', 'Register')}
REDIRECT_HANDLERS = {'Navigate', 'Redirect'}
TEST = re.compile(r'(^|/)(tests?|__tests__|e2e|spec|fixtures?)/|\.(test|spec)\.[a-z]+$')
SRC = {
    'screens': 'facts/entrypoints.json#entry_point[surface=page] (one per full route)',
    'links': 'facts/entrypoints.json#navigation, matched to the screens\' routes',
    'broken': 'facts/entrypoints.json#navigation whose target matches no screen',
    'no_way_in': 'screens no chain of links reaches from the start route',
    'dead_ends': 'pages with no link out and no menu',
    'duplicates': 'routes declared twice, or one component file on several routes',
    'tasks': 'create or edit routes, and Create…/Edit… dialog or form files a screen renders',
    'unowned_links': 'facts/entrypoints.json#navigation in files no screen renders',
    'relative': 'facts/entrypoints.json#navigation[relative] (not resolved to a screen)',
    'without_target': 'screens with no screen-level decision in target-architecture.json',
    'shots': 'media.json#images[kind=screen] with the screen\'s route',
}


def _measure(value, src):
    return {'value': value if isinstance(value, int) and value >= 0 else None, 'src': src, 'unit': 'count'}


def _norm(route):
    route = re.sub(r'^/#(/|$)', lambda m: m.group(1) or '/', str(route or '').strip())    # a hash route /#/x is the /x links name
    return route.rstrip('/') or '/' if route.startswith('/') else route


def _segments(route):
    return [s for s in _norm(route).split('/') if s]


def matches(route, target):
    """Whether a link's target opens this route: segment by segment, a route's parameter (:id, $id, {id}) takes any
    segment, a link's parameter only a route's parameter; a catch-all never matches."""
    r, t = _segments(route), _segments(target)
    if '*' in route or len(r) != len(t): return False
    for a, b in zip(r, t):
        if PARAM.fullmatch(a): continue
        if PARAM.fullmatch(b) or a != b: return False
    return True


def _words(name):
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', name).lower()


def _reach(start, imports, depth, stop=()):
    seen, frontier = {start}, [start]
    for _ in range(depth):
        nxt = []
        for f in frontier:
            for g in imports.get(f, ()):
                if g not in seen and g not in stop:
                    seen.add(g)
                    nxt.append(g)
        frontier = nxt
    return seen



# ---------------------------------------------------------------- the records

def _page_or_link(fact):
    """('page', row) of a page route, ('link', row) of a navigation; None for anything else, or anything in the tests."""
    value, loc = fact.get('value') or {}, fact.get('location') or {}
    path = str(loc.get('path') or '')
    if not path or TEST.search(path) or value.get('category') == 'test': return None
    if fact['kind'] == 'entry_point' and value.get('surface') == 'page' and value.get('route') is not None:
        return 'page', {'route': str(value['route']), 'declared': str(value.get('declared') or value['route']),
                        'handler': str(value.get('handler') or ''), 'router': path,
                        'line': loc.get('start_line'), 'fact': fact.get('id'), 'framework': value.get('framework')}
    if fact['kind'] == 'navigation' and value.get('target'):
        return 'link', {'target': str(value['target']), 'via': value.get('via') or 'link', 'file': path,
                        'line': loc.get('start_line'), 'symbol': loc.get('symbol'), 'fact': fact.get('id'),
                        'dynamic': bool(value.get('dynamic')), 'relative': bool(value.get('relative'))}
    return None


def _names(report):
    """({(file, imported name): [modules]}, {top-level name: the files defining it})."""
    names, defined = defaultdict(list), defaultdict(set)
    for fact in arch_map.facts(report, 'syntax', 'import_edge') + arch_map.facts(report, 'syntax', 'symbol'):
        value, path = fact.get('value') or {}, arch_map.path_of(fact)
        if fact['kind'] == 'import_edge':
            for name in value.get('names') or []: names[(path, name)].append(str(value.get('module') or ''))
        elif value.get('name') and not value.get('parent'):
            defined[str(value['name'])].add(path)
    return names, defined


def _owners(comps):
    """{path: the deepest component holding it}."""
    owners = {}
    for c in sorted(comps, key=lambda c: len(str(c['name']))):
        owners.update({p: c for p in c.get('paths') or [] if isinstance(p, str)})
    return owners


def _target_of(target):
    target_of = {}
    for t in (t for t in target.get('target_components') or [] if isinstance(t, dict) and t.get('name')):
        target_of.update({p: t['name'] for p in t.get('paths') or [] if isinstance(p, str)})
    return target_of


def _feature_of(report):
    """{surface: the first feature naming it}."""
    features = arch_map._load(report / 'features.json', {}) or {}
    feature_of = {}
    for f in (features.get('features') if isinstance(features, dict) else None) or []:
        if not (isinstance(f, dict) and f.get('name')): continue
        for s in f.get('surfaces') or []: feature_of.setdefault(str(s), str(f['name']))
    return feature_of


def _shots(report, media):
    """{route: the screen shots taken of it}; media: media.json's images, else the report's studio/media.json."""
    if media is None:
        media = arch_map._load(report / 'studio/media.json', {}) or {}
        media = media.get('images') if isinstance(media, dict) else None
    shots = defaultdict(list)
    for image in media or []:
        if isinstance(image, dict) and image.get('kind') == 'screen' and image.get('route') and image.get('path'):
            shots[_norm(image['route'])].append(image['path'])
    return shots


def records(report, media=None):
    """Everything the journeys read, each piece empty when its record is missing. media: media.json's images when the
    exporter has them in hand, else the report's studio/media.json."""
    report = Path(report)
    pages, links = [], []
    for found in map(_page_or_link, arch_map.facts(report, 'entrypoints', 'entry_point') + arch_map.facts(report, 'entrypoints', 'navigation')):
        if found: (pages if found[0] == 'page' else links).append(found[1])
    imports = {arch_map.path_of(node): [d for d in (node.get('value') or {}).get('depends_on') or [] if isinstance(d, str)]
               for node in arch_map.facts(report, 'graph', 'graph_node')}
    names, defined = _names(report)
    target = arch_map._load(report / 'target-architecture.json', {}) or {}
    comps = [c for c in target.get('current_components') or [] if isinstance(c, dict) and c.get('name')]
    dead = {arch_map.path_of(f) for f in arch_map.facts(report, 'deadcode', 'engine_finding')
            if (f.get('value') or {}).get('rule') == 'unreachable-module'}
    return {'pages': pages, 'links': links, 'imports': imports, 'dead': dead, 'names': names, 'defined': defined,
            'owners': _owners(comps), 'target_of': _target_of(target), 'feature_of': _feature_of(report),
            'shots': _shots(report, media), 'has_target': bool(comps)}


def component_file(page, r):
    """The file of a page's component: the module the router imports under that name, resolved by the router's own
    imports; else the one file defining the name; else None."""
    handler, router = page['handler'], page['router']
    deps = r['imports'].get(router, [])
    for module in r['names'].get((router, handler), []):
        stem = module.rstrip('/').rsplit('/', 1)[-1]
        found = [d for d in deps if re.sub(r'\.\w+$', '', d).endswith('/' + stem) or re.sub(r'(/index)?\.\w+$', '', d).endswith('/' + stem)]
        if len(found) == 1: return found[0]
    homes = sorted(p for p in r['defined'].get(handler, ()) if not TEST.search(p) and p != router)
    named = [p for p in homes if re.sub(r'\.\w+$', '', p.rsplit('/', 1)[-1]) == handler]
    if len(named) == 1: return named[0]
    return homes[0] if len(homes) == 1 else None


# ---------------------------------------------------------------- the journeys

def _kind(page, routes):
    route = page['route']
    if page['handler'] in REDIRECT_HANDLERS: return 'redirect'
    if page['declared'] == '*' or (route.endswith('/*') and not any(r != route and r.startswith(route[:-1]) for r in routes)): return 'fallback'
    if route.endswith('/*') or path_of(route) is None: return 'layout'     # /app/*, or a root or pathless layout route
    return 'page'


def build(report, previous=None, media=None):
    """The section's body (see the module's docstring), or one with no screens when the records hold none."""
    return from_records(records(report, media), previous)


def _screen(p, r, routes):
    sid = p['route'] if len({q['handler'] for q in r['pages'] if q['route'] == p['route']}) == 1 else f"{p['route']}#{p['handler']}"
    return {'id': sid, 'route': p['route'], 'handler': p['handler'], 'kind': _kind(p, routes), 'file': component_file(p, r),
            'router': p['router'], 'line': p['line'], 'fact': p['fact'],
            'declared': [{'file': p['router'], 'line': p['line'], 'fact': p['fact']}]}


def _screens(r, routes):
    """One screen per (route, handler); the same route twice is one screen declared twice."""
    screens, by_key = [], {}
    for p in sorted(r['pages'], key=lambda p: (p['route'], p['handler'], p['line'] or 0)):
        key = (p['route'], p['handler'])
        if key in by_key:
            by_key[key]['declared'].append({'file': p['router'], 'line': p['line'], 'fact': p['fact']})
            continue
        by_key[key] = _screen(p, r, routes)
        screens.append(by_key[key])
    return screens


def _outer(router, screens):
    return min((s for s in screens if s['router'] == router and s['kind'] == 'layout' and s['route'].endswith('/*')),
               key=lambda s: len(s['route']), default=None)


def _shell(router, screens, imports, stop):
    """A router's menu: what it reaches without passing a screen, shown on the screens under its layout route."""
    files = _reach(router, imports, DEPTH + 1, stop=stop)
    layout = _outer(router, screens)
    prefix = layout['route'][:-2] if layout else None
    scope = sorted(s['id'] for s in screens if s['router'] == router and s['kind'] != 'layout'
                   and (prefix is None or s['route'] == prefix or s['route'].startswith(prefix + '/')))
    root = min((s for s in screens if s['id'] in scope and s['kind'] == 'page'), key=lambda s: (len(s['route']), s['route']), default=None)
    return {'id': f'menu:{router}', 'router': router, 'files': files, 'scope': scope,
            'root': root['id'] if root else None, 'layout': layout['id'] if layout else None}


def _connect(edges, froms, found, link):
    """An edge from each source to each screen a link opens; `link`: (how it goes, its evidence)."""
    via, evidence = link
    for f in froms:
        for t in (t for t in found if f != t['id']):
            edge = edges.setdefault((f, t['id']), {'from': f, 'to': t['id'], 'via': via, 'evidence': []})
            if via == 'redirect': edge['via'] = 'redirect'
            edge['evidence'].append(evidence)


class _Links:
    """Where each link starts (the screens that render it, its route, a menu) and the screens it opens."""

    def __init__(self, r, screens, shells, renders):
        self.r, self.screens, self.shells, self.renders = r, screens, shells, renders
        self.routers = {s['router'] for s in screens}
        self.handlers_of = defaultdict(dict)
        for s in screens: self.handlers_of[s['router']].setdefault(s['handler'], s['id'])
        self.route_line = {(s['router'], d['line']): s['id'] for s in screens for d in s['declared']}
        self.by_route = defaultdict(list)
        for s in screens: self.by_route[_norm(s['route'])].append(s)

    def in_router(self, f, link):
        if (f, link['line']) in self.route_line: return [self.route_line[(f, link['line'])]], 'route'
        if link.get('symbol') in self.handlers_of[f]: return [self.handlers_of[f][link['symbol']]], 'handler'
        return [self.shells[f]['id']], 'menu'

    def sources(self, link):
        f = link['file']
        if f in self.routers: return self.in_router(f, link)
        owners = sorted(self.renders.get(f, ()))
        if owners and len(owners) < SHARED: return owners, 'screen'
        menus = [self.shells[x]['id'] for x in sorted(self.shells) if f in self.shells[x]['files']]
        if menus: return menus, 'menu'
        if owners: return [self.shells[sorted(self.shells)[0]]['id']] if self.shells else owners, 'menu'
        return [], 'unowned'

    def targets_of(self, target):
        exact = [s for s in self.by_route.get(_norm(target), []) if s['kind'] != 'fallback']
        if exact: return exact
        return [s for s in self.screens if s['kind'] in ('page', 'redirect') and matches(s['route'], target)]

    def read(self):
        """(edges, broken links, links no screen renders, relative links)."""
        edges, broken, unowned, relative = {}, [], [], []
        for link in sorted(self.r['links'], key=lambda l: (l['file'], l['line'] or 0, l['target'])):
            froms, how = self.sources(link)
            evidence = {'file': link['file'], 'line': link['line'], 'fact': link['fact'], 'via': link['via'], 'target': link['target']}
            if not froms:
                unowned.append({**evidence, 'dead': link['file'] in self.r['dead']})
                continue
            if link['relative']:
                relative.append({**evidence, 'from': froms[0]})
                continue
            found = self.targets_of(link['target'])
            if not found:
                broken += [{**evidence, 'from': f, 'dynamic': link['dynamic']} for f in froms]
                continue
            _connect(edges, froms, found, (link['via'], evidence))
        return edges, broken, unowned, relative


def _hang_menus(shells, edges):
    """The menu hangs under the root screen of its scope."""
    for shell in shells.values():
        if shell['root'] and any(e['from'] == shell['id'] for e in edges.values()):
            edges[(shell['root'], shell['id'])] = {'from': shell['root'], 'to': shell['id'], 'via': 'menu_of',
                                                   'evidence': [{'file': shell['router'], 'line': None, 'fact': None, 'via': 'menu_of', 'target': None}]}


def _starts(screens):
    """The start: the "/" route, else the shortest page route; and a root layout (__root__, drawn around every page)."""
    around = [s['id'] for s in screens if s['kind'] == 'layout' and path_of(s['route']) is None]
    starts = [s['id'] for s in screens if _norm(s['route']) == '/' and s['kind'] != 'fallback']
    best = min((s for s in screens if s['kind'] == 'page'), key=lambda s: (len(s['route']), s['route']), default=None)
    return (starts or ([best['id']] if best else [])) + around


def _flags_of(s, seen, by_file, broken):
    """(flags, twins) of one screen; `seen`: (depths, links out, menu of each screen)."""
    depth, out, menu_of = seen
    page = s['kind'] == 'page'
    flags = []
    if page and s['id'] not in depth: flags.append('no_way_in')
    if page and not out[s['id']] and s['id'] not in menu_of: flags.append('dead_end')
    twins = sorted(set(by_file.get(s['file'], [])) - {s['id']}) if page else []
    if len(s['declared']) > 1 or twins: flags.append('duplicate')
    if any(b['from'] == s['id'] for b in broken): flags.append('broken_link')
    return flags, twins


def _flag(screens, seen, broken):
    by_file = defaultdict(list)
    for s in screens:
        if s['file'] and s['kind'] == 'page': by_file[s['file']].append(s['id'])
    for s in screens: s['flags'], s['twins'] = _flags_of(s, seen, by_file, broken)


def from_records(r, previous=None):
    """The section's body from records(): the exporter's way, and the synthetic project's (tools/studio_synthetic.py)."""
    routes = sorted({p['route'] for p in r['pages']})
    screens = _screens(r, routes)
    routers = {s['router'] for s in screens}
    screen_files = {s['file'] for s in screens if s['file'] and s['file'] not in routers}
    reach = {s['id']: (_reach(s['file'], r['imports'], DEPTH, stop=routers) if s['file'] and s['file'] not in routers else set())
             for s in screens}
    renders = defaultdict(set)
    for sid, files in reach.items():
        for f in files: renders[f].add(sid)
    shells = {router: _shell(router, screens, r['imports'], screen_files | (routers - {router})) for router in sorted(routers)}
    # every link: its sources, then its target screens
    edges, broken, unowned, relative = _Links(r, screens, shells, renders).read()
    _hang_menus(shells, edges)
    nodes = [s['id'] for s in screens] + [sh['id'] for sh in shells.values() if any(e['from'] == sh['id'] for e in edges.values())]
    out = defaultdict(list)
    for (a, b) in sorted(edges): out[a].append(b)
    starts = _starts(screens)
    paths, depth = _paths(starts, out)
    menu_of = {sid: sh['id'] for sh in shells.values() for sid in sh['scope'] if sh['id'] in nodes}
    _flag(screens, (depth, out, menu_of), broken)
    tasks = _tasks(screens, renders, paths, sorted(r['imports']), r['dead'])
    layout = _layout(nodes, edges, starts, depth, previous)
    journey = {'screens': screens, 'shells': shells, 'nodes': nodes, 'edges': edges, 'broken': broken, 'unowned': unowned,
               'relative': relative, 'starts': starts, 'depth': depth, 'menu_of': menu_of}
    return _assemble(r, journey, tasks, layout)


def _paths(starts, out):
    """({node: [node…]}, {node: clicks}): the shortest chain of links from a start to each node a chain reaches, and
    its length."""
    prev, queue = {s: None for s in starts}, deque(starts)
    while queue:
        cur = queue.popleft()
        for nxt in out[cur]:
            if nxt not in prev:
                prev[nxt] = cur
                queue.append(nxt)
    paths = {}
    for node in prev:
        chain, at = [], node
        while at is not None:
            chain.append(at)
            at = prev[at]
        paths[node] = chain[::-1]
    return paths, {node: len(chain) - 1 for node, chain in paths.items()}


def _name(verb, obj):
    verb = verb.lower()
    ar, en = VERBS.get(verb, (verb, verb.title()))
    return {'ar': f'{ar}: {obj}', 'en': f'{en} {obj}'}


def _route_task(s, paths):
    """((verb, object), task) of a route that creates or edits, by its last segment or its component's name; else None."""
    segs = _segments(s['route'])
    static = [x for x in segs if not x.startswith(':')]
    verb = FORM_SEGMENTS.get(segs[-1].lower()) if segs and not segs[-1].startswith(':') else None
    hit = FORM_NAME.match(s['handler'] or '')
    if hit: verb, obj = hit.group('verb'), _words(hit.group('object'))
    elif verb: obj = static[-2] if len(static) > 1 else (static[0] if static else s['route'])
    else: return None
    return (verb.lower(), obj), {'id': f'task:{verb.lower()}:{obj.replace(" ", "-")}', 'name': _name(verb, obj), 'kind': 'route',
                                 'screen': s['id'], 'file': s['file'], 'line': None, 'path': paths.get(s['id'], []), 'dead': False,
                                 'src': 'route ' + s['route'] + (' (component ' + s['handler'] + ')' if hit else '')}


def _dialog_task(f, renders, paths, dead):
    """((verb, object), task) of a Create…/Edit… dialog or form file a screen renders (or an unreachable one); else None."""
    m = FORM_FILE.search(f)
    hit = FORM_NAME.match(m.group('name')) if m and not TEST.search(f) else None
    if not hit: return None
    verb, obj = hit.group('verb'), _words(hit.group('object'))
    hosts = sorted(renders.get(f, ()), key=lambda sid: (sid not in paths, len(paths.get(sid, ())) or 99, sid))
    if len(hosts) >= SHARED * 2 or (not hosts and f not in dead): return None
    host = hosts[0] if hosts else None
    return (verb.lower(), obj), {'id': f'task:{verb.lower()}:{obj.replace(" ", "-")}', 'name': _name(verb, obj), 'kind': 'dialog',
                                 'screen': host, 'file': f, 'line': None, 'path': paths.get(host, []) if host else [], 'hosts': hosts[:6],
                                 'dead': not hosts,
                                 'src': 'file ' + f + (', rendered by ' + str(len(hosts)) + ' screen(s)' if hosts else
                                                       ', an unreachable module (facts/deadcode.json): no screen renders it')}


def _tasks(screens, renders, paths, files=(), dead=()):
    tasks, seen = [], set()
    found = [_route_task(s, paths) for s in screens if s['kind'] == 'page']
    found += [_dialog_task(f, renders, paths, dead) for f in sorted(set(renders) | set(files))]
    for key, task in filter(None, found):
        if key in seen: continue
        seen.add(key)
        tasks.append(task)
    tasks.sort(key=lambda t: (t.get('dead', False), not t['path'], len(t['path']) or 99, t['kind'] != 'route', t['id']))
    return tasks


# ---------------------------------------------------------------- the layout

def _pinned(previous):
    """{id: (col, row)} of the nodes the previous journeys.json placed."""
    nodes = (previous or {}).get('screens', []) + (previous or {}).get('menus', [])
    return {n['id']: (n['col'], n['row']) for n in nodes
            if isinstance(n, dict) and isinstance(n.get('col'), int) and isinstance(n.get('row'), int)}


def _free_cell(col, taken):
    row = 0
    while (col, row) in taken: row += 1
    taken.add((col, row))
    return col, row


def _place(columns, cells, taken):
    """Each node not pinned in the first free row of its column, a column of more than MAX_ROWS wrapped."""
    start, offset = {}, 0
    for c, column in enumerate(columns):
        start[c] = offset
        offset += max(1, -(-len(column) // MAX_ROWS))
    for c, column in enumerate(columns):
        for i, n in enumerate([n for n in column if n not in cells]):
            cells[n] = _free_cell(start[c] + i // MAX_ROWS, taken)


def _layout(nodes, edges, starts, depth, previous):
    """{id: (col, row)} on a grid: columns are clicks from the start (no way in: a last column), rows ordered by the
    barycentre passes of arch_map, a column of more than MAX_ROWS screens wrapped into the next grid columns; a node
    that had a cell in the previous journeys.json keeps it."""
    pinned = _pinned(previous)
    last = max(depth.values(), default=0) + 1
    layer = {n: depth.get(n, last) for n in nodes}
    pairs = [(a, b) for (a, b) in edges if a in layer and b in layer and layer[a] < layer[b]]
    columns = arch_map.order_columns(layer, pairs) if layer else []
    cells, taken = {}, set()
    for n, cell in pinned.items():
        if n in layer and cell not in taken:
            cells[n] = cell
            taken.add(cell)
    _place(columns, cells, taken)
    return cells


def _xy(cell):
    return PAD + cell[0] * COL_W, PAD + cell[1] * ROW_H


def _curve(a, b):
    """An SVG path from the end side of box a to the start side of box b; a link back or within a column arcs."""
    ax, ay = _xy(a)
    bx, by = _xy(b)
    if b[0] > a[0]:
        x1, y1, x2, y2 = ax + BOX_W, ay + BOX_H / 2, bx, by + BOX_H / 2
        mid = (x1 + x2) / 2
        return f'M{x1:.0f},{y1:.0f} C{mid:.0f},{y1:.0f} {mid:.0f},{y2:.0f} {x2:.0f},{y2:.0f}'
    x1, y1, x2, y2 = ax + BOX_W / 2, ay, bx + BOX_W / 2, by
    lift = min(28 + 10 * abs(a[0] - b[0]) + 6 * abs(a[1] - b[1]), PAD + 36)
    top = min(y1, y2) - lift
    if a[1] < b[1] and a[0] == b[0]:
        x1, y1, x2, y2 = ax + BOX_W, ay + BOX_H / 2, bx + BOX_W, by + BOX_H / 2
        side = ax + BOX_W + 24 + 6 * (b[1] - a[1])
        return f'M{x1:.0f},{y1:.0f} C{side:.0f},{y1:.0f} {side:.0f},{y2:.0f} {x2:.0f},{y2:.0f}'
    return f'M{x1:.0f},{y1:.0f} C{x1:.0f},{top:.0f} {x2:.0f},{top:.0f} {x2:.0f},{y2:.0f}'


# ---------------------------------------------------------------- the section

def _group_of(route, prefix, public=False):
    """The area of a screen: the first fixed segment of its route under its layout's prefix; a screen outside every
    layout of an app that has one is public."""
    if public: return 'public'
    segs = [s for s in _segments(route[len(prefix):] if prefix and route.startswith(prefix) else route) if not s.startswith(':')]
    return segs[0] if segs else '/'


def _out_screen(s, r, journey, drawn):
    """One screen as the Studio draws it; `drawn`: (the cells, each menu's route prefix)."""
    cells, prefixes = drawn
    menu_of = journey['menu_of']
    comp = r['owners'].get(s['file'] or s['router'])   # a handler defined in the router lives in the router's folder
    x, y = _xy(cells[s['id']])
    prefix = prefixes.get(menu_of.get(s['id']), '')
    public = s['id'] not in menu_of and any(prefixes.values())
    return {
        'id': s['id'], 'route': s['route'], 'title': s['handler'] or s['route'], 'kind': s['kind'],
        'file': s['file'], 'router': s['router'], 'line': s['line'], 'fact': s['fact'],
        'declared': s['declared'], 'group': _group_of(s['route'], prefix, public and s['kind'] == 'page' and _norm(s['route']) != '/'), 'feature': r['feature_of'].get(s['route']),
        'component': comp['name'] if comp else None,
        'op': {'retain': 'retain', 'modify': 'modify', 'rebuild': 'rebuild', 'delete': 'delete', 'retire': 'delete'}.get(
            str(comp.get('relation'))) if comp else None,
        'target': r['target_of'].get(s['file'] or '') or (comp.get('target_component') if comp else None),
        'decided': False,
        'start': s['id'] in journey['starts'], 'depth': journey['depth'].get(s['id']), 'menu': menu_of.get(s['id']),
        'flags': s['flags'], 'twins': s['twins'], 'shots': sorted(r['shots'].get(_norm(s['route']), []))[:4],
        'col': cells[s['id']][0], 'row': cells[s['id']][1], 'x': x, 'y': y,
    }


def _out_menu(sh, edges, cells):
    x, y = _xy(cells[sh['id']])
    return {'id': sh['id'], 'router': sh['router'], 'scope': sh['scope'], 'root': sh['root'],
            'files': sorted(f for f in sh['files'] if any(e['evidence'][0]['file'] == f for e in edges.values() if e['from'] == sh['id'])),
            'links': sum(1 for e in edges.values() if e['from'] == sh['id']),
            'col': cells[sh['id']][0], 'row': cells[sh['id']][1], 'x': x, 'y': y}


def _missing(pages, shot_count, relative):
    """What the journeys do not measure yet: each screen's own decision, the shots, the relative links."""
    missing = []
    if pages:
        missing.append({'id': 'screen_target', 'state': 'not_measured', 'step': 'NS44.T1', 'count': _measure(len(pages), SRC['without_target']),
                     'detail': {'ar': 'البنية المستهدفة تقرر المجلدات لا الشاشات: لا قرار لكل شاشة (تبقى، تُدمج، تُحذف).',
                                'en': 'The target architecture decides folders, not screens: no screen has its own decision (keep, merge, delete).'}})
    if pages and not shot_count:
        missing.append({'id': 'shots', 'state': 'not_measured', 'step': 'NS41.T1', 'count': _measure(None, SRC['shots']),
                     'detail': {'ar': 'لا صور للشاشات بعد: تصويرها يحتاج تشغيل التطبيق بموافقتك.',
                                'en': 'No screen shots yet: capturing them needs the app running, with your agreement.'}})
    if relative:
        missing.append({'id': 'relative_links', 'state': 'partial', 'step': 'NS40.T1', 'count': _measure(len(relative), SRC['relative']),
                     'detail': {'ar': 'روابط نسبية لم تُربط بشاشة.', 'en': 'Relative links not resolved to a screen.'}})
    return missing


def _assemble(r, journey, tasks, cells):
    """The section's body; `journey`: the screens, menus, nodes, edges, broken, unowned and relative links, the starts,
    the depths and each screen's menu, as from_records found them."""
    screens, shells, edges = journey['screens'], journey['shells'], journey['edges']
    broken, unowned, relative, starts = journey['broken'], journey['unowned'], journey['relative'], journey['starts']
    prefixes = {sh['id']: (next((s['route'][:-2] for s in screens if s['id'] == sh['layout']), '') if sh['layout'] else '') for sh in shells.values()}
    out_screens = [_out_screen(s, r, journey, (cells, prefixes)) for s in screens]
    menus = [_out_menu(sh, edges, cells) for sh in shells.values() if sh['id'] in journey['nodes']]
    out_edges = [{'from': e['from'], 'to': e['to'], 'via': e['via'], 'back': cells[e['to']][0] <= cells[e['from']][0],
                  'evidence': sorted(e['evidence'], key=lambda v: (v['file'], v['line'] or 0))[:6], 'count': len(e['evidence']),
                  'd': _curve(cells[e['from']], cells[e['to']])}
                 for e in sorted(edges.values(), key=lambda e: (e['from'], e['to']))]
    pages = [s for s in out_screens if s['kind'] == 'page']
    count = lambda flag: sum(flag in s['flags'] for s in pages)
    cols = max((c[0] for c in cells.values()), default=-1) + 1
    rows = max((c[1] for c in cells.values()), default=-1) + 1
    shot_count = sum(1 for s in out_screens if s['shots'])
    groups = defaultdict(list)
    for s in out_screens: groups[s['group']].append(s['id'])
    return {
        'counts': {
            'screens': _measure(len(pages), SRC['screens'] + ', kind page'),
            'hidden_screens': _measure(len(out_screens) - len(pages), SRC['screens'] + ', kind layout, redirect or fallback'),
            'links': _measure(len([e for e in out_edges if e['via'] != 'menu_of']), SRC['links'] + ' (screen pairs)'),
            'link_sites': _measure(sum(e['count'] for e in out_edges if e['via'] != 'menu_of'), SRC['links']),
            'broken': _measure(len(broken), SRC['broken']),
            'no_way_in': _measure(count('no_way_in'), SRC['no_way_in']),
            'dead_ends': _measure(count('dead_end'), SRC['dead_ends']),
            'duplicates': _measure(count('duplicate'), SRC['duplicates']),
            'tasks': _measure(len(tasks), SRC['tasks']),
            'unowned_links': _measure(len(unowned), SRC['unowned_links']),
            'unowned_dead': _measure(sum(u['dead'] for u in unowned), SRC['unowned_links'] + ', in an unreachable module'),
            'without_target': _measure(len(pages) if pages else 0, SRC['without_target']),
            'shots': _measure(shot_count, SRC['shots']),
        },
        'src': SRC,
        'grid': {'cols': cols, 'rows': rows, 'col_w': COL_W, 'row_h': ROW_H, 'box_w': BOX_W, 'box_h': BOX_H, 'pad': PAD,
                 'width': PAD * 2 + max(cols - 1, 0) * COL_W + BOX_W, 'height': PAD * 2 + max(rows - 1, 0) * ROW_H + BOX_H},
        'starts': starts,
        'screens': out_screens,
        'menus': menus,
        'edges': out_edges,
        'broken': broken[:200],
        'unowned': unowned[:200],
        'relative': relative[:100],
        'groups': [{'id': g, 'screens': ids} for g, ids in sorted(groups.items())],
        'tasks': tasks[:MAX_TASKS],
        'capped': {'tasks': max(len(tasks) - MAX_TASKS, 0), 'broken': max(len(broken) - 200, 0), 'unowned': max(len(unowned) - 200, 0)},
        'missing': _missing(pages, shot_count, relative),
    }


def journeys(report, media=None):
    """The section's body; the previous journeys.json of this report pins the layout."""
    previous = None
    path = Path(report) / 'studio/journeys.json'
    if path.is_file():
        try: previous = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError): previous = None
    return build(report, previous, media)
