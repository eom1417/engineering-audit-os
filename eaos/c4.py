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


def write(report):
    """Write both models; returns the files for their validator. Nothing is written without a target record."""
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
    models = {'current': ([(c['name'], c.get('reason') or c.get('relation') or '') for c in current], current_edges)}
    if target.get('target_components'):
        models['target'] = ([(c['name'], c.get('responsibility') or '') for c in target['target_components']],
                            [(e['from'], e['to'], f"{e['imports']} import(s)") for e in target.get('target_edges') or []])
    written = []
    for kind, (components, edges) in models.items():
        folder = report / 'architecture' / kind
        folder.mkdir(parents=True, exist_ok=True)
        dsl, mermaid = workspace(project, _stack(target), components, edges, externals)
        (folder / 'workspace.dsl').write_text(dsl, encoding='utf-8')
        (folder / 'diagram.mmd').write_text(mermaid, encoding='utf-8')
        written.append(Emitted(f'architecture/{kind}/workspace.dsl', 'structurizr-cli',
                               ('structurizr', 'validate', '-workspace', '{path}')))
    return written
