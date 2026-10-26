"""What the product reaches, for the dead-code detector (eaos/facts/dead_code/detect.py): its production entry points and the
roots walked from them (tool configurations, the programs a CI step or a document runs, what a build script bundles),
the resolved import graph, the loads it cannot see (a module named in text, a path literal) and the package data read
whole.
"""
import re
from collections import defaultdict
from pathlib import PurePosixPath

from ..code import bundled
from ..source import classify

ENTRY_FILES = ('__main__.py', 'manage.py', 'wsgi.py', 'asgi.py', 'main.py', 'app.py')
# A tool configuration (vite.config.ts, next.config.mjs): a root to walk from, and never a dead-code candidate.
CONFIG = re.compile(r'(^|/)[^/]*\.config\.[cm]?[jt]s$')


def _is_test(path):
    return classify(path) == 'test'


BUILD_OUTPUT = re.compile(r'^(?:dist|build|out|lib|\.output)(?:[-_.](.+))?$')
SOURCE_SUFFIXES = ('', '.ts', '.mts', '.cts', '.tsx', '.js', '.mjs', '.cjs', '.jsx')
RELATIVE_LITERAL = re.compile(r'''['"`](\.{1,2}/[^'"`\s${}]+)['"`]''')
# A bare path literal with a folder and an extension: `Path(__file__).parent / 'templates/screens/reporter.mjs'`.
PATH_LITERAL = re.compile(r'''['"`]([\w-][\w.-]*(?:/[\w.-]+)+\.\w+)['"`]''')
# Folders a package ships as data, loaded by path at run time: templates and rules.
DATA_FOLDERS = {'templates', 'rules'}


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


BUILD_SCRIPTS = ('.js', '.mjs', '.cjs', '.ts', '.mts')
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
    seeds = _declared_entries(entry_points)
    for path in known: seeds |= _file_seeds(source, path, known)
    return {seed for seed in seeds if seed in known}


def _declared_entries(entry_points):
    return {(f.get('location') or {}).get('path') for f in entry_points
            if f.get('kind') == 'entry_point' and (f.get('value') or {}).get('category') != 'test'
            and (f.get('value') or {}).get('framework') not in ('npm_script',)}


def _html_scripts(path, text):
    return {str(PurePosixPath(path).parent / src).lstrip('./') if '/' in path else src
            for src in re.findall(r'''<script[^>]*\bsrc=["']/?([^"']+)["']''', text)}


def _manifest_seeds(path, text, known):
    """What a package.json runs: its main, module and bin files, and the source of every file a script names."""
    import json
    try: manifest = json.loads(text or '{}')
    except ValueError: manifest = {}
    base = PurePosixPath(path).parent
    bins = manifest.get('bin') if isinstance(manifest.get('bin'), dict) else {'': manifest.get('bin')}
    seeds = {str(base / entry).lstrip('./') for entry in [manifest.get('main'), manifest.get('module'), *bins.values()]
             if isinstance(entry, str)}
    for script in (manifest.get('scripts') or {}).values():
        seeds |= {_source_of(base, file, known) or str(base / file).lstrip('./')
                  for file in re.findall(r'[\w./-]+\.(?:[cm]?[jt]sx?|py)\b', str(script))}
    return seeds


def _file_seeds(source, path, known):
    name = PurePosixPath(path).name
    if name in ENTRY_FILES: return set() if _is_test(path) else {path}
    if name == 'index.html': return _html_scripts(path, source.text(path) or '')
    if name == 'package.json': return _manifest_seeds(path, source.text(path), known)
    return set()


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
    named = (_normalised(base, literal) for literal in RELATIVE_LITERAL.findall(text))
    return {found for found in named if found and found in texts}


def _normalised(base, literal):
    """The snapshot path `literal` names from `base`, or None when it climbs above the root."""
    parts = []
    for part in (base / literal).parts:
        if part == '..':
            if not parts: return None
            parts.pop()
        elif part != '.': parts.append(part)
    return '/'.join(parts)


def _loaded(path, text, texts):
    """Files a module loads by a bare path literal, read from its own folder or a folder above it:
    `Path(__file__).resolve().parent / 'templates/screens/stream-reporter.mjs'` names a file no import reaches."""
    folders = list(PurePosixPath(path).parents)
    out = set()
    for literal in PATH_LITERAL.findall(text):
        out |= {found for folder in folders if (found := str(folder / literal).lstrip('./')) in texts}
    return out


def _glob(glob):
    """A setuptools glob as a pattern: `**/` any folders, `*` any name within one folder."""
    parts = re.split(r'(\*\*/|\*\*|\*|\?)', glob)
    return re.compile(''.join({'**/': '(?:.*/)?', '**': '.*', '*': '[^/]*', '?': '[^/]'}.get(part, re.escape(part)) for part in parts))


def _package_data(source, known):
    """Files a package ships as data: under a templates/ or rules/ folder, or matched by a declared
    `[tool.setuptools.package-data]` glob. They are loaded by path at run time; no import names them."""
    data = {path for path in known if DATA_FOLDERS & set(PurePosixPath(path).parts[:-1]) and not _is_test(path)}
    for manifest in (path for path in known if PurePosixPath(path).name == 'pyproject.toml'):
        data |= _declared_data(source, manifest, known)
    return data


def _package_bases(known, root, package):
    if package == '*': return {PurePosixPath(p).parent for p in known if PurePosixPath(p).name == '__init__.py'}
    return {root / package.replace('.', '/'), root / 'src' / package.replace('.', '/')}


def _matching(known, bases, glob):
    pattern = _glob(glob)
    return {path for path in known for base in bases
            if PurePosixPath(path).is_relative_to(base) and pattern.fullmatch(str(PurePosixPath(path).relative_to(base)))}


def _declared_data(source, manifest, known):
    """The files one pyproject.toml's `[tool.setuptools.package-data]` globs match."""
    section = re.search(r'^\[tool\.setuptools\.package-data\]\s*$(.*?)(?=^\[|\Z)', source.text(manifest) or '', re.M | re.S)
    root = PurePosixPath(manifest).parent
    data = set()
    for package, globs in re.findall(r'^\s*"?([\w.*-]+)"?\s*=\s*\[([^\]]*)\]', section.group(1) if section else '', re.M):
        bases = _package_bases(known, root, package)
        for glob in re.findall(r'["\']([^"\']+)["\']', globs): data |= _matching(known, bases, glob)
    return data


def _reachable(seeds, graph, texts):
    reached, frontier = set(seeds), set(seeds)
    while True:
        while frontier:
            frontier = {child for path in frontier for child in graph.get(path, ())} - reached
            reached |= frontier
        named = _text_loads(reached, texts)
        if not named: return reached
        reached |= named
        frontier = named


def _text_loads(reached, texts):
    """Files the reached modules load without an import: named in their text as a module, or by a path literal."""
    blob = '\n'.join(texts[path] for path in reached if path in texts)
    named = {path for path in texts if path not in reached and _named(path, blob)}
    named |= {found for path in reached if path in texts
              for found in _relative(path, texts[path], texts) | _loaded(path, texts[path], texts)} - reached
    return named


def _roots(source, known, seeds):
    """Where the walk starts: the production entry points and, when there are any, the tool configurations and the
    programs a CI step or a document says to run."""
    # A tool configuration (vite.config.ts, next.config.mjs) is loaded by the tool itself whenever it runs; what it
    # imports (a dev-server plugin, the API it mounts) is reached through it. It is a root to walk from, not an entry
    # point: a library with only a test-runner config still has no production entry, and is judged as a library.
    # A program a CI step or a document says to run is walked from the same way, and the files a build script hands
    # its bundler (eaos/facts/code/bundled.py).
    if not seeds: return seeds
    configs = {path for path in known if CONFIG.search(path) and not _is_test(path)}
    folders = {PurePosixPath(path).parent for path in known if PurePosixPath(path).name == 'package.json'}
    commanded = {path for path in _commanded(source, known, folders) if not _is_test(path)}
    return seeds | configs | commanded | _bundles(source, known)


def _bundles(source, known):
    """The files the project's build scripts hand their bundler (eaos/facts/code/bundled.py)."""
    return {found for path in known if path.endswith(BUILD_SCRIPTS) and not _is_test(path)
            for found in bundled.entries(path, source.text(path) or '', known)}

def _walk(source, known, texts, resolved, entry_points):
    """(seeds, reached, whole, test_importers): what the product reaches from its roots, and the files read whole.
    `texts`: the text of each code file."""
    graph, test_importers = _edges(resolved)
    seeds = _seeds(source, known, entry_points)
    reached = _reachable(_roots(source, known, seeds), graph, texts)
    # Package data and files loaded by a path literal are run or read whole by something else (a test runner, k6,
    # a codemod engine): they are reached, and their names are not judged one by one.
    whole = _package_data(source, known) | {found for path in reached if path in texts for found in _loaded(path, texts[path], texts)}
    return seeds, reached | whole, whole, test_importers
