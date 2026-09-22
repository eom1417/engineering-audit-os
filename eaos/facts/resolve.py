"""Turn import observations into real file→file edges, or say plainly that they are unresolved.

An edge is only RESOLVED when a concrete target file exists in the snapshot. Anything else stays
EXTERNAL, AMBIGUOUS or UNRESOLVED; nothing is promoted to a confirmed relationship by guessing.
"""
from pathlib import PurePosixPath
import re
from . import digest, make
from .source import language_of

NAME = 'resolve'
VERSION = '1'
LIMITATIONS = [
    'Only statically written imports are resolved; dynamic loading and injection are invisible.',
    'EXTERNAL means "not a file in this snapshot", not "third-party package" in every case.',
    'AMBIGUOUS edges have more than one plausible target and must not be read as a dependency.',
    'A resolved import is a source dependency, not proof that the call happens at runtime.',
]
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


def js_candidates(importer, module):
    if not module.startswith('.'): return []
    target = js_directory(importer, module)
    if not target: return ['index.js', 'index.ts', 'index.mjs']
    return [target] + [target + suffix for suffix in JS_SUFFIXES] + [target + index for index in JS_INDEX]


def package_main(directory, source, known):
    """A require of a directory resolves through its package.json main field, as Node does."""
    manifest = (directory + '/package.json').lstrip('/')
    if manifest not in known: return []
    import json as json_module
    try: data = json_module.loads(source.text(manifest) or '{}')
    except ValueError: return []
    base = (directory + '/').lstrip('/')
    entries = [data.get('main'), data.get('module')]
    exports = data.get('exports')
    if isinstance(exports, dict):
        root = exports.get('.')
        entries.append(root if isinstance(root, str) else (root or {}).get('require') if isinstance(root, dict) else None)
    out = []
    for entry in entries:
        if not isinstance(entry, str): continue
        cleaned = (base + entry.lstrip('./')).replace('//', '/')
        out += [cleaned] + [cleaned + suffix for suffix in JS_SUFFIXES] + [cleaned + index for index in JS_INDEX]
    return out


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


def run(target, source, imports=None, external_edges=None, **options):
    """Augment our import graph with what the external engine resolved.

    `external_edges` is a list of `call_edge` / `import_edge` facts produced by
    `eaos.facts.external`. Each carries resolution=RESOLVED_BY_ENGINE; we keep them
    separate from edges we resolved ourselves so a reviewer can tell which
    engine claimed the relationship.
    """
    from . import syntax
    facts, fingerprints = [], []
    known = {item['path'] for item in source.readable()}
    directories = {PurePosixPath(p).parent.as_posix() for p in known}
    go_module = go_module_name(source)
    rows = imports if imports is not None else [f for f in syntax.run(target, source)['facts'] if f['kind'] == 'import_edge']
    counts = {'RESOLVED': 0, 'EXTERNAL': 0, 'AMBIGUOUS': 0, 'UNRESOLVED': 0,
                'RESOLVED_BY_ENGINE': 0}
    expanded = []
    for row in sorted(rows, key=lambda f: (f['location']['path'], f['location'].get('start_line', 0), f['value']['module'])):
        names = row['value'].get('names') or []
        # `from package import submodule` depends on the submodule, not on the package __init__.
        if row['value'].get('language') == 'python' and names:
            base = row['value']['module']
            matched = 0
            for name in names:
                child = dict(row, value=dict(row['value'], module=(base + '.' + name) if base else name, names=[]))
                if any(candidate in known
                       for candidate in python_candidates(row['location']['path'], child['value']['module'], row['value'].get('level', 0))):
                    expanded.append(child)
                    matched += 1
            # Only when every imported name is a submodule does the package import add nothing further.
            if matched == len(names): continue
        expanded.append(row)
    for row in expanded:
        importer = row['location']['path']
        module = row['value']['module']
        language = row['value'].get('language') or language_of(importer)
        level = row['value'].get('level', 0)
        if language == 'python': candidates = python_candidates(importer, module, level)
        elif language in {'javascript', 'typescript', 'tsx'}: candidates = js_candidates(importer, module)
        elif language == 'go': candidates = go_candidates(module, go_module)
        elif language in {'java', 'kotlin', 'scala'}: candidates = jvm_candidates(module)
        elif language in {'c', 'cpp'}: candidates = js_candidates(importer, './' + module) if not module.startswith('<') else []
        else: candidates = js_candidates(importer, module) if module.startswith('.') else []
        matches = [c for c in dict.fromkeys(candidates) if c in known]
        if language in {'java', 'kotlin', 'scala'} and not matches:
            suffix = jvm_candidates(module)
            matches = sorted(p for p in known if any(p.endswith('/' + s) for s in suffix))
        if language in {'javascript', 'typescript', 'tsx'} and not matches and module.startswith('.'):
            matches = [c for c in dict.fromkeys(package_main(js_directory(importer, module), source, known)) if c in known]
        if language == 'go' and not matches and candidates:
            prefix = candidates[0]
            matches = sorted(p for p in known if p.startswith(prefix) and language_of(p) == 'go')
        # A Go import `import ".../internal/config"` resolves to a package, not a single file.
        # When every candidate is in the same directory it is not ambiguity: the directory
        # IS the target. Real ambiguity only exists when candidates span multiple directories.
        if language == 'go' and len(matches) > 1:
            folders = {PurePosixPath(p).parent.as_posix() for p in matches}
            if len(folders) == 1:
                resolution, value = 'RESOLVED', sorted(matches)[0]
                target_kind = 'package'
            else:
                resolution, value = 'AMBIGUOUS', None
                target_kind = None
        elif len(matches) == 1: resolution, value, target_kind = 'RESOLVED', matches[0], None
        elif len(matches) > 1: resolution, value, target_kind = 'AMBIGUOUS', None, None
        elif not candidates or (language in {'javascript', 'typescript', 'tsx'} and not module.startswith('.')) or (language == 'python' and not level and module.split('.')[0] not in {PurePosixPath(p).parts[0] for p in known} | {d.split('/')[0] for d in directories}):
            resolution, value, target_kind = 'EXTERNAL', None, None
        else: resolution, value, target_kind = 'UNRESOLVED', None, None
        counts[resolution] += 1
        fingerprints.append(row['id'])
        facts.append(make('module_edge', NAME, VERSION, row['input_sha'],
                          {'path': importer, 'start_line': row['location'].get('start_line')},
                          {'module': module, 'language': language, 'to_path': value,
                           'target_kind': target_kind,
                           'candidates': matches[:5] if resolution == 'AMBIGUOUS' else matches,
                           'import_fact_id': row['id']},
                          resolution=resolution, limitations=LIMITATIONS))
    # Layer in what the external engine resolved. Each carries its own resolution marker.
    engine_facts = list(external_edges or [])
    facts.extend(engine_facts)
    counts['RESOLVED_BY_ENGINE'] = sum(1 for f in engine_facts if f.get('resolution') == 'RESOLVED_BY_ENGINE')

    internal = counts['RESOLVED'] + counts['AMBIGUOUS'] + counts['UNRESOLVED']
    summary = {'edges': len(facts), 'by_resolution': counts,
               'resolved_by_us': counts['RESOLVED'],
               'resolved_by_engine': counts['RESOLVED_BY_ENGINE'],
               'internal_resolution_rate': round(counts['RESOLVED'] / internal, 3) if internal else 0.0,
               'go_module': go_module,
               'interpretation': 'Source dependencies only. Unresolved and ambiguous edges stay visible and must never be drawn as confirmed dependencies.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(''.join(sorted(fingerprints)).encode('utf-8')), 'reason': None}
