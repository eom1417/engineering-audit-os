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
import sys
import tempfile
from pathlib import Path

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
    spans = []
    for node in tree.body:
        names = ([node.name] if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else
                 [t.id for t in getattr(node, 'targets', []) if isinstance(t, ast.Name)] +
                 ([node.target.id] if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) else []))
        if name in names:
            start = min([d.lineno for d in getattr(node, 'decorator_list', [])] + [node.lineno])
            spans.append((start, node.end_lineno))
    for start, end in sorted(spans, reverse=True): del lines[start - 1:end]
    if spans: Path(path).write_text(''.join(lines), encoding='utf-8')
    return bool(spans)


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
        if not binary: return None
        return [([binary, '-t', str(TRANSFORM), '--parser=tsx', f"--name={detail['symbol']}", detail['path']], None)]
    if kind == 'npm':
        binary = which('npm') or 'npm'
        flags = ['--package-lock-only', '--ignore-scripts', '--no-audit', '--no-fund', '--loglevel=error']
        if detail['direct']:
            return [([binary, 'install', f"{detail['package']}@{detail['fixed']}", *flags], None)]
        return [([binary, 'pkg', 'set', f"overrides.{detail['package']}={detail['fixed']}"], None), ([binary, 'install', *flags], None)]
    return None


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
        before, code, shown = _stats(copy), 0, []
        for step, description in steps:
            if callable(step):
                try: step()
                except (OSError, SyntaxError, ValueError): code = 1
                shown.append(description)
            else:
                import os
                done = subprocess.run(step, cwd=copy, capture_output=True, text=True, timeout=600,
                                      env={**os.environ, 'BABEL_DISABLE_CACHE': '1'})
                code = code or done.returncode
                shown.append(shlex.join([Path(step[0]).name, *step[1:]]).replace(str(TRANSFORM), 'eaos/templates/codemods/remove-declaration.cjs'))
            if code: break
        after = _stats(copy)
        changed = _changed(copy, target, before, after)
        if not owned: _restore(copy, target, before, after)
        return {'exit': code, 'files_changed': len(changed)}, ' && '.join(shown)
    finally:
        if owned: shutil.rmtree(holder, ignore_errors=True)


def card_for(task, facts_by_id, target):
    """What the codemod of one task changes, or None when its family has no mechanical tool."""
    rules = json.loads(RULES.read_text(encoding='utf-8'))
    facts = [facts_by_id[f] for f in (task.get('evidence') or {}).get('fact_ids') or [] if f in facts_by_id]
    pattern = task.get('pattern')
    if pattern in ('remove_dead', 'dead_code'):
        fact = next((f for f in facts if (f.get('value') or {}).get('rule')), None)
        if not fact: return None
        rule, path = fact['value']['rule'], fact['location']['path']
        tool = rules['remove_dead'].get(rule)
        if isinstance(tool, dict): tool = tool.get(LANGUAGES.get(Path(path).suffix))
        if not tool: return None
        return {'kind': tool, 'path': path, 'symbol': fact['location'].get('symbol')}
    if pattern == 'leftover':
        fact = next(iter(facts), None)
        return {'kind': 'delete-file', 'path': fact['location']['path']} if fact else None
    if pattern == 'upgrade_dependency':
        fact = next(iter(facts), None)
        if not fact: return None
        ecosystem, _, rest = str(fact['location'].get('symbol')).partition(':')
        package, _, _ = rest.rpartition('@')
        fixed = next((m['value'] for m in fact['value'].get('measurements') or [] if m['name'] == 'fixed_in'), None)
        if ecosystem != 'npm' or not fixed or not (Path(target) / 'package-lock.json').is_file(): return None
        manifest = json.loads((Path(target) / 'package.json').read_text(encoding='utf-8'))
        direct = package in (manifest.get('dependencies') or {}) or package in (manifest.get('devDependencies') or {})
        return {'kind': 'npm', 'package': package, 'fixed': fixed, 'direct': direct}
    return None


MECHANICAL = ('remove_dead', 'dead_code', 'leftover', 'upgrade_dependency')


def attach(tasks, out, target):
    """Give every mechanical card its codemod, dry-run on an isolated copy; returns how many were attached."""
    facts_by_id = {}
    for path in sorted((Path(out) / 'facts').glob('*.json')):
        try: data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError): continue
        for fact in data.get('facts') or []:
            if isinstance(fact, dict) and fact.get('id'): facts_by_id[fact['id']] = fact
    cards = [(task, card_for(task, facts_by_id, target)) for task in tasks if task.get('pattern') in MECHANICAL]
    cards = [(task, card) for task, card in cards if card]
    if not cards: return 0
    from .verify import isolated_copy
    holder = Path(tempfile.mkdtemp(prefix='eaos-codemod-'))
    attached = 0
    try:
        # One copy for the whole run, put back after every card: a copy per card on a large project was
        # hundreds of full copies, and none of them was ever removed.
        copy = isolated_copy(Path(target), holder / 'project')
        for task, card in cards:
            result, command = dry_run(card, target, copy)
            if result is None: continue
            task['codemod'] = {'tool': card['kind'], 'command': command, 'dry_run': result}
            attached += 1
    finally:
        shutil.rmtree(holder, ignore_errors=True)
    return attached
