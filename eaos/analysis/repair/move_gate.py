"""What the move gate (M8.5) compares before and after a batch of moves, read from the copy alone:

    surface(root)                 the public surface: every entry point the code declares (endpoints, pages, commands),
                                  the commands a package declares (pyproject scripts, package.json bin and scripts) with
                                  the file each runs, and the names every source file exposes
    surface_differences(...)      each difference, the files' old places read through the moves
    test_results(output)          {test name: passed, failed or skipped} from what a test run printed (unittest -v,
                                  pytest -rA, TAP, jest and vitest), else the counts it printed
    test_differences(...)         each test not back with its name and result, each check whose exit changed

A move changes no behaviour: any difference refuses the batch whole (journeys/fix/move_batch.py).

Its limit: the surface is read inside the repository. The names each file exposes are compared through the moves, so a
module of a published package that moves keeps its names under a new import path, and whoever imports the old path
from outside the repository is not seen (PUBLISHED says so in the proposal)."""
import ast
import json
import re
import tempfile
import tomllib
from collections import Counter
from pathlib import Path, PurePosixPath

from .move_python import dotted
from ...core.system.files import read_json
from ...facts.repository.craft import normal_path

PUBLISHED = ('This project publishes a package (pyproject [project] or package.json without "private"): a moved module '
             'keeps its names under a new import path, and code outside this repository that imports the old path breaks. '
             'The gate reads this repository only.')
SURFACES = ('http', 'page', 'cli', 'graphql', 'rpc', 'websocket', 'job', 'event')
JS_EXPORT = re.compile(r'^\s*export\s+(?:default\s+(?:async\s+)?(?:function|class)?\s*(\w+)?|(?:declare\s+)?(?:async\s+)?'
                       r'(?:function\*?|class|const|let|var|type|interface|enum|abstract\s+class)\s+(\w+)|\{([^}]*)\}|\*\s+as\s+(\w+))', re.M)
UNITTEST = re.compile(r'^(\w+) \(([\w.]+)\)(?:\n[^\n]*?)? \.\.\. (ok|FAIL|ERROR|skipped|expected failure|unexpected success)', re.M)
PYTEST = re.compile(r'^(PASSED|FAILED|ERROR|XFAIL|XPASS) (\S+::\S+)', re.M)
TAP = re.compile(r'^\s*(not ok|ok) \d+ - (.+?)(?:\s+#\s*(SKIP|TODO)\b.*)?$', re.M | re.I)
MARKED = re.compile(r'^\s*(✓|√|✔|×|✕|✗|↓)\s+(.+?)(?:\s+\(?\d+(?:\.\d+)?\s*m?s\)?)?\s*$', re.M)
COUNTS = re.compile(r'(\d+)\s+(passed|failed|skipped|errors?)\b|Ran (\d+) tests?', re.I)
RESULT = {'ok': 'passed', 'passed': 'passed', 'xpass': 'passed', 'unexpected success': 'passed', '✓': 'passed', '√': 'passed',
          '✔': 'passed', 'fail': 'failed', 'failed': 'failed', 'error': 'failed', 'not ok': 'failed', '×': 'failed', '✕': 'failed',
          '✗': 'failed', 'skipped': 'skipped', 'expected failure': 'skipped', 'xfail': 'skipped', '↓': 'skipped'}


def surface(root, known):
    """{entries, commands, exports} of the code at `root`; `known` its files."""
    return {'entries': _entries(root), 'commands': commands(root, known), 'exports': exports(root, known)}


def _entries(root):
    """Every entry point the facts find (surface, method, route): what users and callers reach."""
    from ...facts.run import collect
    with tempfile.TemporaryDirectory(prefix='eaos-move-gate-') as out:
        collect(Path(root).resolve(), out, ['syntax', 'resolve', 'entrypoints'])
        facts = (read_json(Path(out) / 'facts/entrypoints.json') or {}).get('facts') or []
    rows = {(v.get('surface'), v.get('http_method'), v.get('route')) for v in (f.get('value') or {} for f in facts)
            if v.get('surface') in SURFACES and v.get('route')}
    return sorted(rows, key=str)


def commands(root, known):
    """{command: the file it runs} a package declares: pyproject's scripts (by module), package.json's bin (by file) and
    scripts (by name: their text is the move tool's to rewrite)."""
    out = {}
    for path in sorted(p for p in known if PurePosixPath(p).name in ('pyproject.toml', 'package.json')):
        text = _text(root, path)
        if text is None: continue
        if path.endswith('.toml'): out.update(_python_commands(text, known, PurePosixPath(path).parent.as_posix()))
        else: out.update(_node_commands(text, PurePosixPath(path).parent.as_posix()))
    return out


def _python_commands(text, known, folder):
    try: data = tomllib.loads(text)
    except tomllib.TOMLDecodeError: return {}
    project = data.get('project') or {}
    declared = {**(project.get('scripts') or {}), **(project.get('gui-scripts') or {}),
                **(((data.get('tool') or {}).get('poetry') or {}).get('scripts') or {})}
    return {f'script:{name}': _module_file(str(target).split(':')[0], known, folder) for name, target in declared.items()}


def _module_file(module, known, folder):
    """The file a dotted module name is read from (the package's folder, then its src/ layout)."""
    base = '' if folder in ('', '.') else folder + '/'
    stem = module.replace('.', '/')
    for candidate in (f'{base}{stem}.py', f'{base}{stem}/__init__.py', f'{base}src/{stem}.py', f'{base}src/{stem}/__init__.py'):
        if candidate in known: return candidate
    return f'missing:{module}'


def _node_commands(text, folder):
    try: data = json.loads(text)
    except ValueError: return {}
    base = '' if folder in ('', '.') else folder + '/'
    binaries = data.get('bin') or {}
    binaries = {data.get('name') or 'bin': binaries} if isinstance(binaries, str) else binaries
    out = {f'bin:{base}{name}': normal_path(base + str(target)) for name, target in binaries.items()}
    out.update({f'npm:{base}{name}': name for name in (data.get('scripts') or {})})
    return out


def published(root, known):
    """Whether the project publishes a package others import: pyproject's [project], or a package.json not private."""
    for path in (p for p in known if PurePosixPath(p).name in ('pyproject.toml', 'package.json')):
        text = _text(root, path) or ''
        if path.endswith('.toml') and re.search(r'(?m)^\[project\]', text): return True
        if path.endswith('.json') and '"name"' in text and not re.search(r'"private"\s*:\s*true', text): return True
    return False


def exports(root, known):
    """{file: the sorted names it exposes}: a Python module's public top-level names, a JavaScript or TypeScript module's
    exports. A test file exposes nothing anyone imports."""
    out = {}
    for path in sorted(known):
        suffix = PurePosixPath(path).suffix
        if suffix not in ('.py', '.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx'): continue
        text = _text(root, path)
        if text is None: continue
        names = _python_names(text) if suffix == '.py' else _js_names(text)
        if names is not None: out[path] = sorted(names)
    return out


def _python_names(text):
    try: tree = ast.parse(text)
    except SyntaxError: return None
    return {n for node in tree.body for n in _defined(node) if not n.startswith('_')}


def _defined(node):
    """The names one top-level statement binds."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): return {node.name}
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return {t.id for t in (node.targets if isinstance(node, ast.Assign) else [node.target]) if isinstance(t, ast.Name)}
    if isinstance(node, (ast.Import, ast.ImportFrom)): return {(a.asname or a.name).split('.')[0] for a in node.names if a.name != '*'}
    return set()


def _js_names(text):
    names = set()
    for default_name, declared, braces, star in JS_EXPORT.findall(text):
        if declared: names.add(declared)
        elif braces: names |= {part.split(' as ')[-1].strip() for part in braces.split(',') if part.strip()}
        elif star: names.add(star)
        else: names.add('default')
    return names


def _text(root, path):
    try: return (Path(root) / path).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError): return None


def surface_differences(before, after, mapping):
    """Each difference of the public surface, the old places read through `mapping` {old file: new file}."""
    return _entry_differences(before, after) + _command_differences(before, after, mapping) + _export_differences(before, after, mapping)


def _shown(row):
    return ' '.join(str(x) for x in row if x)


def _entry_differences(before, after):
    return ([f'the entry point {_shown(row)} is gone' for row in before['entries'] if row not in after['entries']]
            + [f'a new entry point appeared: {_shown(row)}' for row in after['entries'] if row not in before['entries']])


def _command_differences(before, after, mapping):
    out = []
    for name, runs in before['commands'].items():
        now = after['commands'].get(name)
        if now != mapping.get(runs, runs): out.append(f'the command {name} ran {runs} and now runs {now or "nothing"}')
    return out + [f'a new command appeared: {name}' for name in after['commands'] if name not in before['commands']]


def _export_differences(before, after, mapping):
    out = []
    for path, names in before['exports'].items():
        new = mapping.get(path, path)
        if after['exports'].get(new) == names: continue
        lost = sorted(set(names) - set(after['exports'].get(new) or []))
        out.append(f'{new} no longer exposes what {path} did' + (f': {", ".join(lost[:5])}' if lost else ''))
    return out


def test_results(output):
    """{name: Counter of results} of every test the output names, or {'(counts)': Counter} when it names none."""
    found = Counter()
    for _, name, result in UNITTEST.findall(output): found[(name, RESULT[result.lower()])] += 1
    for result, name in PYTEST.findall(output): found[(name, RESULT[result.lower()])] += 1
    for result, name, directive in TAP.findall(output): found[(name.strip(), 'skipped' if directive else RESULT[result.lower()])] += 1
    for mark, name in MARKED.findall(output): found[(name.strip(), RESULT[mark])] += 1
    if found: return found
    counts = Counter()
    for number, kind, ran in COUNTS.findall(output):
        if ran: counts[('(ran)', 'count')] += int(ran)
        else: counts[('(counts)', RESULT.get(kind.lower().rstrip('s'), 'failed'))] += int(number)
    return counts


def renamed_tests(mapping):
    """{old: new} of the module and file names a test's name carries, for every moved file: its path (pytest, jest),
    and its dotted module read from each folder both places share (unittest discovers from tests/, or from the root)."""
    names = {}
    for old, new in mapping.items():
        names[old] = new
        if not old.endswith('.py'): continue
        before, after = dotted(old), dotted(new)
        shared = 0
        while shared < min(len(before), len(after)) - 1 and before[shared] == after[shared]: shared += 1
        for start in range(shared + 1):
            if before[start:] != after[start:]: names['.'.join(before[start:])] = '.'.join(after[start:])
    return names


def _translated(name, names):
    for old in sorted(names, key=len, reverse=True):
        for at in _starts(name, old):
            return name[:at] + names[old] + name[at + len(old):]
    return name


def _starts(name, old):
    """Where `old` starts in `name` as a whole module or path name (after a start, a space, a parenthesis or a slash)."""
    at = name.find(old)
    while at >= 0:
        before, after = name[at - 1] if at else ' ', name[at + len(old):at + len(old) + 1]
        if before in ' (/' and (after in ('', '.', ':', ')', ' ', '/')): yield at
        at = name.find(old, at + 1)


def test_differences(before, after, mapping):
    """Each check that ran before and not after, each whose exit changed, and each test not back with its name and
    result (a suite that found no test after counts as every test lost); rows: [{argv, exit, output}]."""
    names = renamed_tests(mapping)
    now = {tuple(row['argv']): row for row in after}
    out = []
    for old in before:
        row = now.get(tuple(old['argv']))
        if row is None:
            out.append(f"{' '.join(old['argv'])} ran before the moves and not after")
            continue
        if old['exit'] != row['exit']: out.append(f"{' '.join(row['argv'])} exited {old['exit']} and now {row['exit']}")
        expected = Counter({(_translated(n, names), r): c for (n, r), c in test_results(old['output']).items()})
        got = test_results(row['output'])
        out += [f'{n}: {r} before, not after' for (n, r) in sorted(expected - got)][:20]
        out += [f'{n}: {r} after, not before' for (n, r) in sorted(got - expected)][:20]
    return out


def unproven(before):
    """Why the project's tests cannot prove a move changed nothing (no test ran, or none could be counted), else ''."""
    if not before: return 'the project has no check or test EAOS can run'
    if not any(test_results(row['output']) for row in before): return 'its tests ran, but EAOS could not read which passed'
    return ''
