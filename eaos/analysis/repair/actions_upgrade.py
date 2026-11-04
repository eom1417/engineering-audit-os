"""A GitHub Action with a published vulnerability, upgraded where the workflows use it: no lock file names an Action,
so the inventory alone found it and no batch could move it (a stranger's Python library, its publishing Action,
2026-11-04). A tag reference (`@v1.12.4`) takes the fixed tag; a commit pinned with its tag in a comment
(`@<sha> # v1.12.4`) takes the fixed tag's commit, read from the Action's own repository, and the comment says the tag.
A moving major tag (`@v1`) is left: it already follows its releases."""
import re
from pathlib import Path
from ...core.system.process import run_command

ACTIONS = 'GitHub Actions:'      # the ecosystem the inventory (syft, osv-scanner) names an Action by
USES = r'(uses:\s*["\']?{action}@)([0-9A-Za-z._/-]+)(["\']?)([ \t]*#[ \t]*v?[0-9][^\n]*)?'


def action_card(fact):
    """The codemod of a vulnerable Action with a fix, {kind, package, version, fixed}; None for anything else."""
    symbol = str(fact['location'].get('symbol'))
    fixed = next((m['value'] for m in (fact.get('value') or {}).get('measurements') or [] if m['name'] == 'fixed_in'), None)
    if not symbol.startswith(ACTIONS) or not fixed: return None
    package, _, version = symbol.removeprefix(ACTIONS).rpartition('@')
    return {'kind': 'actions', 'package': package, 'version': version, 'fixed': fixed}


def workflows(root):
    """The workflow and composite Action files of the project."""
    folder = Path(root) / '.github'
    return sorted(path for path in folder.rglob('*') if path.suffix in ('.yml', '.yaml') and path.is_file()) if folder.is_dir() else []


def bump(root, action, fixed):
    """Upgrade every use of `action` to its tag `fixed`; the files changed. RuntimeError when a pinned commit's tag cannot
    be read from the Action's repository (the batch's copy is put back then)."""
    pattern, changed, known = re.compile(USES.format(action=re.escape(action))), [], {}

    def commit():
        if 'commit' not in known: known['commit'] = _commit_of(action, fixed)     # read once, for every use
        return known['commit']
    for path in workflows(root):
        text = path.read_text(encoding='utf-8')
        new = pattern.sub(lambda found: _moved(found, fixed, commit), text)
        if new != text:
            path.write_text(new, encoding='utf-8')
            changed.append(path)
    return changed


def _moved(found, fixed, commit):
    """One `uses:` line moved to the fixed tag, or as it was when its reference is a moving major tag."""
    ref, tag = found[2], _tag(fixed, found[2], found[4])
    if re.fullmatch(r'[0-9a-f]{40}', ref): return f'{found[1]}{commit()}{found[3]} # {tag}'
    if re.fullmatch(r'v?\d+', ref): return found[0]
    return f'{found[1]}{tag}{found[3]}{found[4] or ""}'


def _tag(fixed, ref, comment):
    """The fixed version written as the project writes its tags: with the `v` its reference or comment has."""
    bare = str(fixed).removeprefix('v')
    return ('v' if (ref.startswith('v') or (comment or '').lstrip(' \t#').startswith('v')) else '') + bare


def _commit_of(action, fixed):
    """The commit of the fixed tag in the Action's repository (owner/repo, whatever path follows)."""
    repository = '/'.join(action.split('/')[:2])
    bare = str(fixed).removeprefix('v')
    names = [f'{prefix}{bare}{peeled}' for peeled in ('^{}', '') for prefix in ('v', '')]     # an annotated tag's commit first
    shown = run_command(['git', 'ls-remote', '--tags', f'https://github.com/{repository}', *names], timeout=60)
    rows = dict(reversed(line.split('\t')) for line in shown.stdout.splitlines() if '\t' in line)
    commit = next((rows[f'refs/tags/{name}'] for name in names if f'refs/tags/{name}' in rows), None)
    if shown.returncode or not commit: raise RuntimeError(f'the tag {fixed} of {repository} could not be read from GitHub')
    return commit
