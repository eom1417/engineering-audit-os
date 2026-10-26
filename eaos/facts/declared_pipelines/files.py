"""Pipelines declared in build, CI and workflow files (GitHub Actions `needs`, Make and just targets, npm script
chains, Step Functions, n8n, Node-RED exports), read as text without running them (eaos/facts/declared_pipelines/detect.py)."""
import json
import re
from collections import defaultdict
from pathlib import Path

from .read import slug, site, Found


def _need_values(value):
    """The jobs a `needs:` value names on its own line: a list in brackets or one name."""
    if value.startswith('['): return [v.strip(' "\'') for v in value.strip('[]').split(',') if v.strip()]
    return [value.strip('"\'')] if value else []


def _read_jobs(lines, jobs_at):
    """{job: {line, needs, needs_line}} of a workflow's `jobs:` block, its `needs` inline or as a list below."""
    jobs, current, indent, needs_line = {}, None, None, None
    for number, line, depth in _block_lines(lines, jobs_at):
        match = re.match(r'^(\s*)([A-Za-z0-9_-]+):\s*(#.*)?$', line)
        if match and indent in (None, depth):   # the first key sets the jobs' indent
            indent, current, needs_line = depth, match.group(2), None
            jobs[current] = {'line': number, 'needs': [], 'needs_line': None}
            continue
        if current is None: continue
        need = re.match(r'^\s*needs:\s*(.*)$', line)
        if need and depth == indent + 2:
            value = need.group(1).split('#')[0].strip()
            jobs[current]['needs_line'] = number
            jobs[current]['needs'] += _need_values(value)
            if not value: needs_line = depth
            continue
        if needs_line is not None:
            item = _list_item(line, depth, needs_line)
            if item:
                jobs[current]['needs'].append(item)
                continue
            needs_line = None
    return jobs


def _block_lines(lines, start):
    """(number, line, indent) of each line of the block under line `start`, blank lines and comments aside."""
    for number, line in enumerate(lines[start + 1:], start=start + 2):
        if not line.strip() or line.lstrip().startswith('#'): continue
        depth = len(line) - len(line.lstrip())
        if depth == 0: return
        yield number, line, depth


def _list_item(line, depth, under):
    """The name a `- name` line lists, when it is indented under the key at depth `under`; None otherwise."""
    item = re.match(r'^\s*-\s*([A-Za-z0-9_-]+)', line)
    return item.group(1) if item and depth > under else None


def github_actions(rel, text, out):
    lines = text.splitlines()
    jobs_at = next((i for i, line in enumerate(lines) if re.match(r'^jobs:\s*$', line)), None)
    if jobs_at is None: return
    jobs = _read_jobs(lines, jobs_at)
    if not any(job['needs'] for job in jobs.values()): return
    found = Found(f'{rel}:jobs', f'{Path(rel).name} jobs', 'github_actions', site(rel, jobs_at + 1, lines[jobs_at]),
                  [site(rel, jobs_at + 1, lines[jobs_at])])
    for name, job in jobs.items(): found.stage(name, site(rel, job['line'], lines[job['line'] - 1]))
    for name, job in jobs.items():
        at = job['needs_line'] or job['line']
        for need in job['needs']:
            found.edge(f'{found.id}/{slug(need)}', f'{found.id}/{slug(name)}', 'declared', site(rel, at, lines[at - 1]), kind='control')
    _fans(found)
    out.append(found)


def _targets(lines, kind):
    """{target: (line, [targets it depends on])} of a Makefile or a justfile."""
    targets = {}
    pattern = re.compile(r'^([A-Za-z0-9_.\-/]+)\s*:(?!=)\s*([^#=]*)$' if kind == 'makefile' else r'^@?([A-Za-z0-9_-]+)(?:\s+[^:]*)?:\s*([^#=]*)$')
    for number, line in enumerate(lines, start=1):
        match = pattern.match(line)
        if match and not match.group(1).startswith('.'):
            targets[match.group(1)] = (number, [t for t in match.group(2).split() if not t.startswith(('$', '"', "'"))])
    return targets


def make_targets(rel, text, out, kind):
    lines = text.splitlines()
    targets = _targets(lines, kind)
    edges = [(need, name) for name, (_, needs) in targets.items() for need in needs if need in targets]
    if len(edges) < 2: return
    found = Found(f'{rel}:targets', f'{Path(rel).name} targets', kind, site(rel, 1, lines[0] if lines else ''))
    for name, (number, _) in targets.items():
        if any(name in edge for edge in edges): found.stage(name, site(rel, number, lines[number - 1]))
    for need, name in edges:
        found.edge(f'{found.id}/{slug(need)}', f'{found.id}/{slug(name)}', 'declared', site(rel, targets[name][0], lines[targets[name][0] - 1]), kind='control')
    out.append(found)


def npm_scripts(rel, text, out):
    try: scripts = (json.loads(text) or {}).get('scripts') or {}
    except (ValueError, AttributeError): return
    lines = text.splitlines()
    for name, command in scripts.items():
        if not isinstance(command, str) or '&&' not in command: continue
        parts = [p.strip() for p in command.split('&&') if p.strip()]
        if len(parts) >= 2: out.append(_npm_chain(rel, name, parts, lines))


def _npm_chain(rel, name, parts, lines):
    """One npm script chaining commands with `&&`: a stage per command (the script it runs), each after the one before."""
    number = next((i for i, line in enumerate(lines, start=1) if re.search(rf'"{re.escape(name)}"\s*:', line)), 1)
    found = Found(f'{rel}:{name}', f'npm run {name}', 'npm_scripts', site(rel, number, lines[number - 1] if lines else ''),
                  [site(rel, number, lines[number - 1] if lines else '')])
    previous = None
    for part in parts:
        match = re.match(r'^(?:npm|pnpm|yarn|bun)(?:\s+run)?\s+([A-Za-z0-9:_.-]+)', part)
        label = match.group(1) if match else part
        key = found.stage(label, site(rel, number, lines[number - 1]))
        found.stages[key]['tools'] = [part.split()[0]]
        if previous: found.edge(previous, key, 'order', site(rel, number, lines[number - 1]), kind='control')
        previous = key
    return found


def json_exports(rel, text, out):
    if not text.lstrip().startswith(('{', '[')) or len(text) > 2_000_000: return
    try: data = json.loads(text)
    except ValueError: return
    lines = text.splitlines()
    line_of = lambda word: next((i for i, line in enumerate(lines, start=1) if word in line), 1)
    if isinstance(data, dict) and isinstance(data.get('States'), dict) and data.get('StartAt'):
        out.append(_step_functions(rel, data, line_of))
        return
    found = _flow_export(rel, data, line_of)
    if found and found.edges: out.append(found)


def _flow_export(rel, data, line_of):
    """The n8n workflow or Node-RED flow a JSON file exports, or None."""
    if isinstance(data, dict) and isinstance(data.get('nodes'), list) and isinstance(data.get('connections'), dict):
        return _n8n(rel, data, line_of)
    if isinstance(data, list) and data and all(isinstance(n, dict) for n in data) and any('wires' in n for n in data):
        return _node_red(rel, data, line_of)
    return None


def _step_functions(rel, data, line_of):
    """A Step Functions state machine: its states, their next states, its choices and its catches."""
    found = Found(f'{rel}:states', f'{Path(rel).name} state machine', 'step_functions', site(rel, line_of('"StartAt"'), None))
    for name in data['States']: found.stage(name, site(rel, line_of(f'"{name}"'), None))
    for name, state in data['States'].items():
        if isinstance(state, dict): _state_links(found, name, state, data['States'], site(rel, line_of(f'"{name}"'), None))
    return found


def _state_links(found, name, state, states, where):
    """One state's edges to its next, default and chosen states, its choice router and its catches."""
    stage, choices = f'{found.id}/{slug(name)}', [c for c in state.get('Choices') or [] if isinstance(c, dict)]
    for target in [state.get('Next'), state.get('Default')] + [c.get('Next') for c in choices]:
        if target in states: found.edge(stage, f'{found.id}/{slug(target)}', 'declared', where)
    if state.get('Type') == 'Choice':
        found.routers.append({'id': f'{found.id}:{slug(name)}', 'pipeline': found.id, 'stage': stage, 'kind': 'switch',
                              'table': name, 'on': name, 'entry': where,
                              'branches': [{'condition': _unparse_choice(c), 'to': f"{found.id}/{slug(c.get('Next'))}", 'evidence': where}
                                           for c in choices],
                              'total': bool(state.get('Default')), 'default': state.get('Default'), 'unhandled': []})
    _state_catches(found, name, stage, state.get('Catch') or [], where)


def _state_catches(found, name, stage, catches, where):
    """A state's catches: an error lane to the state each one sends its failures to."""
    for catch in catches:
        if isinstance(catch, dict) and catch.get('Next'):
            found.errors.append({'id': f'{found.id}:{slug(name)}:catch', 'pipeline': found.id, 'from': stage,
                                 'to': catch['Next'], 'kind': 'catch', 'condition': ','.join(catch.get('ErrorEquals') or []),
                                 'evidence': where})


def _n8n(rel, data, line_of):
    """An n8n workflow: its nodes and their main connections."""
    found = Found(f'{rel}:n8n', str(data.get('name') or Path(rel).stem), 'n8n', site(rel, line_of('"nodes"'), None))
    for node in data['nodes']:
        if isinstance(node, dict) and node.get('name'): found.stage(node['name'], site(rel, line_of(f'"{node["name"]}"'), None))
    for source, outputs in data['connections'].items():
        for target in _main_targets(outputs):
            found.edge(f'{found.id}/{slug(source)}', f"{found.id}/{slug(target.get('node'))}", 'declared', site(rel, line_of(f'"{source}"'), None))
    return found


def _main_targets(outputs):
    """The nodes an n8n node's main outputs connect to."""
    return [target for lane in (outputs or {}).get('main') or [] for target in lane or [] if isinstance(target, dict)]


def _node_red(rel, data, line_of):
    """A Node-RED flow: its wired nodes and their wires."""
    found = Found(f'{rel}:flow', Path(rel).stem, 'node_red', site(rel, 1, None))
    ids = {n.get('id'): n.get('name') or n.get('type') or n.get('id') for n in data if n.get('id')}
    for node in data:
        if node.get('id') and node.get('wires') is not None: found.stage(ids[node['id']], site(rel, line_of(f'"{node["id"]}"'), None))
    for node in data:
        for target in _wired(node, ids):
            found.edge(f'{found.id}/{slug(ids[node["id"]])}', f'{found.id}/{slug(ids[target])}', 'declared', site(rel, line_of(f'"{node["id"]}"'), None))
    return found


def _wired(node, ids):
    """The known nodes a Node-RED node's wires lead to."""
    return [target for port in node.get('wires') or [] for target in port or [] if target in ids]


def _unparse_choice(choice):
    keys = [k for k in choice if k not in ('Next',)]
    return ' '.join(f'{k}={choice[k]}' for k in keys)[:80] or 'choice'


def _fans(found):
    """Forks (one stage feeding several) and their joins (one stage fed by all of them)."""
    outgoing, incoming = defaultdict(list), defaultdict(set)
    for a, b in found.edges: outgoing[a].append(b); incoming[b].add(a)
    for fork, branches in outgoing.items():
        if len(branches) < 2: continue
        joins = [stage for stage, sources in incoming.items() if set(branches) <= sources]
        found.fans.append({'id': f'{fork}:fan', 'pipeline': found.id, 'fork': fork, 'join': joins[0] if joins else None,
                           'branches': branches, 'matched': bool(joins), 'kind': 'parallel', 'evidence': found.stages[fork]['entry']})

