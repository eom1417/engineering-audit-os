"""Dead code: what no user of the product can reach, and what nothing reads.

Three questions, each answered from facts already collected and the text of the snapshot:

- A module no production entry point imports, directly or through other modules. Tests do not count
  as users: a module imported only by its own test is dead for the product, though it is a review candidate
  (test_only), not a removal, since the tests may pin it on purpose. A program in a scripts/ or tools/ folder that
  nothing on record runs is a review candidate too: programs are run, not imported.
  Entry points include the source a built start script comes from (`node dist-server/main.mjs` runs
  `server/main.mjs`); tool configurations, and programs a CI step, container or make recipe, or document runs,
  are walked from as well.
- A top-level function or class whose name appears nowhere outside its own definition, or only in tests.
- A module-level constant (UPPER_CASE) that nothing reads.

The reference check is textual on purpose. A name held in a registry dictionary, passed to getattr as a
string, or listed in a JSON file is a reference an import graph cannot see; counting any occurrence as a
reference trades a few missed candidates for no false accusation. What survives is dead by two measures:
the graph does not reach it, and no text names it.

`adjudicate` applies the same test to the dead-code candidates an external engine reports, so EAOS asserts
one verdict per candidate whoever raised it: confirmed, or refuted with the reason written down.
"""
import re
from collections import Counter, defaultdict
from pathlib import PurePosixPath

from . import digest, make
from .source import classify, language_of

NAME = 'deadcode'
VERSION = '1'
LIMITATIONS = [
    'A reference is any occurrence of the name in code or configuration text outside its definition; a name '
    'reused for something else keeps a dead symbol alive, so misses are possible and false accusations rare.',
    'Reachability follows resolved imports from production entry points; a module loaded by a computed path '
    'counts as reached only when its dotted or slashed path appears as text somewhere reached.',
    'Methods are not judged: a method is called through an object whose type is not resolved here.',
    'A built output named by a script (dist/, build/, out/, dist-<name>/) is traced back to its source by path; a '
    'build that renames or bundles differently leaves that entry unseen.',
]
TOKEN = re.compile(r'[A-Za-z_$][\w$]*')
PY_CONSTANT = re.compile(r'^(_?[A-Z][A-Z0-9_]*[A-Z0-9])\s*(?::[^=]+)?=(?!=)', re.M)
JS_CONSTANT = re.compile(r'^(?:export\s+)?const\s+(_?[A-Z][A-Z0-9_]*[A-Z0-9])\s*[:=]', re.M)
REFERENCE_SUFFIXES = ('.json', '.yaml', '.yml', '.toml', '.cfg', '.ini', '.html')
ENTRY_FILES = ('__main__.py', 'manage.py', 'wsgi.py', 'asgi.py', 'main.py', 'app.py')
# Files that are not product code even when parsed: build and tool configuration, package markers,
# type declarations, migrations, examples. They are never candidates.
NOT_CANDIDATES = (re.compile(r'(^|/)[^/]*\.config\.[cm]?[jt]s$'), re.compile(r'(^|/)(conftest|setup|noxfile|fabfile)\.py$'),
                  re.compile(r'(^|/)__init__\.py$'), re.compile(r'\.d\.ts$'), re.compile(r'(^|/)migrations?/'),
                  re.compile(r'(^|/)(vite-env|next-env)\.d\.ts$'), re.compile(r'(^|/)examples?/'))


def _is_test(path):
    return classify(path) == 'test'


def _tokens(text):
    return Counter(TOKEN.findall(text))


BUILD_OUTPUT = re.compile(r'^(?:dist|build|out|lib|\.output)(?:[-_.](.+))?$')
SOURCE_SUFFIXES = ('', '.ts', '.mts', '.cts', '.tsx', '.js', '.mjs', '.cjs', '.jsx')
RELATIVE_LITERAL = re.compile(r'''['"`](\.{1,2}/[^'"`\s${}]+)['"`]''')


def _source_of(base, file, known):
    """The snapshot file a script runs: itself, or the source its build output is compiled from.

    `node dist-server/main.mjs` runs what the build makes of `server/main.mjs`; `node dist/index.js` what it makes
    of `src/index.ts` or `index.ts`. The output is not in the snapshot, so without this the production entry the
    start script names is no seed, and everything only it imports looks dead."""
    path = str(base / file).lstrip('./')
    if path in known: return path
    parts = PurePosixPath(file.lstrip('./')).parts
    output = BUILD_OUTPUT.match(parts[0]) if len(parts) > 1 else None
    if not output: return None
    rest = PurePosixPath(*parts[1:])
    for folder in ([output.group(1)] if output.group(1) else []) + ['src', '']:
        stem = str((base / folder / rest).with_suffix('')).lstrip('./')
        for suffix in SOURCE_SUFFIXES:
            if stem + suffix in known: return stem + suffix
    return None


CODE_PATH = re.compile(r'(?<![\w/.-])((?:\.{1,2}/)?[\w][\w./-]*\.(?:[cm]?[jt]sx?|py))\b')
RUN_COMMAND = re.compile(r'\b(?:node|python3?|tsx|ts-node|bun|deno\s+run|bash|sh)\s+(?:--?[\w-]+(?:[= ][\w./:=-]+)?\s+)*'
                         r'((?:\.{1,2}/)?[\w][\w./-]*\.(?:[cm]?[jt]sx?|py))\b')
# Files whose lines are commands a machine runs: CI workflows, container and make recipes, process files, shell scripts.
AUTOMATION = re.compile(r'(^|/)(\.github/workflows/[^/]+\.ya?ml|\.gitlab-ci\.ya?ml|\.circleci/[^/]+\.ya?ml|azure-pipelines\.ya?ml|'
                        r'bitbucket-pipelines\.ya?ml|Jenkinsfile|Dockerfile[^/]*|[^/]*\.dockerfile|docker-compose[^/]*\.ya?ml|'
                        r'compose\.ya?ml|Makefile|justfile|Procfile|[^/]*\.sh)$')


def _commanded(source, known, folders):
    """Programs a machine or a person is told to run: every code file an automation file names (a CI step
    `node scripts/audit-sbom.mjs`, a Dockerfile CMD), and every one a document gives as a command to run. A
    program is run, not imported, so the import graph never reaches it; the command that runs it is its use."""
    out = set()
    for path in known:
        if AUTOMATION.search(path): pattern = CODE_PATH
        elif path.endswith('.md') and not _is_test(path): pattern = RUN_COMMAND
        else: continue
        bases = {PurePosixPath(path).parent, PurePosixPath('.'), *folders}
        for file in set(pattern.findall(source.text(path) or '')):
            if file.startswith('/'): continue
            out |= {found for base in bases if (found := _source_of(base, file, known))}
    return out


def _seeds(source, known, entry_points):
    """Production entry points, plus the files a runtime loads first: __main__.py, index.html scripts, manifests."""
    seeds = {(f.get('location') or {}).get('path') for f in entry_points
             if f.get('kind') == 'entry_point' and (f.get('value') or {}).get('category') != 'test'
             and (f.get('value') or {}).get('framework') not in ('npm_script',)}
    for path in known:
        name = PurePosixPath(path).name
        if name in ENTRY_FILES and not _is_test(path): seeds.add(path)
        if name == 'index.html':
            for src in re.findall(r'''<script[^>]*\bsrc=["']/?([^"']+)["']''', source.text(path) or ''):
                seeds.add(str(PurePosixPath(path).parent / src).lstrip('./') if '/' in path else src)
        if name == 'package.json':
            import json
            try: manifest = json.loads(source.text(path) or '{}')
            except ValueError: manifest = {}
            base = PurePosixPath(path).parent
            bins = manifest.get('bin') if isinstance(manifest.get('bin'), dict) else {'': manifest.get('bin')}
            for entry in [manifest.get('main'), manifest.get('module'), *bins.values()]:
                if isinstance(entry, str): seeds.add(str(base / entry).lstrip('./'))
            for script in (manifest.get('scripts') or {}).values():
                for file in re.findall(r'[\w./-]+\.(?:[cm]?[jt]sx?|py)\b', str(script)):
                    seeds.add(_source_of(base, file, known) or str(base / file).lstrip('./'))
    return {seed for seed in seeds if seed in known}


def _edges(resolved):
    graph, test_importers = defaultdict(set), defaultdict(set)
    for fact in resolved:
        if fact.get('kind') != 'module_edge': continue
        to_path = (fact.get('value') or {}).get('to_path')
        path = (fact.get('location') or {}).get('path')
        if not (path and to_path): continue
        (test_importers[to_path].add(path) if _is_test(path) else graph[path].add(to_path))
    return graph, test_importers


def _named(path, blob):
    """A module a computed import loads is named in text: eaos.facts.domain, or eaos/facts/domain."""
    stem = str(PurePosixPath(path).with_suffix(''))
    return stem.replace('/', '.') in blob or stem in blob


def _relative(path, text, texts):
    """Files a module names by a literal path relative to itself: `new URL("./server/index.mjs", import.meta.url)`,
    `new Worker("./worker.js")`. The import graph does not see these loads; the literal says what they load."""
    base = PurePosixPath(path).parent
    out = set()
    for literal in RELATIVE_LITERAL.findall(text):
        parts = []
        for part in (base / literal).parts:
            if part == '..':
                if not parts: break
                parts.pop()
            elif part != '.': parts.append(part)
        else:
            if parts and '/'.join(parts) in texts: out.add('/'.join(parts))
    return out


def _reachable(seeds, graph, texts):
    reached, frontier = set(seeds), set(seeds)
    while True:
        while frontier:
            frontier = {child for path in frontier for child in graph.get(path, ())} - reached
            reached |= frontier
        blob = '\n'.join(texts[path] for path in reached if path in texts)
        named = {path for path in texts if path not in reached and _named(path, blob)}
        named |= {found for path in reached if path in texts for found in _relative(path, texts[path], texts)} - reached
        if not named: return reached
        reached |= named
        frontier = named


PROGRAM_FOLDERS = {'scripts', 'script', 'bin', 'tools', 'tool'}
REVIEW_REASONS = {'test_only': 'only tests name it: delete it with them, or keep it as the contract they pin',
                  'review': 'a program is run, not imported, and a person may run it by hand: nothing in CI, the '
                            'manifests or the docs runs it, so ask whether anyone still does before deleting it'}


def _finding(rule, path, line, symbol, message, subject_kind, evidence, sha, tests=(), program=False):
    # A name or module only tests read is either dead with its tests, or a contract the tests pin on purpose (a
    # test harness kept outside tests/); the text cannot tell which, so it is a review candidate (test_only), not an
    # asserted defect. A program in a scripts/ or tools/ folder is never imported: that nothing imports it says
    # nothing about whether anyone runs it, so it is a review candidate too.
    verdict = 'review' if program else 'test_only' if tests else 'confirmed'
    return make('engine_finding', NAME, VERSION, sha,
                {'path': path, 'start_line': line, 'symbol': symbol},
                {'engine': 'eaos', 'engine_version': VERSION, 'rule': rule, 'kind': 'dead_code', 'method': 'deterministic',
                 'message': message, 'subject_kind': subject_kind, 'measurements': [], 'engine_confidence': None,
                 'sites': [{'path': path, 'line': line}], 'evidence': evidence, 'tests': list(tests),
                 'adjudication': {'verdict': verdict, 'reason': REVIEW_REASONS.get(verdict, evidence)}},
                limitations=LIMITATIONS)


class References:
    """Where each name is written, split into product text and test text, per file."""

    def __init__(self, source):
        self.texts, self.product, self.tests = {}, {}, {}
        for item in source.readable():
            path = item['path']
            if language_of(path) is None and not path.endswith(REFERENCE_SUFFIXES): continue
            # A file under docs/ is documentation whatever its extension: naming a symbol there is not using it.
            if 'docs' in PurePosixPath(path).parts[:-1]: continue
            text = source.text(path)
            if text is None: continue
            self.texts[path] = text
            (self.tests if _is_test(path) else self.product)[path] = _tokens(text)

    def outside(self, name, path, span=None):
        """(product occurrences outside the definition, test files naming it)."""
        count = sum(tokens.get(name, 0) for other, tokens in self.product.items() if other != path)
        own = self.product.get(path, Counter()).get(name, 0)
        if own:
            lines = (self.texts.get(path) or '').split('\n')
            start, end = span or (1, 0)
            inside = Counter(TOKEN.findall('\n'.join(lines[start - 1:end]))).get(name, 0) if end >= start else 0
            count += max(own - inside, 0)
        tests = sorted(other for other, tokens in self.tests.items() if tokens.get(name))
        return count, tests


GLOBAL_OBJECTS = {'window', 'globalThis', 'self', 'global', 'document', 'navigator', 'console', 'process'}


def run(target, source, symbols=None, resolved=None, entry_points=None, **options):
    symbols = [f for f in (symbols or []) if f.get('kind') == 'symbol']
    known = {item['path'] for item in source.readable()}
    code = {path for path in known if language_of(path) in ('python', 'javascript', 'typescript', 'tsx')}
    refs = References(source)
    graph, test_importers = _edges(resolved or [])
    seeds = _seeds(source, known, entry_points or [])
    # A tool configuration (vite.config.ts, next.config.mjs) is loaded by the tool itself whenever it runs; what it
    # imports (a dev-server plugin, the API it mounts) is reached through it. It is a root to walk from, not an entry
    # point: a library with only a test-runner config still has no production entry, and is judged as a library.
    # A program a CI step or a document says to run is walked from the same way.
    configs = {path for path in known if NOT_CANDIDATES[0].search(path) and not _is_test(path)}
    folders = {PurePosixPath(path).parent for path in known if PurePosixPath(path).name == 'package.json'}
    commanded = {path for path in _commanded(source, known, folders) if not _is_test(path)}
    reached = _reachable(seeds | configs | commanded if seeds else seeds, graph, {p: refs.texts[p] for p in code if p in refs.texts})
    sha = digest(str(source.fingerprint).encode('utf-8'))
    facts = []
    # With no production entry point, nothing says who uses the code: a library's public names serve callers
    # outside the snapshot. Then only what is private by convention (`_name`) is judged, and no module is.
    judged = (lambda name: True) if seeds else (lambda name: name.startswith('_'))
    unreachable = sorted(path for path in code if seeds and path not in reached and not _is_test(path)
                         and classify(path) == 'source' and not any(rule.search(path) for rule in NOT_CANDIDATES))
    for path in unreachable:
        tests = sorted(test_importers.get(path, ()))
        why = f'imported only by tests ({", ".join(tests[:3])})' if tests else 'no production entry point imports it'
        program = bool(PROGRAM_FOLDERS & set(PurePosixPath(path).parts[:-1]))
        if program and not tests: why = 'a program nothing in CI, the manifests or the docs runs'
        facts.append(_finding('unreachable-module', path, 1, path, f'unreachable module `{path}`: {why}', 'module',
                              f'{len(seeds)} production entry points and the resolved import graph do not reach it', sha,
                              tests, program))
    dead_modules = set(unreachable)
    for fact in symbols:
        value, location = fact.get('value') or {}, fact.get('location') or {}
        path, name = location.get('path'), value.get('name')
        if (not path or path in dead_modules or path not in code or _is_test(path) or classify(path) != 'source'
                or any(rule.search(path) for rule in NOT_CANDIDATES)): continue
        if value.get('kind') not in ('function', 'class') or value.get('parent') or value.get('decorators'): continue
        if not name or name.startswith('__') or name in ('main', 'default') or not judged(name): continue
        # `window.alert = ...` replaces a platform global: every bare `alert()` reaches it, and none names it.
        if name.split('.', 1)[0] in GLOBAL_OBJECTS and '.' in name: continue
        # `declare global { interface Window {...} }` extends a type the platform owns; nothing names it to use it.
        start = location.get('start_line') or 1
        if 'declare ' in '\n'.join((refs.texts.get(path) or '').split('\n')[max(0, start - 4):start]): continue
        count, tests = refs.outside(name, path, (start, location.get('end_line') or 0))
        if count: continue
        module = str(PurePosixPath(path).with_suffix(''))
        how = f'referenced only by tests ({", ".join(tests[:3])})' if tests else 'no reference outside its definition'
        facts.append(_finding('unused-symbol', path, location.get('start_line') or 1, name,
                              f'unused {value["kind"]} `{module}.{name}`: {how}', 'symbol',
                              f'the name occurs nowhere in product code or configuration outside lines '
                              f'{location.get("start_line")}-{location.get("end_line")}', sha, tests))
    for path in sorted(code - dead_modules):
        if _is_test(path) or classify(path) != 'source' or any(rule.search(path) for rule in NOT_CANDIDATES): continue
        text = refs.texts.get(path) or ''
        pattern = PY_CONSTANT if language_of(path) == 'python' else JS_CONSTANT
        for match in pattern.finditer(text):
            name, line = match.group(1), text.count('\n', 0, match.start()) + 1
            if not judged(name): continue
            count, tests = refs.outside(name, path, (line, line))
            if count: continue
            module = str(PurePosixPath(path).with_suffix(''))
            facts.append(_finding('unread-constant', path, line, name,
                                  f'constant `{module}.{name}` is never read' + (f' outside tests ({", ".join(tests[:3])})' if tests else ''),
                                  'symbol', f'the name occurs nowhere in product code or configuration except line {line}', sha, tests))
    summary = {'production_entry_points': len(seeds), 'modules_reached': len(reached & code), 'code_modules': len(code),
               'unreachable_modules': len(unreachable),
               'unused_symbols': sum(f['value']['rule'] == 'unused-symbol' for f in facts),
               'unread_constants': sum(f['value']['rule'] == 'unread-constant' for f in facts),
               'evaluated_kinds': {'eaos': {'dead_code': {'status': 'observed', 'granularity': 'symbol'}}}}
    return {'facts': facts, 'summary': summary, 'available': True, 'input_sha': sha, 'reason': None}


def adjudicate(findings, source, own=()):
    """One verdict per dead-code candidate from any engine, written into value.adjudication.

    confirmed    EAOS's own detector reports the same file and name
    refuted      the name is referenced outside its definition in product text, or held in a registry
    not_a_symbol the finding names no function, class, constant or module (a marker, a comment)
    unconfirmed  none of the above: the engine's word alone
    The engine's own fields are left as it wrote them.
    """
    refs = References(source)
    ours = {((f.get('location') or {}).get('path'), (f.get('location') or {}).get('symbol')) for f in own}
    for fact in findings:
        value = fact.get('value') or {}
        if fact.get('kind') != 'engine_finding' or value.get('kind') != 'dead_code' or value.get('engine') == 'eaos': continue
        location = fact.get('location') or {}
        path, symbol = location.get('path'), location.get('symbol')
        qualified = re.search(r'(?:function|method|class)\s+`?([\w./$]+)`?|`([\w./$]+)`', value.get('message') or '')
        name = (symbol if symbol and symbol != path else None) or (next(g for g in qualified.groups() if g) if qualified else None)
        name = name.rsplit('.', 1)[-1].rsplit('/', 1)[-1] if name else None
        if not name or not TOKEN.fullmatch(name):
            value['adjudication'] = {'verdict': 'not_a_symbol', 'reason': 'the finding names no symbol or module'}
        elif value.get('referenced_by_registry'):
            value['adjudication'] = {'verdict': 'refuted', 'reason': 'held in a registry the import graph cannot see'}
        elif (path, name) in ours:
            value['adjudication'] = {'verdict': 'confirmed', 'reason': 'EAOS finds no reference outside its definition either'}
        else:
            count, _ = refs.outside(name, path, (location.get('start_line') or 1, location.get('end_line') or location.get('start_line') or 0))
            value['adjudication'] = ({'verdict': 'refuted', 'reason': f'the name occurs {count} time(s) in product text outside its definition'}
                                     if count else {'verdict': 'unconfirmed', 'reason': 'the engine alone reports it'})
    return findings
