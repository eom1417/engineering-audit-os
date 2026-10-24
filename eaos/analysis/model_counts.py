"""The counts and scales the report's views show (eaos/report/human_report/, the Studio), each computed once here so no
view counts on its own (eaos/analysis/model.py holds the problems, the score and the cards they count).
"""


def remaining(items, shown):
    return max(0, len(items) - shown)


def structure_counts(target):
    current = target.get('current_components') or target.get('components') or []
    components = target.get('target_components') or []
    relations = {}
    for component in current:
        relation = component.get('relation')
        relations[relation] = relations.get(relation, 0) + 1
    return {'relations': relations, 'current': len(current), 'target': len(components),
            'layers': len({c.get('layer') for c in components}),
            'moves': sum(g.get('files_to_move') or 0 for g in target.get('gap_matrix') or [])}


def layer_counts(members):
    return {'parts': len(members), 'files': sum(c.get('files') or 0 for c in members)}


def density_counts(files, found):
    density = found / max(files, 1)
    return {'size': max(files, 1), 'density': density, 'per_ten': round(density * 10)}


def architecture_counts(cmap):
    return {'parts': len(cmap['nodes']), 'links': len(cmap['edges']),
            'loops': sum(e['cycle'] for e in cmap['edges']), 'wrong': sum(e['wrong'] for e in cmap['edges'])}


def system_counts(sm):
    counts = {key: len(sm[key]) for key in ('pages', 'callers', 'apis', 'handlers', 'modules', 'data')}
    counts.update(answered=sum(bool(a['handlers']) for a in sm['apis']),
                  tables=sum(d['id'].startswith('T:') for d in sm['data']),
                  untraced=sum(not p['traced'] for p in sm['pages']))
    counts['services'] = counts['data'] - counts['tables']
    counts['columns'] = (counts['pages'] + counts['callers'], counts['apis'], counts['handlers'], counts['modules'], counts['data'])
    return counts


def collection_count(items):
    return len(items)


def all_card_count(groups):
    return sum(len(cards) for _, _, cards in groups)


def problems_left(totals):
    return totals['total'] - totals['closed']


def unparsed_count(coverage):
    return (coverage.get('source_files') or 0) - (coverage.get('files_parsed') or 0)


def history_scale(points):
    top = max(h['percent'] for h in points)
    return next((s for s in (5, 10, 20, 25, 50, 100) if s >= top * 1.1), 100)


def history_ticks(points):
    scale = history_scale(points)
    return (0, scale / 2, scale)


def drill_counts(drill):
    """Displayed drill counts, including the same truncation as the drawing."""
    if not drill: return drill
    reverse = [[] for _ in drill['files']]
    for source, imports in enumerate(drill['imports']):
        for destination in imports: reverse[destination].append(source)
    for component in drill['comps']: component['counts'] = _component_counts(component, drill['imports'], reverse)
    outgoing, incoming = {}, {}
    for call in drill['calls']:
        outgoing.setdefault(call[0], []).append(call)
        incoming.setdefault(call[2], []).append(call)
    drill['file_counts'] = [_file_counts(f, own, outgoing.get(f, []), incoming.get(f, [])) for f, own in enumerate(drill['functions'])]
    return drill


def _component_counts(component, imports, reverse):
    files = sorted(component['files'], key=lambda f: -(len(reverse[f]) + len(imports[f])))[:30]
    selected = set(files)
    return {'inside': sum(g in selected for f in files for g in imports[f]),
            'shown': len(files), 'more': len(component['files']) - len(files),
            'used_by': len(component['used_by']), 'uses': len(component['uses'])}


def _file_counts(f, own, outgoing, incoming):
    """A file's functions, and the calls in and out of the 30 it draws (at most 14 a side)."""
    touched = {}
    for call in outgoing: touched[call[1]] = touched.get(call[1], 0) + 1
    for call in incoming: touched[call[3]] = touched.get(call[3], 0) + 1
    selected = set(sorted(own, key=lambda name: -touched.get(name, 0))[:30])
    left = {(c[0], c[1]) for c in incoming if c[0] != f and c[3] in selected}
    right = {(c[2], c[3]) for c in outgoing if c[2] != f and c[1] in selected}
    return {'own': len(own), 'left': min(len(left), 14), 'right': min(len(right), 14)}


def system_details(sm):
    """Counts shown by each selectable system node and feature."""
    if not sm: return sm
    for node in (node for group in ('pages', 'callers', 'apis', 'handlers', 'modules', 'data') for node in sm[group]):
        node['counts'] = _node_counts(node, sm['related'].get(node['id'], []))
    sm['feature_counts'] = {feature['name']: len(feature['pages']) for feature in sm['features']}
    return sm


def _node_counts(node, related):
    groups = {kind: sum(item.startswith(kind) and item != node['id'] for item in related) for kind in 'PCAHMTS'}
    return {'calls': len(node.get('calls') or []), 'shared': len(node.get('shared') or []),
            'pages': len(node.get('pages') or []), 'groups': groups,
            'more': {kind: max(0, count - 40) for kind, count in groups.items()}}


def pipeline_counts(section, pipelines=None, shown=60):
    """Scalar labels for the report's selected pipelines, from the Studio section."""
    pipelines = section.get('pipelines') or [] if pipelines is None else pipelines
    ids = {p['id'] for p in pipelines}
    confidence = section.get('confidence', {}).get('value')
    return {'stages': {p['id']: len(p['stages']) for p in pipelines},
            'drawn': {p['id']: sum(s['pipeline'] == p['id'] for s in section['stages']) for p in pipelines},
            'more': max(0, sum(s['pipeline'] in ids for s in section['stages']) - shown),
            'confidence': round(confidence * 100) if confidence is not None else '—'}
