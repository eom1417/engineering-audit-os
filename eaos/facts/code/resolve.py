"""Turn import observations into real file→file edges, or say plainly that they are unresolved.

An edge is only RESOLVED when a concrete target file exists in the snapshot. Anything else stays
EXTERNAL, AMBIGUOUS or UNRESOLVED; nothing is promoted to a confirmed relationship by guessing.
"""
from pathlib import PurePosixPath
import re
from .. import digest, make
from ..source import language_of

NAME = 'resolve'
VERSION = '1'
LIMITATIONS = [
    'Only statically written imports are resolved; dynamic loading and injection are invisible.',
    'EXTERNAL means "not a file in this snapshot", not "third-party package" in every case.',
    'AMBIGUOUS edges have more than one plausible target and must not be read as a dependency.',
    'A resolved import is a source dependency, not proof that the call happens at runtime.',
    'When `target_kind` is "package" the import names the directory in `package_path`; `to_path` is '
    'one source file standing in for it, so that every reader of the graph still follows a file.',
]


def non_test_files(paths):
    """The paths that are not a test file, by each language's own naming convention.

    A package's stand-in file must not be a test: an import of `internal/engine` that points at
    `append_replace_test.go` puts a fixture on the dependency graph. Returns an empty list when
    every candidate is a test, and the caller then falls back to the full list rather than
    dropping the edge.
    """
    markers = ('_test.go', '_test.py', '.test.ts', '.test.js', '.spec.ts', '.spec.js', '_spec.rb')
    return [path for path in paths
            if not path.endswith(markers) and not PurePosixPath(path).name.startswith('test_')]
JS_SUFFIXES = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.vue', '.svelte']
JS_INDEX = ['/index.ts', '/index.tsx', '/index.js', '/index.jsx']


def python_candidates(importer, module, level):
    parts = module.split('.') if module else []
    if level:
        base = PurePosixPath(importer).parent
        for _ in range(level - 1):
            base = base.parent
        stem = base.joinpath(*parts).as_posix().lstrip('/')
        return [stem + '.py', stem + '/__init__.py']
    candidates = []
    dotted = '/'.join(parts)
    candidates += [dotted + '.py', dotted + '/__init__.py']
    for ancestor in list(PurePosixPath(importer).parents):
        prefix = ancestor.as_posix()
        prefix = '' if prefix == '.' else prefix + '/'
        candidates += [prefix + dotted + '.py', prefix + dotted + '/__init__.py']
    return candidates


def js_directory(importer, module):
    """Normalise a relative specifier the way a module loader would, resolving .. properly."""
    stack = []
    for part in (PurePosixPath(importer).parent / module).parts:
        if part in {'', '.'}: continue
        if part == '..':
            if stack: stack.pop()
            continue
        stack.append(part)
    return '/'.join(stack)


def _jsonc(text):
    """tsconfig.json allows comments and trailing commas; strip both before json.loads."""
    import json as json_module
    text = re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', lambda m: m.group(0) if m.group(0)[0] == '"' else '', text, flags=re.S)
    text = re.sub(r',\s*([}\]])', r'\1', text)
    try: return json_module.loads(text)
    except ValueError: return {}


VITE_ALIAS = re.compile(r'''["']?([@~][\w-]*)["']?\s*:\s*(?:path\.)?resolve\(\s*__dirname\s*,\s*["']\.?/?([^"']*)["']\s*\)''')


def js_aliases(source, known):
    """Path aliases, as (prefix, [directories]) longest prefix first: `@/` -> `src/`.

    Read from compilerOptions.paths in every tsconfig*.json and jsconfig.json (relative to that file
    and its baseUrl), then from `alias` entries in vite.config.*. Without either, `@/` and `~/` still
    point at src/ when it exists: no npm package can be named with an empty scope, so they are never
    external.
    """
    aliases = {}
    for path in sorted(known):
        name = PurePosixPath(path).name
        if '/node_modules/' in '/' + path: continue
        if name.startswith(('tsconfig', 'jsconfig')) and name.endswith('.json'): _config_aliases(source, path, aliases)
        elif name.startswith('vite.config.'): _vite_aliases(source, path, aliases)
    _default_aliases(aliases, known)
    return sorted(((prefix, list(dict.fromkeys(folders))) for prefix, folders in aliases.items()), key=lambda row: -len(row[0]))


def _default_aliases(aliases, known):
    """`@/` and `~/`, when nothing declares them, point at src/ if the snapshot has one."""
    has_src = any(p.startswith('src/') for p in known)
    for prefix in ('@/', '~/'):
        if prefix not in aliases and has_src: aliases[prefix] = ['src/']


def _alias_folder(base, target):
    folder = js_directory((base / 'x').as_posix(), './' + str(target).rstrip('*'))
    return (folder + '/') if folder and str(target).endswith('/*') else folder


def _config_aliases(source, path, aliases):
    """compilerOptions.paths of one tsconfig or jsconfig, relative to it and its baseUrl."""
    options = (_jsonc(source.text(path) or '') or {}).get('compilerOptions') or {}
    base = PurePosixPath(path).parent / (options.get('baseUrl') or '.')
    for pattern, targets in (options.get('paths') or {}).items():
        if not isinstance(targets, list): continue
        for target in targets: aliases.setdefault(pattern.rstrip('*'), []).append(_alias_folder(base, target))


def _vite_aliases(source, path, aliases):
    for prefix, folder in VITE_ALIAS.findall(source.text(path) or ''):
        folder = js_directory(path, './' + folder)
        aliases.setdefault(prefix + '/', []).append(folder + '/' if folder else '')


def alias_of(module, aliases):
    """The alias prefix a specifier starts with, or None."""
    return next((prefix for prefix, _ in aliases if module == prefix.rstrip('/') or module.startswith(prefix)), None)


# TypeScript's own rule: `import './env.js'` in a .ts file names the source ./env.ts (and .jsx a .tsx, .mjs a .mts,
# .cjs a .cts), because the import is written as it will be once compiled.
TS_SOURCE_OF = {'.js': ('.ts', '.tsx'), '.jsx': ('.tsx',), '.mjs': ('.mts',), '.cjs': ('.cts',)}


def js_expand(target):
    stem, dot, extension = target.rpartition('.')
    typed = [stem + suffix for suffix in TS_SOURCE_OF.get('.' + extension, ())] if dot and '/' not in extension else []
    return [target] + typed + [target + suffix for suffix in JS_SUFFIXES] + [target + index for index in JS_INDEX]


def js_candidates(importer, module, aliases=()):
    # A bundler query (`./styles.css?url`, `./worker?raw`) names the same file.
    module = module.split('?', 1)[0]
    if module.startswith('.'):
        target = js_directory(importer, module)
        return js_expand(target) if target else ['index.js', 'index.ts', 'index.mjs']
    prefix = alias_of(module, aliases)
    return _alias_candidates(module, prefix, aliases) if prefix is not None else []


def _alias_target(folder, rest):
    return (folder + rest).strip('/') if folder.endswith('/') or not rest else (folder + '/' + rest).strip('/')


def _alias_candidates(module, prefix, aliases):
    rest = module[len(prefix):] if module.startswith(prefix) else ''
    out = []
    for row_prefix, folders in aliases:
        if row_prefix != prefix: continue
        for folder in folders: out += js_expand(_alias_target(folder, rest))
    return out


def package_main(directory, source, known):
    """A require of a directory resolves through its package.json main field, as Node does."""
    manifest = (directory + '/package.json').lstrip('/')
    if manifest not in known: return []
    import json as json_module
    try: data = json_module.loads(source.text(manifest) or '{}')
    except ValueError: return []
    base = (directory + '/').lstrip('/')
    out = []
    for entry in _package_entries(data):
        if not isinstance(entry, str): continue
        cleaned = (base + entry.lstrip('./')).replace('//', '/')
        out += [cleaned] + [cleaned + suffix for suffix in JS_SUFFIXES] + [cleaned + index for index in JS_INDEX]
    return out


def _package_entries(data):
    """What a package.json names as its entry: its main, its module, and the root of its exports (or its require)."""
    entries = [data.get('main'), data.get('module')]
    exports = data.get('exports')
    if isinstance(exports, dict):
        root = exports.get('.')
        entries.append(root if isinstance(root, str) else (root or {}).get('require') if isinstance(root, dict) else None)
    return entries


def go_candidates(module, go_module):
    if not go_module or not module.startswith(go_module): return []
    relative = module[len(go_module):].strip('/')
    return [relative + '/', relative]


def jvm_candidates(module):
    path = module.replace('.', '/').rstrip('/*')
    return [path + '.java', path + '.kt', path + '.scala']


def go_module_name(source):
    for item in source.readable():
        if PurePosixPath(item['path']).name == 'go.mod':
            text = source.text(item['path']) or ''
            match = re.search(r'^module\s+(\S+)', text, re.M)
            if match: return match.group(1)
    return None


JS_LANGUAGES = {'javascript', 'typescript', 'tsx'}
JVM_LANGUAGES = {'java', 'kotlin', 'scala'}


def _submodule(row, base, name):
    return dict(row, value=dict(row['value'], module=(base + '.' + name) if base else name, names=[]))


def _with_submodules(row, known):
    """`from package import submodule` depends on the submodule, not on the package __init__: one edge per
    imported name that is a submodule, then the package import unless every name was one."""
    names = row['value'].get('names') or []
    if row['value'].get('language') != 'python' or not names: return [row]
    level = row['value'].get('level', 0)
    children = [child for child in (_submodule(row, row['value']['module'], name) for name in names)
                if any(candidate in known for candidate in python_candidates(row['location']['path'], child['value']['module'], level))]
    # Only when every imported name is a submodule does the package import add nothing further.
    return children if len(children) == len(names) else children + [row]


def _candidates(language, importer, module, level, context):
    if language == 'python': return python_candidates(importer, module, level)
    if language in JS_LANGUAGES: return js_candidates(importer, module, context['aliases'])
    if language == 'go': return go_candidates(module, context['go_module'])
    if language in JVM_LANGUAGES: return jvm_candidates(module)
    if language in {'c', 'cpp'}: return js_candidates(importer, './' + module) if not module.startswith('<') else []
    return js_candidates(importer, module) if module.startswith('.') else []


def _matches(language, importer, module, candidates, context):
    """The snapshot files an import may name; when none is a candidate, the language's own fallback."""
    known = context['known']
    matches = [c for c in dict.fromkeys(candidates) if c in known]
    if matches: return matches
    if language in JVM_LANGUAGES: return _jvm_matches(module, known)
    if language in JS_LANGUAGES and module.startswith('.'): return _package_matches(importer, module, context)
    if language == 'go' and candidates: return _go_matches(candidates[0], known)
    return matches


def _jvm_matches(module, known):
    """A JVM import's file anywhere under a source root: the files ending on its package path."""
    suffix = jvm_candidates(module)
    return sorted(p for p in known if any(p.endswith('/' + s) for s in suffix))


def _package_matches(importer, module, context):
    """A relative JavaScript import of a directory: the files its package.json names."""
    known = context['known']
    return [c for c in dict.fromkeys(package_main(js_directory(importer, module), context['source'], known)) if c in known]


def _go_matches(folder, known):
    """A Go import of a package: the Go files under its directory."""
    return sorted(p for p in known if p.startswith(folder) and language_of(p) == 'go')


def _go_package(matches):
    """A Go import `import ".../internal/config"` resolves to a package, not a single file. When every candidate is in
    the same directory it is not ambiguity: the directory IS the target. Real ambiguity only exists when candidates
    span multiple directories."""
    folders = {PurePosixPath(p).parent.as_posix() for p in matches}
    if len(folders) != 1: return 'AMBIGUOUS', None, None, None
    # `to_path` has to stay a file: the graph, the policy and the tracer all follow it.
    # It stands in for the package, so it must never be a test file while a source file
    # exists -- an edge into `_test.go` would put somebody else's fixtures on the
    # architecture picture. `package_path` carries the target the import actually names.
    return 'RESOLVED', sorted(non_test_files(matches) or matches)[0], 'package', folders.pop()


def _external(language, module, level, candidates, context):
    if not candidates: return True
    if language in JS_LANGUAGES and not module.startswith('.') and alias_of(module, context['aliases']) is None: return True
    return language == 'python' and not level and module.split('.')[0] not in context['roots']


def _resolution(edge, candidates, matches, context):
    """(resolution, to_path, target_kind, package_path) of one import."""
    language, module, level = edge
    if language == 'go' and len(matches) > 1: return _go_package(matches)
    if len(matches) == 1: return 'RESOLVED', matches[0], None, None
    excluded = None if matches else next((c for c in dict.fromkeys(candidates) if c in context['out_of_scope']), None)
    if excluded is not None:
        # The target exists but sits in an excluded vendored directory (components/ui): outside the
        # analysed system like a package, not an unresolved import. package_path keeps where it points.
        return 'EXTERNAL', None, 'excluded', excluded
    if len(matches) > 1: return 'AMBIGUOUS', None, None, None
    if _external(language, module, level, candidates, context): return 'EXTERNAL', None, None, None
    return 'UNRESOLVED', None, None, None


def _module_edge(row, context):
    """(resolution, module_edge fact) of one import observation."""
    importer = row['location']['path']
    module = row['value']['module']
    language = row['value'].get('language') or language_of(importer)
    level = row['value'].get('level', 0)
    candidates = _candidates(language, importer, module, level, context)
    matches = _matches(language, importer, module, candidates, context)
    resolution, value, target_kind, package_path = _resolution((language, module, level), candidates, matches, context)
    return resolution, make('module_edge', NAME, VERSION, row['input_sha'],
                            {'path': importer, 'start_line': row['location'].get('start_line')},
                            {'module': module, 'language': language, 'to_path': value,
                             'target_kind': target_kind, 'package_path': package_path,
                             'candidates': matches[:5] if resolution == 'AMBIGUOUS' else matches,
                             'import_fact_id': row['id']},
                            resolution=resolution, limitations=LIMITATIONS)


def _context(source, known):
    """What resolving every import shares: the files, the Go module, the JavaScript aliases, the excluded files, and the
    top folders a Python import of the project starts with."""
    directories = {PurePosixPath(p).parent.as_posix() for p in known}
    return {'source': source, 'known': known, 'go_module': go_module_name(source), 'aliases': js_aliases(source, known),
            'out_of_scope': set(getattr(source, 'excluded_files', ())),
            'roots': {PurePosixPath(p).parts[0] for p in known} | {d.split('/')[0] for d in directories}}


def _summary(facts, counts, go_module):
    internal = counts['RESOLVED'] + counts['AMBIGUOUS'] + counts['UNRESOLVED']
    return {'edges': len(facts), 'by_resolution': counts,
            'resolved_by_us': counts['RESOLVED'],
            'resolved_by_engine': counts['RESOLVED_BY_ENGINE'],
            'internal_resolution_rate': round(counts['RESOLVED'] / internal, 3) if internal else 0.0,
            'go_module': go_module,
            'interpretation': 'Source dependencies only. Unresolved and ambiguous edges stay visible and must never be drawn as confirmed dependencies.'}


def _read_imports(target, source):
    """The import observations the syntax extractor reads, when the caller passed none."""
    from . import syntax
    return [f for f in syntax.run(target, source)['facts'] if f['kind'] == 'import_edge']


def run(target, source, imports=None, external_edges=None, **options):
    """Augment our import graph with what the external engine resolved.

    `external_edges` is a list of `call_edge` / `import_edge` facts produced by
    `eaos.facts.engine_findings`. Each carries resolution=RESOLVED_BY_ENGINE; we keep them
    separate from edges we resolved ourselves so a reviewer can tell which
    engine claimed the relationship.
    """
    facts, fingerprints = [], []
    known = {item['path'] for item in source.readable()}
    context = _context(source, known)
    rows = imports if imports is not None else _read_imports(target, source)
    counts = {'RESOLVED': 0, 'EXTERNAL': 0, 'AMBIGUOUS': 0, 'UNRESOLVED': 0,
                'RESOLVED_BY_ENGINE': 0}
    ordered = sorted(rows, key=lambda f: (f['location']['path'], f['location'].get('start_line', 0), f['value']['module']))
    for row in (edge for row in ordered for edge in _with_submodules(row, known)):
        resolution, fact = _module_edge(row, context)
        counts[resolution] += 1
        fingerprints.append(row['id'])
        facts.append(fact)
    # Layer in what the external engine resolved. Each carries its own resolution marker.
    engine_facts = list(external_edges or [])
    facts.extend(engine_facts)
    counts['RESOLVED_BY_ENGINE'] = sum(1 for f in engine_facts if f.get('resolution') == 'RESOLVED_BY_ENGINE')
    return {'facts': facts, 'summary': _summary(facts, counts, context['go_module']), 'available': True,
            'input_sha': digest(''.join(sorted(fingerprints)).encode('utf-8')), 'reason': None}
