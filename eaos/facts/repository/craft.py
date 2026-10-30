"""The repository's layout read as an engineer reads it (M7.8), from its files alone: a folder too crowded to look
through, a family of files that wants its own folder, a name that says nothing, two versions of one file, source in a
folder tools skip as output, a document naming a path that is not there, tests that do not follow the code, no map for
extending it, and what it publishes of the computer it was made on. A framework's own folders (catalog limits: exempt_folders) are never one."""
import re
from collections import defaultdict
from pathlib import PurePosixPath

from ..defects.leftovers import _source_after_all
from .catalog import finding

PREFIX = re.compile(r'^([a-z][a-z0-9]{2,})[_-][a-z0-9]')
VERSION = re.compile(r'^(?:new[_-](?P<a>.+)|(?P<b>.+?)[_-](?:v\d+|new|old2|final))$', re.I)
BACKTICKED = re.compile(r'`([A-Za-z0-9_.][\w./-]*/[\w.-]+\.\w{1,6})(?::\d+)?`')


def _source(paths, limits):
    return [p for p in paths if PurePosixPath(p).suffix.lower() in limits['source_ext']]


def _exempt(folder, limits):
    return any(part in limits['exempt_folders'] for part in PurePosixPath(folder).parts)


def _by_folder(paths):
    folders = defaultdict(list)
    for path in paths: folders[PurePosixPath(path).parent.as_posix()].append(path)
    return folders


def crowded(paths, limits):
    return [finding('crowded-folder', folder, {'path': folder, 'count': len(files)})
            for folder, files in sorted(_by_folder(_source(paths, limits)).items())
            if len(files) > limits['crowded_files'] and not _exempt(folder, limits)]


def families(paths, limits):
    found = []
    for folder, files in sorted(_by_folder(_source(paths, limits)).items()):
        if len(files) < limits['family_folder_min'] or _exempt(folder, limits): continue
        prefixes = defaultdict(list)
        for path in files:
            match = PREFIX.match(PurePosixPath(path).stem)
            if match and match[1] not in limits['family_stop_prefixes']: prefixes[match[1]].append(path)
        found += [finding('prefix-family', f'{folder}/{prefix}_*', {'path': folder, 'prefix': f'{prefix}_', 'folder': prefix,
                                                                     'count': len(group)})
                  for prefix, group in sorted(prefixes.items()) if len(group) >= limits['family_min']]
    return found


def vague(source, paths, limits):
    found = []
    for path in _source(paths, limits):
        if PurePosixPath(path).stem.lower() not in limits['vague_names']: continue
        lines = (source.text(path) or '').count('\n')
        if lines > limits['vague_lines']: found.append(finding('vague-name', path, {'path': path, 'lines': lines}))
    return found


def versions(paths, limits):
    stems = {(PurePosixPath(p).parent, PurePosixPath(p).stem, PurePosixPath(p).suffix): p for p in _source(paths, limits)}
    found = []
    for (folder, stem, suffix), path in sorted(stems.items(), key=lambda row: row[1]):
        match = VERSION.match(stem)
        original = stems.get((folder, match['a'] or match['b'], suffix)) if match else None
        if original: found.append(finding('version-name', path, {'path': path, 'original': original}))
    return found


def traps(paths, imported, limits):
    found = []
    for path in _source(paths, limits):
        folder = next((part for part in PurePosixPath(path).parts[:-1] if part in limits['trap_folders']), None)
        if folder and _source_after_all(path, imported): found.append(finding('trap-folder', path, {'path': path, 'folder': folder}))
    return found


def _history(path, limits):
    return any(part.split('.')[0] in limits['history_docs'] for part in PurePosixPath(path).parts)


def stale_docs(source, everything, limits):
    tree = _tree(everything)
    found = []
    for doc in sorted(p for p in everything if p.endswith('.md') and not _history(p, limits)): found += _stale_in(source, doc, tree)
    return found[:50]


def _tree(everything):
    """(every file and folder of the repository, its first-level folders)."""
    return ({PurePosixPath(p).parent.as_posix() for p in everything} | set(everything),
            {PurePosixPath(p).parts[0] for p in everything if len(PurePosixPath(p).parts) > 1})


def _stale_in(source, doc, tree):
    named = sorted(set(BACKTICKED.findall(source.text(doc) or '')))
    return [finding('stale-doc-path', doc, {'path': doc, 'named': name}) for name in named if _gone(doc, name, *tree)]


def _gone(doc, named, folders, tops):
    """Whether `named`, a path of the repository's own tree (its first folder is one of the repository's; an output's is
    not), is found neither from the root nor from the document's folder."""
    return named.split('/')[0] in tops and not any(normal_path(base, named) in folders for base in ('', PurePosixPath(doc).parent.as_posix()))


def normal_path(*joined):
    """The path the parts name, `..` and `.` resolved inside the repository (never above its root)."""
    parts = []
    for part in PurePosixPath(*joined).parts:
        if part == '..' and parts: parts.pop()
        elif part not in ('.', ''): parts.append(part)
    return '/'.join(parts)


def no_guide(paths, everything, limits):
    """A project large enough to get lost in, with no extension guide (eaos/analysis/repair/project_guide.py)."""
    source = _source(paths, limits)
    if len(source) < limits['guide_min_files'] or any(PurePosixPath(p).name == 'EXTENDING.md' for p in everything): return []
    return [finding('no-extending-guide', 'docs/EXTENDING.md', {'path': 'docs/EXTENDING.md', 'count': len(source)})]


def tests_flat(paths, limits):
    tests = [p for p in paths if PurePosixPath(p).parts[0] in ('tests', 'test') and len(PurePosixPath(p).parts) == 2
             and re.match(r'(test_.*\.py|.*\.(test|spec)\.\w+)$', PurePosixPath(p).name)]
    code = [f for f, files in _by_folder(_source(paths, limits)).items() if len(files) >= 3 and f.split('/')[0] not in ('tests', 'test')]
    if len(tests) <= limits['tests_flat_max'] or len(code) < 3: return []
    root = PurePosixPath(tests[0]).parts[0]
    return [finding('tests-flat', root, {'path': root, 'count': len(tests)})]


def dev_details(source, paths, limits):
    patterns = [(re.compile(pattern), what) for pattern, what in limits['dev_details']]
    found = []
    for path in paths:
        if PurePosixPath(path).name.split('.')[0] in limits['dev_detail_skip'] or PurePosixPath(path).name in limits['dev_detail_skip']: continue
        if (hit := _first_detail(source.text(path) or '', patterns)):
            found.append(finding('dev-detail', path, {'path': path, 'what': hit[1], 'line': hit[0]}))
    return found[:50]


def _first_detail(text, patterns):
    """(line, what) of the first line publishing a machine detail; a line that defines such a pattern is not one."""
    for number, line in enumerate(text.splitlines(), 1):
        if '\\b' in line or '(?<' in line: continue
        for pattern, what in patterns:
            if pattern.search(line): return number, what
    return None
