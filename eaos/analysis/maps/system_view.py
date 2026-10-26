"""The system map's drawing data (eaos/analysis/maps/system.py finds its nodes and links): every column capped (MAX_*),
the links drawn, and for each node every node it reaches or is reached from.
"""
from collections import defaultdict

from .system_paths import METHODS

MAX_PAGES, MAX_CALLERS, MAX_APIS, MAX_HANDLERS, MAX_MODULES, MAX_DATA = 80, 24, 160, 120, 30, 60


def assemble(client, server, wiring, r):
    """Cap every column, then the links drawn and, for each node, every node it reaches or is reached from. `client`:
    (pages, shared callers, APIs); `server`: (handlers, modules, tables, services); `wiring`: (links, uses)."""
    (pages, shared, apis), (links, uses) = client, wiring
    if not pages and not apis: return None
    cols, capped = _columns(client, server, wiring)
    view = {'cols': cols, 'links': links, 'uses': uses, 'capped': capped, 'root': r['root'],
            'kept_apis': {a['id'] for a in cols['apis']},
            'ids': {x['id'] for name in ('pages', 'callers', 'apis', 'handlers', 'modules', 'data') for x in cols[name]}}
    view['edges'], view['holds'] = _edges(view)
    # what each node reaches (down) and is reached from (up): the page's highlight
    view['related'] = _related(view, _Reach(cols, links, shared))
    return _drawn(view)


def _cap(items, limit, name, weight, capped):
    items = sorted(items, key=weight)
    capped[name] = max(len(items) - limit, 0)
    return items[:limit]


def _columns(client, server, wiring):
    """Every column capped and ordered, and how many each cap left out."""
    (pages, shared, apis), (handlers, modules, tables, services), (links, uses) = client, server, wiring
    capped = {}
    api_list = _cap(apis.values(), MAX_APIS, 'apis', lambda a: (-len(a['callers']) - 2 * bool(a['handlers']), a['group'], a['path'], a['method']), capped)
    api_list.sort(key=lambda a: (a['group'], a['path'], METHODS.index(a['method']) if a['method'] in METHODS else 9))
    page_list = _cap(pages, MAX_PAGES, 'pages', lambda p: (-len(links[p['id']] | {x for c in uses[p['id']] for x in links[c]}), p['route']), capped)
    page_list.sort(key=lambda p: (p['route'] == '*', p['route'], p['component']))
    caller_list = _cap(shared.values(), MAX_CALLERS, 'callers', lambda c: (-len(links[c['id']]), c['path']), capped)
    caller_list.sort(key=lambda c: c['path'])
    return {'apis': api_list, 'pages': page_list, 'callers': caller_list,
            'handlers': _cap(handlers.values(), MAX_HANDLERS, 'handlers', lambda h: (-len(h['apis']), h['path']), capped),
            'modules': _cap(modules.values(), MAX_MODULES, 'modules', lambda m: (-len(m['handlers']), m['name']), capped),
            'data': _cap(list(tables.values()) + list(services.values()), MAX_DATA, 'data', lambda d: (d['id'][0] == 'S', d['name']), capped)}, capped


def _handler_edges(h, module_of, holds):
    """A handler's links to the parts it uses and the data it reaches; data its own part holds is linked from that part."""
    edges = [(h['id'], 'M:' + m, n, 'use') for m, n in sorted(h['modules'].items())]
    for d, m in h['via'].items():
        if m and 'M:' + m in module_of and m in h['modules']: holds['M:' + m].add(d)
        else: edges.append((h['id'], d, 1, 'data'))
    return edges


def _call_edges(cols, links, uses, kept_apis):
    """The client side's links, (from, to, weight, kind): page or caller -> API, page -> shared caller, API -> handler."""
    sources = [p['id'] for p in cols['pages']] + [c['id'] for c in cols['callers']]
    return ([(s, a, 1, 'call') for s in sources for a in sorted(links[s]) if a in kept_apis]
            + [(p['id'], c, 1, 'uses') for p in cols['pages'] for c in sorted(uses[p['id']])] + _answer_edges(cols['apis']))


def _answer_edges(apis):
    """API -> handler: an answer when the handler's function is known, else a guess."""
    return [(a['id'], 'H:' + h['path'], 1, 'answer' if h['function'] else 'guess') for a in apis for h in a['handlers']]


def _edges(view):
    """(the links drawn, module id -> data ids its files hold or use)."""
    cols = view['cols']
    edges = _call_edges(cols, view['links'], view['uses'], view['kept_apis'])
    module_of = {m['id']: m for m in cols['modules']}
    holds = defaultdict(set)
    for h in cols['handlers']: edges += _handler_edges(h, module_of, holds)
    for m, ds in holds.items(): edges += [(m, d, 1, 'data') for d in sorted(ds)]
    ids = view['ids']
    return sorted({(a, b): (a, b, n, k) for a, b, n, k in edges if a in ids and b in ids}.values()), holds


class _Reach:
    """What a node reaches below it and is reached from above it, among the kept APIs and handlers."""

    def __init__(self, cols, links, shared):
        self.api_of = {a['id']: a for a in cols['apis']}
        self.handler_of = {h['id']: h for h in cols['handlers']}
        self.shared = shared
        self.callers_of = defaultdict(set)
        for source, called in links.items():
            for a in called: self.callers_of[a].add(source)

    def below_handler(self, hid):
        h = self.handler_of[hid]
        return {'M:' + m for m in h['modules']} | {'T:' + t for t in h['tables']} | {'S:' + s for s in h['services']}

    def below_api(self, a):
        out = set()
        for hid in ('H:' + h['path'] for h in self.api_of[a]['handlers']):
            if hid in self.handler_of: out |= {hid} | self.below_handler(hid)
        return out

    def above_api(self, a):
        out = set(self.callers_of[a])
        for c in list(out):
            if c.startswith('C:') and c[2:] in self.shared: out |= set(self.shared[c[2:]]['pages'])
        return out

    def below(self, apis):
        return {x for a in apis if a in self.api_of for x in self.below_api(a)}

    def above(self, apis):
        return {x for a in apis if a in self.api_of for x in {a} | self.above_api(a)}


def _page_reach(p, links, uses):
    reach = set(links[p['id']]) | set(uses[p['id']])
    for c in uses[p['id']]: reach |= links[c]
    return reach


def _related(view, reach):
    """For each node, every node it reaches or is reached from, among the nodes drawn."""
    cols, links, uses, holds = view['cols'], view['links'], view['uses'], view['holds']
    related = {}
    for p in cols['pages']:
        down = _page_reach(p, links, uses)
        related[p['id']] = {p['id']} | down | reach.below(down)
    for c in cols['callers']:
        related[c['id']] = {c['id']} | set(c['pages']) | links[c['id']] | reach.below(links[c['id']])
    for a in cols['apis']:
        related[a['id']] = {a['id']} | reach.above_api(a['id']) | reach.below_api(a['id'])
    for h in cols['handlers']:
        related[h['id']] = {h['id']} | reach.below_handler(h['id']) | reach.above(h['apis'])
    for m in cols['modules']: related[m['id']] = _module_related(m, holds, reach)
    for d in cols['data']:
        related[d['id']] = _data_related(d, cols['handlers'], holds, reach)
    return {k: sorted(v & view['ids']) for k, v in related.items()}


def _module_related(m, holds, reach):
    """A part, the data it holds, its kept handlers and what reaches them."""
    hs = [x for x in m['handlers'] if x in reach.handler_of]
    return {m['id']} | holds.get(m['id'], set()) | {x for h in hs for x in {h} | reach.above(reach.handler_of[h]['apis'])}


def _data_related(d, handlers, holds, reach):
    hs = [h for h in handlers if d['id'] in reach.below_handler(h['id'])]
    return {d['id']} | {m for m, ds in holds.items() if d['id'] in ds} | {x for h in hs for x in {h['id']} | reach.above(h['apis'])}


def _common(paths):
    """The folder every path shares, with a trailing slash; '' when none."""
    dirs = [p.split('/')[:-1] for p in paths]
    head = []
    for parts in zip(*dirs) if dirs else ():
        if len(set(parts)) != 1: break
        head.append(parts[0])
    return '/'.join(head) + '/' if head else ''


def _short(p, prefix):
    return p[len(prefix):] if prefix and p.startswith(prefix) and p != prefix else p


def _module_short(name, parts):
    if parts and (name + '/').startswith(parts) and name + '/' != parts: return (name + '/')[len(parts):].rstrip('/')
    return name.rsplit('/', 1)[-1]


def _drawn_handlers(handlers, kept_apis, prefix):
    return [{'id': h['id'], 'path': h['path'], 'short': _short(h['path'], prefix), 'apis': [a for a in h['apis'] if a in kept_apis],
             'modules': sorted(h['modules']), 'tables': h['tables'], 'services': h['services']} for h in handlers]


def _features(pages):
    """Each feature with the drawn pages that belong to it, by name."""
    features = defaultdict(list)
    for p in pages:
        for f in p['features']: features[f].append(p['id'])
    return [{'name': f, 'pages': ps} for f, ps in sorted(features.items())]


def _api_counts(apis):
    """The APIs no handler answers (an outside URL aside), those matched by a guess, and the ways they were matched."""
    return {'unknown': sum(1 for a in apis if not a['handlers'] and '://' not in a['path']),
            'guessed': sum(1 for a in apis if a['handlers'] and not a['exact']),
            'how': sorted({h['how'] for a in apis for h in a['handlers']})}


def _drawn_pages(pages, links, uses, ids, kept_apis):
    return [{k: v for k, v in p.items() if k != 'reach'} | {'calls': sorted(links[p['id']] & kept_apis), 'shared': sorted(uses[p['id']] & ids)}
            for p in pages]


def _drawn_callers(callers, links, kept_apis, prefix):
    return [dict(c, calls=sorted(links[c['id']] & kept_apis), short=_short(c['path'], prefix)) for c in callers]


def _drawn_apis(apis):
    return [{k: (sorted(v) if isinstance(v, set) else v) for k, v in a.items()} for a in apis]


def _drawn(view):
    """The system map as the report and the Studio read it."""
    cols, links, uses, ids, kept_apis, root = view['cols'], view['links'], view['uses'], view['ids'], view['kept_apis'], view['root']
    server, client = _common([h['path'] for h in cols['handlers']]), _common([c['path'] for c in cols['callers']])
    parts = _common([m['name'] + '/' for m in cols['modules']]) if len(cols['modules']) > 1 else ''
    return {'pages': _drawn_pages(cols['pages'], links, uses, ids, kept_apis),
            'callers': _drawn_callers(cols['callers'], links, kept_apis, client or root),
            'apis': _drawn_apis(cols['apis']),
            'handlers': _drawn_handlers(cols['handlers'], kept_apis, server or root),
            'modules': [dict(m, short=_module_short(m['name'], parts)) for m in cols['modules']], 'data': cols['data'],
            'features': _features(cols['pages']),
            'edges': [{'from': a, 'to': b, 'n': n, 'kind': k} for a, b, n, k in view['edges']], 'related': view['related'], 'capped': view['capped'],
            **_api_counts(cols['apis'])}
