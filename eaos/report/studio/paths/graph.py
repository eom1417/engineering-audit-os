"""The graph of every code path: each node and link stored once, and the builder that walks a page or a server entry
through its lanes, from the records (eaos/report/studio/paths/records.py) to a gap where they stop."""
from collections import defaultdict
from pathlib import Path

from ....analysis.maps import system as sm
from .records import line_number

LANES = ('screen', 'component', 'handler', 'call', 'endpoint', 'service', 'data')
IMPORT_STEPS = 2          # a component reaches the files that make its calls through at most two imports
SERVER_STEPS = 3          # a handler reaches the parts behind it through at most three imports
MAX_CALLS = 60            # calls drawn per path; the rest are counted in the path's `capped`
MAX_ITEMS = 12            # unresolved calls listed on a trace gap


def _measure(value, src):
    return {'value': value, 'src': src, 'unit': 'count'}


def _fact_id(fact):
    return fact.get('id') if isinstance(fact, dict) and isinstance(fact.get('id'), str) else None


class _Graph:
    """The nodes and links of every path, each stored once; a path lists the links it walks, in order."""

    def __init__(self, owner, cards_of):
        self.nodes, self.edges, self.index = {}, [], {}
        self.owner, self.cards_of = owner, cards_of

    def node(self, nid, lane, label, kind='step', **more):
        """A node, once. `more`, by name: path, line, fact, part (the part of today owning it) and any extra field."""
        if nid not in self.nodes:
            path, line, fact, part = (more.pop(key, None) for key in ('path', 'line', 'fact', 'part'))
            extra = more
            cards, steps = self.cards_of(path) if path and kind != 'gap' else ([], [])
            self.nodes[nid] = {'id': nid, 'lane': lane, 'kind': kind, 'label': str(label)[:200], 'path': path or None,
                               'line': line_number(line), 'fact': _fact_id(fact),
                               'component': None if kind == 'gap' else part or (self.owner(path) if path else None),
                               'cards': cards, 'steps': steps, 'reason': None, 'detail': None, 'items': [], 'group': None, **extra}
        return nid

    def link(self, a, b, how, fact=None, path=None, line=None):
        key = (a, b, how)
        if key not in self.index:
            self.index[key] = len(self.edges)
            self.edges.append({'from': a, 'to': b, 'how': how, 'fact': _fact_id(fact), 'path': path or None, 'line': line_number(line)})
        return self.index[key]

    def gap(self, nid, lane, reason, label, detail=None, items=()):
        self.node(nid, lane, label, kind='gap')
        self.nodes[nid].update(reason=reason, detail=detail, items=list(items)[:MAX_ITEMS])
        return nid


class _Builder:
    def __init__(self, r, owner, cards_of):
        self.r, self.owner, self.g = r, owner, _Graph(owner, cards_of)
        self.behind = {}            # endpoint node -> the links behind it, walked once and reused by every path

    def trace_gap(self, pid, lane, origin, flow, steps):
        value = (flow or {}).get('value') or {}
        stops = _stops(value)
        count = value.get('unresolved_steps')
        if not stops and not count: return 0
        total = count if isinstance(count, int) else len(stops)
        items = [{'callee': str(s.get('callee') or ''), 'path': s.get('from_path'), 'line': line_number(s.get('line')),
                  'resolution': s.get('resolution')} for s in stops]
        gid = self.g.gap(f'G:trace:{pid}', lane, 'trace_stopped', value.get('flow_id') or pid, detail=str(total), items=items)
        where = flow.get('location') or {}
        steps.append(self.g.link(origin, gid, 'trace', flow, where.get('path'), where.get('start_line')))
        return total

    def server_side(self, origin, start, flow):
        """The links behind a server-side handler file: the parts it calls or imports, the tables and services."""
        if origin in self.behind: return self.behind[origin]
        imports = self.r['imports']
        called = _called(flow, start)
        steps = self._part_links(origin, start, flow, called)
        near = {start} | {to for to, _ in called} | sm._reach(start, imports, SERVER_STEPS - 1)
        steps += self._table_links(origin, near)
        steps += self._service_links(origin, near | sm._reach(start, imports, SERVER_STEPS + 1))
        self.behind[origin] = steps
        return steps

    def _part_links(self, origin, start, flow, called):
        """A link to each other part the handler calls (traced), then to each it imports, once per part."""
        g, home, seen, steps = self.g, self.owner(start), set(), []
        for to, step in called:
            part = self.owner(to)
            if not part or part == home or part in seen: continue
            seen.add(part)
            steps.append(g.link(origin, g.node(f'M:{part}', 'service', part, part=part), 'call', flow, step.get('from_path'), step.get('line')))
        for to in sorted(sm._reach(start, self.r['imports'], SERVER_STEPS) - {start}):
            part = self.owner(to)
            if not part or part == home or part in seen or sm.is_test(to): continue
            seen.add(part)
            steps.append(g.link(origin, g.node(f'M:{part}', 'service', part, part=part), 'imports', None, start, None))
        return steps

    def _table_links(self, origin, near):
        g, steps = self.g, []
        for file in sorted(near):
            for name, fact in self.r['tables'].get(file, ()):
                where, line = sm._path(fact), (fact.get('location') or {}).get('start_line')
                steps.append(g.link(origin, g.node(f'T:{name}', 'data', name, kind='table', path=where, line=line, fact=fact),
                                    'defines', fact, where, line))
        return steps

    def _service_links(self, origin, files_near):
        """A link to each outside service or store a package of the nearby files talks to."""
        services = defaultdict(set)
        for file in sorted(files_near):
            for package in self.r['packages'].get(file, ()):
                if package in sm.SERVICES: services[sm.SERVICES[package]].add(file)
        steps = []
        for (kind, en, ar), files in sorted(services.items()):
            nid = self.g.node(f'X:{en}', 'data', en, kind='store' if kind == 'storage' else 'external', ar=ar)
            steps.append(self.g.link(origin, nid, 'package', None, sorted(files)[0], None))
        return steps

    def onward(self, aid, call):
        """The links after a call: its endpoint and what stands behind it, its table, its outside service, or a gap."""
        g, steps = self.g, []
        if call['table']:
            steps.append(g.link(aid, g.node(f"T:{call['table']}", 'data', call['table'], kind='table'), 'client',
                                call['fact'], call['path'], call['line']))
            return steps
        if '://' in call['url']: return [self._external(aid, call)]
        found, exact = sm.find_handlers(call['method'], call['url'], self.r['routes'], self.r['methods'])
        if not found:
            gid = g.gap(f"G:endpoint:{call['id'][2:]}", 'endpoint', 'no_server_route', call['label'])
            g.nodes[gid]['group'] = call['group']
            return [g.link(aid, gid, 'gap')]
        for handler in found: steps += self._endpoint(aid, call, handler, exact)
        return steps

    def _external(self, aid, call):
        """The link from a call to the outside host its URL names."""
        host = call['url'].split('/')[2] if call['url'].count('/') >= 2 else call['url']
        return self.g.link(aid, self.g.node(f'X:{host}', 'data', host, kind='external'), 'external', call['fact'], call['path'], call['line'])

    def _endpoint(self, aid, call, handler, exact):
        """The link from a call to one server handler that answers it, and what stands behind that handler."""
        g, (file, function, how) = self.g, handler
        route = next((x for x in self.r['routes'] if x['file'] == file and sm.same_route(x['route'], call['url'])), None) or {}
        eid = g.node(f"E:{file}#{function or ''}", 'endpoint', function or Path(file).name, path=file,
                     line=route.get('fact', {}).get('location', {}).get('start_line'), fact=route.get('fact'))
        steps = [g.link(aid, eid, 'route' if how == 'entry point' and exact else 'file_route', route.get('fact'), file, g.nodes[eid]['line'])]
        flow = self.r['flow_of'].get((file, route.get('handler') or function))
        return steps + self.server_side(eid, file, flow)

    def page(self, pid, entry):
        g, r = self.g, self.r
        sid = self._screen(entry)
        steps, capped, unresolved = [], 0, None
        flow = r['flows'].get((entry['path'], entry['handler'], entry['route']))
        comp = sm.component_file({'route': entry['route'], 'component': str(entry['handler'] or ''), 'router': entry['path']},
                                 r['flow_list'], r['names'], r['imports'])
        if comp == entry['path']: comp = None
        if not comp:
            steps.append(g.link(sid, g.gap(f'G:component:{pid}', 'component', 'component_not_found', entry['handler'] or entry['route']),
                                'route', entry['fact'], entry['path'], entry['line']))
            return sid, steps, flow, 0, None
        cid = g.node(f'C:{comp}', 'component', entry['handler'] or Path(comp).stem, path=comp)
        steps.append(g.link(sid, cid, 'route', entry['fact'], entry['path'], entry['line']))
        traced = _traced_files(flow)
        calls = self._calls_near(comp, traced)
        capped = max(len(calls) - MAX_CALLS, 0)
        for file, call in calls[:MAX_CALLS]: steps += self._call_links(cid, comp, (file, call), traced, flow)
        unresolved = self.trace_gap(pid, 'handler', cid, flow, steps) if flow else None
        return sid, steps, flow, capped, unresolved

    def _screen(self, entry):
        """A page's screen node."""
        return self.g.node(f"S:{entry['route']} {entry['handler'] or ''}".rstrip(), 'screen', entry['route'] or '/', path=entry['path'],
                           line=entry['line'], fact=entry['fact'], group=sm.api_group(entry['route'] or '/'))

    def _calls_near(self, comp, traced):
        """[(file, call)] of the calls in the component's file, the files its flow touches and those it imports, in that
        order, never in a test file."""
        reach = sm._reach(comp, self.r['imports'], IMPORT_STEPS)
        files = sorted({comp} | set(traced) | reach, key=lambda f: (f != comp, f not in traced, f))
        return [(file, call) for file in files if not sm.is_test(file) for call in self.r['calls'].get(file, ())]

    def _call_links(self, cid, comp, found, traced, flow):
        """The component to the handler holding a call, the handler to the call, and what the call reaches."""
        g, r = self.g, self.r
        file, call = found
        how = 'contains' if file == comp else 'call' if file in traced else 'imports'
        hid = g.node(f"H:{file}#{call['function'] or call['line']}", 'handler', call['function'] or Path(file).name, path=file,
                     line=next((f['start'] for f in r['functions'].get(file, ()) if f['name'] == call['function']), call['line']))
        if how == 'call':
            step = traced[file]
            steps = [g.link(cid, hid, how, flow, step.get('from_path'), step.get('line'))]
        else:
            steps = [g.link(cid, hid, how, None, comp, None)]
        aid = g.node(call['id'], 'call', call['label'], path=call['path'], line=call['line'], fact=call['fact'], group=call['group'])
        steps.append(g.link(hid, aid, 'request', call['fact'], call['path'], call['line']))
        return steps + self.onward(aid, call)

    def server(self, pid, entry):
        g, r = self.g, self.r
        label = f"{entry['method']} {entry['route']}" if entry['method'] else entry['route'] or entry['handler']
        eid = g.node(f"E:{entry['path']}#{entry['handler']}", 'endpoint', label, path=entry['path'], line=entry['line'], fact=entry['fact'])
        flow = r['flows'].get((entry['path'], entry['handler'], entry['route']))
        steps = []
        if not flow:
            steps.append(g.link(eid, g.gap(f'G:handler:{pid}', 'service', 'handler_not_found', entry['handler']), 'gap'))
            return eid, steps, None, 0, None
        first = next((s.get('from_path') for s in (flow.get('value') or {}).get('steps') or [] if isinstance(s, dict)), None)
        steps += self.server_side(eid, first or entry['path'], flow)
        unresolved = self.trace_gap(pid, 'service', eid, flow, steps)
        return eid, steps, flow, 0, unresolved


def _called(flow, start):
    """[(file, step)] the traced flow calls into, other than the handler's own file and test files."""
    called = []
    for step in ((flow or {}).get('value') or {}).get('steps') or []:
        to = step.get('to_path') if isinstance(step, dict) else None
        if step.get('resolution') in ('local', 'imported') and to and to != start and not sm.is_test(to): called.append((to, step))
    return called


def _stops(value):
    """The steps of a flow its trace could not resolve (unresolved or ambiguous)."""
    return [s for s in value.get('steps') or [] if isinstance(s, dict) and s.get('resolution') in ('unresolved', 'ambiguous')]


def _traced_files(flow):
    """{file: the first traced step touching it}."""
    traced = {}
    for step in ((flow or {}).get('value') or {}).get('steps') or []:
        if not isinstance(step, dict): continue
        for file in (step.get('to_path'), step.get('from_path')):
            if file and file not in traced: traced[file] = step
    return traced
