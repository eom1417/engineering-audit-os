"""studio/system.json: the project as two maps, today and the target, with how each part of today gets there.

Read only from records the check already wrote; nothing is invented and every number names its source (`src`):

    today        target-architecture.json current_components: each component, its files, kind, fan-in/out, its
                 relation to the target (retain, modify, rebuild, delete) and the target component it goes to
    imports      facts/graph.json graph_node depends_on, counted between the components that own the two files
                 (the same count as eaos/analysis/maps/architecture.py); an edge inside one strongly connected group is a cycle edge
    findings     the cards (cards.json) by severity: a card counts in the deepest component holding its first path,
                 the rule the Studio's ranked list uses, so the map and the list show one number
    target       target-architecture.json target_components and target_edges; a target component fed by no part of
                 today is introduced, by two or more is a merge, by one takes that part's relation
    decisions    target-architecture.json decisions: the structure decision recorded for each component

The layout (regions, positions, land, labels, edge curves) is computed by eaos/report/studio/territory.py, so the Studio only
draws. This section is the precursor of NS39.T1's unified graph: the same nodes and weighted edges, read by one page.
"""
from collections import Counter, defaultdict
from pathlib import Path

from ...analysis.maps import architecture as arch_map
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
    while _split_largest(groups, max(8, share * len(names))): pass
    _merge_small(groups)
    return _regions(groups)


def _children(prefix, members):
    """The folder's subfolders with more than one component, and its rest: its own files and single-folder children."""
    own, children = [], defaultdict(list)
    for name in members:
        seg = _segments(name)
        (own if len(seg) <= len(prefix) else children[tuple(seg[:len(prefix) + 1])]).append(name)
    new = {('dir', key): m for key, m in children.items() if len(m) > 1}
    rest = own + [n for m in children.values() if len(m) == 1 for n in m]
    if rest: new[('rest', prefix)] = rest
    return new


def _split_largest(groups, most):
    """Split the largest folder region one level down; False when it holds `most` or fewer, or splitting cannot help."""
    big = max(groups, key=lambda k: (len(groups[k]), k))
    members = groups[big]
    if big[0] != 'dir' or len(members) <= most: return False
    new = _children(big[1], members)
    if len(new) < 2 or len(groups) - 1 + len(new) > territory.MAX_REGIONS: return False
    del groups[big]
    groups.update(new)
    return True


def _merge_small(groups):
    """Small top-level folders share one region."""
    small = [k for k, m in groups.items() if k[0] == 'dir' and len(k[1]) <= 1 and len(m) <= 2]
    if len(small) >= 2:
        merged = [n for k in sorted(small) for n in groups.pop(k)]
        groups[('top', ())] = merged


def _regions(groups):
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


def _findings(names, card_rows):
    """{component: Counter of the severities of its cards}: a card counts in the deepest component holding its first path."""
    find = owner_of(set(names))
    findings = defaultdict(Counter)
    for card in card_rows:
        if not card.get('paths'): continue
        home = find(card['paths'][0])
        if home is not None and card.get('severity') in SEVERITIES: findings[home][card['severity']] += 1
    return findings


def _views(current, links, card_rows, target, decision_of):
    """(today's map, the target's map); `links`: (imports between components, their cycle groups)."""
    names = [c['name'] for c in current]
    findings = _findings(names, card_rows)
    sources = defaultdict(list)
    for c in current:
        if c.get('target_component'): sources[c['target_component']].append(c['name'])
    current_view = _current_view(current, links, findings, (sources, decision_of))
    return current_view, _target_view(target, sources, {c['name']: c for c in current}, findings)


def _current_node(n, c, g, sev, context):
    """One component of today's map: its files, findings, what happens to it, and where it is drawn."""
    sources, decision_of = context
    return {'id': n['id'], 'short': n['short'], 'kind': c.get('kind') or 'package', 'region': n['region'],
            'files': n['files'], 'fan_in': c.get('fan_in'), 'fan_out': c.get('fan_out'),
            'findings': {**{s: sev.get(s, 0) for s in SEVERITIES}, 'total': sum(sev.values())},
            'op': RELATION.get(c.get('relation'), 'modify'), 'target': c.get('target_component'),
            'merged_with': max(len(sources.get(c.get('target_component'), [])) - 1, 0),
            'reason': str(c.get('reason') or '').split(' (', 1)[0][:300],
            'decision': decision_of.get(c.get('id')),
            'x': g['x'], 'y': g['y'], 'r': g['r'], 'label': g['label']}


def _current_view(current, links, findings, context):
    between, groups = links
    names = [c['name'] for c in current]
    region_of, regions = group(names)
    by_region = {r['id']: r for r in regions}
    by_name = {c['name']: c for c in current}
    nodes = [{'id': c['name'], 'short': short(c['name'], by_region[region_of[c['name']]]), 'files': int(c.get('files') or 0),
              'region': region_of[c['name']]} for c in current]
    edges = [(a, b, n) for (a, b), n in sorted(between.items())]
    pic = territory.draw(nodes, edges, regions, _family(names, region_of))
    cur_nodes = [_current_node(n, by_name[n['id']], pic['nodes'][n['id']], findings[n['id']], context) for n in nodes]
    return {'regions': [{**_region_row(r['id'], nodes, findings), **r, **pic['regions'][r['id']]} for r in regions if r['id'] in pic['regions']],
            'nodes': cur_nodes, 'edges': _drawn_edges(edges, groups, pic), 'scale': pic['scale'], 'bounds': pic['bounds']}


def _family(names, region_of):
    """(parent, child) pairs one folder apart in one region: drawn side by side."""
    return [(a, b) for a in names for b in names if a != b and b.startswith(a + '/') and b.count('/') == a.count('/') + 1
            and region_of[a] == region_of[b]]


def _drawn_edges(edges, groups, pic):
    """The links the picture drew, each marked when its two ends share an import cycle."""
    return [{'from': a, 'to': b, 'imports': n, 'cycle': groups.get(a) is not None and groups.get(a) == groups.get(b),
             **pic['edges'][(a, b)]} for a, b, n in edges if (a, b) in pic['edges']]


def _region_row(region, nodes, findings):
    """A region's components, files and findings, and its largest component."""
    mine = [n for n in nodes if n['region'] == region]
    return {'components': len(mine), 'files': sum(n['files'] for n in mine), 'findings': sum(sum(findings[n['id']].values()) for n in mine),
            'lead': max(mine, key=lambda n: (n['files'], n['id']))['id']}


def _target_node(t, n, g, feeds, known):
    """One target component: the components of today that feed it, and so what it takes (introduce, merge, or theirs)."""
    by_name, findings = known
    ops = {RELATION.get(by_name[s].get('relation'), 'modify') for s in feeds}
    op = 'introduce' if not feeds else 'merge' if len(feeds) > 1 else ops.pop()
    return {'id': t['name'], 'short': n['short'], 'layer': t.get('layer'), 'region': n['region'], 'files': n['files'],
            'responsibility': str(t.get('responsibility') or '')[:400], 'sources': feeds, 'op': op,
            'carried': sum(sum(findings[s].values()) for s in feeds),
            'x': g['x'], 'y': g['y'], 'r': g['r'], 'label': g['label']}


def _target_layers(target):
    """The target's named components, and one region per layer, the most populated first."""
    tcomps = [t for t in target.get('target_components') or [] if isinstance(t, dict) and t.get('name')]
    layers = sorted({t.get('layer') or '' for t in tcomps}, key=lambda l: (-sum((t.get('layer') or '') == l for t in tcomps), l))
    return tcomps, [{'id': f'layer:{l}', 'kind': 'layer', 'folder': None, 'name': layer_name(l)} for l in layers]


def _target_nodes(tcomps):
    return [{'id': t['name'], 'short': t['name'] if len(t['name']) <= 22 else '…' + t['name'][-21:],
             'files': int(t.get('files') or 0), 'region': f"layer:{t.get('layer') or ''}"} for t in tcomps]


def _target_edges(target, tnames):
    return [(e['from'], e['to'], int(e.get('imports') or 1)) for e in target.get('target_edges') or []
            if isinstance(e, dict) and e.get('from') in tnames and e.get('to') in tnames]


def _target_regions(tregions, tnodes, tpic):
    return [{**r, 'components': sum(n['region'] == r['id'] for n in tnodes),
             'files': sum(n['files'] for n in tnodes if n['region'] == r['id']), 'findings': None,
             'lead': max((n for n in tnodes if n['region'] == r['id']), key=lambda n: (n['files'], n['id']))['id'],
             **tpic['regions'][r['id']]} for r in tregions if r['id'] in tpic['regions']]


def _target_view(target, sources, by_name, findings):
    # the target: its own territory, one region per layer
    tcomps, tregions = _target_layers(target)
    tnodes, tedges = _target_nodes(tcomps), _target_edges(target, {t['name'] for t in tcomps})
    tpic = territory.draw(tnodes, tedges, tregions)
    out_t = [_target_node(t, n, tpic['nodes'][t['name']], sorted(sources.get(t['name'], [])), (by_name, findings))
             for t, n in zip(tcomps, tnodes)]
    return {'regions': _target_regions(tregions, tnodes, tpic),
                   'nodes': out_t,
                   'edges': [{'from': a, 'to': b, 'imports': n, 'cycle': False, **tpic['edges'][(a, b)]}
                             for a, b, n in tedges if (a, b) in tpic['edges']],
                   'scale': tpic['scale'], 'bounds': tpic['bounds']}


def _between(graph_nodes, current):
    """Counter {(component, component): imports} between the components that own the two files."""
    owner = _owners(current)
    between = Counter()
    for node in graph_nodes:
        here = owner.get(arch_map.path_of(node))
        if not here: continue
        for there in (owner.get(dep) if isinstance(dep, str) else None for dep in (node.get('value') or {}).get('depends_on') or []):
            if there and there != here: between[(here, there)] += 1
    return between


def _owners(current):
    """{file: the component that owns it}."""
    return {p: c['name'] for c in current for p in c.get('paths') or [] if isinstance(p, str)}


def _cycle_groups(names, between):
    """{component: its strongly connected group}, for the groups of more than one component."""
    groups = arch_map.strong_groups(sorted(names), list(between)) if between else {}
    sizes = Counter(groups.values())
    return {k: v for k, v in groups.items() if sizes[v] > 1}


def _decisions(target, current):
    """{component id: the first structure decision about it}."""
    by_id = {c.get('id'): c for c in current}
    decision_of = {}
    for d in target.get('decisions') or []:
        if isinstance(d, dict) and d.get('component_id') in by_id and d.get('component_id') not in decision_of:
            decision_of[d['component_id']] = {'id': str(d.get('id') or ''), 'chosen': str(d.get('chosen') or '')[:400]}
    return decision_of


CURRENT_OPERATIONS = ('retain', 'modify', 'rebuild', 'delete')


def _operation(op, ops, tops):
    """How many components take an operation: today's for retain..delete, the target's for merge and introduce."""
    if op in CURRENT_OPERATIONS: return _measure(ops.get(op, 0), 'target-architecture.json#current_components[].relation (count)')
    return _measure(tops.get(op, 0), 'target-architecture.json#target_components fed by ' + ('2 or more' if op == 'merge' else 'no')
                    + ' current components (count)')


def _named_components(target):
    """Today's components that have a name."""
    return [c for c in target.get('current_components') or [] if isinstance(c, dict) and c.get('name')]


def system(report, card_rows):
    """The section's body: {world, counts, operations, src, current, target, capped}."""
    report = Path(report)
    target = arch_map._load(report / 'target-architecture.json', {}) or {}
    comps = _named_components(target)
    ranked = sorted(comps, key=lambda c: (-(c.get('files') or 0), c['name']))
    current = sorted(ranked[:MAX_NODES], key=lambda c: c['name'])
    names = {c['name'] for c in current}
    graph_nodes = arch_map.facts(report, 'graph', 'graph_node')
    between = _between(graph_nodes, current)
    links = (between, _cycle_groups(names, between))
    current_view, target_view = _views(current, links, card_rows, target, _decisions(target, current))
    ops = Counter(n['op'] for n in current_view['nodes'])
    tops = Counter(n['op'] for n in target_view['nodes'])
    have_graph = bool(graph_nodes)
    return {
        'world': {'width': territory.W, 'height': territory.H},
        'graph': 'precursor of NS39.T1: components and their weighted import edges, today and in the target',
        'counts': {
            'components': _measure(len(current), 'target-architecture.json#current_components (count)'),
            'regions': _measure(len(current_view['regions']), 'eaos/report/studio/system.py group(): folders split while one region holds most components'),
            'edges': _measure(len(current_view['edges']) if have_graph else None, SRC['imports'] + ' (count of component pairs)'),
            'imports': _measure(sum(between.values()) if have_graph else None, SRC['imports']),
            'target_components': _measure(len(target_view['nodes']), 'target-architecture.json#target_components (count)'),
            'target_edges': _measure(len(target_view['edges']), 'target-architecture.json#target_edges (count)'),
            'target_regions': _measure(len(target_view['regions']), 'target-architecture.json#target_components[].layer (distinct)'),
        },
        'operations': {op: _operation(op, ops, tops) for op in OPERATIONS},
        'src': SRC,
        'capped': max(len(comps) - len(current), 0),
        'current': current_view,
        'target': target_view,
    }
