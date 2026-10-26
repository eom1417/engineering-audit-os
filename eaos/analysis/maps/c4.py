"""C4 models of today's system and of its target, as Structurizr DSL and as Mermaid, written from the records.

architecture/current/workspace.dsl   the user, the external systems the facts show, the application and its
                                     database as containers, and every current component with the
                                     dependencies between them (target-architecture.json -> current_components).
architecture/target/workspace.dsl    the same context, and every target component with only the
                                     dependencies the reference type's layer rules allow (target_edges).
architecture/*/diagram.mmd           the component view as a Mermaid flowchart, for the four reports.

The model is text EAOS writes; no Structurizr library is used. The Structurizr CLI (pinned, on its pinned
JRE) parses and validates each workspace, so a model that names an element twice or breaks the grammar is
rejected by the tool itself. Names are the records' names, quoted and escaped; identifiers are generated.
"""
import json
import re
from pathlib import Path



def quote(text):
    return '"' + str(text).replace('\\', '\\\\').replace('"', '\\"') + '"'


def _load(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def _stack(target):
    return target.get('reference') or 'application'


def _externals(report):
    from ...live.trials.load_plans import dependencies
    return [(name, 'Supabase' if name == 'supabase' else ('the project\'s own API' if name == 'api' else name))
            for name, _, _ in dependencies(report)]


def workspace(project, stack, components, edges, externals):
    """(dsl text, mermaid text) for one model; components [(name, description)], edges [(from, to, label)]."""
    ids = {name: f'c{index}' for index, (name, _) in enumerate(components, 1)}
    lines = _model_lines(project, stack, components, edges, externals, ids)
    lines += ['  }', '  views {', '    systemContext system {', '      include *', '      autolayout', '    }',
              '    container system {', '      include *', '      autolayout', '    }',
              '    component app {', '      include *', '      autolayout', '    }', '  }', '}', '']
    return '\n'.join(lines), _plain_mermaid(components, edges, ids)


def _model_lines(project, stack, components, edges, externals, ids):
    """The DSL's model: the user, the system with its components, the outside systems and every link."""
    ext_ids = {name: f'ext{index}' for index, (name, _) in enumerate(externals, 1)}
    lines = [f'workspace {quote(project)} {{', '  model {', '    user = person "User"',
             f'    system = softwareSystem {quote(project)} {{',
             f'      app = container "Application" {quote(stack)} {{']
    lines += [f'        {ids[name]} = component {quote(name)} {quote(description[:200])}' for name, description in components]
    lines += ['      }', '    }']
    lines += [f'    {ext_ids[name]} = softwareSystem {quote(label)}' for name, label in externals]
    lines.append('    user -> app "uses"')
    lines += [f'    app -> {ext_ids[name]} "calls"' for name, _ in externals]
    lines += [f'    {ids[source]} -> {ids[sink]} {quote(label)}' for source, sink, label in edges
              if source in ids and sink in ids and source != sink]
    return lines


def _plain_mermaid(components, edges, ids):
    safe = lambda name: re.sub(r'[^A-Za-z0-9_]', '_', ids[name])
    mermaid = ['flowchart LR'] + [f'  {safe(name)}["{name.replace(chr(34), chr(39))}"]' for name, _ in components]
    mermaid += [f'  {safe(a)} --> {safe(b)}' for a, b, _ in edges if a in ids and b in ids and a != b]
    return '\n'.join(mermaid) + '\n'


MAX_EDGES = 150


def readable(names, edges, group_of, cycles=(), limit=MAX_EDGES, title=''):
    """A Mermaid flowchart a person reads in VS Code: the parts in one subgraph per layer (or top folder), each link
    labelled with its import count, strongest first and capped at `limit` (a comment says how many are left out),
    and the links inside an import loop drawn red. edges: [(from, to, count or None)]."""
    ids = {name: f'c{index}' for index, name in enumerate(names, 1)}
    lines = ['flowchart LR'] + ([f'  %% {title}'] if title else []) + _subgraphs(names, group_of, ids)
    kept = sorted(((a, b, n) for a, b, n in edges if a in ids and b in ids and a != b), key=lambda e: (-(e[2] or 0), e[0], e[1]))
    if len(kept) > limit:
        lines.append(f'  %% {len(kept) - limit} of the {len(kept)} links are left out: only the {limit} strongest are drawn')
    return '\n'.join(lines + _links(kept[:limit], ids, cycles)) + '\n'


def _quoted(text):
    return str(text).replace('"', "'")


def _subgraphs(names, group_of, ids):
    """One subgraph per layer (or top folder), its parts inside."""
    groups, lines = {}, []
    for name in names: groups.setdefault(group_of.get(name) or 'other', []).append(name)
    for number, (group, members) in enumerate(sorted(groups.items()), 1):
        lines += [f'  subgraph g{number}["{_quoted(group)}"]'] + [f'    {ids[n]}["{_quoted(n)}"]' for n in members] + ['  end']
    return lines


def _links(kept, ids, cycles):
    """The links, labelled with their import count, the ones inside an import loop styled red."""
    lines = [f'  {ids[a]} -->|{n} imports| {ids[b]}' if n else f'  {ids[a]} --> {ids[b]}' for a, b, n in kept]
    red = [str(index) for index, (a, b, _) in enumerate(kept) if (a, b) in cycles]
    if red:
        lines.append('  %% red: the link is inside an import loop (each end reaches the other)')
        lines.append(f'  linkStyle {",".join(red)} stroke:#d03b3b,stroke-width:2px')
    return lines


def _current_diagram(report, target, current):
    """Today's parts, grouped by the target layer they go to (else their top folder), with the import counts and loops
    of facts/graph.json (eaos/analysis/maps/architecture.py); with no graph, the package dependencies, unlabelled."""
    from . import architecture as arch_map
    layer = {c.get('name'): c.get('layer') for c in target.get('target_components') or [] if isinstance(c, dict)}
    names = [c['name'] for c in current]
    group_of = {c['name']: layer.get(c.get('target_component')) or '/'.join(c['name'].split('/')[:2]) for c in current}
    try: cmap = arch_map.component_map(report, target)
    except Exception: cmap = None
    edges, cycles = _current_links(cmap, current)
    return readable(names, edges, group_of, cycles, title="today's parts; a label is the number of imports along the link")


def _package_edges(current, label):
    """The links between today's components by the packages they depend on: depends_on names packages, and a
    component's package is its origin ('.' is the root package, '')."""
    by_package = {('' if c.get('origin') == '.' else c.get('origin')): c['name'] for c in current}
    return [(c['name'], by_package[d], label) for c in current for d in c.get('depends_on') or [] if d in by_package]


def _current_links(cmap, current):
    """(edges, cycles) of today's parts: the import counts and loops of the component map, else the package links."""
    if not cmap: return _package_edges(current, None), set()
    name_of = {n['id']: n['name'] for n in cmap['nodes']}
    return ([(name_of[e['from']], name_of[e['to']], e['n']) for e in cmap['edges']],
            {(name_of[e['from']], name_of[e['to']]) for e in cmap['edges'] if e['cycle']})


def _in_loops(names, edges):
    """The links whose two ends are in one strongly connected group of the parts: each reaches the other."""
    from .layout import strong_groups
    group = strong_groups(names, [(a, b) for a, b, _ in edges if a in names and b in names])
    return {(a, b) for a, b, _ in edges if a in group and b in group and group[a] == group[b]}


def _target_diagram(target):
    comps = [c for c in target.get('target_components') or [] if isinstance(c, dict) and c.get('name')]
    names = [c['name'] for c in comps]
    edges = [(e['from'], e['to'], e.get('imports')) for e in target.get('target_edges') or [] if isinstance(e, dict)]
    return readable(names, edges, {c['name']: c.get('layer') for c in comps}, _in_loops(names, edges),
                    title='the target parts by layer; only the links the layer rules allow')


def write(report):
    """Write both models; returns the files written. Nothing is written without a target record.
    Beside them, architecture/system.mmd: pages, APIs, server handlers and data (eaos/analysis/maps/system.py)."""
    report = Path(report)
    target = _load(report / 'target-architecture.json', None)
    if not target: return []
    project = ((_load(report / 'dossier.json', {}) or {}).get('provenance') or {}).get('target') or report.name
    project = Path(project).name
    externals = _externals(report)
    written = []
    for kind, model in _models(report, target).items():
        _write_model(report / 'architecture' / kind, (project, _stack(target), externals), model)
        written.append(f'architecture/{kind}/workspace.dsl')
    _write_system_map(report)
    return written


def _models(report, target):
    """{current, target}: each (components, edges, the readable diagram's maker); the target only when it has parts."""
    current = target.get('current_components') or []
    models = {'current': ([(c['name'], c.get('reason') or c.get('relation') or '') for c in current],
                          _package_edges(current, 'depends on'), lambda: _current_diagram(report, target, current))}
    if target.get('target_components'):
        models['target'] = ([(c['name'], c.get('responsibility') or '') for c in target['target_components']],
                            [(e['from'], e['to'], f"{e['imports']} import(s)") for e in target.get('target_edges') or []],
                            lambda: _target_diagram(target))
    return models


def _write_model(folder, system, model):
    """workspace.dsl and diagram.mmd of one model; `system` is (project, stack, externals)."""
    components, edges, diagram = model
    folder.mkdir(parents=True, exist_ok=True)
    dsl, mermaid = workspace(*system[:2], components, edges, system[2])
    try: mermaid = diagram()
    except Exception: pass                  # the plain flowchart stays: a diagram is never a reason to fail
    (folder / 'workspace.dsl').write_text(dsl, encoding='utf-8')
    (folder / 'diagram.mmd').write_text(mermaid, encoding='utf-8')


def _write_system_map(report):
    """architecture/system.mmd: pages, APIs, server handlers and data; never a reason to fail."""
    try:
        from . import system_drawing, system as system_map
        text = system_drawing.mermaid(system_map.build(report))
        if text: (report / 'architecture' / 'system.mmd').write_text(text, encoding='utf-8')
    except Exception:
        pass
