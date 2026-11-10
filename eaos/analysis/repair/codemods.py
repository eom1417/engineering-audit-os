"""A codemod for every mechanical card, tried on an isolated copy before anyone runs it for real.

The mechanical families (eaos/rules/codemods.json) and their tools:
  remove_dead, unreachable module   delete-file: the file goes
  remove_dead, unused symbol        jscodeshift with eaos/templates/codemods/remove-declaration.cjs (JS/TS),
                                    or python-ast: the definition's lines, from the syntax tree (Python)
  leftover                          delete-file
  upgrade_dependency (npm, bun, uv) a direct dependency: npm install pkg@fixed (bun add); a transitive one:
                                    overrides["pkg@>=vulnerable <=fixed"] = fixed in package.json (that version's
                                    copies only), then npm install (bun install); npm's --package-lock-only,
                                    bun's --lockfile-only, both --ignore-scripts, so nothing is installed and no
                                    project code runs. A lock file card's packages: every override, then each
                                    install once. uv: one `uv lock --upgrade-package pkg==fixed` per lock file,
                                    every package of the card in it; go and cargo: eaos/analysis/repair/lock_tools.py
Each card gets codemod {tool, command, dry_run {exit, files_changed}}. The dry run is the real command on a
copy made by eaos.live.testing.verify.isolated_copy; files_changed counts files added, removed or modified there. A
tool that changes nothing did nothing, and says so with files_changed 0. The project is never written.
"""
import ast
import json
import re
import shlex
import shutil
import subprocess
import tempfile
from functools import partial
from pathlib import Path, PurePosixPath

from ...core import progress
from ...core.system.files import read_json
from .actions_upgrade import action_card, bump
from .lock_tools import LOCK_TOOLS
from ...core.system.errors import noted

RULES = Path(__file__).resolve().parents[2] / 'rules/codemods.json'
TRANSFORM = Path(__file__).resolve().parents[2] / 'templates/codemods/remove-declaration.cjs'
LANGUAGES = {'.py': 'python', '.js': 'javascript', '.jsx': 'javascript', '.ts': 'typescript', '.tsx': 'tsx',
             '.mjs': 'javascript'}


def _stats(root):
    """{path: (size, mtime_ns)} of every project file; tool caches (node_modules/.cache and the like) are not the
    project. A stat is cheap where reading every file is not: a large project dry-runs hundreds of cards."""
    import os
    from ...core.project.workspace import SKIP_DIRS
    root, found = Path(root), {}
    for base, directories, names in os.walk(root):
        directories[:] = [d for d in directories if d not in SKIP_DIRS]
        for name in names:
            path = Path(base) / name
            try: stat = path.stat()
            except OSError as error:
                noted('a file that vanished or cannot be read is left out of the listing', error)
                continue
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


def binary(tool):
    """Where a codemod's tool is: EAOS's own first (uv: the one its installer brought), then the computer's."""
    from ...core.toolchain.pins import uv
    from ...engines.process import which
    return uv() if tool == 'uv' else which(tool)


NPM_FLAGS = ['--package-lock-only', '--ignore-scripts', '--no-audit', '--no-fund', '--loglevel=error']
# Each package.json manager's (command that sets one dependency, flags that write only the lock and run no script of the
# project, the flag naming the folder). bun keeps a dev dependency in devDependencies and reads npm's overrides keys.
LOCK_ONLY = {'npm': ('install', NPM_FLAGS, '--prefix'),
             'bun': ('add', ['--lockfile-only', '--ignore-scripts'], '--cwd')}


def _manifest_steps(detail, executable, copy):
    """In each folder: a direct dependency set at its fixed version; a transitive one overridden, then installed."""
    steps, (add, flags, at) = [], LOCK_ONLY[detail['kind']]
    for folder, direct in detail.get('folders') or [(detail.get('folder', '.'), detail['direct'])]:
        prefix = [at, folder] if folder != '.' else []
        if direct:
            steps.append(([executable, add, f"{detail['package']}@{detail['fixed']}", *flags, *prefix], None))
        else:
            # Only the vulnerable version's copies, never every copy of the package: another major line keeps its own
            # (npm keeps a key's range only when it holds the fixed version too; a key of one version moves one copy).
            key = f"{detail['package']}@>={detail['version']} <={detail['fixed']}"
            manifest = Path(copy) / folder / 'package.json'
            steps += [(lambda manifest=manifest, key=key: _override(manifest, key, detail['fixed']),
                       f"override {key} with {detail['fixed']} in {PurePosixPath(folder, 'package.json')}"),
                      ([executable, 'install', *flags, *prefix], None)]
    return steps


def _override(manifest, key, fixed):
    """package.json's overrides[key] = fixed, the file otherwise as it was written (its indent, its characters)."""
    text = manifest.read_text(encoding='utf-8')
    data = json.loads(text)
    data.setdefault('overrides', {})[key] = fixed
    indent = re.search(r'\n([ \t]+)"', text)
    manifest.write_text(json.dumps(data, indent=indent[1] if indent else 2, ensure_ascii=False) + '\n',
                        encoding='utf-8')


def _commands(card, copy):
    """[(argv, None) or (callable, description)] for one card, in the copy."""
    kind, detail = card['kind'], card
    if kind == 'delete-file':
        return [(lambda: (copy / detail['path']).unlink(), f"rm {shlex.quote(detail['path'])}")]
    if kind == 'python-ast':
        return [(lambda: remove_python(copy / detail['path'], detail['symbol']),
                 f"python-ast remove {detail['symbol']} from {detail['path']}")]
    if kind == 'jscodeshift':
        found = binary('jscodeshift')
        return [([found, '-t', str(TRANSFORM), '--parser=tsx', f"--name={detail['symbol']}",
                  detail['path']], None)] if found else None
    if kind in (*LOCK_ONLY, *LOCK_TOOLS, 'uv', 'actions'): return _upgrade_steps(detail, copy)
    return None


def _upgrade_steps(card, copy):
    """The steps of an upgrade card, one package's or a lock file card's, by its lock file's tool."""
    members, executable = card.get('group') or [card], binary(card['kind']) or card['kind']
    if card['kind'] in LOCK_TOOLS: return LOCK_TOOLS[card['kind']](members, executable, copy)
    if card['kind'] == 'actions':
        return [(partial(bump, copy, m['package'], m['fixed']), f"uses: {m['package']}@{m['fixed']}")
                for m in members]
    return _uv_steps(members, executable) if card['kind'] == 'uv' else _group_steps(members, executable, copy)


def _uv_steps(members, executable):
    """One `uv lock` moving every package to its fixed version: the lock alone is written, nothing installed or built
    for the project."""
    folder = members[0]['folder']
    pins = [part for member in members for part in ('--upgrade-package', f"{member['package']}=={member['fixed']}")]
    return [([executable, 'lock', *pins, *(['--directory', folder] if folder != '.' else [])], None)]


def _group_steps(members, executable, copy):
    """Every package's steps, the edits of the manifests first, then each install once."""
    steps = [step for member in members for step in _manifest_steps(member, executable, copy)]
    installs = {tuple(step): (step, text) for step, text in steps if not callable(step)}
    return [(step, text) for step, text in steps if callable(step)] + list(installs.values())


def _run_step(step, description, copy):
    """(exit code, the command as shown) of one step in the copy."""
    if callable(step):
        try:
            step()
            return 0, description
        except (OSError, SyntaxError, ValueError) as problem:
            return 1, f'{description}: {problem}'
    import os
    done = subprocess.run(step, cwd=copy, capture_output=True, text=True, timeout=600,  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- a codemod's argv built here (jscodeshift, npm --ignore-scripts), run in an isolated copy, no shell
                          env={**os.environ, 'BABEL_DISABLE_CACHE': '1'})
    return done.returncode, shlex.join([Path(step[0]).name, *step[1:]]).replace(
        str(TRANSFORM), 'eaos/templates/codemods/remove-declaration.cjs')


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
    from ...live.testing.verify import isolated_copy
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
    if pattern == 'upgrade_dependency': return _upgrades_card(facts, target)
    return None


def _upgrades_card(facts, target):
    """A lock file card's packages each get their own change, and the card passes or fails whole; one package: its
    own."""
    members = [action_card(fact) or _upgrade_card(fact, target) for fact in facts]
    if not members or None in members: return None
    return members[0] if len(members) == 1 else {'kind': members[0]['kind'], 'group': _past_vulnerable(members)}


def _past_vulnerable(members):
    """Each package's target moved on while it is another vulnerable version of the card (1.5.4 fixed in 1.6.8, itself
    fixed in 1.6.11: both go to 1.6.11), so no step puts back a version the card removes. Another line of the package
    (a 1.x beside a 2.x) keeps its own."""
    fixes = {(member['package'], member['version']): member['fixed'] for member in members}
    for member in members:
        seen = set()
        while (member['package'], member['fixed']) in fixes and member['fixed'] not in seen:
            seen.add(member['fixed'])
            member['fixed'] = fixes[(member['package'], member['fixed'])]
    return members


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
    """An upgrade to the fixed version by the lock file's own tool (rules/codemods.json); npm's in every folder whose
    lock file holds the vulnerable version."""
    package, _, version = str(fact['location'].get('symbol')).partition(':')[2].rpartition('@')
    fixed = next((m['value'] for m in fact['value'].get('measurements') or [] if m['name'] == 'fixed_in'), None)
    # The lock file the scanner read names the folder: an app in app/ has its manifest there, not at the root.
    lock = PurePosixPath(fact['location'].get('path') or 'package-lock.json')
    kind, folder = _upgrade_tools().get(lock.name), str(lock.parent)
    if not kind or not fixed or not (Path(target) / lock).is_file(): return None
    if kind not in LOCK_ONLY: return {'kind': kind, 'package': package, 'version': version, 'fixed': fixed,
                                      'folder': folder}
    folders = _upgrade_folders(target, lock, package, version)
    return {'kind': kind, 'package': package, 'version': version, 'fixed': fixed,
            'direct': _direct_in(target, folder, package), 'folder': folder,
            'folders': [(where, _direct_in(target, where, package)) for where in folders]}


def _upgrade_tools():
    """{lock file name: the tool whose codemod rewrites it}."""
    return json.loads(RULES.read_text(encoding='utf-8'))['upgrade_dependency']


def _upgrade_folders(target, lock, package, version):
    """The folder of the lock file the scanner read, then the others holding the same version, each with a
    package.json."""
    # The same vulnerable version in another lock file of the project (a server/ beside the app) is the same
    # problem: the card's acceptance scans the whole project, so every such lock file is upgraded with it (npm's).
    others = _lock_folders_with(target, package, version) if lock.name == 'package-lock.json' else []
    folders = [str(lock.parent)] + [where for where in others if where != str(lock.parent)]
    return [where for where in folders if (Path(target) / where / 'package.json').is_file()]


def _lock_folders_with(target, package, version):
    """Folders (relative, '.' for the root) whose package-lock.json holds `package` at `version`."""
    found = []
    for lock in sorted(Path(target).rglob('package-lock.json')):
        if 'node_modules' in lock.parts: continue
        packages = read_json(lock, {}).get('packages') or {}
        if any(key.split('node_modules/')[-1] == package and (row or {}).get('version') == version
               for key, row in packages.items()):
            found.append(str(PurePosixPath(lock.relative_to(target).as_posix()).parent))
    return found


# Each lock file's package manager and the command a person runs to move one package in it. A batch upgrades only a
# lock file that has a codemod (rules/codemods.json) whose tool is installed: a card no tool can pass is not fixable.
MANAGERS = {'package-lock.json': ('npm', 'npm install {package}@{fixed}'), 'bun.lock': ('bun', 'bun update {package}'),
            'bun.lockb': ('bun', 'bun update {package}'), 'pnpm-lock.yaml': ('pnpm', 'pnpm update {package}'),
            'yarn.lock': ('yarn', 'yarn up {package}'), 'uv.lock': ('uv', 'uv lock --upgrade-package {package}'),
            'poetry.lock': ('poetry', 'poetry update {package}'), 'Pipfile.lock': ('pipenv', 'pipenv update {package}'),
            'go.mod': ('go', 'go get {package}@v{fixed} && go mod tidy'),
            'go.sum': ('go', 'go get {package}@v{fixed} && go mod tidy'),
            'Cargo.lock': ('cargo', 'cargo update -p {package} --precise {fixed}'),
            'Gemfile.lock': ('bundle', 'bundle update {package}'),
            'composer.lock': ('composer', 'composer update {package}')}


def manual_upgrade(path, package, fixed):
    """Why a batch cannot move `package` in the lock file at `path`, as {'why', 'tool', 'lock', 'command'}; None when
    it can, or when the site is no lock file (a requirements.txt is a text edit). 'lock' is a component no lock file
    names."""
    lock = PurePosixPath(path).name
    if lock == 'sbom.cdx.json': return {'why': 'lock', 'tool': '', 'lock': lock, 'command': ''}
    if lock not in MANAGERS: return None
    tool, command = MANAGERS[lock]
    command = command.format(package=package, fixed=str(fixed).removeprefix('v'))
    if lock not in _upgrade_tools():
        return {'why': 'tool', 'tool': tool, 'lock': lock, 'command': command}
    return None if binary(tool) else {'why': 'missing', 'tool': tool, 'lock': lock, 'command': command}


MECHANICAL = ('remove_dead', 'dead_code', 'leftover', 'upgrade_dependency')


def _codemod_cards(tasks, out, target):
    """(task, codemod) of every mechanical card whose family has a tool."""
    from ...facts.store import by_id
    mechanical = [task for task in tasks if task.get('pattern') in MECHANICAL]
    facts_by_id = by_id(out, {i for task in mechanical for i in (task.get('evidence') or {}).get('fact_ids') or []})
    cards = [(task, card_for(task, facts_by_id, target)) for task in mechanical]
    return [(task, card) for task, card in cards if card]


def attach(tasks, out, target):
    """Give every mechanical card its codemod, dry-run on an isolated copy; returns how many were attached."""
    cards = _codemod_cards(tasks, out, target)
    if not cards: return 0
    from ...live.testing.verify import isolated_copy
    holder = Path(tempfile.mkdtemp(prefix='eaos-codemod-'))
    try:
        # One copy for the whole run, put back after every card: a copy per card on a large project would be
        # hundreds of full copies.
        return _try_cards(cards, target, isolated_copy(Path(target), holder / 'project'))
    finally:
        shutil.rmtree(holder, ignore_errors=True)


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
