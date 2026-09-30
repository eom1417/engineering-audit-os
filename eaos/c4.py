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

from .emit.base import Emitted


def quote(text):
    return '"' + str(text).replace('\\', '\\\\').replace('"', '\\"') + '"'


def _load(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def _stack(target):
    return target.get('reference') or 'application'


def _externals(report):
    from .emit.nfr import dependencies
    return [(name, 'Supabase' if name == 'supabase' else ('the project\'s own API' if name == 'api' else name))
            for name, _, _ in dependencies(report)]


def workspace(project, stack, components, edges, externals):
    """(dsl text, mermaid text) for one model; components [(name, description)], edges [(from, to, label)]."""
    ids = {name: f'c{index}' for index, (name, _) in enumerate(components, 1)}
    ext_ids = {name: f'ext{index}' for index, (name, _) in enumerate(externals, 1)}
    lines = [f'workspace {quote(project)} {{', '  model {', '    user = person "User"',
             f'    system = softwareSystem {quote(project)} {{',
             f'      app = container "Application" {quote(stack)} {{']
    for name, description in components:
        lines.append(f'        {ids[name]} = component {quote(name)} {quote(description[:200])}')
    lines += ['      }', '    }']
    for name, label in externals:
        lines.append(f'    {ext_ids[name]} = softwareSystem {quote(label)}')
    lines.append('    user -> app "uses"')
    for name, _ in externals:
        lines.append(f'    app -> {ext_ids[name]} "calls"')
    for source, sink, label in edges:
        if source in ids and sink in ids and source != sink:
            lines.append(f'    {ids[source]} -> {ids[sink]} {quote(label)}')
    lines += ['  }', '  views {', '    systemContext system {', '      include *', '      autolayout', '    }',
              '    container system {', '      include *', '      autolayout', '    }',
              '    component app {', '      include *', '      autolayout', '    }', '  }', '}', '']
    safe = lambda name: re.sub(r'[^A-Za-z0-9_]', '_', ids[name])
    mermaid = ['flowchart LR'] + [f'  {safe(name)}["{name.replace(chr(34), chr(39))}"]' for name, _ in components]
    mermaid += [f'  {safe(a)} --> {safe(b)}' for a, b, _ in edges if a in ids and b in ids and a != b]
    return '\n'.join(lines), '\n'.join(mermaid) + '\n'


MAX_EDGES = 150


def readable(names, edges, group_of, cycles=(), limit=MAX_EDGES, title=''):
    """A Mermaid flowchart a person reads in VS Code: the parts in one subgraph per layer (or top folder), each link
    labelled with its import count, strongest first and capped at `limit` (a comment says how many are left out),
    and the links inside an import loop drawn red. edges: [(from, to, count or None)]."""
    ids = {name: f'c{index}' for index, name in enumerate(names, 1)}
    q = lambda text: str(text).replace('"', "'")
    lines = ['flowchart LR'] + ([f'  %% {title}'] if title else [])
    groups = {}
    for name in names: groups.setdefault(group_of.get(name) or 'other', []).append(name)
    for number, (group, members) in enumerate(sorted(groups.items()), 1):
        lines.append(f'  subgraph g{number}["{q(group)}"]')
        lines += [f'    {ids[n]}["{q(n)}"]' for n in members]
        lines.append('  end')
    kept = sorted(((a, b, n) for a, b, n in edges if a in ids and b in ids and a != b), key=lambda e: (-(e[2] or 0), e[0], e[1]))
    if len(kept) > limit:
        lines.append(f'  %% {len(kept) - limit} of the {len(kept)} links are left out: only the {limit} strongest are drawn')
    red = []
    for index, (a, b, n) in enumerate(kept[:limit]):
        lines.append(f'  {ids[a]} -->|{n} imports| {ids[b]}' if n else f'  {ids[a]} --> {ids[b]}')
        if (a, b) in cycles: red.append(str(index))
    if red:
        lines.append('  %% red: the link is inside an import loop (each end reaches the other)')
        lines.append(f'  linkStyle {",".join(red)} stroke:#d03b3b,stroke-width:2px')
    return '\n'.join(lines) + '\n'


def _current_diagram(report, target, current):
    """Today's parts, grouped by the target layer they go to (else their top folder), with the import counts and loops
    of facts/graph.json (eaos/arch_map.py); with no graph, the package dependencies, unlabelled."""
    from . import arch_map
    layer = {c.get('name'): c.get('layer') for c in target.get('target_components') or [] if isinstance(c, dict)}
    names = [c['name'] for c in current]
    group_of = {c['name']: layer.get(c.get('target_component')) or '/'.join(c['name'].split('/')[:2]) for c in current}
    try: cmap = arch_map.component_map(report, target)
    except Exception: cmap = None
    if cmap:
        name_of = {n['id']: n['name'] for n in cmap['nodes']}
        edges = [(name_of[e['from']], name_of[e['to']], e['n']) for e in cmap['edges']]
        cycles = {(name_of[e['from']], name_of[e['to']]) for e in cmap['edges'] if e['cycle']}
    else:
        by_package = {('' if c.get('origin') == '.' else c.get('origin')): c['name'] for c in current}
        edges = [(c['name'], by_package[d], None) for c in current for d in c.get('depends_on') or [] if d in by_package]
        cycles = set()
    return readable(names, edges, group_of, cycles, title="today's parts; a label is the number of imports along the link")


def _target_diagram(target):
    from .arch_map import strong_groups
    comps = [c for c in target.get('target_components') or [] if isinstance(c, dict) and c.get('name')]
    names = [c['name'] for c in comps]
    edges = [(e['from'], e['to'], e.get('imports')) for e in target.get('target_edges') or [] if isinstance(e, dict)]
    group = strong_groups(names, [(a, b) for a, b, _ in edges if a in names and b in names])
    cycles = {(a, b) for a, b, _ in edges if a in group and b in group and group[a] == group[b]}
    return readable(names, edges, {c['name']: c.get('layer') for c in comps}, cycles,
                    title='the target parts by layer; only the links the layer rules allow')


def write(report):
    """Write both models; returns the files for their validator. Nothing is written without a target record.
    Beside them, architecture/system.mmd: pages, APIs, server handlers and data (eaos/system_map.py)."""
    report = Path(report)
    target = _load(report / 'target-architecture.json', None)
    if not target: return []
    project = ((_load(report / 'dossier.json', {}) or {}).get('provenance') or {}).get('target') or report.name
    project = Path(project).name
    externals = _externals(report)
    current = target.get('current_components') or []
    # depends_on names packages; a component's package is its origin ('.' is the root package, '').
    by_package = {('' if c.get('origin') == '.' else c.get('origin')): c['name'] for c in current}
    current_edges = [(c['name'], by_package[d], 'depends on') for c in current for d in c.get('depends_on') or [] if d in by_package]
    models = {'current': ([(c['name'], c.get('reason') or c.get('relation') or '') for c in current], current_edges,
                          lambda: _current_diagram(report, target, current))}
    if target.get('target_components'):
        models['target'] = ([(c['name'], c.get('responsibility') or '') for c in target['target_components']],
                            [(e['from'], e['to'], f"{e['imports']} import(s)") for e in target.get('target_edges') or []],
                            lambda: _target_diagram(target))
    written = []
    for kind, (components, edges, diagram) in models.items():
        folder = report / 'architecture' / kind
        folder.mkdir(parents=True, exist_ok=True)
        dsl, mermaid = workspace(project, _stack(target), components, edges, externals)
        try: mermaid = diagram()
        except Exception: pass                  # the plain flowchart stays: a diagram is never a reason to fail
        (folder / 'workspace.dsl').write_text(dsl, encoding='utf-8')
        (folder / 'diagram.mmd').write_text(mermaid, encoding='utf-8')
        written.append(Emitted(f'architecture/{kind}/workspace.dsl', 'structurizr-cli',
                               ('structurizr', 'validate', '-workspace', '{path}')))
    try:
        from . import system_map
        text = system_map.mermaid(system_map.build(report))
        if text: (report / 'architecture' / 'system.mmd').write_text(text, encoding='utf-8')
    except Exception:
        pass
    return written
