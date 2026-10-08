"""A synthetic Studio data folder at scale: every section of contracts v1 and v2, valid, linked, and deterministic.

The Studio is built and gated against real reports, but none of them is large. This writes the folder EAOS would
write for a project of N cards and M components (default 5,000 and 1,000, STUDIO-COMPLETE.md), so the pages, the
search and the screen gates are tested at the scale a company project reaches. Every id a section cites exists in
the section it points to: a card's evidence, a function's callers, a gap's operations, an operation's step.

    python tools/studio_synthetic.py --out DIR [--cards 5000] [--components 1000] [--seed 7]

DIR then holds <section>.json, its .js twin and manifest.json, exactly as eaos/studio/export.py lays them out; give it
to the screen gate with `python tools/studio_gates.py --studio --data DIR`.
"""
import argparse
import hashlib
import json
import random
from collections import Counter
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from eaos import artifact_contracts  # noqa: E402
from eaos.studio import coverage as coverage_section  # noqa: E402
from eaos.studio import data_paths as data_map  # noqa: E402
from eaos.studio import infra as infra_map  # noqa: E402
from eaos.studio import export  # noqa: E402
from eaos.studio import paths as paths_section  # noqa: E402
from eaos.studio import hidden as hidden_map  # noqa: E402
from eaos.studio import journeys as journeys_map  # noqa: E402

DOMAINS = ('work-orders', 'assets', 'vehicles', 'drivers', 'invoices', 'payments', 'inventory', 'reports', 'auth', 'users',
           'billing', 'routes', 'maintenance', 'fuel', 'alerts', 'audit', 'settings', 'notifications', 'contracts', 'suppliers')
LAYERS = ('pages', 'features', 'shared', 'data-access', 'config')
SEVERITIES = ('critical', 'high', 'medium', 'low', 'info')
KINDS = ('complexity', 'dead_code', 'literal_duplication', 'secret', 'missing_rls', 'layer_violation', 'cycle', 'unused_dependency')
OPERATIONS = ('retain', 'refactor', 'rebuild', 'merge', 'delete', 'new')
STATES = ('open', 'open', 'open', 'in_batch', 'on_branch', 'done', 'resolved', 'skipped')
TASK_STATE = export.TASK_STATE
HEAD = {'schema_version': 1, 'contract': export.CONTRACT}
V2 = {**HEAD, 'revision': export.REVISION}
WHEN = '2026-10-08T09:00:00+00:00'
WHY = {'complexity': ('دالة معقّدة يصعب اختبارها ويكثر فيها الخطأ عند التعديل.', 'A complex function is hard to test and easy to break when changed.'),
       'dead_code': ('كود لا يشغّله أحد يبقى يُقرأ ويُصان.', 'Code nobody runs is still read and maintained.'),
       'literal_duplication': ('نسختان من القاعدة نفسها تتباعدان مع الوقت.', 'Two copies of one rule drift apart over time.'),
       'secret': ('مفتاح سرّي في الكود يصل إلى كل من يقرأ المستودع.', 'A secret in the code reaches everyone who reads the repository.'),
       'missing_rls': ('جدول بلا أمان صفوف يقرؤه أي مستخدم.', 'A table without row security is readable by any user.'),
       'layer_violation': ('طبقة تتجاوز أخرى فيصعب تغيير أيّ منهما وحدها.', 'A layer that skips another makes either hard to change alone.'),
       'cycle': ('حلقة استيراد تمنع فصل الوحدتين.', 'An import cycle keeps the two modules from being separated.'),
       'unused_dependency': ('مكتبة لا تُستعمل تكبّر البناء وتزيد الثغرات المحتملة.', 'An unused library grows the build and the attack surface.')}


def measure(value, src, unit='count'):
    return {'value': value, 'src': src, 'unit': unit}


def ratio(value, src):
    return {'value': value, 'src': src}


def synthetic_paths(comps, layer, modules, card_rows, pages=250, calls=3):
    """studio/paths.json for the synthetic project: a page per component (up to `pages`), each through its layers, one
    call in five with no server route (a gap), laid out and clustered by EAOS's own functions; and the timeline of a
    plan whose waves run the cards in order."""
    mods = {}
    for path, comp in modules: mods.setdefault(comp, []).append(path)
    on_file = {}
    for card in card_rows:
        for path in card['paths']: on_file.setdefault(path, []).append(card)
    nodes, edges, out = {}, [], []

    def node(nid, lane, label, kind='step', path=None, component=None, **extra):
        cards = on_file.get(path, []) if path else []
        nodes.setdefault(nid, {'id': nid, 'lane': lane, 'kind': kind, 'label': label, 'fact': None, 'path': path, 'line': 1 if path else None,
                               'component': component, 'cards': [c['id'] for c in cards][:20], 'group': extra.pop('group', None),
                               'steps': sorted({c['milestone'] for c in cards}), 'reason': None, 'detail': None, 'items': [], **extra})
        return nid

    def link(a, b, how, path=None):
        edges.append({'from': a, 'to': b, 'how': how, 'fact': None, 'path': path, 'line': 1 if path else None})
        return len(edges) - 1
    for i, comp in enumerate(comps[:pages]):
        domain = comp.rsplit('-', 1)[0]
        route = f'/{domain}/{i}'
        part = lambda c: f'src/{layer[c]}/{c}'
        steps = [link(node(f'S:{route}', 'screen', route, path='src/App.tsx', component='src', group=f'/{domain}'),
                      node(f'C:{mods[comp][0]}', 'component', comp, path=mods[comp][0], component=part(comp)), 'route', 'src/App.tsx')]
        for j in range(calls):
            other = comps[(i * 7 + j * 13 + 1) % len(comps)]
            h = node(f'H:{mods[other][1]}#fn{j}', 'handler', f'fn{j}', path=mods[other][1], component=part(other))
            steps.append(link(steps and f'C:{mods[comp][0]}', h, ('call', 'imports', 'contains')[j % 3], mods[comp][0]))
            url = f'/api/{other.rsplit("-", 1)[0]}/{(i + j) % 40}'
            a = node(f'A:GET {url}', 'call', f'GET {url}', path=mods[other][1], component=part(other), group=f'/api/{other.rsplit("-", 1)[0]}')
            steps.append(link(h, a, 'request', mods[other][1]))
            if (i + j) % 5 == 0:
                g = node(f'G:endpoint:GET {url}', 'endpoint', f'GET {url}', kind='gap', group=f'/api/{other.rsplit("-", 1)[0]}')
                nodes[g].update(reason='no_server_route')
                steps.append(link(a, g, 'gap'))
                continue
            server = comps[(i * 3 + j) % len(comps)]
            e = node(f'E:{mods[server][2]}#handle', 'endpoint', 'handle', path=mods[server][2], component=part(server))
            steps.append(link(a, e, 'route', mods[server][2]))
            m = node(f'M:{part(server)}', 'service', part(server), component=part(server))
            steps.append(link(e, m, 'imports', mods[server][2]))
            t = node(f'T:{server.replace("-", "_")}', 'data', server.replace('-', '_'), kind='table')
            steps.append(link(e, t, 'defines', mods[server][2]))
        ids = {edges[k][end] for k in steps for end in ('from', 'to')}
        columns = paths_section.layout(ids, {n: nodes[n]['lane'] for n in ids}, [(edges[k]['from'], edges[k]['to']) for k in steps])
        out.append({'id': f'{domain}-{i}', 'title': route, 'handler': comp, 'surface': 'page', 'entry': f'S:{route}', 'fact': None, 'flow': None, 'flow_fact': None,
                    'steps': steps, 'columns': columns, 'gaps': sum(nodes[n]['kind'] == 'gap' for n in ids), 'capped': 0,
                    'unresolved': None, 'reach': 6})
    used = Counter(n for p in out for column in p['columns'] for n in column)
    node_rows = [{**nodes[n], 'paths': used[n]} for n in sorted(nodes)]
    named = {n['component'] for n in node_rows}
    parts = {f'src/{layer[c]}/{c}': {'op': ('retain', 'refactor', 'rebuild', 'merge', 'delete')[i % 5], 'target': f'{layer[c]}/{c}', 'layer': layer[c]}
             for i, c in enumerate(comps) if f'src/{layer[c]}/{c}' in named}
    tasks = [{'id': c['id'], 'paths': c['paths'], 'prerequisites': []} for c in card_rows]
    plan = {'tasks': tasks, 'milestones': [{'id': f'M{n + 1}', 'goal': f'Step {n + 1}', 'name': f'step-{n + 1}',
                                            'tasks': [c['id'] for c in card_rows if c['milestone'] == f'M{n + 1}']} for n in range(12)],
            'waves': [{'wave': w + 1, 'tasks': [c['id'] for c in card_rows[w * 200:(w + 1) * 200]]} for w in range((len(card_rows) + 199) // 200)]}
    gaps = sum(n['kind'] == 'gap' for n in node_rows)
    count = lambda value, src: measure(value, f'synthetic: {src}')
    return {**V2, 'lanes': list(paths_section.LANES), 'paths': out, 'nodes': node_rows, 'edges': edges, 'components': parts, 'new': [],
            'overview': paths_section.overview(node_rows, edges),
            'counts': {'paths': count(len(out), 'pages'), 'nodes': count(len(node_rows), 'nodes'), 'links': count(len(edges) - gaps, 'links'),
                       'gaps': count(gaps, 'gaps'), 'no_server_route': count(gaps, 'gaps'), 'trace_stopped': count(0, 'none'),
                       'component_not_found': count(0, 'none'), 'handler_not_found': count(0, 'none'),
                       'unresolved_steps': count(None, 'no flows'), 'calls': count(sum(n['lane'] == 'call' for n in node_rows), 'calls'),
                       'calls_answered': count(sum(n['lane'] == 'call' for n in node_rows) - gaps, 'calls'), 'by_call': count(0, 'none'),
                       'by_imports': count(0, 'none')},
            'src': {'paths': 'synthetic'}, 'timeline': paths_section.timeline(plan, card_rows, 'en')}


def data_maps(comps, layer, modules, rng):
    """The data paths and infrastructure sections, made by EAOS's own exporters from synthetic records: each module
    either writes one of its component's two tables or reads any table, and one write in twenty lands in another
    component's table, so some tables have several writers."""
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
def synthetic_pipeline(stages=1000, width=8):
    """studio/pipeline.json for the synthetic project: one product pipeline of `stages` stages in `width` lanes, a router
    every 50 stages with its labelled branches, a fork and its join every 100, a failure lane per router, a side channel,
    a dead stage and an unresolved call, and the ideal and gap views, every id resolving."""
    site = lambda path, line: {'path': path, 'line': line, 'fact': None, 'text': None}
    rows, edges, routers, fans, gap = [], [], [], [], []
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
    for i in range(49, stages, 50):
        targets = [j for j in (i + 1, i + 2, i + 3) if j < stages]
        routers.append({'id': f'p:r{i}', 'pipeline': 'p', 'stage': f'p:s{i}', 'kind': 'dict_dispatch', 'on': 'record.kind',
                        'entry': rows[i]['entry'], 'branches': [{'condition': f'kind == {k}', 'to': f'p:s{j}', 'evidence': rows[i]['entry']}
                                                                 for k, j in zip(('a', 'b', 'c'), targets)],
                        'total': i % 100 != 49, 'default': None, 'unhandled': [] if i % 100 != 49 else ['d']})
        if i % 100 == 49:
            gap.append({'id': f'gap:P4:r{i}', 'rule': 'P4', 'pipeline': 'p', 'subject': f'p:r{i}', 'subject_kind': 'router', 'operation': 'refactor',
                        'detail': 'kind d has no branch', 'evidence': rows[i]['entry'], 'card': None, 'step': None})
    for i in range(0, stages - width, 100):
        fans.append({'id': f'p:f{i}', 'pipeline': 'p', 'fork': f'p:s{i}', 'join': f'p:s{i + width}' if i % 200 else None,
                     'branches': [f'p:s{j}' for j in range(i + 1, min(i + width, stages))], 'matched': bool(i % 200), 'kind': 'parallel',
                     'evidence': rows[i]['entry']})
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
                for r in routers], 'hidden': hidden, 'unresolved': unresolved, 'rules': rules,
            'views': {'current': {'stages': [r['id'] for r in rows], 'edges': [e['id'] for e in edges]},
                      'ideal': {'stages': [{'id': r['id'], 'op': 'retain', 'label': r['label'], 'pipeline': 'p'} for r in rows],
                                'edges': [{'from': e['from'], 'to': e['to'], 'op': 'retain', 'pipeline': 'p'} for e in edges], 'made_by': 'rules'},
                      'gap': gap},
            'counts': {'stages': count(stages, 'stages'), 'edges': count(len(edges), 'edges'), 'gaps': count(len(gap), 'gap')},
            'src': {'pipeline': 'synthetic'}}


def build(cards=5000, components=1000, seed=7, functions_per_module=2, modules_per_component=3):
    """{section: data} for a synthetic project; nothing is written."""
    rng = random.Random(seed)
    comps = [f'{DOMAINS[i % len(DOMAINS)]}-{i // len(DOMAINS) + 1}' for i in range(components)]
    layer = {name: LAYERS[i % len(LAYERS)] for i, name in enumerate(comps)}
    modules = [(f'src/{layer[c]}/{c}/m{j}.ts', c) for c in comps for j in range(modules_per_component)]
    fns = [(f'{path}#fn{k}', f'fn{k}', path, c) for path, c in modules for k in range(functions_per_module)]

    facts, card_rows = [], []
    for i in range(cards):
        path, comp = modules[rng.randrange(len(modules))]
        kind, severity = KINDS[i % len(KINDS)], SEVERITIES[min(int(rng.random() ** 2 * 5), 4)]
        fact = f'FACT-{i:06d}'
        line = 1 + rng.randrange(400)
        facts.append({'id': fact, 'kind': 'engine_finding', 'engine': ('enola', 'jscpd', 'semgrep', 'knip')[i % 4], 'path': path,
                      'line': line, 'summary': f'{kind.replace("_", " ")} in {path}', 'sites': [{'path': path, 'line': 1}],
                      'code': {'start': max(1, line - 2), 'line': line, 'hidden': [],
                               'lines': [f'const v{n} = step{n}(input)  // m{i % 3}' for n in range(max(1, line - 2), line + 3)]}})
        card_rows.append({'id': f'TASK-{i + 1:05d}', 'key': f'k{i:06d}', 'title': f'{kind.replace("_", " ").capitalize()} in {comp} (m{i % 3})',
                          'kind': kind, 'category': ('structure', 'security', 'performance', 'cleanup')[i % 4], 'severity': severity,
                          'fixable': i % 3 == 0, 'needs_decision': i % 11 == 0, 'scope': 'group' if i % 17 == 0 else 'place',
                          'place': path, 'paths': [path], 'evidence': [fact], 'state': STATES[i % len(STATES)],
                          'milestone': f'M{i % 12 + 1}', 'confidence': (1.0, 0.7, 0.4)[i % 3], '_component': comp,
                          'why': dict(zip(('ar', 'en'), WHY[kind]))})
    by_comp = {}
    for card in card_rows: by_comp.setdefault(card.pop('_component'), []).append(card)
    closed = lambda rows: sum(c['state'] in ('done', 'resolved') for c in rows)

    steps = []
    for n in range(12):
        tasks = [c for c in card_rows if c['milestone'] == f'M{n + 1}']
        steps.append({'id': f'M{n + 1}', 'title': f'Step {n + 1}', 'state': 'active' if n < 3 else 'todo', 'weight': len(tasks),
                      'gate': f'Every card of step {n + 1} closed', 'depends_on': [f'M{n}'] if n else [], 'sub_plan': None,
                      'tasks': [{'id': c['id'], 'title': c['title'], 'state': TASK_STATE[c['state']], 'acceptance': None, 'depends_on': []}
                                for c in tasks]})
    ops, gaps = [], []
    for i, comp in enumerate(comps):
        op = OPERATIONS[i % len(OPERATIONS)]
        rows = by_comp.get(comp, [])
        ops.append({'id': f'op-{i + 1}', 'op': op, 'subject': comp, 'subject_kind': 'component', 'target': f'{layer[comp]}/{comp}',
                    'reason': f'{op.capitalize()} {comp} toward the target structure.', 'plan': 'fix', 'step': f'M{i % 12 + 1}', 'order': i + 1,
                    'after': [f'op-{i}'] if i % 5 else [], 'gap': f'gap-{comp}', 'cards': [c['id'] for c in rows[:20]],
                    'branch': None, 'state': 'todo'})
        gaps.append({'id': f'gap-{comp}', 'component': comp, 'operation': op, 'to': f'{layer[comp]}/{comp}', 'responsibility': f'Owns {comp}.',
                     'files': modules_per_component, 'cards': [c['id'] for c in rows], 'cards_closed': closed(rows),
                     'steps': [f'M{i % 12 + 1}'], 'operations': [f'op-{i + 1}'], 'decision': None,
                     'closed': ratio(round(closed(rows) / len(rows), 4) if rows else None, 'cards_closed / cards')})
    callers = {fid: [] for fid, *_ in fns}
    function_rows = []
    for index, (fid, name, path, comp) in enumerate(fns):
        callees = [fns[(index + step) % len(fns)][0] for step in (1, 7) if len(fns) > 1]
        for callee in callees: callers[callee].append(fid)
        function_rows.append({'id': fid, 'name': name, 'module': path, 'line': 10, 'end_line': 30, 'language': 'TypeScript', 'kind': 'function',
                              'signature': f'{name}(input: unknown): void', 'summary': None, 'exported': index % 2 == 0,
                              'lines': measure(21, 'synthetic', 'lines'), 'complexity': measure(1 + index % 15, 'synthetic'),
                              'callers': [], 'callees': callees, 'reads': [], 'writes': [{'kind': 'table', 'name': comp.replace('-', '_')}],
                              'cards': []})
    for row in function_rows: row['callers'] = callers[row['id']][:20]
    scans = []
    for n in range(30):
        scans.append({'id': f'scan{n:02d}', 'commit': f'{n:07x}', 'branch': 'main', 'at': f'2026-09-{n % 30 + 1:02d}T09:00:00+00:00',
                      'score': round(0.4 + n / 100, 3), 'open': {s: cards // (5 * (1 + n // 10)) for s in SEVERITIES},
                      'added': None if n == 0 else 10, 'resolved': None if n == 0 else 25, 'open_keys': []})
    images = [{'id': f'screens/s{i}.png', 'path': f'screens/s{i}.png', 'title': f'Screen {i}', 'kind': 'screen', 'batch': None, 'phase': 'baseline',
               'route': f'/{DOMAINS[i % len(DOMAINS)]}', 'viewport': '390', 'pair': None} for i in range(40)]
    screens = [{'id': f'screen-{i}', 'route': f'/{DOMAINS[i % len(DOMAINS)]}/{i}', 'title': f'Screen {i}', 'component': comps[i % len(comps)],
                'file': f'src/pages/Screen{i}.tsx', 'shots': [{'path': f'screens/s{i % 40}.png', 'width': 390, 'phase': 'baseline', 'batch': None}],
                'inputs': [{'id': 'q', 'label': None, 'kind': 'text', 'labelled': False, 'validated': None, 'required': False}],
                'issues': [{'id': f'screen-{i}-1', 'rule': 'label', 'severity': 'high', 'summary': 'A field has no label.', 'element': 'input#q',
                            'width': 390, 'box': {'x': 16, 'y': 100, 'w': 358, 'h': 44}, 'card': None, 'state': 'open'}]}
               for i in range(min(200, components))]
    total, done = len(card_rows), sum(c['state'] in ('done', 'resolved') for c in card_rows)
    sections = {
        'meta': {**HEAD, 'languages': [{'name': 'TypeScript', 'files': len(modules), 'share': 1.0}],
                 'files': measure(len(modules), 'synthetic'), 'lines': measure(len(modules) * 120, 'synthetic', 'lines'),
                 'stages': [{'id': 'S01', 'title': 'S01', 'state': 'done'}]},
        'head': {**HEAD, 'scanned': {'commit': f'{29:07x}', 'branch': 'main', 'at': WHEN},
                 'eaos': {'version': 'synthetic', 'commit': 'synthetic', 'digest': 'synthetic'}, 'freshness': 'fresh',
                 'verdict': f'{total} problems; EAOS fixes {sum(c["fixable"] for c in card_rows)} of them by itself.',
                 'next': {'action': 'Start a fix batch', 'tool': 'fix_start'}},
        'health': {**HEAD, 'score': ratio(0.69, 'synthetic'), 'formula': 'synthetic',
                   'domains': [{'id': area, 'name': area, 'score': ratio(0.7, 'synthetic'), 'cards': total // 4}
                               for area in ('structure', 'security', 'performance', 'cleanup')],
                   'history': [{'at': s['at'], 'commit': s['commit'], 'score': s['score']} for s in scans]},
        'cards': {**HEAD, 'cards': card_rows},
        'evidence': {**HEAD, 'facts': facts},
        'story': {**HEAD, 'current': {'summary': f'{components} components.',
                                      'components': [{'name': c, 'layer': layer[c], 'files': modules_per_component} for c in comps]},
                  'target': {'summary': 'The same components, one owner each.',
                             'components': [{'name': f'{layer[c]}/{c}', 'responsibility': f'Owns {c}.', 'layer': layer[c]} for c in comps]},
                  'gap': [{'component': g['component'], 'relation': 'modify', 'to': g['to'], 'files': g['files'], 'cards': g['cards'][:50],
                           'closed': g['cards_closed']} for g in gaps],
                  'indicators': [{'id': 'S1', 'name': 'S1', 'today': measure(0.6, 'synthetic'), 'expected': measure(0.8, 'synthetic'),
                                  'target': measure(0.9, 'synthetic')}]},
        'docs': {**HEAD, 'docs': [{'id': f'docs/D{i}.md', 'title': f'Document {i}', 'path': f'docs/D{i}.md', 'group': ('start', 'story', 'plan', 'technical')[i % 4],
                                   'bytes': 4000, 'order': i} for i in range(100)]},
        'plans': {**HEAD, 'plans': [{'id': 'fix', 'title': 'Fix plan', 'kind': 'fix', 'parent': None, 'state': 'active', 'goal': '', 'indicators': [],
                                     'steps': steps, 'progress': ratio(round(done / total, 4) if total else None, 'ledger')}]},
        'decisions': {**HEAD, 'decisions': [{'id': f'decision-{i}', 'question': f'Approve the operation on {comps[i]}?',
                                             'recommendation': 'Yes.', 'options': [{'id': 'yes', 'label': 'Yes'}, {'id': 'later', 'label': 'Later'}],
                                             'blocks': [c['id'] for c in by_comp.get(comps[i], [])], 'state': 'waiting', 'answer': None,
                                             'plan': 'fix', 'asked': WHEN, 'tool': None} for i in range(min(20, components))]},
        'media': {**HEAD, 'images': images},
        'functions': {**V2, 'modules': [{'id': path, 'component': comp, 'language': 'TypeScript', 'functions': functions_per_module}
                                        for path, comp in modules], 'functions': function_rows},
        'screens': {**V2, 'screens': screens},
        'gaps': {**V2, 'gaps': gaps},
        'operations': {**V2, 'operations': ops},
        'history': {**V2, 'scans': scans, 'events': [{'at': s['at'], 'kind': 'scan', 'title': f'Check {s["id"]}', 'ref': s['commit']} for s in scans]},
        'quality': {**V2, 'detectors': [{'id': f'{k}', 'name': k, 'engine': None, 'applies': True, 'precision': ratio(0.9, 'synthetic'),
                                         'recall': ratio(None, 'not measured'), 'labelled': None} for k in KINDS],
                    'capabilities': [{'id': 'C2', 'name': 'Current state', 'value': ratio(0.6, 'synthetic')}],
                    'indicators': [{'id': 'S1', 'name': 'S1', 'value': ratio(0.88, 'synthetic'), 'target': 0.8}]},
    }
    sections['paths'] = synthetic_paths(comps, layer, modules, card_rows)
    sections.update(maps(comps, layer, card_rows))
    data_paths, infra = data_maps(comps, layer, modules, rng)
    sections.update(data_paths={**V2, **data_paths}, infra={**V2, **infra})
    sections['pipeline'] = synthetic_pipeline(stages=max(components, 50))
    written = list(sections)
    sections['coverage'] = {**V2, **coverage_section.coverage(Path('.'), sections, written, [], 'en')}
    return sections


def maps(comps, layer, card_rows):
    """journeys and hidden for the synthetic project, built by the exporter's own code from records like a scan's: one
    screen per component under an /app layout, a sidebar menu to the first screen of each domain, each screen linking
    to the next of its domain, every tenth a create form, and unseen work (writes, outside calls, dead code) behind them."""
    router, pages, links, imports, names = 'src/App.tsx', [], [], {}, {}
    files = {c: f'src/pages/{c}.tsx' for c in comps}
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


def write(folder, sections, name='synthetic'):
    """Write every section, checked against its contract, then the manifest; returns the problems found (none expected)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    contracts, problems, entries = artifact_contracts.contracts(), [], []
    for section, data in sections.items():
        problems += [f'{section}: {line}' for line in artifact_contracts.validate(data, contracts[f'studio-{section}'])[:5]]
        blob = export._write(folder, section, data)
        entries.append({'name': section, 'file': f'{section}.json', 'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob)})
    manifest = {**HEAD, 'revision': export.REVISION,
                'built': {'version': 'synthetic', 'commit': 'synthetic', 'digest': 'synthetic', 'studio_digest': 'synthetic', 'built': WHEN},
                'project': {'name': name}, 'scanned': sections['head']['scanned'], 'sections': entries}
    problems += [f'manifest: {line}' for line in artifact_contracts.validate(manifest, contracts['studio-manifest'])[:5]]
    export._write(folder, 'manifest', manifest)
    return problems


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--out', required=True)
    parser.add_argument('--cards', type=int, default=5000)
    parser.add_argument('--components', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=7)
    args = parser.parse_args(argv)
    problems = write(args.out, build(args.cards, args.components, args.seed))
    for line in problems: print(line, file=sys.stderr)
    print(f'wrote {args.out}: {args.cards} cards, {args.components} components' + (f'; {len(problems)} contract problems' if problems else ''))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
