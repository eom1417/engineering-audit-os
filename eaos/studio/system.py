"""studio/system.json: the project as two maps, today and the target, with how each part of today gets there.

Read only from records the check already wrote; nothing is invented and every number names its source (`src`):

    today        target-architecture.json current_components: each component, its files, kind, fan-in/out, its
                 relation to the target (retain, modify, rebuild, delete) and the target component it goes to
    imports      facts/graph.json graph_node depends_on, counted between the components that own the two files
                 (the same count as eaos/arch_map.py); an edge inside one strongly connected group is a cycle edge
    findings     the cards (cards.json) by severity: a card counts in the deepest component holding its first path,
                 the rule the Studio's ranked list uses, so the map and the list show one number
    target       target-architecture.json target_components and target_edges; a target component fed by no part of
                 today is introduced, by two or more is a merge, by one takes that part's relation
    decisions    target-architecture.json decisions: the structure decision recorded for each component

The layout (regions, positions, land, labels, edge curves) is computed by eaos/studio/territory.py, so the Studio only
draws. This section is the precursor of NS39.T1's unified graph: the same nodes and weighted edges, read by one page.
"""
from collections import Counter, defaultdict
from pathlib import Path

from .. import arch_map
from . import territory

MAX_NODES = 200
SEVERITIES = ('critical', 'high', 'medium', 'low')
OPERATIONS = ('retain', 'modify', 'rebuild', 'delete', 'merge', 'introduce')
RELATION = {'retain': 'retain', 'modify': 'modify', 'rebuild': 'rebuild', 'delete': 'delete', 'retire': 'delete'}

# Region names for the folders and layers most projects use; any other name is shown as it is, an identifier.
NAMES = {
    'components': ('مكونات الواجهة', 'Components'), 'pages': ('الصفحات', 'Pages'), 'views': ('العروض', 'Views'),
    'screens': ('الشاشات', 'Screens'), 'lib': ('المكتبة المشتركة', 'Lib'), 'utils': ('الأدوات المساعدة', 'Utils'),
    'services': ('الخدمات', 'Services'), 'api': ('واجهة API', 'API'), 'api-client': ('عميل API', 'API client'),
    'hooks': ('الخطافات', 'Hooks'), 'store': ('الحالة', 'Store'), 'state': ('الحالة', 'State'), 'models': ('النماذج', 'Models'),
    'routes': ('المسارات', 'Routes'), 'controllers': ('المتحكمات', 'Controllers'), 'tests': ('الاختبارات', 'Tests'),
    'test': ('الاختبارات', 'Tests'), 'docs': ('الوثائق', 'Docs'), 'tools': ('الأدوات', 'Tools'), 'scripts': ('السكربتات', 'Scripts'),
    'features': ('الميزات', 'Features'), 'modules': ('الوحدات', 'Modules'), 'core': ('النواة', 'Core'),
    'shared': ('المشترك', 'Shared'), 'common': ('المشترك', 'Common'), 'config': ('الإعدادات', 'Config'), 'app': ('التطبيق', 'App'),
    'server': ('الخادم', 'Server'), 'client': ('العميل', 'Client'), 'types': ('الأنواع', 'Types'), 'assets': ('الأصول', 'Assets'),
    'data': ('البيانات', 'Data'), 'db': ('قاعدة البيانات', 'Database'), 'database': ('قاعدة البيانات', 'Database'),
    'migrations': ('الترحيلات', 'Migrations'), 'ui': ('الواجهة', 'UI'), 'layouts': ('التخطيطات', 'Layouts'),
    'platform': ('المنصة', 'Platform'), 'domain': ('النطاق', 'Domain'), 'infrastructure': ('البنية التحتية', 'Infrastructure'),
    'adapters': ('المحولات', 'Adapters'), 'application': ('التطبيق', 'Application'), 'src': ('الشيفرة', 'Source'),
    'packages': ('الحزم', 'Packages'), 'apps': ('التطبيقات', 'Apps'), 'web': ('الويب', 'Web'), 'backend': ('الخلفية', 'Backend'),
    'frontend': ('الواجهة الأمامية', 'Frontend'), 'entities': ('الكيانات', 'Entities'), 'repositories': ('المستودعات', 'Repositories'),
}
SRC = {
    'files': 'target-architecture.json#current_components[].files',
    'fan_in': 'target-architecture.json#current_components[].fan_in',
    'fan_out': 'target-architecture.json#current_components[].fan_out',
    'imports': 'facts/graph.json#graph_node.value.depends_on, counted between the components owning both files',
    'findings': 'cards.json#cards[].severity, a card counted in the deepest component holding its first path',
    'target_files': 'target-architecture.json#target_components[].files',
    'target_imports': 'target-architecture.json#target_edges[].imports',
    'sources': 'target-architecture.json#current_components[].target_component',
}


def _segments(name):
    return [] if name in ('', '.', '(root)') else name.split('/')


def group(names, share=0.45):
    """{name: region id} and [{id, kind, folder}]: folders split from the top, largest first, while the largest region
    holds more than `share` of the components and the map keeps at most MAX_REGIONS regions. A folder's own files and
    its single-folder children form its "rest" region; small top-level folders share one region."""
    if not names: return {}, []
    groups = defaultdict(list)
    for name in names: groups[('dir', tuple(_segments(name)[:1]))].append(name)
    while True:
        big = max(groups, key=lambda k: (len(groups[k]), k))
        members = groups[big]
        if big[0] != 'dir' or len(members) <= max(8, share * len(names)): break
        prefix = big[1]
        own, children = [], defaultdict(list)
        for name in members:
            seg = _segments(name)
            (own if len(seg) <= len(prefix) else children[tuple(seg[:len(prefix) + 1])]).append(name)
        new = {('dir', key): m for key, m in children.items() if len(m) > 1}
        rest = own + [n for m in children.values() if len(m) == 1 for n in m]
        if rest: new[('rest', prefix)] = rest
        if len(new) < 2 or len(groups) - 1 + len(new) > territory.MAX_REGIONS: break
        del groups[big]
        groups.update(new)
    small = [k for k, m in groups.items() if k[0] == 'dir' and len(k[1]) <= 1 and len(m) <= 2]
    if len(small) >= 2:
        merged = [n for k in sorted(small) for n in groups.pop(k)]
        groups[('top', ())] = merged
    region_of, regions = {}, []
    for key in sorted(groups, key=lambda k: (-len(groups[k]), k)):
        kind, prefix = key
        folder = '/'.join(prefix)
        rid = f'{kind}:{folder}'
        regions.append({'id': rid, 'kind': kind, 'folder': folder or None, 'name': region_name(kind, folder)})
        for name in groups[key]: region_of[name] = rid
    return region_of, regions


def region_name(kind, folder):
    """{ar, en, ident}: ident is true when the name is the folder itself (shown as an identifier, left to right)."""
    last = folder.rsplit('/', 1)[-1] if folder else ''
    if kind == 'top': return {'ar': 'الجذر ومجلدات صغيرة', 'en': 'Root and small folders', 'ident': False}
    if kind == 'rest': return {'ar': f'بقية {folder}', 'en': f'Rest of {folder}', 'ident': False}
    if not folder: return {'ar': 'جذر المستودع', 'en': 'Repository root', 'ident': False}
    if last.lower() in NAMES:
        ar, en = NAMES[last.lower()]
        return {'ar': ar, 'en': en, 'ident': False}
    return {'ar': folder, 'en': folder, 'ident': True}


def layer_name(layer):
    if layer and layer.lower() in NAMES:
        ar, en = NAMES[layer.lower()]
        return {'ar': ar, 'en': en, 'ident': False}
    return {'ar': layer or '—', 'en': layer or '—', 'ident': bool(layer)}


def short(name, region):
    """The label a dot carries: its path without the region's folder, the last part when long."""
    folder = region.get('folder') or ''
    rest = name[len(folder) + 1:] if folder and name.startswith(folder + '/') else name
    if rest in ('', '.') or name == folder: rest = name.rsplit('/', 1)[-1]
    return rest if len(rest) <= 22 else '…/' + rest.rsplit('/', 1)[-1]


def owner_of(names):
    """The deepest component holding a path (the Studio's ranked list uses the same rule), else (root)."""
    ordered = sorted((n for n in names if n != '(root)'), key=len, reverse=True)

    def find(path):
        return next((n for n in ordered if path == n or path.startswith(n + '/')), '(root)' if '(root)' in names else None)
    return find


def _measure(value, src, unit='count'):
    return {'value': value, 'src': src, 'unit': unit}


def _views(current, between, groups, card_rows, target, decision_of):
    names = [c['name'] for c in current]
    region_of, regions = group(names)
    by_region = {r['id']: r for r in regions}
    find = owner_of(set(names))
    findings = defaultdict(Counter)
    for card in card_rows:
        if not card.get('paths'): continue
        home = find(card['paths'][0])
        if home is not None and card.get('severity') in SEVERITIES: findings[home][card['severity']] += 1
    by_name = {c['name']: c for c in current}
    sources = defaultdict(list)
    for c in current:
        if c.get('target_component'): sources[c['target_component']].append(c['name'])
    nodes = [{'id': c['name'], 'short': short(c['name'], by_region[region_of[c['name']]]), 'files': int(c.get('files') or 0),
              'region': region_of[c['name']]} for c in current]
    family = [(a, b) for a in names for b in names if a != b and b.startswith(a + '/') and b.count('/') == a.count('/') + 1
              and region_of[a] == region_of[b]]
    edges = [(a, b, n) for (a, b), n in sorted(between.items())]
    pic = territory.draw(nodes, edges, regions, family)
    cur_nodes = []
    for n in nodes:
        c, g = by_name[n['id']], pic['nodes'][n['id']]
        sev = findings[n['id']]
        relation = RELATION.get(c.get('relation'), 'modify')
        cur_nodes.append({'id': n['id'], 'short': n['short'], 'kind': c.get('kind') or 'package', 'region': n['region'],
                          'files': n['files'], 'fan_in': c.get('fan_in'), 'fan_out': c.get('fan_out'),
                          'findings': {**{s: sev.get(s, 0) for s in SEVERITIES}, 'total': sum(sev.values())},
                          'op': relation, 'target': c.get('target_component'),
                          'merged_with': max(len(sources.get(c.get('target_component'), [])) - 1, 0),
                          'reason': str(c.get('reason') or '').split(' (', 1)[0][:300],
                          'decision': decision_of.get(c.get('id')),
                          'x': g['x'], 'y': g['y'], 'r': g['r'], 'label': g['label']})
    cur_edges = [{'from': a, 'to': b, 'imports': n, 'cycle': groups.get(a) is not None and groups.get(a) == groups.get(b),
                  **pic['edges'][(a, b)]} for a, b, n in edges if (a, b) in pic['edges']]
    current_view = {'regions': [{**r, 'components': sum(region_of[x] == r['id'] for x in names),
                                 'files': sum(n['files'] for n in nodes if n['region'] == r['id']),
                                 'findings': sum(sum(findings[x].values()) for x in names if region_of[x] == r['id']),
                                 'lead': max((n for n in nodes if n['region'] == r['id']), key=lambda n: (n['files'], n['id']))['id'],
                                 **pic['regions'][r['id']]} for r in regions if r['id'] in pic['regions']],
                    'nodes': cur_nodes, 'edges': cur_edges, 'scale': pic['scale'], 'bounds': pic['bounds']}
    # the target: its own territory, one region per layer
    tcomps = [t for t in target.get('target_components') or [] if isinstance(t, dict) and t.get('name')]
    tnames = {t['name'] for t in tcomps}
    layers = sorted({t.get('layer') or '' for t in tcomps}, key=lambda l: (-sum((t.get('layer') or '') == l for t in tcomps), l))
    tregions = [{'id': f'layer:{l}', 'kind': 'layer', 'folder': None, 'name': layer_name(l)} for l in layers]
    tnodes = [{'id': t['name'], 'short': t['name'] if len(t['name']) <= 22 else '…' + t['name'][-21:],
               'files': int(t.get('files') or 0), 'region': f"layer:{t.get('layer') or ''}"} for t in tcomps]
    tedges = [(e['from'], e['to'], int(e.get('imports') or 1)) for e in target.get('target_edges') or []
              if isinstance(e, dict) and e.get('from') in tnames and e.get('to') in tnames]
    tpic = territory.draw(tnodes, tedges, tregions)
    out_t = []
    for t, n in zip(tcomps, tnodes):
        feeds = sorted(sources.get(t['name'], []))
        ops = {RELATION.get(by_name[s].get('relation'), 'modify') for s in feeds}
        op = 'introduce' if not feeds else 'merge' if len(feeds) > 1 else ops.pop()
        g = tpic['nodes'][t['name']]
        out_t.append({'id': t['name'], 'short': n['short'], 'layer': t.get('layer'), 'region': n['region'], 'files': n['files'],
                      'responsibility': str(t.get('responsibility') or '')[:400], 'sources': feeds, 'op': op,
                      'carried': sum(sum(findings[s].values()) for s in feeds),
                      'x': g['x'], 'y': g['y'], 'r': g['r'], 'label': g['label']})
    target_view = {'regions': [{**r, 'components': sum(n['region'] == r['id'] for n in tnodes),
                                'files': sum(n['files'] for n in tnodes if n['region'] == r['id']), 'findings': None,
                                'lead': max((n for n in tnodes if n['region'] == r['id']), key=lambda n: (n['files'], n['id']))['id'],
                                **tpic['regions'][r['id']]} for r in tregions if r['id'] in tpic['regions']],
                   'nodes': out_t,
                   'edges': [{'from': a, 'to': b, 'imports': n, 'cycle': False, **tpic['edges'][(a, b)]}
                             for a, b, n in tedges if (a, b) in tpic['edges']],
                   'scale': tpic['scale'], 'bounds': tpic['bounds']}
    return current_view, target_view


def system(report, card_rows):
    """The section's body: {world, counts, operations, src, current, target, capped}."""
    report = Path(report)
    target = arch_map._load(report / 'target-architecture.json', {}) or {}
    comps = [c for c in target.get('current_components') or [] if isinstance(c, dict) and c.get('name')]
    ranked = sorted(comps, key=lambda c: (-(c.get('files') or 0), c['name']))
    current = sorted(ranked[:MAX_NODES], key=lambda c: c['name'])
    names = {c['name'] for c in current}
    owner = {p: c['name'] for c in current for p in c.get('paths') or [] if isinstance(p, str)}
    between = Counter()
    graph_nodes = arch_map.facts(report, 'graph', 'graph_node')
    for node in graph_nodes:
        here = owner.get(arch_map.path_of(node))
        if not here: continue
        for dep in (node.get('value') or {}).get('depends_on') or []:
            there = owner.get(dep) if isinstance(dep, str) else None
            if there and there != here: between[(here, there)] += 1
    groups = arch_map.strong_groups(sorted(names), list(between)) if between else {}
    sizes = Counter(groups.values())
    groups = {k: v for k, v in groups.items() if sizes[v] > 1}
    by_id = {c.get('id'): c for c in current}
    decision_of = {}
    for d in target.get('decisions') or []:
        if isinstance(d, dict) and d.get('component_id') in by_id and d.get('component_id') not in decision_of:
            decision_of[d['component_id']] = {'id': str(d.get('id') or ''), 'chosen': str(d.get('chosen') or '')[:400]}
    current_view, target_view = _views(current, between, groups, card_rows, target, decision_of)
    ops = Counter(n['op'] for n in current_view['nodes'])
    tops = Counter(n['op'] for n in target_view['nodes'])
    have_graph = bool(graph_nodes)
    return {
        'world': {'width': territory.W, 'height': territory.H},
        'graph': 'precursor of NS39.T1: components and their weighted import edges, today and in the target',
        'counts': {
            'components': _measure(len(current), 'target-architecture.json#current_components (count)'),
            'regions': _measure(len(current_view['regions']), 'eaos/studio/system.py group(): folders split while one region holds most components'),
            'edges': _measure(len(current_view['edges']) if have_graph else None, SRC['imports'] + ' (count of component pairs)'),
            'imports': _measure(sum(between.values()) if have_graph else None, SRC['imports']),
            'target_components': _measure(len(target_view['nodes']), 'target-architecture.json#target_components (count)'),
            'target_edges': _measure(len(target_view['edges']), 'target-architecture.json#target_edges (count)'),
            'target_regions': _measure(len(target_view['regions']), 'target-architecture.json#target_components[].layer (distinct)'),
        },
        'operations': {op: _measure(ops.get(op, 0) if op in ('retain', 'modify', 'rebuild', 'delete') else tops.get(op, 0),
                                    'target-architecture.json#current_components[].relation (count)'
                                    if op in ('retain', 'modify', 'rebuild', 'delete') else
                                    'target-architecture.json#target_components fed by ' + ('2 or more' if op == 'merge' else 'no') + ' current components (count)')
                       for op in OPERATIONS},
        'src': SRC,
        'capped': max(len(comps) - len(current), 0),
        'current': current_view,
        'target': target_view,
    }
