"""Leftover files: temp edits, build outputs, committed credentials, unimported archive directories.

A file is a leftover when its filename or location declares it is not part of the product and
nothing imports it. Reporting a leftover also proves the file is unreachable: the import graph
that the resolver built is checked for any reference to the file or its module path, and a
file that the graph still reaches is left alone.
"""
import os
import re
from pathlib import PurePosixPath
from . import digest, make

NAME = 'leftovers'
VERSION = '1'
LIMITATIONS = [
    'Filename patterns cannot catch every intent; a "scratch.tsx" with no pattern match stays in the tree.',
    'A leftover is reported only after the import graph is available; the resolver must have run first.',
    'A leftover .env may be the only source of environment configuration for the project; the tool records it, the operator decides.',
    'Binary artifacts committed by mistake are listed by path only; their contents are not opened.',
]

# Temp-edit patterns: filenames a developer writes when they want to keep the original around.
TEMP_NAME = re.compile(r'temp_\w+|\w+_old\b|\w+_copy\b|\w+_backup\b|\w+_bak\b|\w+_orig\b', re.I)
# Build-output patterns: a file whose name starts with "build_" or lives under a generated artifact dir.
BUILD_PREFIX = re.compile(r'(^|[\\/])build[_-]')
BUILD_DIRS = {'dist', 'build', 'out', 'target', 'bin', 'obj', '.next', '.nuxt', '.svelte-kit', '.cache',
              'node_modules', '__pycache__', '.gradle', '.terraform', 'coverage', '.pytest_cache',
              'dist-ssr', 'storybook-static', 'public/build', 'artifacts'}
# A directory whose name signals it is archived or no longer in use.
ARCHIVE_DIR = re.compile(r'(^|[\\/])(?:unused[_-]archive|legacy|deprecated|scratch)(?:[\\/]|$)', re.I)
# Binary files that have no business being committed in a source tree.
BINARY_EXT = {'.dll', '.exe', '.so', '.dylib', '.bin', '.class', '.jar', '.war', '.o', '.a', '.lib',
              '.pyc', '.pyo', '.pdb'}
# Environment files that should never be committed (samples are fine).
ENV_NAME = re.compile(r'(^|[\\/])\.env(?:\.[\w.-]+)?$', re.I)
ENV_SAFE_NAMES = {'.env.example', '.env.sample', '.env.template', '.env.test'}


def _module_paths(rel, language):
    """Return a list of module-path candidates this file could be imported as."""
    parts = PurePosixPath(rel)
    candidates = [rel]
    name = parts.name
    if language == 'python':
        stem = name[:-3] if name.endswith('.py') else name
        candidates.append(stem)
        candidates.append('.'.join(parts.parts[:-1] + (stem,)))
    elif language in {'javascript', 'typescript', 'tsx'}:
        stem = PurePosixPath(name).stem
        candidates.append(stem)
        candidates.append('/'.join(parts.parts[:-1] + (stem,)))
        candidates.append('.'.join(parts.parts[:-1] + (stem,)))
    return candidates


def _is_reachable(rel, language, imported_modules):
    """A file is reachable when any of its module-path candidates appear in the import graph."""
    if not imported_modules: return False
    return any(c in imported_modules for c in _module_paths(rel, language))


def classify(rel):
    """Return a reason string for why this path looks like a leftover, or None."""
    name = PurePosixPath(rel).name
    parts = PurePosixPath(rel).parts
    if name in ENV_SAFE_NAMES: return None
    if ENV_NAME.match(rel): return 'env_file_committed'
    ext = os.path.splitext(name)[1].lower()
    if ext in BINARY_EXT: return 'committed_binary'
    if TEMP_NAME.search(name): return 'temp_or_backup_name'
    if any(part in {'backup', 'bak', 'old', 'orig'} for part in parts): return 'temp_or_backup_name'
    if ARCHIVE_DIR.match(rel): return 'archived_directory'
    if any(part in BUILD_DIRS for part in parts): return 'build_output'
    if BUILD_PREFIX.match(name): return 'build_output'
    return None


def _imported_modules(resolve_facts):
    """Module identifiers that something imports into: to_path and module.

    A file that has imports of its own is not necessarily reachable: the import graph
    only says who points at it. We only count the destinations of edges.
    """
    imported = set()
    for row in resolve_facts:
        value = row.get('value') or {}
        for key in ('module', 'to_path'):
            target = value.get(key)
            if target: imported.add(target)
    return imported


def collect(source, resolve_facts):
    """Walk the snapshot, classify each path, prove unimported, and yield fact-ready records."""
    facts_list = []
    imported = _imported_modules(resolve_facts or [])
    for item in source.readable():
        rel = item['path']
        reason = classify(rel)
        if not reason: continue
        # Determine language from extension
        ext = os.path.splitext(rel)[1].lower()
        language = None
        if ext == '.py': language = 'python'
        elif ext in {'.js', '.jsx', '.mjs', '.cjs'}: language = 'javascript'
        elif ext == '.ts': language = 'typescript'
        elif ext == '.tsx': language = 'tsx'
        if _is_reachable(rel, language, imported): continue
        facts_list.append({'path': rel, 'reason': reason, 'sha256': item.get('sha256')})
    return facts_list


def run(target, source, resolve_facts=None, **options):
    """Produce leftover facts for the snapshot, given the resolver's facts."""
    if resolve_facts is None:
        import json as _json
        path = target / 'facts' / 'resolve.json' if hasattr(target, '__truediv__') else None
        if path and path.is_file():
            resolve_facts = _json.loads(path.read_text(encoding='utf-8')).get('facts', [])
    collected = collect(source, resolve_facts or [])
    fingerprints = [record.get('sha256') or digest(record['path'].encode('utf-8')) for record in collected]
    facts_list = [make('leftover', NAME, VERSION, digest(record['path'].encode('utf-8')),
                       {'path': record['path'], 'start_line': 1},
                       {'path': record['path'], 'reason': record['reason']},
                       limitations=LIMITATIONS)
                  for record in collected]
    by_reason = {}
    for record in collected:
        by_reason[record['reason']] = by_reason.get(record['reason'], 0) + 1
    summary = {'candidates': len(facts_list),
               'by_reason': by_reason,
               'interpretation': 'A leftover is reported only after it has been verified as unreachable from any import edge.'}
    return {'facts': facts_list, 'summary': summary, 'available': True,
            'input_sha': digest(''.join(sorted(fingerprints)).encode('utf-8')), 'reason': None}
