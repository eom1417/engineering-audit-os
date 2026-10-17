"""Every page of a running app, found by following its links, and Lighthouse on a few distinct ones.

    crawl(base, out, max_routes, measured)   the pinned Playwright (eaos/templates/screens/crawl.mjs) opens each page
                                             of the app at `base` (its own address on this computer) once, breadth
                                             first, and follows its links: every page it reaches is listed. Lighthouse
                                             (audit.lighthouse, mobile profile) then measures at most `measured` of
                                             them: the entry and the first page of each distinct template after it.
                                             Returns {status, reason?, routes: [{path, template, depth, measured,
                                             scores?, lcp_ms?, cls?, report?}]}; the Lighthouse reports stay in `out`.
    templates(paths)                         {path: template}: pages that are one template with different data
                                             (/items/1 and /items/2, #/tasks/TASK-001 and #/tasks/TASK-004, a list
                                             and its ?filter=) are one page: they are pictured and measured once.

Lighthouse on every crawled route took 28 minutes on EAOS's own Studio (76 routes, most of them the same template
with other data); a page's speed and accessibility are its template's.
"""
import re
from pathlib import Path

from .audit import _node, lighthouse, missing, toolchain

MEASURED = 10                   # pages Lighthouse measures in one crawl
SIBLINGS = 5                    # this many sibling pages under one parent are one template (/blog/<slug>)
DATA = re.compile(r'\d|%|[()~:@.,;=+]')   # a path segment that carries data: a number, an encoded or punctuated name


def _parts(path):
    """(prefix, segments) of a page's address without its query or anchor: a hash route (/#/tasks/1) is split after
    '#/'; a bare '#/' and a folder's index.html are the page itself."""
    address, _, fragment = path.partition('#')
    address = address.split('?', 1)[0]
    route = [s for s in fragment.split('?', 1)[0].split('/') if s] if fragment.startswith('/') else []
    if route: return address.rstrip('/') + '/#', route
    segments = [s for s in address.split('/') if s]
    return '', segments[:-1] if segments and segments[-1] in ('index.html', 'index.htm') else segments


def templates(paths):
    """{path: template}. A segment after the first that carries data (a number, an encoded or punctuated name) is a
    parameter (:id); so is the last segment of pages that share a parent with SIBLINGS or more other last pages
    (/#/flows/cli, /#/flows/main, ...). The query is dropped: a filtered list is the list."""
    split = {path: _parts(path) for path in paths}
    marked = {path: (prefix, [':id' if i and DATA.search(s) else s for i, s in enumerate(segments)])
              for path, (prefix, segments) in split.items()}
    leaves = _leaves(split, marked)
    return {path: _template(prefix, segments, leaves) for path, (prefix, segments) in marked.items()}


def _leaves(split, marked):
    """{(prefix, parent): {last segments}} of the pages with no page under them."""
    shapes = {(prefix, tuple(segments)) for prefix, segments in marked.values()}
    leaves = {}
    for path, (prefix, segments) in marked.items():
        if len(segments) < 2 or _has_pages_under(prefix, segments, shapes): continue     # a section, not a leaf
        leaves.setdefault((prefix, tuple(segments[:-1])), set()).add(split[path][1][-1])
    return leaves


def _has_pages_under(prefix, segments, shapes):
    return any(other[0] == prefix and len(other[1]) > len(segments) and other[1][:len(segments)] == tuple(segments) for other in shapes)


def _template(prefix, segments, leaves):
    """A page's template: its last segment is a parameter when it has SIBLINGS or more sibling leaves."""
    if len(segments) >= 2 and len(leaves.get((prefix, tuple(segments[:-1])), ())) >= SIBLINGS:
        segments = segments[:-1] + [':id']
    return prefix + '/' + '/'.join(segments)


def distinct(paths):
    """{template: [paths]} in the order the paths come (the first is the template's picture), without repeats."""
    paths = list(dict.fromkeys(paths))
    found = {}
    for path, template in templates(paths).items(): found.setdefault(template, []).append(path)
    return found


def discover(base, max_routes=200, timeout=1800, storage_state=None):
    """(routes, error): every page of the app reached from `base` by its links, [{path, depth, status}]."""
    absent = missing('playwright')
    if absent: return None, absent
    config = {'base': base, 'max_routes': max_routes, 'modules': {'playwright': str(toolchain.home() / 'node/node_modules')}}
    if storage_state: config['storage_state'] = str(storage_state)
    result, error = _node('crawl.mjs', config, timeout)
    return (result or {}).get('routes'), error


def _measure(row, base, out, number, storage_state):
    """Lighthouse on one page: its scores into the row, else why it could not be measured."""
    speed = lighthouse(base.rstrip('/') + row['path'], out=out / 'lighthouse' / f'{number:02d}', storage_state=storage_state)
    if speed.get('status') != 'observed':
        row['reason'] = speed.get('reason')
        return
    row.update(measured=True, scores=speed['scores'], lcp_ms=speed['lcp_ms'], cls=speed['cls'],
               report=Path(speed['report']).relative_to(out).as_posix() if speed.get('report') else None)


def crawl(base, out, max_routes=200, measured=MEASURED, storage_state=None):
    routes, error = discover(base, max_routes, storage_state=storage_state)
    if routes is None:
        return {'status': 'unavailable' if error and error.startswith(('not installed', 'Node.js')) else 'error', 'reason': error, 'routes': []}
    routes = [r for r in routes if r.get('status') == 'observed']
    if not routes: return {'status': 'error', 'reason': 'the crawl opened no page of the app', 'routes': []}
    shapes = templates([r['path'] for r in routes])
    chosen = list(dict.fromkeys(paths[0] for paths in distinct(r['path'] for r in routes).values()))[:measured]
    out = Path(out)
    rows = []
    for route in routes:
        row = {'path': route['path'], 'template': shapes[route['path']], 'depth': route.get('depth'), 'measured': False}
        if route['path'] in chosen: _measure(row, base, out, chosen.index(route['path']), storage_state)
        rows.append(row)
    return {'status': 'observed', 'routes': rows, 'templates': len(set(shapes.values())),
            'measured': sum(r['measured'] for r in rows)}
