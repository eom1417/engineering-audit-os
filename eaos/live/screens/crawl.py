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
PUBLISHED_ROUTES, PUBLISHED_MEASURED = 40, 3    # a published site is read gently: a few pages opened, fewer measured
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


def templates(paths, declared=()):
    """{path: template}. A segment after the first that carries data (a number, an encoded or punctuated name) is a
    parameter (:id); so is the last segment of pages that share a parent with SIBLINGS or more other last pages
    (/#/flows/cli, /#/flows/main, ...), unless the code `declared` the page as one of its own (LocalLibrary's
    /catalog/books and /catalog/authors were pictured as one). The query is dropped: a filtered list is the list."""
    split = {path: _parts(path) for path in paths}
    marked = {path: (prefix, [':id' if i and DATA.search(s) else s for i, s in enumerate(segments)])
              for path, (prefix, segments) in split.items()}
    leaves, named = _leaves(split, marked), {_plain(path) for path in declared}
    return {path: _plain(path) if _plain(path) in named else _template(prefix, segments, leaves) for path, (prefix, segments) in marked.items()}


def _plain(path):
    """A page's address without its query and final slash: '/catalog/books/?page=2' is '/catalog/books'."""
    address, mark, fragment = path.partition('#')
    return (address.split('?', 1)[0].rstrip('/') or '/') + mark + fragment.rstrip('/')


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


def distinct(paths, declared=()):
    """{template: [paths]} in the order the paths come (the first is the template's picture), without repeats; a page
    the code `declared` is a template of its own."""
    paths = list(dict.fromkeys(paths))
    found = {}
    for path, template in templates(paths, declared).items(): found.setdefault(template, []).append(path)
    return found


# A screen address the code itself names: '#/now', '/#/plan/today' in a string, as a hash-routed app writes its menu and
# its redirects. The crawl opens these too, so a screen behind a welcome, a button or a slow first load is still found
# (an SPA: the app opened on #/onboarding, its tab bar never showed, and the crawl found one page).
HASH_ROUTE = re.compile(r'''["'`]/?#(/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*)/?["'`]''')
CODE = ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.vue', '.svelte', '.html')
# In a file that routes by the hash (its own table, a HashRouter), a plain '/now' is a screen too; never an /api call.
HASH_ROUTER = re.compile(r'location\.hash|hashchange|HashRouter|createHashRouter|createWebHashHistory')
PATH = re.compile(r'''["'`](/(?!api\b)[a-z][a-z0-9_-]*(?:/[a-z0-9_-]+)*)["'`]''')


def code_routes(root, most=100):
    """['/#/now', '/about', ...]: the screens the project names, in the order first met, `most` at most: the hash routes
    its code names (in an app that routes by the hash, every plain '/now' of its code is one: CoreUI's menu lives in a
    file of its own, and its form pages were never opened), then the pages its files make (file_routes)."""
    from .file_routes import file_routes
    texts = list(_code_texts(root))
    hashed = any(HASH_ROUTER.search(text) for text in texts)
    found = {}
    for text in texts: found.update(dict.fromkeys('/#' + route for route in HASH_ROUTE.findall(text) + (PATH.findall(text) if hashed else [])))
    found.update(dict.fromkeys(as_screen(route, hashed) for route in file_routes(root)))
    return list(found)[:most]


def _code_texts(root):
    from ...core.project.workspace import inventory
    for row in inventory(root)['files']:
        if not row['path'].endswith(CODE): continue
        try: yield (Path(root) / row['path']).read_text(encoding='utf-8', errors='replace')
        except OSError: continue


def hash_routed(root):
    """Whether the app at `root` routes by the hash (#/now): its pages are opened at '/#' + their route."""
    return any(HASH_ROUTER.search(text) for text in _code_texts(root))


def as_screen(route, hashed):
    """A page route of the code as the address that shows it: '/#/forms' in an app that routes by the hash."""
    return '/#' + route if hashed and route.startswith('/') and '#' not in route else route


def discover(base, max_routes=200, storage_state=None, read_only=False, seeds=()):
    """(routes, error): every page of the app reached from `base` by its links, [{path, depth, status}], within half an
    hour. Signed in (`storage_state`), a link that would sign out, delete or change (lock_specs.LEAVES) is never
    followed; `read_only` (a published address) sends nothing but GET."""
    from ..behavior.specs import LEAVES
    absent = missing('playwright')
    if absent: return None, absent
    config = {'base': base, 'max_routes': max_routes, 'modules': {'playwright': str(toolchain.home() / 'node/node_modules')},
              'read_only': read_only, 'seeds': list(seeds)}
    if storage_state: config.update(storage_state=str(storage_state), leaves=LEAVES)
    result, error = _node('crawl.mjs', config, 1800)
    return (result or {}).get('routes'), error


def _measure(row, base, out, number, storage_state):
    """Lighthouse on one page: its scores into the row, else why it could not be measured."""
    speed = lighthouse(base.rstrip('/') + row['path'], out=out / 'lighthouse' / f'{number:02d}', storage_state=storage_state)
    if speed.get('status') != 'observed':
        row['reason'] = speed.get('reason')
        return
    row.update(measured=True, scores=speed['scores'], lcp_ms=speed['lcp_ms'], cls=speed['cls'],
               report=Path(speed['report']).relative_to(out).as_posix() if speed.get('report') else None)


def crawl(base, out, max_routes=200, measured=MEASURED, storage_state=None, read_only=False, seeds=()):
    if read_only: max_routes, measured = min(max_routes, PUBLISHED_ROUTES), min(measured, PUBLISHED_MEASURED)
    routes, error = discover(base, max_routes, storage_state=storage_state, read_only=read_only, seeds=seeds)
    if routes is None:
        return {'status': 'unavailable' if error and error.startswith(('not installed', 'Node.js')) else 'error', 'reason': error, 'routes': []}
    routes = [r for r in routes if r.get('status') == 'observed']
    if not routes: return {'status': 'error', 'reason': 'the crawl opened no page of the app', 'routes': []}
    # a published site: Lighthouse cannot be held to reading only, so it loads the pages as any visitor, signed out
    rows, shapes = _measured_rows(routes, base, Path(out), measured, None if read_only else storage_state)
    return {'status': 'observed', 'routes': rows, 'templates': len(set(shapes.values())),
            'measured': sum(r['measured'] for r in rows)}


def _measured_rows(routes, base, out, measured, storage_state):
    """(a row per page with its template, Lighthouse on the first page of each distinct template, `measured` at most;
    {path: template})."""
    shapes = templates([r['path'] for r in routes])
    chosen = list(dict.fromkeys(paths[0] for paths in distinct(r['path'] for r in routes).values()))[:measured]
    rows = []
    for route in routes:
        row = {'path': route['path'], 'template': shapes[route['path']], 'depth': route.get('depth'), 'measured': False}
        if route['path'] in chosen: _measure(row, base, out, chosen.index(route['path']), storage_state)
        rows.append(row)
    return rows, shapes
