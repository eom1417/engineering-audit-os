"""A project's extension guide (M18.3): for each kind of addition, the files to read and to touch, in order, and the
checks to run, from what EAOS read of the project: its layer map (layers.json), which files changed together when one of
that kind was added (facts/code/history.py additions, mass commits left out), GitNexus's areas, the rules the person
pinned and the project's own scripts. Nothing is guessed: a kind the project does not have gets no recipe, and it is
said so. eaos/rules/extending-recipes.json tells the kinds; eaos/analysis/repair/project_guide.py writes the text."""
import json
import math
import re
from collections import Counter
from pathlib import Path, PurePosixPath

from ...core.contracts.vocabulary import classify
from ...core.system.files import read_json
from ...facts.code.history import additions

RULES = Path(__file__).resolve().parents[2] / 'rules' / 'extending-recipes.json'
READ, TOUCH, SHOWN = 5, 6, 8          # the files read and touched per recipe; the commits of a kind read, the newest first
RANK_OF_TEST = 9
FOLDERS, AREAS, AREA_FILES = 3, 12, 3
LOCKS = (('pnpm-lock.yaml', 'pnpm'), ('yarn.lock', 'yarn'), ('bun.lockb', 'bun'))
SCRIPTS = ('typecheck', 'lint', 'test', 'build')
LONE_TEST = re.compile(r'(^|/)tests?\.py$')
WIRING = 2                # the files named for wiring a new one in
LIFT = 1.25               # a file changes with a kind this many times more often than with any commit, or it is no sign


def _kinds():
    rules = json.loads(RULES.read_text(encoding='utf-8'))
    compiled = [{**kind, 'paths': [re.compile(p) for p in kind.get('paths') or ()], 'not': [re.compile(p) for p in kind.get('not') or ()]}
                for kind in rules['kinds']]
    return compiled, [re.compile(p) for p in rules['noise']], rules['role_order']


def _known_by(record):
    """{a kind's `from`: the paths the layer record knows it by}."""
    return {'endpoints': {row['path'] for row in record.get('endpoints') or []},
            'tables': {row['path'] for row in record.get('map') or [] if row.get('side') == 'database'}}


def _a_test(path):
    return classify(path) == 'test' or bool(LONE_TEST.search(path))


def _is(kind, path, known_by):
    """Whether `path` is a file of `kind`; a test is only ever of the kind `test`."""
    if _a_test(path): return kind['id'] == 'test'
    if any(p.search(path) for p in kind['not']): return False
    return path in known_by.get(kind.get('from'), ()) or any(p.search(path) for p in kind['paths'])


def _example(own, seen, verb, tree):
    """(the last real file of this kind, the commit that made it): the newest commit's first such file still there, or
    the first of the kind when the history shows none."""
    for commit in seen:
        for path in sorted(commit[verb], key=lambda path: PurePosixPath(path).stem in ('__init__', 'index')):
            if path in own and path in tree: return path, commit
    return sorted(own)[0], None


def _kept(kind, path, context):
    known_by, noise, tree = context
    return path in tree and (_is(kind, path, known_by) or not any(p.search(path) for p in noise))


def _sign(count, path, seen, history):
    """Whether a file changes with this kind more than with any commit (LIFT), told only when the kind is a small part of
    the history."""
    every = sum(path in commit['changed'] for commit in history)
    return len(seen) * 2 > len(history) or count / len(seen) >= LIFT * every / len(history)


def _together(seen, history, kind, context):
    """The other files that change with this kind's additions: in half of them at least (three in four of a change to a
    file that is there), every one of a lone commit, the most often first; a file that changes with anything is no sign,
    and noise (documents, lock files) only of the kind."""
    counts = Counter(path for commit in seen for path in commit['changed'] if _kept(kind, path, context))
    need = max(2, math.ceil(len(seen) * (0.75 if kind['grows'] == 'changed' else 0.5))) if len(seen) > 1 else 1
    return [path for path, count in counts.most_common() if count >= need
            and (_is(kind, path, context[0]) or _sign(count, path, seen, history))]


def _ordered(paths, rank):
    return sorted(paths, key=lambda path: (RANK_OF_TEST if _a_test(path) else rank.get(path, 3)))


def _test_of(example, seen, tree):
    """The test that goes with it: one that changed with this kind, else one named for it, else none."""
    stem = PurePosixPath(example).stem.lower()
    together = (path for commit in seen for path in commit['changed'] if _a_test(path) and path in tree)
    return next(together, None) or next((path for path in sorted(tree) if _a_test(path) and stem in PurePosixPath(path).stem.lower()), None)


def _recipe(kind, tree, commits, context):
    known_by, noise, rank, importers = context
    own = {path for path in tree if _is(kind, path, known_by)}
    if not own: return None
    seen = [commit for commit in commits if any(_is(kind, path, known_by) for path in commit[kind['grows']])][:SHOWN]
    example, commit = _example(own, seen, kind['grows'], tree)
    peers = _peers(_together(seen, commits, kind, (known_by, noise, tree)) + _wiring(own, importers), example)
    code = _code_of(peers, kind)
    return {'id': kind['id'], 'title': kind['title'], 'grows': kind['grows'], 'example': example, 'commit': _stamp(commit),
            'seen': len(seen), 'read': [example, *code][:READ], 'touch': _ordered(code, rank)[:TOUCH], 'test': _test_of(example, seen, tree)}


def _peers(paths, example):
    return [path for path in dict.fromkeys(paths) if path != example]


def _wiring(own, importers):
    """The files that import several of this kind: what wires a new one in (a router, an index), the most first."""
    counts = Counter(path for one in own for path in importers.get(one, ()) if path not in own)
    return [path for path, count in counts.most_common(WIRING) if count >= 2 and not _a_test(path)]


def _importers(out):
    """{file: the files that import it}, from the check's graph."""
    found = {}
    for fact in (read_json(Path(out) / 'facts' / 'graph.json', {}) or {}).get('facts') or []:
        for other in fact['value'].get('depends_on') or (): found.setdefault(other, set()).add(fact['location']['path'])
    return found


def _code_of(peers, kind):
    return peers if kind['id'] == 'test' else [path for path in peers if not _a_test(path)]


def _stamp(commit):
    return {key: commit[key] for key in ('sha', 'date')} if commit else None


def _ranks(record, order):
    """{path: its place in the order of work: the data first, the screens last}."""
    role = {layer['name']: layer.get('role') for layer in record.get('layers') or []}
    return {row['path']: order.get(role.get(row.get('layer')), order.get(row.get('side'), 3)) for row in record.get('map') or []}


def _layers(record):
    """Each layer with its role, what it may use, its files and the folders that hold most of them."""
    folders = {}
    for row in record.get('map') or []:
        if row.get('layer'): folders.setdefault(row['layer'], Counter())[PurePosixPath(row['path']).parent.as_posix()] += 1
    return [{'name': layer['name'], 'role': layer.get('role'), 'allowed': layer.get('allowed') or [], 'files': layer.get('files') or 0,
             'folders': [folder for folder, _ in folders.get(layer['name'], Counter()).most_common(FOLDERS)]}
            for layer in record.get('layers') or [] if layer.get('files')]


def _area(area):
    return {'name': area['name'], 'files': _production(area.get('files'))[:AREA_FILES], 'entries': (area.get('entries') or [])[:2]}


def _production(paths):
    return [path for path in paths or () if not _a_test(path)]


def _areas(out):
    """GitNexus's areas: each one's production files that hold most of it (facts/external.json)."""
    facts = read_json(Path(out) / 'facts' / 'external.json', {}) or {}
    named = [_area(area) for area in (facts.get('summary') or {}).get('areas') or ()]
    return [area for area in named if area['files']][:AREAS]


def _runner(tree):
    return next((runner for lock, runner in LOCKS if lock in tree), 'npm')


def _npm_scripts(root, tree):
    if 'package.json' not in tree: return []
    scripts = (read_json(Path(root) / 'package.json', {}) or {}).get('scripts') or {}
    return [f'{_runner(tree)} run {name}' for name in SCRIPTS if name in scripts]


def _pytest(tree):
    return bool({'pytest.ini', 'conftest.py', 'tests/conftest.py'} & tree) or any(p.startswith('tests/test_') and p.endswith('.py') for p in tree)


def commands(root, tree):
    """The project's own checks, as it would run them: its scripts, or its language's test command."""
    python = 'python manage.py test' if 'manage.py' in tree else 'python -m pytest' if _pytest(tree) else None
    others = [(python, python), ('go.mod' in tree, 'go test ./...'), ('Cargo.toml' in tree, 'cargo test')]
    return _npm_scripts(root, tree) + [command for there, command in others if there]


def draft(root, out, tree, record=None, pinned=()):
    """The guide's content for the project at `root`, read from the check's folder `out` (its layers.json), or from a
    layer `record` already in hand; `tree`: the paths git tracks; `pinned`: the ids of the rules pinned now."""
    record = record if record is not None else (read_json(Path(out) / 'layers.json', {}) or {})
    tree = set(tree)
    kinds, noise, order = _kinds()
    known_by, rank = _known_by(record), _ranks(record, order)
    commits = additions(root)
    recipes = [_recipe(kind, tree, commits, (known_by, noise, rank, _importers(out))) for kind in kinds]
    return {'layers': _layers(record), 'gaps': len(record.get('gaps') or []), 'areas': _areas(out), 'recipes': [r for r in recipes if r],
            'missing': [kind['title'] for kind, recipe in zip(kinds, recipes) if not recipe], 'checks': commands(root, tree),
            'pinned': list(pinned), 'commits': len(commits)}
