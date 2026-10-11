"""The architecture map: the city of the code (CodeCharta) and its dependency clusters (Emerge), drawn from the code.

    city(target, folder)       ccsh unifiedparser (size and complexity per file) and gitlogparser (how often each file
                               changed), merged into <folder>/city.cc.json: a building per file, its area the size, its
                               height the complexity, its colour the changes; CodeCharta's own viewer opens the file
    clusters(target, folder)   emerge: the file dependency graph with its Louvain modules and fan-in and fan-out, as
                               <folder>/emerge/*.json and the local page <folder>/emerge/html/emerge.html

Each returns {status, reason?, ...counts}: 'observed', 'unavailable' (not installed, nothing to read) or 'error'. The
target is only read; both tools write outside it.
"""
import json
import os
from pathlib import Path

from .process import run, which

SKIP = ('node_modules', '.git', 'dist', 'build', '.venv', 'venv', '__pycache__', 'coverage', '.next', 'vendor')
# emerge reads one language per analysis, by these extensions.
LANGUAGES = {'python': ('.py',), 'javascript': ('.js', '.jsx', '.mjs'), 'typescript': ('.ts', '.tsx'), 'go': ('.go',),
             'java': ('.java',), 'kotlin': ('.kt',)}


def _files(target):
    for root, directories, files in os.walk(target):
        directories[:] = [d for d in directories if d not in SKIP and not d.startswith('.')]
        for name in files: yield Path(root) / name


def _java():
    """ccsh runs on the pinned JRE, which the tools' bin folder holds."""
    from .. import toolchain
    return {'PATH': str(toolchain.home() / 'bin') + os.pathsep + os.environ.get('PATH', '')}


def city(target, folder):
    ccsh = which('ccsh')
    if not ccsh: return {'status': 'unavailable', 'reason': 'ccsh is not installed: python -m eaos tools install --only codecharta'}
    folder.mkdir(parents=True, exist_ok=True)
    parts = [folder / 'code.cc.json']
    code, _, err, _ = run([ccsh, 'unifiedparser', str(target), '-o', str(parts[0]), '-nc'], timeout=1800, env=_java())
    if code or not parts[0].is_file(): return {'status': 'error', 'reason': f'ccsh unifiedparser exited {code}: {err[-400:]}'}
    if (Path(target) / '.git').exists():
        code, _, err, _ = run([ccsh, 'gitlogparser', 'repo-scan', '--repo-path', str(target), '-o', str(folder / 'git.cc.json'), '-nc'],
                              timeout=1800, env=_java())
        if code == 0 and (folder / 'git.cc.json').is_file(): parts.append(folder / 'git.cc.json')
    merged = folder / 'city.cc.json'
    code, _, err, _ = run([ccsh, 'merge', *map(str, parts), '-o', str(merged), '-nc'], timeout=600, env=_java())
    if code or not merged.is_file(): return {'status': 'error', 'reason': f'ccsh merge exited {code}: {err[-400:]}'}
    for part in parts: part.unlink(missing_ok=True)
    (folder / 'git.cc.json').unlink(missing_ok=True)
    files = sum(1 for _ in _leaves(json.loads(merged.read_text(encoding='utf-8')).get('files') or []))
    return {'status': 'observed', 'file': 'city.cc.json', 'buildings': files, 'with_changes': len(parts) > 1}


def _leaves(nodes):
    for node in nodes:
        if node.get('type') == 'File': yield node
        yield from _leaves(node.get('children') or [])


def _config(target, export, languages):
    """emerge's YAML: one analysis per language of the project, every metric that draws the clusters."""
    lines = ['---', 'project_name: map', 'loglevel: error', 'analyses:']
    for language in languages:
        lines += [f'- analysis_name: {language}', f'  source_directory: {json.dumps(str(target))}',
                  '  only_permit_languages:', f'  - {language}', '  only_permit_file_extensions:',
                  *[f'  - {ext}' for ext in LANGUAGES[language]], '  ignore_directories_containing:', *[f'  - {d}' for d in SKIP],
                  '  file_scan:', '  - number_of_methods', '  - source_lines_of_code', '  - dependency_graph', '  - fan_in_out',
                  '  - louvain_modularity', '  export:', f'  - directory: {json.dumps(str(export / language))}', '  - json', '  - d3']
    return '\n'.join(lines) + '\n'


def clusters(target, folder):
    emerge = which('emerge')
    if not emerge: return {'status': 'unavailable', 'reason': 'emerge is not installed: python -m eaos tools install --only emerge'}
    found = {ext for path in _files(target) for ext in [path.suffix]}
    languages = [name for name, exts in LANGUAGES.items() if found & set(exts)]
    if not languages: return {'status': 'unavailable', 'reason': 'no file in a language emerge reads (' + ', '.join(LANGUAGES) + ')'}
    export = folder / 'emerge'
    for language in languages: (export / language).mkdir(parents=True, exist_ok=True)
    config = folder / 'emerge.yaml'
    config.write_text(_config(Path(target).resolve(), export.resolve(), languages), encoding='utf-8')
    code, _, err, seconds = run([emerge, '-c', str(config)], timeout=3600)
    # emerge ends by copying a path to the clipboard, which fails on a computer without one: its files decide.
    drawn = {language: export / language / 'emerge-file_result_dependency_graph-data.json' for language in languages}
    written = {language: path for language, path in drawn.items() if path.is_file()}
    if not written: return {'status': 'error', 'reason': f'emerge exited {code} and wrote no graph: {err[-400:]}'}
    nodes = edges = 0
    for path in written.values():
        graph = json.loads(path.read_text(encoding='utf-8'))
        nodes, edges = nodes + len(graph.get('nodes') or []), edges + len(graph.get('edges') or [])
    return {'status': 'observed', 'languages': sorted(written), 'files': nodes, 'imports': edges,
            'pages': {language: f'emerge/{language}/html/emerge.html' for language in written
                      if (export / language / 'html/emerge.html').is_file()}}
