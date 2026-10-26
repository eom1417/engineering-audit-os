"""A batch of moves (M8.5): the repository's layout put right by moving files, on a branch of its own, never mixed with
fix cards, and refused whole on any difference.

    proposal(report, target)   one tree "today → proposed": each move with its reason (the repository's findings of
                               M7.8: a family of files that wants its folder, tests that do not follow the code; the
                               target shape's placements), and whether the project's tests can prove a move changed nothing
    make(batch)                the moves the person accepted, made in a clone of the authorised commit by the move tool
                               (analysis/repair/moves.py), then the move gate: the public surface (entry points, the
                               commands a package declares, every name each file exposes), every test back with its name
                               and result, every check of the run profile (the build among them) with its exit, nothing
                               newly broken (execute.new_breakage), and the behaviour lock on every screen. Any difference
                               refuses the batch whole; a project whose tests cannot prove it gets the proposal only.

The handed-over branch is fetched into the person's project like a wave's (waves.apply); accept and undo decide it.
"""
import hashlib
import posixpath
from pathlib import Path, PurePosixPath

from ...analysis.repair import move_gate, moves
from ...analysis.repair.move_python import Unmovable
from ...core.project.ledger import TRAILER
from .execute import commit_all, git, new_breakage, own_batch, record_batch

FAMILY, TESTS = 'prefix-family', 'tests-flat'
SOURCE = ('.py', '.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx', '.vue', '.svelte')


# ---------------------------------------------------------------- the proposal

def proposal(report, target):
    """{moves: [{id, from, to, reason, rule, refused}], tree: [lines]}: the moves the repository's findings and the target
    shape draw, each checked alone by the move tool (`refused`: why it cannot be made, else '')."""
    target = Path(target)
    known = moves.files(target)
    drawn = _from_findings(report, known) + _from_target_shape(report, target, known)
    seen, rows = set(), []
    for move in drawn:
        if move['from'] in seen: continue
        seen.add(move['from'])
        refused = _cannot(target, move, known) + _shared_place(move, drawn)
        rows.append({'id': move_id(move), **move, 'refused': '; '.join(refused)})
    return {'moves': rows, 'tree': tree(rows), 'limits': [move_gate.PUBLISHED] if move_gate.published(target, known) else []}


def _cannot(target, move, known):
    """Why the move tool cannot make the move alone: its plan, then the imports it would write (nothing written). The
    plan alone let flaskr/auth.py be proposed into services/auth/, and the batch was refused whole at make: the package's
    `from . import auth` cannot reach a module outside the package."""
    drawn = moves.plan(target, [move], known)
    if drawn['refused']: return drawn['refused']
    try: moves.edits(target, drawn, known)
    except Unmovable as problem: return [str(problem)]
    return []


def _shared_place(move, drawn):
    """Another drawn move sends a different file to the same place: each looks makeable alone, never both together, and
    a batch holding both is refused whole (two email.py files of a Flask app drawn into one feature folder)."""
    others = sorted({m['from'] for m in drawn if m['to'] == move['to'] and m['from'] != move['from']})
    return [f"{', '.join(others)} would become {move['to']} too"] if others else []


def _set(report, name):
    """The facts of one set of the report; [] when the check did not make it (a report older than M7.8)."""
    from ...facts.store import read_set
    try: return read_set(report, name).get('facts') or []
    except (OSError, ValueError): return []


def move_id(move):
    """A move's id, from its two places: the same move keeps it however the proposal changes between two calls."""
    return 'MOVE-' + hashlib.sha256(f"{move['from']}->{move['to']}".encode('utf-8')).hexdigest()[:10]


def _findings(report):
    return [f['value'] for f in _set(report, 'repository')]


def _from_findings(report, known):
    out = []
    for finding in _findings(report):
        if finding['rule'] == FAMILY: out += _family(finding, known)
        elif finding['rule'] == TESTS: out += _mirrored(report, finding, known)
    return out


def _family(finding, known):
    """pipeline_run.py, pipeline_load.py ... into pipeline/: run.py, load.py."""
    folder, prefix = finding['params']['path'], finding['params']['prefix']
    base = '' if folder in ('', '.') else folder + '/'
    members = [p for p in sorted(known) if posixpath.dirname(p) == folder.strip('.') and PurePosixPath(p).name.startswith(prefix)
               and PurePosixPath(p).suffix in SOURCE]
    return [{'from': p, 'to': f"{base}{prefix.rstrip('_-')}/{PurePosixPath(p).name[len(prefix):]}", 'rule': FAMILY,
             'reason': finding.get('en') or f'{len(members)} files share {prefix}: they want their own folder'} for p in members]


def _mirrored(report, finding, known):
    """Each test of a flat tests folder beside the code it reads most: tests/<that code's folder>/."""
    root = finding['params']['path']
    reads = _imports_of(report)
    out = []
    for test in sorted(p for p in known if posixpath.dirname(p) == root and PurePosixPath(p).suffix in SOURCE):
        folder = _mirror(reads.get(test) or [])
        if folder: out.append({'from': test, 'to': f'{root}/{folder}/{PurePosixPath(test).name}', 'rule': TESTS,
                               'reason': finding.get('en') or 'the tests follow the layout of the code they test'})
    return out


def _imports_of(report):
    """{file: [the project files it imports]} from the check's resolved imports."""
    out = {}
    for fact in _set(report, 'resolve'):
        value = fact.get('value') or {}
        if value.get('to_path') and fact.get('kind') == 'module_edge' and value.get('resolution', 'RESOLVED') == 'RESOLVED':
            out.setdefault(fact['location']['path'], []).append(value['to_path'])
    return out


def _mirror(imported):
    """The folder most of the imported code lives in, without its first folder (the package or src/), or None."""
    folders = [PurePosixPath(p).parent.parts[1:] for p in imported if not PurePosixPath(p).name.startswith('test')]
    folders = [f for f in folders if f]
    if not folders: return None
    best = max(set(folders), key=folders.count)
    return '/'.join(best) if folders.count(best) * 2 > len(folders) else None


def _from_target_shape(report, target, known):
    """Each file the target shape places in a component whose folder is plain (no wildcard inside it)."""
    from ...analysis.target_state import projection
    try: projected = projection.project(report, target)
    except (OSError, ValueError, KeyError): return []
    if not projected: return []
    reference = projection.rooted(projection.by_id(projected['reference']), projected['root'])
    out = []
    for path, component in sorted((projected.get('placements') or {}).items()):
        folder = _component_folder(component, reference)
        if folder and path in known and not path.startswith(folder):
            out.append({'from': path, 'to': folder + PurePosixPath(path).name, 'rule': 'target-shape',
                        'reason': f'the target shape keeps it in {component}'})
    return out


def _component_folder(component, reference):
    from ...analysis.target_state.projection import _features_root, _feature_layer
    if component.startswith('feature:'):
        return f"{_features_root(reference, _feature_layer(reference))}/{component.split(':', 1)[1]}/"
    layer = next((layer for layer in reference['layers'] if layer['name'] == component), None)
    pattern = next(iter((layer or {}).get('paths') or ()), '')
    folder = pattern[:-2] if pattern.endswith('**') else ''
    return folder if folder and '*' not in folder else None


def tree(rows):
    """The proposal as one tree "today → proposed", folder by folder; a move that cannot be made says why."""
    lines, folder = [], None
    for row in sorted(rows, key=lambda r: r['from']):
        here = posixpath.dirname(row['from']) or '.'
        if here != folder: lines.append(f'{here}/')
        folder = here
        lines.append(f"  {PurePosixPath(row['from']).name}  →  {row['to']}   ({row['reason']})"
                     + (f"  [cannot: {row['refused']}]" if row['refused'] else ''))
    return lines


# ---------------------------------------------------------------- the batch

def make(batch):
    """The accepted moves made and proved: the summary, its `kept` the moves on the branch, empty when refused (why in
    `refused`). `batch`: {report, target, runtime, number, moves, deliver_as, lock, say}."""
    say = batch.get('say') or (lambda *_: None)
    batch = {**batch, 'kind': 'moves', 'items': batch['moves']}
    root, base = own_batch(batch['target'], batch['runtime'], f"MOVES-{batch['number']}")
    say('before')
    try: before = {'checks': named_checks(root, batch['runtime'], f"moves-{batch['number']}-before"), 'surface': None}
    except RuntimeError as problem: return record_batch(batch, root, base, [], [f'proposal only: the app could not be set up before the moves: {str(problem)[-400:]}'])
    if (why := move_gate.unproven(before['checks'])): return record_batch(batch, root, base, [], ['proposal only: ' + why])
    before['surface'] = move_gate.surface(root, moves.files(root))
    before['mapping'] = moves.plan(root, batch['moves'])['mapping']
    say('moves')
    try: made = moves.apply(root, batch['moves'])
    except Unmovable as problem: return record_batch(batch, root, base, [], [f'the move tool refused: {problem}'])
    touched = [*before['mapping'], *made['rewritten'], *made['created'], *before['mapping'].values()]   # never what a run left
    commit_all(root, f"Move {made['moved']} file(s) to their place\n\n" + '\n'.join(f"  {m['from']} -> {m['to']}" for m in batch['moves'])
               + f'\n\nExecuted by EAOS (move batch).\n\n{TRAILER}: moves', touched)
    say('gate')
    differences = _gate(batch, root, before)
    if differences: git(root, 'reset', '--hard', '--quiet', base)
    return record_batch(batch, root, base, [] if differences else [m.get('id') or m['from'] for m in batch['moves']], differences)


def _gate(batch, root, before):
    """Every difference the moves made: the surface, the tests and checks, what is newly broken, the screens."""
    try: after = named_checks(root, batch['runtime'], f"moves-{batch['number']}-after", [(r['argv'], r['at_root']) for r in before['checks']])
    except RuntimeError as problem: return [f'the app could not be set up after the moves, as it was before them: {str(problem)[-500:]}']
    out = move_gate.surface_differences(before['surface'], move_gate.surface(root, moves.files(root)), before['mapping'])
    out += move_gate.test_differences(before['checks'], after, before['mapping'])
    return out + new_breakage(batch['report'], root) + _lock(batch, root)


def _lock(batch, root):
    """The behaviour lock on every screen (no screen may look different), when the run recorded one."""
    if not batch.get('lock', True) or not (Path(batch['runtime']) / 'behavior-lock').is_dir(): return []
    from ...live.behavior.lock import LockPass, failing_tests, verify_lock
    name = f"moves-{batch['number']}"
    verdict = verify_lock(batch['report'], root, batch['runtime'], LockPass(name))
    return [f"the behaviour lock broke on {verdict['failed']} of {verdict['specs']} specs: "
            + '; '.join(sorted(failing_tests(batch['runtime'], name)))[:600]] if verdict['failed'] else []


def named_checks(root, runtime, name, checks=None):
    """[{argv, at_root, exit, output}] of the run profile's checks and the Python tests on `root`, the tests told to name
    each test they run (unittest -v, pytest -rA), so the gate finds every test back by its name. `checks` [(argv,
    at_root)]: the same commands as before the moves (after them, a tests/ folder emptied by the moves builds none)."""
    from ...live.app.run import LiveRun
    from ...live.testing.verify import python_tests
    live = LiveRun(root, runtime, 'S09')
    if checks is None:
        checks = [(argv, False) for argv in live.profile.get('checks') or []] + [(argv, True) for argv in python_tests(root, live.profile)]
    if not checks: return []
    try:
        live.setup()
        rows = []
        for argv, at_root in checks:
            code, out, err = live.run(_naming(argv), timeout=1800, at_root=at_root)
            rows.append({'argv': [str(a) for a in argv], 'at_root': at_root, 'exit': code, 'output': out + err})
        return rows
    finally:
        live.stop()
        live.record(f'runtime/checks-{name}-log.json')


def _naming(argv):
    """The same command, asking a Python test runner to name each test."""
    argv = [str(a) for a in argv]
    if 'unittest' in argv and '-v' not in argv: return argv + ['-v']
    if 'pytest' in argv and '-rA' not in argv: return argv + ['-rA']
    return argv
