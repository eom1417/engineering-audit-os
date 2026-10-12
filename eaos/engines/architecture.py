"""The architecture map: the city of the code (CodeCharta) and its dependency clusters (Emerge), drawn from the code.

    city(target, folder)       ccsh unifiedparser (size and complexity per file) and gitlogparser (how often each file
                               changed), merged into <folder>/city.cc.json: a building per file, its area the size, its
                               height the complexity, its colour the changes; CodeCharta's own viewer opens the file
    clusters(target, folder)   emerge: the file dependency graph with its Louvain modules and fan-in and fan-out, as
                               <folder>/emerge/<language>/*.json (JSON only: its HTML page weighs 9 MB and nobody opens it)
    digest(folder)             what the assistant reads of both: the hotspots of the city (complexity times changes) and
                               the largest clusters with their members and the files most depended on

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
    if (Path(target) / '.git').exists(): parts += _with_history(ccsh, target, folder)
    merged = folder / 'city.cc.json'
    code, _, err, _ = run([ccsh, 'merge', *map(str, parts), '-o', str(merged), '-nc'], timeout=600, env=_java())
    if code or not merged.is_file(): return {'status': 'error', 'reason': f'ccsh merge exited {code}: {err[-400:]}'}
    for part in parts: part.unlink(missing_ok=True)
    (folder / 'git.cc.json').unlink(missing_ok=True)
    files = sum(1 for _ in _leaves(json.loads(merged.read_text(encoding='utf-8')).get('files') or []))
    return {'status': 'observed', 'file': 'city.cc.json', 'buildings': files, 'with_changes': len(parts) > 1}


def _with_history(ccsh, target, folder):
    """[git.cc.json] when ccsh's history parser read how often each file changed, else []."""
    code, _, err, _ = run([ccsh, 'gitlogparser', 'repo-scan', '--repo-path', str(target), '-o', str(folder / 'git.cc.json'), '-nc'],
                          timeout=1800, env=_java())
    return [folder / 'git.cc.json'] if code == 0 and (folder / 'git.cc.json').is_file() else []


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
                  '  - louvain_modularity', '  export:', f'  - directory: {json.dumps(str(export / language))}', '  - json']
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
    drawn = {language: export / language / STATISTICS for language in languages}
    written = {language: path for language, path in drawn.items() if path.is_file()}
    if not written: return {'status': 'error', 'reason': f'emerge exited {code} and wrote no metrics: {err[-400:]}'}
    files = sum(len(json.loads(path.read_text(encoding='utf-8')).get('local-metrics') or {}) for path in written.values())
    return {'status': 'observed', 'languages': sorted(written), 'files': files}


STATISTICS = 'emerge-statistics-and-metrics.json'
HOTSPOTS, CLUSTERS, MEMBERS = 10, 8, 8


def _paths(nodes, prefix=''):
    """{node id: path} of every file of a cc.json tree, the root folder left out."""
    found = {}
    for node in nodes:
        path = f"{prefix}/{node.get('name')}" if prefix else ('' if node.get('name') == 'root' else node.get('name', ''))
        if node.get('type') == 'File': found[node.get('id')] = path.lstrip('/')
        found.update(_paths(node.get('children') or [], path))
    return found


def _attributes(city_record):
    """{path: metrics} from a cc.json: its lenses (API 2.x, keyed by node id) or the attributes on each file node."""
    nodes = city_record.get('files') or city_record.get('nodes') or []
    paths = _paths(nodes)
    merged = {}
    for lens in (city_record.get('lenses') or {}).values():
        for node, values in ((lens or {}).get('attributes') or {}).items():
            if node in paths: merged.setdefault(paths[node], {}).update(values)
    return merged or {paths[leaf['id']]: leaf.get('attributes') or {} for leaf in _leaves(nodes) if paths.get(leaf.get('id'))}


def digest(folder):
    """{hotspots, clusters, modularity}: the city's files ranked by complexity times changes (size breaks a tie), and
    emerge's Louvain clusters, largest first, each with its members and its most depended-on file. Empty parts when a
    tool did not draw its part."""
    folder = Path(folder)
    out = {'hotspots': _hotspots(folder / 'city.cc.json'), 'clusters': [], 'modularity': None}
    for stats in sorted((folder / 'emerge').glob('*/' + STATISTICS)):
        record = json.loads(stats.read_text(encoding='utf-8'))
        out['clusters'] += _clusters_of(stats.parent.name, record)
        value = (record.get('overall-metrics') or {}).get('louvain-modularity-dependency-graph')
        if isinstance(value, (int, float)): out['modularity'] = value if out['modularity'] is None else min(out['modularity'], value)
    out['clusters'] = sorted(out['clusters'], key=lambda c: (-c['files'], c['id']))[:CLUSTERS]
    return out


def _hotspot_row(path, values):
    complexity, commits = values.get('complexity') or 0, values.get('number_of_commits') or 0
    size = values.get('rloc') or values.get('loc') or 0
    return {'path': path, 'complexity': complexity, 'commits': commits, 'rloc': size,
            'authors': values.get('number_of_authors'), 'score': complexity * max(1, commits)}


def _hotspots(city_file):
    """The city's files ranked by complexity times changes, size breaking a tie; [] when there is no city."""
    if not city_file.is_file(): return []
    rows = [_hotspot_row(path, values) for path, values in _attributes(json.loads(city_file.read_text(encoding='utf-8'))).items()]
    rows.sort(key=lambda r: (-r['score'], -r['rloc'], r['path']))
    return [r for r in rows if r['score'] or r['rloc']][:HOTSPOTS]


def _louvain_groups(record):
    """{Louvain module: [{path, fan_in}]} of one emerge record's files."""
    groups = {}
    for name, values in (record.get('local-metrics') or {}).items():
        key = next((v for k, v in values.items() if 'louvain' in k), None)
        if key is None: continue
        groups.setdefault(key, []).append({'path': str(name).split('/', 1)[-1],
                                           'fan_in': next((v for k, v in values.items() if k.startswith('fan-in')), 0) or 0})
    return groups


def _clusters_of(language, record):
    """One emerge record's clusters, each with its first members and its most depended-on file."""
    clusters = []
    for key, members in _louvain_groups(record).items():
        members.sort(key=lambda m: (-m['fan_in'], m['path']))
        clusters.append({'id': f'{language}-{key}', 'files': len(members), 'members': [m['path'] for m in members[:MEMBERS]],
                         'most_depended_on': members[0]['path'] if members[0]['fan_in'] else None})
    return clusters
