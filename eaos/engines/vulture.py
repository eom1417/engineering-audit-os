"""vulture: unused Python code, each candidate with the confidence vulture gives it.

An independent witness beside EAOS's own dead-code facts and enola's: where two of them name the same file,
the claim is corroborated. Unused functions, methods, classes, properties, imports and unreachable code
become `dead_code` findings, worded so the registry check in eaos/correlate.py can read the name
(the name in backticks after the word function or method). Unused variables, attributes and arguments are counted but not reported (at 60%
confidence they are mostly framework fields), and so is anything in a test file, which a test runner finds by
name. vulture prints text, not JSON; the line shape is pinned by tests/contracts/vulture.json.

vulture cannot see what a framework calls. Read on EAOS itself, nine of its ten reports were such calls: a
function registered by a decorator (`@server.prompt(...)`) and a method that overrides a standard-library hook
(`HTMLParser.handle_starttag`). So each reported candidate is checked against its source, read and never run:
a function decorated by `obj.attr` or `obj.attr(...)` is registered, and a method whose name a standard-library
base class defines is a hook. Both are counted as `called_by_framework`, not reported.
"""
import ast
import importlib.util
import re
import sys
from pathlib import Path, PurePosixPath

from . import tool
from .contract import ERROR, OBSERVED, SYMBOL, Capability, Report, finding, measurement, subject
from .process import run, which

NAME = BINARY = 'vulture'
VERSION = re.compile(r'vulture (\d+\.\d+(?:\.\d+)?)')
PINNED = tool.pinned(NAME)
EXCLUDED = ('.git', 'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', 'vendor')
REPORTED = ('function', 'method', 'class', 'property', 'import', 'unreachable code')
LINE = re.compile(r'^(?P<path>.+?):(?P<line>\d+): (?P<message>.+?) \((?P<confidence>\d+)% confidence(?:, \d+ lines?)?\)$')
UNPARSED = re.compile(r'^(.+?\.pyi?):\d+: ')
UNUSED = re.compile(r"^unused (?P<type>\w+(?: \w+)?) '(?P<name>[^']+)'$")


def capabilities():
    return [Capability('dead_code', 'vulture.unused', granularity=SYMBOL)]


def version():
    return tool.version(BINARY, pattern=VERSION)


def exclusions(target, exclude=()):
    """vulture's --exclude value. vulture matches each pattern against the absolute path of a file, so a pattern
    must be anchored at the target: an unanchored `*/build/*` would drop every file of a project that itself lives
    under some `build` directory (or `.claude/worktrees`). A bare word would match inside any name (build_trial.py),
    so each entry is a directory. fnmatch's `*` crosses `/`, which makes `<target>/*/<name>/*` any depth. vulture
    splits the value on commas, so a comma in the target path is matched by `?`."""
    root = tool.fnmatch_literal(str(Path(target).resolve())).replace(',', '?')
    names = [name.strip('/') for name in EXCLUDED + tuple(exclude) if name.strip('/')]
    return ','.join(f'{root}{middle}{tool.fnmatch_literal(name)}/*' for name in names for middle in ('/', '/*/'))


def in_tests(path):
    parts = PurePosixPath(path).parts
    name = parts[-1] if parts else ''
    return bool({'tests', 'test', 'testing'} & set(parts[:-1])) or name.startswith('test_') or name.endswith('_test.py') \
        or name == 'conftest.py'


def candidates(text):
    """Every line vulture printed, as {path, line, type, name, confidence, message}; other lines are ignored."""
    out = []
    for line in text.splitlines():
        found = LINE.match(line.strip())
        if not found: continue
        message = found.group('message')
        unused = UNUSED.match(message)
        kind = unused.group('type') if unused else ('unreachable code' if message.startswith('unreachable code') else message)
        out.append({'path': tool.relative(found.group('path')), 'line': int(found.group('line')), 'type': kind,
                    'name': unused.group('name') if unused else None, 'confidence': int(found.group('confidence')),
                    'message': message})
    return out


# Decorators that wrap a function without registering it anywhere: an unused function they decorate is unused.
WRAPPING = {'functools', 'abc', 'typing', 'contextlib', 'staticmethod', 'classmethod', 'property', 'dataclasses'}


def _dotted(node):
    """`a.b.c` of a Name or Attribute chain, else None."""
    if isinstance(node, ast.Name): return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return f'{head}.{node.attr}' if head else None
    return None


def registered(definition):
    """Whether a decorator hands the function to something that calls it by registration (`@app.route(...)`,
    `@server.prompt(...)`, `@router.get`): an attribute of an object, called or not, outside WRAPPING."""
    for decorator in definition.decorator_list:
        name = _dotted(decorator.func if isinstance(decorator, ast.Call) else decorator)
        if name and '.' in name and name.split('.')[0] not in WRAPPING and not name.endswith(('.setter', '.getter', '.deleter')):
            return True
    return False


def _stdlib_class_names(module, name, seen=None):
    """Every name a standard-library class defines, read from its source (never imported), following bases
    defined in the same module or imported into it from another standard-library module."""
    seen = set() if seen is None else seen
    if (module, name) in seen or module.split('.')[0] not in sys.stdlib_module_names: return set()
    seen.add((module, name))
    try:
        spec = importlib.util.find_spec(module)
        tree = ast.parse(Path(spec.origin).read_text(encoding='utf-8')) if spec and spec.origin and spec.origin.endswith('.py') else None
    except (ImportError, ValueError, OSError, SyntaxError):
        return set()
    if tree is None: return set()
    imported = _imports(tree)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            names = {item.name for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
            for base in node.bases:
                base_name = _dotted(base)
                if not base_name: continue
                origin = imported.get(base_name.split('.')[0])
                if origin: names |= _stdlib_class_names(*_resolve(origin, base_name), seen)
                elif '.' not in base_name: names |= _stdlib_class_names(module, base_name, seen)
            return names
    return set()


def _imports(tree):
    """{local name: dotted origin} of a module's top-level imports."""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names: out[alias.asname or alias.name] = f'{node.module}.{alias.name}'
        elif isinstance(node, ast.Import):
            for alias in node.names: out[(alias.asname or alias.name).split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
    return out


def _resolve(origin, written):
    """(module, class) for a base written as `written` whose first part was imported from `origin`."""
    dotted = '.'.join([origin, *written.split('.')[1:]])
    module, _, name = dotted.rpartition('.')
    return module, name


def hooks(definition, cls, imported):
    """Whether method `definition` of class `cls` overrides a name a standard-library base class defines."""
    for base in cls.bases:
        written = _dotted(base)
        origin = imported.get(written.split('.')[0]) if written else None
        if origin and definition.name in _stdlib_class_names(*_resolve(origin, written)):
            return True
    return False


def called_by_framework(target, row, cache):
    """Whether the definition a candidate names is registered by a decorator or overrides a standard-library hook,
    read from its source. A file that cannot be read or parsed answers False: the candidate is reported."""
    if row['type'] not in ('function', 'method') or not row['name']: return False
    if row['path'] not in cache:
        try: cache[row['path']] = ast.parse((Path(target) / row['path']).read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError): cache[row['path']] = None
    tree = cache[row['path']]
    if tree is None: return False
    imported = _imports(tree)
    for cls in [None, *(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef))]:
        body = tree.body if cls is None else cls.body
        for node in body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != row['name']: continue
            first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
            if not first <= row['line'] <= node.lineno: continue
            return registered(node) or (cls is not None and hooks(node, cls, imported))
    # A function nested in another function (`@server.prompt` inside a `build_server()`) is found by line.
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == row['name'] \
                and min([node.lineno, *(d.lineno for d in node.decorator_list)]) <= row['line'] <= node.lineno:
            return registered(node)
    return False


def normalise(rows, found, target=None):
    """(findings, candidates by type, candidates in test files, candidates a framework calls). Without `target`
    nothing is read, so nothing is set aside as called by a framework."""
    findings, by_type, in_test_files, framework, cache = [], {}, 0, [], {}
    for row in rows:
        by_type[row['type']] = by_type.get(row['type'], 0) + 1
        if row['type'] not in REPORTED: continue
        if in_tests(row['path']): in_test_files += 1; continue
        if target is not None and called_by_framework(target, row, cache):
            framework.append(f"{row['path']}:{row['line']}:{row['name']}"); continue
        message = (f"unused {row['type']} `{row['name']}` ({row['confidence']}% confidence)" if row['name']
                   else f"{row['message']} ({row['confidence']}% confidence)")
        findings.append(finding(NAME, found, f"unused_{row['type'].replace(' ', '_')}", 'dead_code',
                                subject('symbol', f"{row['path']}:{row['name'] or row['line']}", row['path'], row['line']), message,
                                measurements=[measurement('confidence', row['confidence'], unit='%')],
                                engine_confidence=row['confidence'] / 100, raw_ref=f'{NAME}/vulture.txt'))
    return findings, dict(sorted(by_type.items())), in_test_files, framework


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target, probe=version)
    if declined: return declined
    found = version()
    target = Path(target).resolve()
    output = Path(workdir) / NAME / 'vulture.txt'
    output.parent.mkdir(parents=True, exist_ok=True)
    code, out, error, seconds = run([which(BINARY), '.', '--exclude', exclusions(target, exclude)], cwd=target)
    # 0: nothing unused; 1: some file did not parse (the rest is still reported); 3: unused code found.
    if code not in (0, 1, 3):
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    output.write_text(out, encoding='utf-8')
    rows = candidates(out)
    findings, by_type, in_test_files, framework = normalise(rows, found, target)
    unparsed = sorted({tool.relative(spot.group(1), target) for spot in map(UNPARSED.match, error.splitlines()) if spot})
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, raw=str(output), findings=findings,
                  coverage={'status': 'observed', 'candidates': len(rows), 'by_type': by_type,
                            'reported_types': list(REPORTED), 'in_test_files_not_reported': in_test_files,
                            'called_by_framework_not_reported': framework,
                            'unparsed_files': unparsed},
                  evaluated={'dead_code': {'status': 'observed', 'granularity': SYMBOL}})
