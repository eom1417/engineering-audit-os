"""Code reached but never run (M13.2): what ran of the project while EAOS ran its tests, its server and its pages
(eaos/live/testing/ran.py, <out>/live/ran-*.json), read against its own functions (the `syntax` facts).

A function is never run when its file was measured (some run read it: a function of it ran, or its lines did) and no run
ran it: neither its name among the functions a run ran (Node, the browser) nor any line of its body (Coverage.py). A
module is never run when an entry point reaches it (the graph), runs of its language were measured, and none read
it. Each is a suspect, not a verdict: a screen no page opened, an error no test raised, run nowhere here. What ran around
it is said: the functions of its file that ran, and for a module, the modules that import it that ran.
"""
from pathlib import Path, PurePosixPath

from ...core.contracts.vocabulary import classify
from ...core.system.files import read_json

KINDS = ('tests', 'server', 'browser')
FAMILIES = {'.py': 'python', '.js': 'js', '.jsx': 'js', '.mjs': 'js', '.cjs': 'js', '.ts': 'js', '.tsx': 'js', '.vue': 'js', '.svelte': 'js'}
AROUND = 4


def records(out):
    """{kind: its record} of the runs that left one."""
    found = {kind: read_json(Path(out) / 'live' / f'ran-{kind}.json') for kind in KINDS}
    return {kind: record for kind, record in found.items() if record is not None}


def ran_files(found):
    """{path: {'ran': set, 'lines': set}} over every run: a function ran when any run ran it."""
    files = {}
    for record in found.values():
        for path, row in (record.get('files') or {}).items():
            into = files.setdefault(path, {'ran': set(), 'lines': set()})
            into['ran'].update(row.get('ran') or ())
            into['lines'].update(n for first, last in row.get('lines') or () for n in range(first, last + 1))
    return files


def _own_function(fact, owners):
    """Whether a symbol is one of the project's functions: not a test, not a callback (no signature of its own, or a
    function's child), which runs or not with the one around it."""
    value, path = fact['value'], fact['location']['path']
    return (value.get('kind') in ('function', 'method') and value.get('signature') is not None
            and (path, value.get('parent')) not in owners and classify(path) == 'source')


def functions(sets):
    """The project's own functions: [{path, name, line, end_line}]."""
    facts = [f for f in (sets.get('syntax') or {}).get('facts', []) if f['kind'] == 'symbol']
    owners = {(f['location']['path'], f['value']['name']) for f in facts if f['value'].get('kind') == 'function'}
    return [{'path': f['location']['path'], 'name': f['value']['name'], 'line': f['location']['start_line'],
             'end_line': f['location'].get('end_line') or f['location']['start_line']} for f in facts if _own_function(f, owners)]


def did_run(function, row):
    """Whether a run ran the function: by its name, or by a line of its body."""
    if function['name'] in row['ran']: return True
    return any(n in row['lines'] for n in range(function['line'] + 1, function['end_line'] + 1)) or (
        function['line'] == function['end_line'] and function['line'] in row['lines'])


def never_run_functions(sets, found):
    """{path: {'never': [names], 'around': [names that ran]}} for the measured files."""
    files, out = ran_files(found), {}
    for function in functions(sets):
        row = files.get(function['path'])
        if row is None: continue
        entry = out.setdefault(function['path'], {'never': [], 'around': []})
        entry['around' if did_run(function, row) else 'never'].append(function['name'])
    return {path: {'never': sorted(set(e['never'])), 'around': sorted(set(e['around']))[:AROUND]}
            for path, e in sorted(out.items()) if e['never']}


def _family(path): return FAMILIES.get(PurePosixPath(path).suffix)


def _graph(sets):
    """(graph nodes, {module: the modules that import it})."""
    nodes = [f for f in (sets.get('graph') or {}).get('facts', []) if f['kind'] == 'graph_node']
    importers = {}
    for node in nodes:
        for target in node['value'].get('depends_on') or []: importers.setdefault(target, []).append(node['location']['path'])
    return nodes, importers


def _unread(node, files, families):
    """Whether an entry point reaches the module, runs of its language were measured, and none read it."""
    path = node['location']['path']
    return (node['value'].get('entry_distance') is not None and path not in files and _family(path) in families
            and classify(path) == 'source')


def never_run_modules(sets, found):
    """[{path, around}]: modules an entry point reaches, of a language some run measured, that no run read; `around`:
    the modules importing it that ran."""
    files, (nodes, importers) = ran_files(found), _graph(sets)
    families = {_family(path) for path in files} - {None}
    return [{'path': node['location']['path'], 'around': sorted(p for p in importers.get(node['location']['path'], []) if p in files)[:AROUND]}
            for node in sorted(nodes, key=lambda n: n['location']['path']) if _unread(node, files, families)]


def measured(found):
    """What was measured, in words: the runs that read code, and those that said why they read none."""
    return {kind: ('read' if record.get('files') else record.get('reason') or 'nothing read') for kind, record in found.items()}
