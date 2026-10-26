"""journeys.json's body: every screen, menu and link as the Studio draws them, the counts with their sources, the
groups, the tasks and what is not measured yet."""
from collections import defaultdict

from .layout import BOX_H, BOX_W, COL_W, PAD, ROW_H, curve, xy
from .routes import _norm, _segments

MAX_TASKS = 40
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
    x, y = xy(cells[s['id']])
    prefix = prefixes.get(menu_of.get(s['id']), '')
    public = s['id'] not in menu_of and any(prefixes.values())
    return {
        'id': s['id'], 'route': s['route'], 'title': s['handler'] or s['route'], 'kind': s['kind'],
        'file': s['file'], 'router': s['router'], 'line': s['line'], 'fact': s['fact'],
        'declared': s['declared'], 'group': _group_of(s['route'], prefix, public and s['kind'] == 'page' and _norm(s['route']) != '/'), 'feature': r['feature_of'].get(s['route']),
        **_change_of(s, comp, r), 'decided': False,
        'start': s['id'] in journey['starts'], 'depth': journey['depth'].get(s['id']), 'menu': menu_of.get(s['id']),
        'flags': s['flags'], 'twins': s['twins'], 'shots': sorted(r['shots'].get(_norm(s['route']), []))[:4],
        'col': cells[s['id']][0], 'row': cells[s['id']][1], 'x': x, 'y': y,
    }


def _change_of(s, comp, r):
    """A screen's component of today (the System map's), its operation, and the target component it goes to."""
    return {'component': comp['name'] if comp else None,
            'op': {'retain': 'retain', 'modify': 'modify', 'rebuild': 'rebuild', 'delete': 'delete', 'retire': 'delete'}.get(
                str(comp.get('relation'))) if comp else None,
            'target': r['target_of'].get(s['file'] or '') or (comp.get('target_component') if comp else None)}


def _out_menu(sh, edges, cells):
    x, y = xy(cells[sh['id']])
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


def _prefixes(screens, shells):
    """{menu: the route prefix of the layout it belongs to, '' for none}."""
    route_of = {s['id']: s['route'][:-2] for s in reversed(screens)}      # the first screen of an id, as next() found it
    return {sh['id']: route_of.get(sh['layout'], '') if sh['layout'] else '' for sh in shells.values()}


def _out_edges(edges, cells):
    """Every link between two screens, drawn, with up to six of its sites."""
    return [{'from': e['from'], 'to': e['to'], 'via': e['via'], 'back': cells[e['to']][0] <= cells[e['from']][0],
             'evidence': sorted(e['evidence'], key=lambda v: (v['file'], v['line'] or 0))[:6], 'count': len(e['evidence']),
             'd': curve(cells[e['from']], cells[e['to']])}
            for e in sorted(edges.values(), key=lambda e: (e['from'], e['to']))]


def _journey_counts(out_screens, out_edges, journey, tasks):
    """The section's numbers, each with the record it is read from."""
    pages = [s for s in out_screens if s['kind'] == 'page']
    shot_count = sum(1 for s in out_screens if s['shots'])
    broken, unowned = journey['broken'], journey['unowned']
    count = lambda flag: sum(flag in s['flags'] for s in pages)
    links = [e for e in out_edges if e['via'] != 'menu_of']
    return {
        'screens': _measure(len(pages), SRC['screens'] + ', kind page'),
        'hidden_screens': _measure(len(out_screens) - len(pages), SRC['screens'] + ', kind layout, redirect or fallback'),
        'links': _measure(len(links), SRC['links'] + ' (screen pairs)'),
        'link_sites': _measure(sum(e['count'] for e in links), SRC['links']),
        'broken': _measure(len(broken), SRC['broken']),
        'no_way_in': _measure(count('no_way_in'), SRC['no_way_in']),
        'dead_ends': _measure(count('dead_end'), SRC['dead_ends']),
        'duplicates': _measure(count('duplicate'), SRC['duplicates']),
        'tasks': _measure(len(tasks), SRC['tasks']),
        'unowned_links': _measure(len(unowned), SRC['unowned_links']),
        'unowned_dead': _measure(sum(u['dead'] for u in unowned), SRC['unowned_links'] + ', in an unreachable module'),
        'without_target': _measure(len(pages), SRC['without_target']),
        'shots': _measure(shot_count, SRC['shots']),
    }


def _grid(cells):
    cols = max((c[0] for c in cells.values()), default=-1) + 1
    rows = max((c[1] for c in cells.values()), default=-1) + 1
    return {'cols': cols, 'rows': rows, 'col_w': COL_W, 'row_h': ROW_H, 'box_w': BOX_W, 'box_h': BOX_H, 'pad': PAD,
            'width': PAD * 2 + max(cols - 1, 0) * COL_W + BOX_W, 'height': PAD * 2 + max(rows - 1, 0) * ROW_H + BOX_H}


def _assemble(r, journey, tasks, cells):
    """The section's body; `journey`: the screens, menus, nodes, edges, broken, unowned and relative links, the starts,
    the depths and each screen's menu, as from_records found them."""
    screens, shells, edges = journey['screens'], journey['shells'], journey['edges']
    broken, unowned, relative, starts = journey['broken'], journey['unowned'], journey['relative'], journey['starts']
    out_screens = [_out_screen(s, r, journey, (cells, _prefixes(screens, shells))) for s in screens]
    menus = [_out_menu(sh, edges, cells) for sh in shells.values() if sh['id'] in journey['nodes']]
    out_edges = _out_edges(edges, cells)
    pages = [s for s in out_screens if s['kind'] == 'page']
    shot_count = sum(1 for s in out_screens if s['shots'])
    groups = defaultdict(list)
    for s in out_screens: groups[s['group']].append(s['id'])
    return {
        'counts': _journey_counts(out_screens, out_edges, journey, tasks),
        'src': SRC,
        'grid': _grid(cells),
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
