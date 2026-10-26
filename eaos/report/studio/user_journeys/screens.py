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

The layout is pinned across scans and views (eaos/report/studio/user_journeys/layout.py). Here: the screens, the links
between them, the menus and the flags; report/studio/user_journeys/routes.py: a route's spelling and matching; report/studio/user_journeys/records.py: what is read; report/studio/user_journeys/tasks.py:
what a person does; report/studio/user_journeys/section.py: the body as the Studio draws it.
"""
import json
from collections import defaultdict, deque
from pathlib import Path

from ....live.behavior.specs import path_of
from .layout import layout as grid
from .records import component_file, records
from .routes import DEPTH, SHARED, _norm, _reach, matches
from .section import _assemble
from .tasks import _tasks

REDIRECT_HANDLERS = {'Navigate', 'Redirect'}


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
    scope = _scope(router, screens, prefix)
    root = min((s for s in screens if s['id'] in scope and s['kind'] == 'page'), key=lambda s: (len(s['route']), s['route']), default=None)
    return {'id': f'menu:{router}', 'router': router, 'files': files, 'scope': scope,
            'root': root['id'] if root else None, 'layout': layout['id'] if layout else None}


def _scope(router, screens, prefix):
    """The screens a router's menu shows on: its own, not layouts, under the layout route's `prefix` when it has one."""
    return sorted(s['id'] for s in screens if s['router'] == router and s['kind'] != 'layout'
                  and (prefix is None or s['route'] == prefix or s['route'].startswith(prefix + '/')))


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
    return _start(screens) + around


def _start(screens):
    """The "/" route, else the shortest page route; none without a page."""
    starts = [s['id'] for s in screens if _norm(s['route']) == '/' and s['kind'] != 'fallback']
    best = min((s for s in screens if s['kind'] == 'page'), key=lambda s: (len(s['route']), s['route']), default=None)
    return starts or ([best['id']] if best else [])


def _flags_of(s, seen, by_file, broken_from):
    """(flags, twins) of one screen; `seen`: (depths, links out, menu of each screen); `broken_from`: the screens a
    broken link starts from."""
    depth, out, menu_of = seen
    page = s['kind'] == 'page'
    flags = []
    if page and s['id'] not in depth: flags.append('no_way_in')
    if page and not out[s['id']] and s['id'] not in menu_of: flags.append('dead_end')
    twins = sorted(set(by_file.get(s['file'], [])) - {s['id']}) if page else []
    if len(s['declared']) > 1 or twins: flags.append('duplicate')
    if s['id'] in broken_from: flags.append('broken_link')
    return flags, twins


def _flag(screens, seen, broken):
    by_file = defaultdict(list)
    for s in screens:
        if s['file'] and s['kind'] == 'page': by_file[s['file']].append(s['id'])
    broken_from = {b['from'] for b in broken}
    for s in screens: s['flags'], s['twins'] = _flags_of(s, seen, by_file, broken_from)


def from_records(r, previous=None):
    """The section's body from records(): the exporter's way, and the synthetic project's (tools/studio_synthetic.py)."""
    routes = sorted({p['route'] for p in r['pages']})
    screens = _screens(r, routes)
    routers = {s['router'] for s in screens}
    screen_files = {s['file'] for s in screens if s['file'] and s['file'] not in routers}
    renders = _renders(screens, r['imports'], routers)
    shells = {router: _shell(router, screens, r['imports'], screen_files | (routers - {router})) for router in sorted(routers)}
    # every link: its sources, then its target screens
    edges, broken, unowned, relative = _Links(r, screens, shells, renders).read()
    _hang_menus(shells, edges)
    nodes = [s['id'] for s in screens] + _linked_menus(shells, edges)
    out = defaultdict(list)
    for (a, b) in sorted(edges): out[a].append(b)
    starts = _starts(screens)
    paths, depth = _paths(starts, out)
    menu_of = _menu_of(shells, nodes)
    _flag(screens, (depth, out, menu_of), broken)
    tasks = _tasks(screens, renders, paths, sorted(r['imports']), r['dead'])
    layout = grid(nodes, edges, depth, previous)
    journey = {'screens': screens, 'shells': shells, 'nodes': nodes, 'edges': edges, 'broken': broken, 'unowned': unowned,
               'relative': relative, 'starts': starts, 'depth': depth, 'menu_of': menu_of}
    return _assemble(r, journey, tasks, layout)


def _renders(screens, imports, routers):
    """{file: the screens that render it}: a screen's component file and what it imports, DEPTH steps, never through a
    router."""
    reach = {s['id']: (_reach(s['file'], imports, DEPTH, stop=routers) if s['file'] and s['file'] not in routers else set())
             for s in screens}
    renders = defaultdict(set)
    for sid, files in reach.items():
        for f in files: renders[f].add(sid)
    return renders


def _linked_menus(shells, edges):
    """The menus some link starts from."""
    return [sh['id'] for sh in shells.values() if any(e['from'] == sh['id'] for e in edges.values())]


def _menu_of(shells, nodes):
    """{screen: the drawn menu shown on it}."""
    return {sid: sh['id'] for sh in shells.values() for sid in sh['scope'] if sh['id'] in nodes}


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


def journeys(report, media=None):
    """The section's body; the previous journeys.json of this report pins the layout."""
    previous = None
    path = Path(report) / 'studio/journeys.json'
    if path.is_file():
        try: previous = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError): previous = None
    return build(report, previous, media)
