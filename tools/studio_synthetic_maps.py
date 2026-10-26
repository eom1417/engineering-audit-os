"""The synthetic project's maps (tools/studio_synthetic.py), made by EAOS's own exporters from synthetic records: the code
paths, the journeys and hidden work, the data paths and infrastructure, and a pipeline at scale."""
import json
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from studio_synthetic_base import DOMAINS, ROOT, V2, measure, ratio
from eaos.report.studio import data_paths as data_map  # noqa: E402
from eaos.report.studio import infra as infra_map  # noqa: E402
from eaos.report.studio import paths as paths_section  # noqa: E402
from eaos.report.studio import hidden as hidden_map  # noqa: E402
from eaos.report.studio import user_journeys as journeys_map  # noqa: E402


PAGES, CALLS = 250, 3         # the synthetic paths: a page per component, up to PAGES, each making CALLS calls


def synthetic_paths(comps, layer, modules, card_rows):
    """studio/paths.json for the synthetic project: a page per component (up to PAGES), each through its layers, one
    call in five with no server route (a gap), laid out and clustered by EAOS's own functions; and the timeline of a
    plan whose waves run the cards in order."""
    mods = {}
    for path, comp in modules: mods.setdefault(comp, []).append(path)
    graph, project = _Graph(card_rows), _Project(comps, layer, mods)
    out = [_synthetic_page(graph, project, i) for i in range(min(PAGES, len(comps)))]
    used = Counter(n for p in out for column in p['columns'] for n in column)
    node_rows = [{**graph.nodes[n], 'paths': used[n]} for n in sorted(graph.nodes)]
    named = {n['component'] for n in node_rows}
    parts = {f'src/{layer[c]}/{c}': {'op': ('retain', 'refactor', 'rebuild', 'merge', 'delete')[i % 5], 'target': f'{layer[c]}/{c}', 'layer': layer[c]}
             for i, c in enumerate(comps) if f'src/{layer[c]}/{c}' in named}
    return {**V2, 'lanes': list(paths_section.LANES), 'paths': out, 'nodes': node_rows, 'edges': graph.edges, 'components': parts, 'new': [],
            'overview': paths_section.overview(node_rows, graph.edges), 'counts': _path_counts(out, node_rows, graph.edges),
            'src': {'paths': 'synthetic'}, 'timeline': paths_section.timeline(_synthetic_plan(card_rows), card_rows, 'en')}


class _Graph:
    """The nodes and links of the synthetic paths; a node carries the cards on its file."""

    def __init__(self, card_rows):
        self.nodes, self.edges, self.on_file = {}, [], {}
        for card in card_rows:
            for path in card['paths']: self.on_file.setdefault(path, []).append(card)

    def node(self, nid, lane, label, kind='step', path=None, component=None, **extra):  # limits: parameters -- a node's fields, as eaos/report/studio/paths/graph.py's
        cards = self.on_file.get(path, []) if path else []
        self.nodes.setdefault(nid, {'id': nid, 'lane': lane, 'kind': kind, 'label': label, 'fact': None, 'path': path, 'line': 1 if path else None,
                                    'component': component, 'cards': [c['id'] for c in cards][:20], 'group': extra.pop('group', None),
                                    'steps': sorted({c['milestone'] for c in cards}), 'reason': None, 'detail': None, 'items': [], **extra})
        return nid

    def link(self, a, b, how, path=None):
        self.edges.append({'from': a, 'to': b, 'how': how, 'fact': None, 'path': path, 'line': 1 if path else None})
        return len(self.edges) - 1


@dataclass
class _Project:
    """The synthetic project the paths walk: its components, each one's layer, and each one's files."""
    comps: list
    layer: dict
    mods: dict

    def part(self, comp):
        return f'src/{self.layer[comp]}/{comp}'


def _synthetic_page(graph, project, i):
    """Page i: its screen and component, then CALLS calls through their layers, laid out in columns."""
    mods, part = project.mods, project.part
    comp = project.comps[i]
    domain = comp.rsplit('-', 1)[0]
    route = f'/{domain}/{i}'
    steps = [graph.link(graph.node(f'S:{route}', 'screen', route, path='src/App.tsx', component='src', group=f'/{domain}'),
                        graph.node(f'C:{mods[comp][0]}', 'component', comp, path=mods[comp][0], component=part(comp)), 'route', 'src/App.tsx')]
    for j in range(CALLS): steps += _synthetic_call(graph, project, i, j)
    ids = {graph.edges[k][end] for k in steps for end in ('from', 'to')}
    columns = paths_section.layout(ids, {n: graph.nodes[n]['lane'] for n in ids}, [(graph.edges[k]['from'], graph.edges[k]['to']) for k in steps])
    return {'id': f'{domain}-{i}', 'title': route, 'handler': comp, 'surface': 'page', 'entry': f'S:{route}', 'fact': None, 'flow': None, 'flow_fact': None,
            'steps': steps, 'columns': columns, 'gaps': sum(graph.nodes[n]['kind'] == 'gap' for n in ids), 'capped': 0,
            'unresolved': None, 'reach': 6}


def _synthetic_call(graph, project, i, j):
    """The links of call j of page i: handler, request, then a gap (one call in five) or the endpoint, its service and table."""
    node, link = graph.node, graph.link
    comps, mods, part = project.comps, project.mods, project.part
    comp = comps[i]
    other = comps[(i * 7 + j * 13 + 1) % len(comps)]
    h = node(f'H:{mods[other][1]}#fn{j}', 'handler', f'fn{j}', path=mods[other][1], component=part(other))
    steps = [link(f'C:{mods[comp][0]}', h, ('call', 'imports', 'contains')[j % 3], mods[comp][0])]
    url = f'/api/{other.rsplit("-", 1)[0]}/{(i + j) % 40}'
    a = node(f'A:GET {url}', 'call', f'GET {url}', path=mods[other][1], component=part(other), group=f'/api/{other.rsplit("-", 1)[0]}')
    steps.append(link(h, a, 'request', mods[other][1]))
    if (i + j) % 5 == 0:
        g = node(f'G:endpoint:GET {url}', 'endpoint', f'GET {url}', kind='gap', group=f'/api/{other.rsplit("-", 1)[0]}')
        graph.nodes[g].update(reason='no_server_route')
        return steps + [link(a, g, 'gap')]
    server = comps[(i * 3 + j) % len(comps)]
    e = node(f'E:{mods[server][2]}#handle', 'endpoint', 'handle', path=mods[server][2], component=part(server))
    steps.append(link(a, e, 'route', mods[server][2]))
    m = node(f'M:{part(server)}', 'service', part(server), component=part(server))
    steps.append(link(e, m, 'imports', mods[server][2]))
    t = node(f'T:{server.replace("-", "_")}', 'data', server.replace('-', '_'), kind='table')
    return steps + [link(e, t, 'defines', mods[server][2])]


def _synthetic_plan(card_rows):
    """A plan of twelve steps whose waves run the cards in order, 200 a wave."""
    tasks = [{'id': c['id'], 'paths': c['paths'], 'prerequisites': []} for c in card_rows]
    return {'tasks': tasks, 'milestones': [{'id': f'M{n + 1}', 'goal': f'Step {n + 1}', 'name': f'step-{n + 1}',
                                              'tasks': [c['id'] for c in card_rows if c['milestone'] == f'M{n + 1}']} for n in range(12)],
            'waves': [{'wave': w + 1, 'tasks': [c['id'] for c in card_rows[w * 200:(w + 1) * 200]]} for w in range((len(card_rows) + 199) // 200)]}


def _path_counts(out, node_rows, edges):
    gaps = sum(n['kind'] == 'gap' for n in node_rows)
    calls = sum(n['lane'] == 'call' for n in node_rows)
    count = lambda value, src: measure(value, f'synthetic: {src}')
    return {'paths': count(len(out), 'pages'), 'nodes': count(len(node_rows), 'nodes'), 'links': count(len(edges) - gaps, 'links'),
            'gaps': count(gaps, 'gaps'), 'no_server_route': count(gaps, 'gaps'), 'trace_stopped': count(0, 'none'),
            'component_not_found': count(0, 'none'), 'handler_not_found': count(0, 'none'),
            'unresolved_steps': count(None, 'no flows'), 'calls': count(calls, 'calls'),
            'calls_answered': count(calls - gaps, 'calls'), 'by_call': count(0, 'none'), 'by_imports': count(0, 'none')}


def data_maps(comps, layer, modules, rng):
    """The data paths and infrastructure sections, made by EAOS's own exporters from synthetic records: each module
    either writes one of its component's two tables or reads any table, and one write in twenty lands in another
    component's table, so some tables have several writers."""
    access = _data_access(comps, modules, rng)
    runtime = [{'id': 'FACT-R-1', 'kind': 'deployment_target', 'location': {'path': 'vercel.json'}, 'value': {'kind': 'hosting', 'host': 'Vercel'}},
               {'id': 'FACT-R-2', 'kind': 'ci_step', 'location': {'path': '.github/workflows/ci.yml'}, 'value': {'name': 'test'}}]
    runtime += [{'id': f'FACT-R-H{i}', 'kind': 'integration_target', 'location': {'path': modules[i % len(modules)][0]}, 'value': {'host': f'api.{d}.example-service.io'}}
                for i, d in enumerate(DOMAINS)]
    target = {'reference': 'react-vite-spa-rest',
              'current_components': [{'name': f'src/{layer[c]}/{c}', 'target_component': f'{layer[c]}/{c}', 'paths': []} for c in comps],
              'target_components': [{'name': f'{layer[c]}/{c}'} for c in comps],
              'infrastructure': [{'area': 'hosting', 'present': True, 'decision': 'Keep: declared.', 'tool': None, 'evidence': 'vercel.json'},
                                 {'area': 'observability', 'present': False, 'decision': 'Introduce: errors reported.', 'tool': 'OpenTelemetry', 'evidence': '0'}]}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        (out / 'facts').mkdir()
        (out / 'facts/entrypoints.json').write_text(json.dumps({'facts': access}), encoding='utf-8')
        (out / 'facts/runtime.json').write_text(json.dumps({'facts': runtime}), encoding='utf-8')
        (out / 'target-architecture.json').write_text(json.dumps(target), encoding='utf-8')
        return data_map.data_paths(out, 'en'), infra_map.infra(out, 'en')
def _data_access(comps, modules, rng):
    """The data access facts: each module writes one of its component's two tables (one write in twenty another
    component's), or, one module in three, reads any table."""
    tables = [f'{c.replace("-", "_")}_{k}' for c in comps for k in ('items', 'log')]
    access, n = [], 0
    for i, (path, comp) in enumerate(modules):
        own = [f'{comp.replace("-", "_")}_items', f'{comp.replace("-", "_")}_log']
        calls = [(own[i % 2], ('insert', 'update')[i % 2]) if rng.random() > 0.05 else (tables[rng.randrange(len(tables))], 'update')]
        if i % 3 == 2: calls = [(tables[rng.randrange(len(tables))], 'select')]
        for table, op in calls:
            n += 1
            value = {'client': 'supabase', 'target': table, 'operation': op, 'bounded': None, 'category': 'source'}
            if op != 'select' and rng.random() < 0.6: value.update(keys=sorted(rng.sample(('name', 'state', 'owner', 'due', 'amount'), 2)), keys_partial=False)
            access.append({'id': f'FACT-DA-{n:06d}', 'kind': 'data_access', 'location': {'path': path, 'start_line': 1 + n % 300}, 'value': value})
    return access


def synthetic_pipeline(stages=1000, width=8):
    """studio/pipeline.json for the synthetic project: one product pipeline of `stages` stages in `width` lanes, a router
    every 50 stages with its labelled branches, a fork and its join every 100, a failure lane per router, a side channel,
    a dead stage and an unresolved call, and the ideal and gap views, every id resolving."""
    rows, edges = _pipeline_stages(stages, width)
    routers, gap = _pipeline_routers(rows, stages)
    fans = [{'id': f'p:f{i}', 'pipeline': 'p', 'fork': f'p:s{i}', 'join': f'p:s{i + width}' if i % 200 else None,
             'branches': [f'p:s{j}' for j in range(i + 1, min(i + width, stages))], 'matched': bool(i % 200), 'kind': 'parallel',
             'evidence': rows[i]['entry']} for i in range(0, stages - width, 100)]
    hidden = [{'id': 'p:h0', 'pipeline': 'p', 'kind': 'side_channel', 'channel': 'global', 'name': 'CACHE', 'stages': ['p:s1', 'p:s30'], 'evidence': rows[1]['entry']},
              {'id': 'p:h1', 'pipeline': 'p', 'kind': 'dead_stage', 'channel': None, 'name': 'stage 3', 'stages': ['p:s3'], 'evidence': rows[3]['entry']}]
    unresolved = [{'id': 'p:u0', 'pipeline': 'p', 'stage': 'p:s10', 'call': 'getattr(module, name)()', 'reason': 'dynamic dispatch', 'evidence': rows[10]['entry']}]
    rules = [{**rule, 'broken': sum(g['rule'] == rule['id'] for g in gap)}
             for rule in __import__('json').loads((ROOT / 'eaos/data/pipeline-rules.json').read_text(encoding='utf-8'))]
    count = lambda value, src: measure(value, f'synthetic: {src}')
    return {**V2, 'detected': True, 'confidence': ratio(0.9, 'synthetic'), 'verdict': f'A synthetic pipeline of {stages} stages.',
            'kinds': ['orchestrator'], 'evidence': [rows[0]['entry']],
            'looked_for': [{'kind': 'orchestrator', 'label': 'orchestrator', 'found': 1, 'how': 'synthetic'}],
            'pipelines': [{'id': 'p', 'title': 'synthetic', 'kind': 'orchestrator', 'role': 'product', 'confidence': 0.9, 'entry': rows[0]['entry'],
                           'evidence': [rows[0]['entry']], 'parent': None, 'stages': [r['id'] for r in rows], 'counts': {'stages': stages}}],
            'stages': rows, 'edges': edges, 'routers': routers, 'fans': fans, 'control': [], 'error_lanes': [
                {'id': f'p:e{r["id"]}', 'pipeline': 'p', 'from': r['stage'], 'to': 'failed', 'kind': 'catch', 'condition': None, 'evidence': r['entry']}
                for r in routers], 'hidden': hidden, 'unresolved': unresolved, 'rules': rules, 'views': _pipeline_views(rows, edges, gap),
            'counts': {'stages': count(stages, 'stages'), 'edges': count(len(edges), 'edges'), 'gaps': count(len(gap), 'gap')},
            'src': {'pipeline': 'synthetic'}}


def _site(path, line):
    return {'path': path, 'line': line, 'fact': None, 'text': None}


def _pipeline_stages(stages, width):
    """(stages, edges): a stage per index in `width` lanes, a router every 50, each fed by the stage a lane before."""
    site, rows, edges = _site, [], []
    for i in range(stages):
        layer, order = i // width, i % width
        path = f'pipeline/stage_{i // 50:02d}.py'
        rows.append({'id': f'p:s{i}', 'pipeline': 'p', 'label': f'stage {i}', 'kind': 'router' if i % 50 == 49 else 'stage',
                     'entry': site(path, 1 + 10 * (i % 50)), 'symbol': f'pipeline.stage_{i // 50:02d}.step_{i}',
                     'tools': ['pandas'] if i % 7 == 0 else [], 'inputs': [{'name': f'v{i - 1}', 'kind': 'value', 'shape': 'DataFrame'}] if i else [],
                     'outputs': [{'name': f'v{i}', 'kind': 'value', 'shape': 'DataFrame'}],
                     'side_effects': [{'kind': 'file', 'name': f'out/{i}.parquet', 'path': path, 'line': 2 + 10 * (i % 50), 'fact': None, 'text': None}] if i % 25 == 0 else [],
                     'optional': False, 'marks': ['slow'] if i % 97 == 0 else [], 'sub_pipeline': None, 'coverage': 'measured',
                     'layer': layer, 'order': order, 'cards': [], 'steps': []})
        if i >= width:
            edges.append({'id': f'p:s{i - width}->s{i}', 'pipeline': 'p', 'from': f'p:s{i - width}', 'to': f'p:s{i}', 'kind': 'data',
                          'data': {'names': [f'v{i - width}'], 'shape': 'DataFrame'}, 'matched_by': 'value', 'condition': None,
                          'evidence': site(path, 1 + 10 * (i % 50))})
    return rows, edges


def _pipeline_routers(rows, stages):
    """(routers, gap): a router at every 50th stage with three labelled branches; one in two misses a kind (a P4 gap)."""
    routers, gap = [], []
    for i in range(49, stages, 50):
        targets = [j for j in (i + 1, i + 2, i + 3) if j < stages]
        routers.append({'id': f'p:r{i}', 'pipeline': 'p', 'stage': f'p:s{i}', 'kind': 'dict_dispatch', 'on': 'record.kind',
                        'entry': rows[i]['entry'], 'branches': [{'condition': f'kind == {k}', 'to': f'p:s{j}', 'evidence': rows[i]['entry']}
                                                                 for k, j in zip(('a', 'b', 'c'), targets)],
                        'total': i % 100 != 49, 'default': None, 'unhandled': [] if i % 100 != 49 else ['d']})
        if i % 100 == 49:
            gap.append({'id': f'gap:P4:r{i}', 'rule': 'P4', 'pipeline': 'p', 'subject': f'p:r{i}', 'subject_kind': 'router', 'operation': 'refactor',
                        'detail': 'kind d has no branch', 'evidence': rows[i]['entry'], 'card': None, 'step': None})
    return routers, gap


def _pipeline_views(rows, edges, gap):
    """The pipeline today, its ideal by the rules (every stage and edge retained), and the gap between them."""
    return {'current': {'stages': [r['id'] for r in rows], 'edges': [e['id'] for e in edges]},
            'ideal': {'stages': [{'id': r['id'], 'op': 'retain', 'label': r['label'], 'pipeline': 'p'} for r in rows],
                      'edges': [{'from': e['from'], 'to': e['to'], 'op': 'retain', 'pipeline': 'p'} for e in edges], 'made_by': 'rules'},
            'gap': gap}


def maps(comps, layer, card_rows):
    """journeys and hidden for the synthetic project, built by the exporter's own code from records like a scan's: one
    screen per component under an /app layout, a sidebar menu to the first screen of each domain, each screen linking
    to the next of its domain, every tenth a create form, and unseen work (writes, outside calls, dead code) behind them."""
    files = {c: f'src/pages/{c}.tsx' for c in comps}
    pages, links, imports, names = _screen_records(comps, layer, files)
    owners = {f: {'name': f'src/pages/{layer[c]}', 'relation': ('retain', 'modify', 'rebuild', 'delete')[i % 4], 'target_component': layer[c]}
              for i, (c, f) in enumerate(files.items())}
    records = {'pages': pages, 'links': links, 'imports': imports, 'names': names, 'defined': {}, 'owners': owners, 'target_of': {},
               'feature_of': {}, 'shots': {}, 'dead': set(), 'has_target': True}
    journeys = journeys_map.from_records(records)
    items = [{'id': f'writes:http:/{layer[c]}', 'group': 'writes', 'kind': 'http', 'name': f'/{layer[c]}', 'file': f'src/api/{layer[c]}.ts',
              'line': 3, 'fact': f'FACT-write-{layer[c]}', 'files': [f'src/api/{layer[c]}.ts'], 'detail': None} for c in comps[:len(set(layer.values()))]]
    items += [{'id': f'dead:unreachable-module:{i}', 'group': 'dead', 'kind': 'unreachable-module', 'name': f'src/old/m{i}.ts', 'file': f'src/old/m{i}.ts',
               'line': 1, 'fact': f'FACT-dead-{i}', 'files': [f'src/old/m{i}.ts'], 'detail': None} for i in range(300)]
    items.append({'id': 'outside:api.example.com', 'group': 'outside', 'kind': 'host', 'name': 'api.example.com', 'file': 'src/old/client.ts',
                  'line': 1, 'fact': 'FACT-host', 'files': ['src/old/client.ts'], 'detail': None})
    reach = {s['id']: ({s['file'], *imports.get(s['file'], [])} if s['file'] else set()) for s in journeys['screens'] if s['kind'] == 'page'}
    hidden = hidden_map.assemble(items, journeys, reach, {f: o['name'] for f, o in owners.items()}, card_rows[:50])
    return {'journeys': {**V2, **journeys}, 'hidden': {**V2, **hidden}}


def _screen_records(comps, layer, files):
    """(pages, links, imports, names) of the synthetic screens: a page per component under /app, a menu entry to each
    domain's first, a link to the next of its domain, every tenth a create form, and a broken link now and then."""
    router, pages, links, imports, names = 'src/App.tsx', [], [], {}, {}
    pages.append({'route': '/', 'declared': '/', 'handler': 'Root', 'router': router, 'line': 1, 'fact': 'FACT-route-root', 'framework': 'react_router'})
    pages.append({'route': '/app/*', 'declared': '/app/*', 'handler': 'Shell', 'router': router, 'line': 2, 'fact': 'FACT-route-shell', 'framework': 'react_router'})
    links.append({'target': '/app', 'via': 'redirect', 'file': router, 'line': 1, 'symbol': 'Root', 'fact': 'FACT-nav-root', 'dynamic': False, 'relative': False})
    pages.append({'route': '/app', 'declared': '/', 'handler': 'Home', 'router': router, 'line': 3, 'fact': 'FACT-route-home', 'framework': 'react_router'})
    names[(router, 'Home')] = ['./pages/Home']
    imports[router] = ['src/pages/Home.tsx', 'src/Sidebar.tsx', *files.values()]
    imports['src/Sidebar.tsx'] = ['src/nav/menu.ts']
    imports['src/pages/Home.tsx'] = []
    first = {}
    for i, c in enumerate(comps):
        handler = 'P' + c.replace('-', '_')
        domain = c.rsplit('-', 1)[0]
        pages.append({'route': f'/app/{domain}/{c}', 'declared': f'/{domain}/{c}', 'handler': handler, 'router': router, 'line': 10 + i, 'fact': f'FACT-route-{i}', 'framework': 'react_router'})
        names[(router, handler)] = [f'./pages/{c}']
        imports[files[c]] = [f'src/api/{layer[c]}.ts']
        if domain not in first:
            first[domain] = c
            links.append({'target': f'/app/{domain}/{c}', 'via': 'menu', 'file': 'src/nav/menu.ts', 'line': len(first), 'symbol': None, 'fact': f'FACT-menu-{i}', 'dynamic': False, 'relative': False})
        nxt = comps[i + len(DOMAINS)] if i + len(DOMAINS) < len(comps) else None
        if nxt: links.append({'target': f'/app/{domain}/{nxt}', 'via': 'link', 'file': files[c], 'line': 20, 'symbol': handler, 'fact': f'FACT-nav-{i}', 'dynamic': False, 'relative': False})
        if i % 10 == 0:
            pages.append({'route': f'/app/{domain}/{c}/new', 'declared': f'/{domain}/{c}/new', 'handler': 'Create' + handler, 'router': router, 'line': 5000 + i, 'fact': f'FACT-route-new-{i}', 'framework': 'react_router'})
            names[(router, 'Create' + handler)] = [f'./pages/{c}New']
            imports[router].append(f'src/pages/{c}New.tsx')
            imports[f'src/pages/{c}New.tsx'] = [f'src/api/{layer[c]}.ts']
            links.append({'target': f'/app/{domain}/{c}/new', 'via': 'link', 'file': files[c], 'line': 30, 'symbol': handler, 'fact': f'FACT-new-{i}', 'dynamic': False, 'relative': False})
        if i % 97 == 5: links.append({'target': f'/app/{domain}/{c}/missing', 'via': 'navigate', 'file': files[c], 'line': 40, 'symbol': handler, 'fact': f'FACT-broken-{i}', 'dynamic': False, 'relative': False})
    return pages, links, imports, names
