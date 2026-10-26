"""The code limits EAOS holds itself to: each function's cyclomatic complexity, length and parameters, each module's
length, logic written once, and no unused import or variable.

Complexity, lengths and parameters: what exceeds the limit today is listed in tools/code_limits.json with its current size and may
only shrink; a new entry, or a listed one that grew, fails tests/guards/test_code_limits.py. When an entry shrinks or drops
under the limit, `python tools/code_limits.py --tighten` rewrites the list. A function whose parameters cannot be grouped
(a public tool mirroring its command's options, a record's constructor) says why on its `def` line instead, the way a
justified pyflakes or Semgrep line does: `# limits: parameters -- <why>`; it is not counted and needs no entry, and a
comment with no reason after `--` does not count. Duplicates and leftovers have no list: there are none, and the test
keeps it so.
"""
import ast
import hashlib
import io
import json
import linecache
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eaos.core.contracts.code_laws import MAX_COMPLEXITY, MAX_FUNCTION_LINES, MAX_LINES, MAX_PARAMETERS, complexity  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'tools' / 'code_limits.json'
FOLDERS = ('eaos', 'tools')
# Each kind of limit and its number; every kind but 'modules' is keyed by function.
# EAOS holds itself to the target laws since M3 (2026-10-24): complexity 10, modules of 400 lines. The laws it holds every
# project to stay eaos/core/contracts/code_laws.py's.
LIMITS = {'functions': min(MAX_COMPLEXITY, 10), 'function_lines': MAX_FUNCTION_LINES, 'parameters': MAX_PARAMETERS,
          'modules': min(MAX_LINES, 400)}
# The kinds a function may justify on its signature, and the comment that does: the kind, then `--` and a reason.
JUSTIFIABLE = ('parameters',)
_JUSTIFIED = re.compile(r'#\s*limits:\s*([\w, ]+?)\s+--\s*\S')


def functions(tree, prefix=''):
    """(qualified name, node) of every named function, methods and nested functions included."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = f'{prefix}{node.name}'
            if not isinstance(node, ast.ClassDef): yield name, node
            yield from functions(node, name + '.')
        else:
            yield from functions(node, prefix)


def modules():
    for folder in FOLDERS:
        yield from sorted(path for path in (ROOT / folder).rglob('*.py') if '__pycache__' not in path.parts)


def parameters(function):
    """The parameters a caller passes, self and cls aside (*args and **kwargs are not counted)."""
    named = function.args.posonlyargs + function.args.args + function.args.kwonlyargs
    return sum(arg.arg not in ('self', 'cls') for arg in named)


def justified(function, lines):
    """The kinds of JUSTIFIABLE the function's signature (its `def` line to the line before its body) says why it
    exceeds: `# limits: parameters -- <why>`. No reason after `--`, no justification."""
    last = max(function.lineno, function.body[0].lineno - 1)
    said = {kind.strip() for line in lines[function.lineno - 1:last] for match in _JUSTIFIED.finditer(line)
            for kind in match.group(1).split(',')}
    return said & set(JUSTIFIABLE)


def studio(over):
    """The Studio's JavaScript (console/src) held to the same complexity and module length (M4.6), counted by EAOS's own
    facts (eaos/facts/code/metrics.py: 1 + the lexical branches, each nested function alone), added to `over`."""
    import tempfile
    from eaos.facts.run import collect
    with tempfile.TemporaryDirectory() as out:
        collect(ROOT / 'console', Path(out), ['syntax', 'metrics'], exclude=('node_modules', 'dist', 'tools', 'scripts'))
        facts = json.loads((Path(out) / 'facts' / 'metrics.json').read_text(encoding='utf-8'))['facts']
    for fact in (f for f in facts if f['kind'] == 'metric'):
        value, rel = fact['value'], 'console/' + fact['location']['path']
        if value['scope'] == 'file' and value['lines'] > LIMITS['modules']: over['modules'][rel] = value['lines']
        key = f"{rel}::{fact['location'].get('symbol')}"
        if value['scope'] in ('function', 'method') and value['complexity'] > LIMITS['functions']:
            over['functions'][key] = max(value['complexity'], over['functions'].get(key, 0))
    return over


def measure():
    """Everything over a limit today: {kind: {path::name or path: size}}, a kind per LIMITS."""
    over = studio({kind: {} for kind in LIMITS})
    for path in modules():
        text, rel = path.read_text(encoding='utf-8'), path.relative_to(ROOT).as_posix()
        if len(lines := text.splitlines()) > LIMITS['modules']: over['modules'][rel] = len(lines)
        for name, node in functions(ast.parse(text, rel)):
            sizes = {'functions': complexity(node), 'function_lines': node.end_lineno - node.lineno + 1,
                     'parameters': parameters(node)}
            excused = justified(node, lines)
            for kind, size in sizes.items():
                if size > LIMITS[kind] and kind not in excused: over[kind][f'{rel}::{name}'] = size
    return over


class _Anonymous(ast.NodeTransformer):
    """Forget names, so two functions that differ only in what they call their variables compare equal."""
    def visit_Name(self, node): return ast.copy_location(ast.Name(id='_', ctx=node.ctx), node)

    def visit_arg(self, node): node.arg = '_'; return node


def _shape(function):
    body = [node for node in function.body if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))]
    tree = _Anonymous().visit(ast.parse(ast.unparse(ast.Module(body=body, type_ignores=[]))))
    return hashlib.sha256(ast.dump(tree).encode()).hexdigest()


def duplicates(smallest=3):
    """Groups of functions with the same body (names aside), of at least `smallest` statements: logic written twice."""
    shapes = defaultdict(list)
    for path in modules():
        rel = path.relative_to(ROOT).as_posix()
        for name, node in functions(ast.parse(path.read_text(encoding='utf-8'), rel)):
            if len(node.body) >= smallest: shapes[_shape(node)].append(f'{rel}::{name}')
    return sorted(group for group in shapes.values() if len(group) > 1)


def leftovers():
    """Unused imports and variables, and other pyflakes findings, except on a line that says why (# noqa)."""
    from pyflakes.api import checkPath
    from pyflakes.reporter import Reporter
    out = io.StringIO()
    for path in modules(): checkPath(str(path), Reporter(out, out))
    return [message for message in out.getvalue().splitlines() if '# noqa' not in _source_line(message)]


def _source_line(message):
    path, number = message.split(':')[:2]
    return linecache.getline(path, int(number)) if number.isdigit() else ''


def breaches(over, baseline):
    """What is over a limit and not allowed by the baseline: new entries, and listed entries that grew. A listed function
    moved to another module, or out of its class, keeps its allowance (_moved): splitting a module is how it shrinks, and
    the move alone made each of its complex functions "new" (EAOS's five largest modules could not be split, 2026-10-15)."""
    allowed = {kind: baseline.get(kind, {}) if kind == 'modules' else
               {**_moved(over.get(kind, {}), baseline.get(kind, {})), **baseline.get(kind, {})} for kind in LIMITS}
    return [f'{key}: {size} (allowed {allowed[kind].get(key, limit)})'
            for kind, limit in LIMITS.items()
            for key, size in sorted(over.get(kind, {}).items()) if size > allowed[kind].get(key, limit)]


def _moved(now, listed):
    """{new key: allowance} for each function over the limit at a key not listed whose own name is that of a listed one
    no longer at its key: the same function, moved."""
    name = lambda key: key.split('::')[-1].split('.')[-1]
    gone = {}
    for key, size in listed.items():
        if key not in now: gone[name(key)] = max(size, gone.get(name(key), 0))
    return {key: gone[name(key)] for key in now if key not in listed and name(key) in gone}


def load():
    return json.loads(BASELINE.read_text(encoding='utf-8'))


def write(over):
    BASELINE.write_text(json.dumps(over, indent=1, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    current = measure()
    if '--tighten' in sys.argv:
        if found := breaches(current, load()): sys.exit('cannot tighten, over the limits:\n' + '\n'.join(found))
        write(current)
    print(f"{len(current['functions'])} functions over complexity {LIMITS['functions']}, "
          f"{len(current['function_lines'])} over {MAX_FUNCTION_LINES} lines, "
          f"{len(current['parameters'])} over {MAX_PARAMETERS} parameters, "
          f"{len(current['modules'])} modules over {LIMITS['modules']} lines, {len(duplicates())} duplicated functions, "
          f"{len(leftovers())} leftovers")
