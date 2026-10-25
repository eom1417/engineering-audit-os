"""Broken code: what fails the first time it runs, or tells a reader to do something impossible.

- An undefined name (Python): read in a scope, assigned in none it can see, and not a builtin. Scopes are
  resolved by the standard library's symtable, the way the interpreter itself resolves them, so a name
  a function assigns, a closure captures, or a module defines under a condition is never reported.
- A key written twice in one dictionary literal with different values: the first value is silently lost.
- An import of a project file that does not exist (JavaScript and TypeScript), read from the resolver:
  a relative or aliased specifier no file answers.
- A document that instructs a command the project does not have: a subcommand of its own CLI, an npm
  script, or a file to run.

Each is certain from the text: no heuristic score, no engine confidence.
"""
import ast
import builtins
import json
import fnmatch
import re
import symtable
from pathlib import PurePosixPath

from . import make
from .source import classify, language_of

NAME = 'broken'
VERSION = '1'
LIMITATIONS = [
    'Undefined names are judged for Python only; a module with a star import is skipped, since any name may come from it.',
    'Names injected at runtime (exec, globals() writes, module __getattr__) are invisible and would be reported; none is assumed.',
    'Documented commands are checked against the CLI subcommands the code declares with argparse, the npm scripts in '
    'package.json, and the files in the snapshot; a command another tool provides is not judged.',
]
BUILTINS = set(dir(builtins)) | {'__file__', '__name__', '__doc__', '__spec__', '__package__', '__loader__', '__builtins__',
                                 '__path__', '__annotations__', '__dict__', '__module__', '__qualname__', '__class__'}
SUBPARSER = re.compile(r'''add_parser\(\s*['"]([a-z][\w-]*)['"]''')
NPM_RUN = re.compile(r'''\b(?:npm|pnpm|yarn|bun)\s+run\s+([\w:.*-]+(?:<[^<>\s`]*>|\{[^{}\s`]*\}|\[[^\[\]\s`]*\]|\$\{?\w+\}?|…)*)''')
# A placeholder written after a script name (`deploy:<target>`, `deploy:{env}`, `deploy:$ENV`, `deploy:…`) stands
# for any text: the command names a family of scripts, and is matched as a pattern, not as the literal prefix.
PLACEHOLDER = re.compile(r'''<[^<>]*>|\{[^{}]*\}|\[[^\[\]]*\]|\$\{?\w+\}?|…|\.\.\.''')
RUN_FILE = re.compile(r'''\b(?:python3?|node|bash|sh|tsx|ts-node|deno\s+run)\s+((?:\./)?[\w./-]+\.(?:py|[cm]?[jt]s|sh))\b''')
CODE_SPAN = re.compile(r'```[^\n]*\n(.*?)```|`([^`\n]+)`', re.S)


def _fact(rule, path, line, symbol, message, severity, evidence, sha):
    return make('broken_code', NAME, VERSION, sha, {'path': path, 'start_line': line, 'symbol': symbol},
                {'rule': rule, 'message': message, 'severity': severity, 'evidence': evidence}, limitations=LIMITATIONS)


def _scopes(table):
    yield table
    for child in table.get_children(): yield from _scopes(child)


def undefined_names(text, path):
    """(name, line) for every name read where no enclosing scope, the module, or builtins defines it."""
    try:
        tree = ast.parse(text)
        top = symtable.symtable(text, path, 'exec')
    except (SyntaxError, ValueError):
        return []
    if _has_star_import(tree):
        return []
    missing = _missing(top, _module_names(top))
    # Report the read inside the scope that lacks the name, not the first mention anywhere in the file:
    # `values` is defined in one function and read by mistake in another.
    scopes = {node.lineno: node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda))}
    found = []
    for name, owners in missing.items():
        lines = [line for owner in owners for line in _reads(scopes.get(owner, tree) if owner else tree, name)]
        if lines: found.append((name, min(lines)))
    return sorted(found, key=lambda item: item[1])


def _module_names(top):
    """The names the module itself assigns or imports."""
    return {symbol.get_name() for symbol in top.get_symbols() if symbol.is_assigned() or symbol.is_imported()}


def _has_star_import(tree):
    return any(isinstance(node, ast.ImportFrom) and any(alias.name == '*' for alias in node.names) for node in ast.walk(tree))


def _unresolved(symbol, scope, top, module):
    """Whether a name this scope reads is defined in no scope it can see, nor in the module or builtins."""
    if not symbol.is_referenced() or symbol.get_name() in BUILTINS or symbol.get_name() in module: return False
    if scope is top: return not (symbol.is_assigned() or symbol.is_imported())
    if symbol.is_local() or symbol.is_free() or symbol.is_parameter(): return False
    return symbol.is_global()


def _missing(top, module):
    """name -> the line of each scope that reads it without a definition (0 for the module)."""
    missing = {}
    for scope in _scopes(top):
        line = scope.get_lineno() if scope is not top else 0
        for symbol in scope.get_symbols():
            if _unresolved(symbol, scope, top, module): missing.setdefault(symbol.get_name(), []).append(line)
    return missing


def _reads(region, name):
    return [node.lineno for node in ast.walk(region)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == name]


def duplicate_keys(text):
    """(key, first line, second line) for every constant key written twice in one dict literal with different values."""
    try: tree = ast.parse(text)
    except SyntaxError: return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict): continue
        seen = {}
        for key, value in zip(node.keys, node.values):
            if not isinstance(key, ast.Constant): continue
            if key.value in seen and ast.dump(seen[key.value][1]) != ast.dump(value):
                out.append((key.value, seen[key.value][0], key.lineno))
            seen.setdefault(key.value, (key.lineno, value))
    return out


def _cli(source, known):
    """(program names, subcommands) the project's own CLI declares; empty when it declares none."""
    programs, subcommands = set(), set()
    for path in known:
        name = PurePosixPath(path).name
        text = source.text(path) or ''
        if name == 'pyproject.toml':
            block = re.search(r'\[project\.scripts\](.*?)(?:\n\[|\Z)', text, re.S)
            programs |= set(re.findall(r'^\s*([\w-]+)\s*=', block.group(1), re.M)) if block else set()
        if name == '__main__.py':
            programs.add('python -m ' + '.'.join(PurePosixPath(path).parent.parts))
        if language_of(path) == 'python' and classify(path) == 'source' and 'add_parser(' in text:
            # Subcommands registered in a loop (`add_parser(name, ...)`) are not literal arguments; every quoted
            # word in a file that builds the parser is a name the CLI may register, so none of them is judged stale.
            subcommands |= set(SUBPARSER.findall(text)) | set(re.findall(r'''['"]([a-z][\w-]*)['"]''', text))
    return programs, subcommands


def stale_instructions(source, known, everything):
    """(doc, line, command) for every documented command the project does not have."""
    programs, subcommands = _cli(source, known)
    scripts = _npm_scripts(source, known)
    commands = {'call': _subcommand_call(programs), 'subcommands': subcommands, 'scripts': scripts,
                'all_scripts': set().union(*scripts.values()) if scripts else set(), 'everything': everything}
    out = []
    for path, text in _documents(source, known):
        for match in CODE_SPAN.finditer(text):
            span = match.group(1) or match.group(2) or ''     # an empty block (```\n```) has neither
            line = text.count('\n', 0, match.start()) + 1
            out += [(path, line, command) for command in _stale_in_span(span, path, commands)]
    return sorted(set(out))


def _npm_scripts(source, known):
    """{folder of a package.json: its script names}."""
    scripts = {}
    for path in known:
        if PurePosixPath(path).name != 'package.json': continue
        try: scripts[str(PurePosixPath(path).parent)] = set((json.loads(source.text(path) or '{}').get('scripts') or {}))
        except ValueError: pass
    return scripts


def _subcommand_call(programs):
    if not programs: return None
    return re.compile(r'(?:^|[\s(`$])(' + '|'.join(re.escape(p) for p in sorted(programs, key=len, reverse=True)) + r')\s+([a-z][\w-]*)')


def _documents(source, known):
    for path in sorted(known):
        if not path.endswith('.md') or classify(path) == 'test': continue
        yield path, source.text(path) or ''


def _script_exists(command, all_scripts):
    # `npm run deploy:*` or `npm run deploy:<target>` names a family of scripts: it exists when one does.
    pattern = PLACEHOLDER.sub('*', command)
    return any(fnmatch.fnmatchcase(name, pattern) for name in all_scripts)


def _file_exists(file, doc, scripts, everything):
    # A command documented at the root is often run from the app's own folder (the one with package.json).
    bases = [PurePosixPath(doc).parent] + [PurePosixPath(folder) for folder in scripts]
    return '/' not in file or file in everything or any(str(base / file) in everything for base in bases)


def _unknown_files(span, doc, scripts, everything):
    out = []
    for found in RUN_FILE.finditer(span):
        if found.group(1).startswith('/'): continue   # an absolute path is outside the project
        if not _file_exists(found.group(1).lstrip('./'), doc, scripts, everything): out.append(found.group(0))
    return out


def _stale_in_span(span, doc, commands):
    """The commands one code span of a document instructs that the project does not have."""
    stale = []
    if commands['call'] and commands['subcommands']:
        stale += [f'{found.group(1)} {found.group(2)}' for found in commands['call'].finditer(span)
                  if found.group(2) not in commands['subcommands']]
    if commands['scripts']:
        stale += [found.group(0) for found in NPM_RUN.finditer(span) if not _script_exists(found.group(1), commands['all_scripts'])]
    return stale + _unknown_files(span, doc, commands['scripts'], commands['everything'])


def _python_facts(path, text, sha):
    facts = [_fact('undefined-name', path, line, name,
                   f'undefined name `{name}` in {path}:{line}: no enclosing scope, the module or builtins define it; '
                   f'this line raises NameError when it runs', 'high',
                   'symtable finds the name referenced as a global that the module never assigns or imports', sha)
             for name, line in undefined_names(text, path)]
    facts += [_fact('duplicate-key', path, second, str(key),
                    f'duplicate key `{key}` in one dictionary literal in {path} (lines {first} and {second}): '
                    f'the first value is silently discarded', 'medium',
                    'two constant keys equal, their values different, in one ast.Dict', sha)
              for key, first, second in duplicate_keys(text)]
    return facts


def _missing_import_fact(fact, sha):
    value = fact.get('value') or {}
    if fact.get('kind') != 'module_edge' or fact.get('resolution') != 'UNRESOLVED': return None
    if value.get('language') not in ('javascript', 'typescript', 'tsx'): return None
    location = fact.get('location') or {}
    path, module = location.get('path'), value.get('module') or ''
    return _fact('missing-import', path, location.get('start_line') or 1, module,
                 f'{path} imports `{module}`, which does not exist in the project: the module fails to load',
                 'high' if classify(path) == 'source' else 'low',
                 'the resolver found no file for a relative or aliased specifier', sha)


def _missing_import_facts(resolved, sha):
    """A fact per resolved import that names a module the snapshot does not have."""
    return [found for found in (_missing_import_fact(fact, sha) for fact in resolved) if found]


def run(target, source, resolved=None, **options):
    known = {item['path'] for item in source.readable()}
    everything = {item['path'] for item in source.inventory['files']}
    sha = source.content_fingerprint
    facts = []
    for path in sorted(known):
        if language_of(path) == 'python': facts += _python_facts(path, source.text(path) or '', sha)
    facts += _missing_import_facts(resolved or [], sha)
    for doc, line, command in stale_instructions(source, known, everything):
        facts.append(_fact('stale-instruction', doc, line, command,
                           f'{doc} instructs `{command}`, a command the project does not have: it no longer exists, or does not exist yet', 'low',
                           'not among the CLI subcommands, npm scripts or files the snapshot declares', sha))
    summary = {rule: sum(f['value']['rule'] == rule for f in facts)
               for rule in ('undefined-name', 'duplicate-key', 'missing-import', 'stale-instruction')}
    return {'facts': facts, 'summary': summary, 'available': True, 'input_sha': sha, 'reason': None}
