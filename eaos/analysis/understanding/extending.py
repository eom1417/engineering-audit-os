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
CHECK_SCRIPT = re.compile(r'^(tools|scripts|bin)/(quality|check|checks|verify|lint|test|tests|ci)\.sh$')
GUIDE_OWN = re.compile(r'(^|/)(EXTENDING|AGENTS|CLAUDE)\.md$')     # a commit of the guide alone says nothing of how the project grew
DATA = re.compile(r'(^|/)(fixtures?|golden|snapshots?|__snapshots__|testdata|contracts|rule-tests)/')
MIN_USERS, SENSITIVE, FEATURES = 5, 5, 12
HEAVY, HEAVY_BYTES = 6, 100_000
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
    """Whether `path` is a file of `kind`; a test is only ever of the kind `test`; a kind the layer record reads for
    itself (the endpoints it found) is told by that record, its path patterns only when the record has none."""
    if _a_test(path): return kind['id'] == 'test'
    if any(p.search(path) for p in kind['not']): return False
    known = known_by.get(kind.get('from'))
    return path in known if known else any(p.search(path) for p in kind['paths'])


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
    return {'id': kind['id'], 'title': kind['title'], 'grows': kind['grows'], 'example': example, 'commit': _stamp(commit), 'home': _home(own),
            'seen': len(seen), 'read': [example, *code][:READ], 'touch': _ordered(code, rank)[:TOUCH], 'test': _test_of(example, seen, tree)}


def _home(own):
    """The folder that holds most files of this kind, its data and snapshots aside."""
    real = [path for path in own if not _data(path)] or own
    return Counter(PurePosixPath(path).parent.as_posix() for path in real).most_common(1)[0][0]


def _data(path):
    return bool(DATA.search(path))


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


def _folders_of(record):
    """{layer: its folders by the number of files}."""
    folders = {}
    for row in record.get('map') or ():
        if row.get('layer'): folders.setdefault(row['layer'], Counter())[PurePosixPath(row['path']).parent.as_posix()] += 1
    return folders


def _layers(record):
    """Each layer with its role, what it may and may not use, its files and the folders that hold most of them."""
    folders = _folders_of(record)
    return [{'name': layer['name'], 'role': layer.get('role'), 'allowed': layer.get('allowed') or [], 'denied': layer.get('denied') or [],
             'files': layer['files'], 'folders': [folder for folder, _ in folders.get(layer['name'], Counter()).most_common(FOLDERS)]}
            for layer in record.get('layers') or () if layer.get('files')]


def _area(area):
    return {'name': area['name'], 'files': _production(area.get('files'))[:AREA_FILES], 'entries': (area.get('entries') or [])[:2]}


def _production(paths):
    return [path for path in paths or () if not _a_test(path)]


def _areas(out):
    """The project's areas and each one's production files: GitNexus's area skills (facts/external.json), else, where it
    did not run (a commercial project skips it), the groups of EAOS's own code map (architecture/map.json)."""
    facts = read_json(Path(out) / 'facts' / 'external.json', {}) or {}
    named = [_area(area) for area in (facts.get('summary') or {}).get('areas') or ()]
    return ([area for area in named if area['files']] or _own_areas(out))[:AREAS]


def _own_areas(out):
    digest = (read_json(Path(out) / 'architecture' / 'map.json', {}) or {}).get('digest') or {}
    groups = ({'name': _area_name(group['members']), 'files': _production(group['members'])[:AREA_FILES], 'entries': []}
              for group in digest.get('clusters') or ())
    return [group for group in groups if group['files']]


def _area_name(members):
    """A group's name: the folder most of its files are in."""
    return Counter(PurePosixPath(path).parent.as_posix() for path in members).most_common(1)[0][0]


def _runner(tree):
    return next((runner for lock, runner in LOCKS if lock in tree), 'npm')


def _npm_scripts(root, tree):
    if 'package.json' not in tree: return []
    scripts = (read_json(Path(root) / 'package.json', {}) or {}).get('scripts') or {}
    return [f'{_runner(tree)} run {name}' for name in SCRIPTS if name in scripts]


def _own_scripts(tree):
    """The check scripts the project keeps in its tools folders (`tools/quality.sh`), as it would run them."""
    return sorted(f'bash {path}' for path in tree if CHECK_SCRIPT.search(path))


def _python_tests(tree):
    tests = [path for path in tree if path.endswith('.py') and classify(path) == 'test']
    if not tests: return None
    declared = {'pytest.ini', 'conftest.py', 'tests/conftest.py', 'tox.ini'} & tree
    return 'python -m pytest' if declared else f'python -m unittest discover -s {PurePosixPath(tests[0]).parts[0]}'


def commands(root, tree):
    """The project's own checks, as it would run them: its scripts, or its language's test command."""
    python = 'python manage.py test' if 'manage.py' in tree else _python_tests(tree)
    others = [(python, python), ('go.mod' in tree, 'go test ./...'), ('Cargo.toml' in tree, 'cargo test')]
    return _own_scripts(tree) + _npm_scripts(root, tree) + [command for there, command in others if there]


def _tests_home(tree):
    """Where the tests live: their first folders, the most first, and how many."""
    tests = [path for path in tree if _a_test(path) and not _data(path)]
    folders = Counter(PurePosixPath(path).parts[0] if len(PurePosixPath(path).parts) > 1 else '.' for path in tests)
    return {'count': len(tests), 'folders': [folder for folder, count in folders.most_common(FOLDERS) if count * 10 >= len(tests)]}


def _nodes(out):
    return [fact for fact in (read_json(Path(out) / 'facts' / 'graph.json', {}) or {}).get('facts') or () if fact.get('kind') == 'graph_node']


def _reuse(out):
    """The production files most others import, the first place to look before writing something again."""
    rows = sorted(((fact['value'].get('fan_in') or 0, fact['location']['path']) for fact in _nodes(out)), key=lambda row: (-row[0], row[1]))
    return [{'path': path, 'users': users} for users, path in rows if users >= MIN_USERS and not _a_test(path)][:SHOWN]


def _sensitive(out):
    """The files where complexity and changes meet (the code map's hotspots)."""
    digest = (read_json(Path(out) / 'architecture' / 'map.json', {}) or {}).get('digest') or {}
    return [{'path': row['path'], 'commits': row.get('commits'), 'complexity': row.get('complexity')} for row in (digest.get('hotspots') or ())[:SENSITIVE]]


def _features(out):
    features = (read_json(Path(out) / 'features.json', {}) or {}).get('features') or ()
    return [{'name': feature['name'], 'surfaces': (feature.get('surfaces') or ())[:2], 'tables': (feature.get('tables') or ())[:3]}
            for feature in features][:FEATURES]


def _departures(record):
    """What the check found against the project's own structure, told once each, the most serious first."""
    rank = {'high': 0, 'medium': 1, 'low': 2}
    found = sorted(record.get('findings') or (), key=lambda finding: rank.get(finding.get('severity'), 3))
    untested = (record.get('tests') or {}).get('layers_untested') or ()
    return [finding['en'] for finding in found][:SHOWN] + ([f"Layers with no test: {', '.join(untested)}."] if untested else [])


def _heavy(root, tree):
    """The tracked files too large to read by chance (data, snapshots, locks), by folder, the heaviest first."""
    patterns = [re.compile(pattern) for pattern in json.loads(RULES.read_text(encoding='utf-8'))['heavy']]
    weights = Counter()
    for path in tree:
        if any(pattern.search(path) for pattern in patterns) and (Path(root) / path).is_file():
            weights[PurePosixPath(path).parent.as_posix()] += (Path(root) / path).stat().st_size
    return [folder for folder, weight in weights.most_common(HEAVY) if weight >= HEAVY_BYTES]


def _keeps(recipe, record, layers):
    """What a new file of this recipe must keep: what its example's layer may not use."""
    placed = next((row.get('layer') for row in record.get('map') or () if row['path'] == recipe['example']), None)
    denied = next((layer['denied'] for layer in layers if layer['name'] == placed), ())
    return {**recipe, 'layer': placed, 'denied': list(denied)}


def _order(recipes):
    """The recipes of a new feature, in the order its work goes: data first, its test last."""
    order = json.loads(RULES.read_text(encoding='utf-8'))['feature_order']
    return [recipe['id'] for recipe in sorted((r for r in recipes if r['id'] in order), key=lambda r: order.index(r['id']))]


def _grown(root):
    """The project's commits; one of the guide alone says nothing of how it grew."""
    return [commit for commit in additions(root) if not all(GUIDE_OWN.search(path) for path in commit['changed'])]


def _recipes(tree, commits, record, out):
    """(the recipes this project has, each with what it must keep; the titles of the kinds it does not have)."""
    kinds, noise, order = _kinds()
    context = (_known_by(record), noise, _ranks(record, order), _importers(out))
    drawn = [(kind, _recipe(kind, tree, commits, context)) for kind in kinds]
    layers = _layers(record)
    return [_keeps(recipe, record, layers) for _, recipe in drawn if recipe], [kind['title'] for kind, recipe in drawn if not recipe]


def _guide_facts(out, record):
    """What the check read that a recipe does not hold: the parts of the guide besides its recipes."""
    return {'layers': _layers(record), 'gaps': len(record.get('gaps') or ()), 'areas': _areas(out), 'reuse': _reuse(out), 'sensitive': _sensitive(out),
            'features': _features(out), 'departures': _departures(record)}


def draft(root, out, tree, record=None, pinned=()):
    """The guide's content for the project at `root`, read from the check's folder `out` (its layers.json), or from a
    layer `record` already in hand; `tree`: the paths git tracks; `pinned`: the ids of the rules pinned now."""
    record = (read_json(Path(out) / 'layers.json', {}) or {}) if record is None else record
    tree, commits = set(tree), _grown(root)
    recipes, missing = _recipes(tree, commits, record, out)
    return {**_guide_facts(out, record), 'recipes': recipes, 'feature_steps': _order(recipes), 'missing': missing, 'checks': commands(root, tree),
            'tests': _tests_home(tree), 'heavy': _heavy(root, tree), 'pinned': list(pinned), 'commits': len(commits)}
