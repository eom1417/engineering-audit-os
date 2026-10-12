"""A codemod for every mechanical card, tried on an isolated copy before anyone runs it for real.

The mechanical families (eaos/rules/codemods.json) and their tools:
  remove_dead, unreachable module   delete-file: the file goes
  remove_dead, unused symbol        jscodeshift with eaos/templates/codemods/remove-declaration.cjs (JS/TS),
                                    or python-ast: the definition's lines, from the syntax tree (Python)
  leftover                          delete-file
  upgrade_dependency (npm)          a direct dependency: npm install pkg@fixed; a transitive one:
                                    npm pkg set overrides.pkg=fixed, then npm install; both --package-lock-only
                                    --ignore-scripts, so no project code runs
Each card gets codemod {tool, command, dry_run {exit, files_changed}}. The dry run is the real command on a
copy made by eaos.verify.isolated_copy; files_changed counts files added, removed or modified there. A tool
that changes nothing did nothing, and says so with files_changed 0. The project is never written.
"""
import ast
import json
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from . import progress

RULES = Path(__file__).resolve().parent / 'rules/codemods.json'
TRANSFORM = Path(__file__).resolve().parent / 'templates/codemods/remove-declaration.cjs'
LANGUAGES = {'.py': 'python', '.js': 'javascript', '.jsx': 'javascript', '.ts': 'typescript', '.tsx': 'tsx', '.mjs': 'javascript'}


def _stats(root):
    """{path: (size, mtime_ns)} of every project file; tool caches (node_modules/.cache and the like) are not the project.
    A stat is cheap where reading every file is not: a large project dry-runs hundreds of cards."""
    import os
    from .workspace import SKIP_DIRS
    root, found = Path(root), {}
    for base, directories, names in os.walk(root):
        directories[:] = [d for d in directories if d not in SKIP_DIRS]
        for name in names:
            path = Path(base) / name
            try: stat = path.stat()
            except OSError: continue
            found[path.relative_to(root).as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return found


def _changed(copy, pristine, before, after):
    """Paths whose content the card changed: a stat that moved is confirmed against the untouched file."""
    changed = []
    for key in set(before) | set(after):
        if before.get(key) == after.get(key): continue
        if key not in before or key not in after: changed.append(key); continue
        if (Path(copy) / key).read_bytes() != (Path(pristine) / key).read_bytes(): changed.append(key)
    return changed


def _restore(copy, pristine, before, after):
    """Put the copy back as it was before the card: every path it touched, from the untouched project."""
    for key in set(before) | set(after):
        if before.get(key) == after.get(key): continue
        target = Path(copy) / key
        if key in before: shutil.copy2(Path(pristine) / key, target)
        elif target.exists(): target.unlink()


def remove_python(path, name):
    """Remove the top-level def, class or assignment named `name`; True when something went."""
    text = Path(path).read_text(encoding='utf-8')
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    spans = [(min([d.lineno for d in getattr(node, 'decorator_list', [])] + [node.lineno]), node.end_lineno)
             for node in tree.body if name in _names_of(node)]
    for start, end in sorted(spans, reverse=True): del lines[start - 1:end]
    if spans: Path(path).write_text(''.join(lines), encoding='utf-8')
    return bool(spans)


def _names_of(node):
    """The names a top-level statement defines: a def or class, or the targets of an assignment."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): return [node.name]
    return ([t.id for t in getattr(node, 'targets', []) if isinstance(t, ast.Name)] +
            ([node.target.id] if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) else []))


NPM_FLAGS = ['--package-lock-only', '--ignore-scripts', '--no-audit', '--no-fund', '--loglevel=error']


def _npm_steps(detail, binary):
    """In each folder: a direct dependency installed at its fixed version; a transitive one overridden, then installed."""
    steps = []
    for folder, direct in detail.get('folders') or [(detail.get('folder', '.'), detail['direct'])]:
        prefix = ['--prefix', folder] if folder != '.' else []
        if direct:
            steps.append(([binary, 'install', f"{detail['package']}@{detail['fixed']}", *NPM_FLAGS, *prefix], None))
        else:
            steps += [([binary, 'pkg', 'set', f"overrides.{detail['package']}={detail['fixed']}", *prefix], None),
                      ([binary, 'install', *NPM_FLAGS, *prefix], None)]
    return steps


def _commands(card, copy):
    """[(argv, None) or (callable, description)] for one card, in the copy."""
    from .engines.process import which
    kind, detail = card['kind'], card
    if kind == 'delete-file':
        return [(lambda: (copy / detail['path']).unlink(), f"rm {shlex.quote(detail['path'])}")]
    if kind == 'python-ast':
        return [(lambda: remove_python(copy / detail['path'], detail['symbol']),
                 f"python-ast remove {detail['symbol']} from {detail['path']}")]
    if kind == 'jscodeshift':
        binary = which('jscodeshift')
        return [([binary, '-t', str(TRANSFORM), '--parser=tsx', f"--name={detail['symbol']}", detail['path']], None)] if binary else None
    if kind == 'npm': return _npm_steps(detail, which('npm') or 'npm')
    return None


def _run_step(step, description, copy):
    """(exit code, the command as shown) of one step in the copy."""
    if callable(step):
        try:
            step()
            return 0, description
        except (OSError, SyntaxError, ValueError):
            return 1, description
    import os
    done = subprocess.run(step, cwd=copy, capture_output=True, text=True, timeout=600,
                          env={**os.environ, 'BABEL_DISABLE_CACHE': '1'})
    return done.returncode, shlex.join([Path(step[0]).name, *step[1:]]).replace(str(TRANSFORM), 'eaos/templates/codemods/remove-declaration.cjs')


def _run_steps(steps, copy):
    """(exit code, commands shown): the steps in order, stopping at the first that fails."""
    code, shown = 0, []
    for step, description in steps:
        result, text = _run_step(step, description, copy)
        code = code or result
        shown.append(text)
        if code: break
    return code, shown


def dry_run(card, target, copy=None):
    """{exit, files_changed} of the card's commands on an isolated copy of the target, and the command text.

    With `copy` (attach() makes one per run), the copy is restored after the card instead of copied anew; without
    it, a copy is made and removed. Either way no copy outlives the call that made it."""
    from .verify import isolated_copy
    owned = copy is None
    if owned:
        holder = Path(tempfile.mkdtemp(prefix='eaos-codemod-'))
        copy = isolated_copy(Path(target), holder / 'project')
    try:
        steps = _commands(card, copy)
        if steps is None: return None, None
        before = _stats(copy)
        code, shown = _run_steps(steps, copy)
        after = _stats(copy)
        changed = _changed(copy, target, before, after)
        if not owned: _restore(copy, target, before, after)
        return {'exit': code, 'files_changed': len(changed)}, ' && '.join(shown)
    finally:
        if owned: shutil.rmtree(holder, ignore_errors=True)


def card_for(task, facts_by_id, target):
    """What the codemod of one task changes, or None when its family has no mechanical tool."""
    facts = [facts_by_id[f] for f in (task.get('evidence') or {}).get('fact_ids') or [] if f in facts_by_id]
    pattern = task.get('pattern')
    if pattern in ('remove_dead', 'dead_code'): return _removal_card(facts)
    if pattern == 'leftover':
        fact = next(iter(facts), None)
        return {'kind': 'delete-file', 'path': fact['location']['path']} if fact else None
    if pattern == 'upgrade_dependency':
        fact = next(iter(facts), None)
        return _upgrade_card(fact, target) if fact else None
    return None


def _removal_card(facts):
    """The tool that removes a dead symbol or file, by the finding's rule and the file's language."""
    rules = json.loads(RULES.read_text(encoding='utf-8'))
    fact = next((f for f in facts if (f.get('value') or {}).get('rule')), None)
    if not fact: return None
    rule, path = fact['value']['rule'], fact['location']['path']
    tool = rules['remove_dead'].get(rule)
    if isinstance(tool, dict): tool = tool.get(LANGUAGES.get(Path(path).suffix))
    if not tool: return None
    return {'kind': tool, 'path': path, 'symbol': fact['location'].get('symbol')}


def _direct_in(target, where, package):
    """True when the package.json in `where` names the package itself, not only through another one."""
    manifest = json.loads((Path(target) / where / 'package.json').read_text(encoding='utf-8'))
    return package in (manifest.get('dependencies') or {}) or package in (manifest.get('devDependencies') or {})


def _upgrade_card(fact, target):
    """An npm upgrade to the fixed version, in every folder whose lock file holds the vulnerable version."""
    ecosystem, _, rest = str(fact['location'].get('symbol')).partition(':')
    package, _, _ = rest.rpartition('@')
    fixed = next((m['value'] for m in fact['value'].get('measurements') or [] if m['name'] == 'fixed_in'), None)
    # The lock file the scanner read names the folder: an app in app/ has its manifest there, not at the root.
    folder = str(PurePosixPath(fact['location'].get('path') or 'package-lock.json').parent)
    if ecosystem != 'npm' or not fixed or not (Path(target) / folder / 'package-lock.json').is_file(): return None
    # The same vulnerable version in another lock file of the project (a server/ beside the app) is the same
    # problem: the card's acceptance scans the whole project, so every such lock file is upgraded with it.
    folders = [folder] + [where for where in _lock_folders_with(target, package, rest.rpartition('@')[2]) if where != folder]
    folders = [where for where in folders if (Path(target) / where / 'package.json').is_file()]
    return {'kind': 'npm', 'package': package, 'fixed': fixed, 'direct': _direct_in(target, folder, package), 'folder': folder,
            'folders': [(where, _direct_in(target, where, package)) for where in folders]}


def _lock_folders_with(target, package, version):
    """Folders (relative, '.' for the root) whose package-lock.json holds `package` at `version`."""
    found = []
    for lock in sorted(Path(target).rglob('package-lock.json')):
        if 'node_modules' in lock.parts: continue
        try: packages = json.loads(lock.read_text(encoding='utf-8')).get('packages') or {}
        except (OSError, ValueError): continue
        if any(key.split('node_modules/')[-1] == package and (row or {}).get('version') == version for key, row in packages.items()):
            found.append(str(PurePosixPath(lock.relative_to(target).as_posix()).parent))
    return found


MECHANICAL = ('remove_dead', 'dead_code', 'leftover', 'upgrade_dependency')


def attach(tasks, out, target):
    """Give every mechanical card its codemod, dry-run on an isolated copy; returns how many were attached."""
    facts_by_id = _facts_by_id(out)
    cards = [(task, card_for(task, facts_by_id, target)) for task in tasks if task.get('pattern') in MECHANICAL]
    cards = [(task, card) for task, card in cards if card]
    if not cards: return 0
    from .verify import isolated_copy
    holder = Path(tempfile.mkdtemp(prefix='eaos-codemod-'))
    try:
        # One copy for the whole run, put back after every card: a copy per card on a large project was
        # hundreds of full copies, and none of them was ever removed.
        return _try_cards(cards, target, isolated_copy(Path(target), holder / 'project'))
    finally:
        shutil.rmtree(holder, ignore_errors=True)


def _facts_by_id(out):
    facts_by_id = {}
    for path in sorted((Path(out) / 'facts').glob('*.json')):
        try: data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError): continue
        for fact in data.get('facts') or []:
            if isinstance(fact, dict) and fact.get('id'): facts_by_id[fact['id']] = fact
    return facts_by_id


def _try_cards(cards, target, copy):
    """Dry-run each card's codemod on the copy and attach it to its task: how many were attached."""
    attached = 0
    for done, (task, card) in enumerate(cards):
        progress.count('codemod trials', done, len(cards))
        result, command = dry_run(card, target, copy)
        if result is None: continue
        task['codemod'] = {'tool': card['kind'], 'command': command, 'dry_run': result}
        attached += 1
    progress.count('codemod trials', len(cards), len(cards))
    return attached
