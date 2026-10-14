"""What delivering a batch of fixes needs besides agent_tools' delivery (fix_start, accept, the Studio): a branch's commit,
the batch waiting for the person's decision, a landing on the branch EAOS works on, and the branch a batch merges into."""
from . import branches, guided


def commit_of(project, branch):
    """The commit of a local branch, else of origin's; '' when there is no such branch."""
    for ref in (f'refs/heads/{branch}', f'refs/remotes/origin/{branch}'):
        done = guided._git(project, 'rev-parse', '--verify', '--quiet', ref + '^{commit}')
        if done.returncode == 0: return done.stdout.strip()
    return ''


def waiting_batch(state):
    """The last batch handed over and waiting for the person's decision (accept or undo), or None."""
    return next((w for w in reversed(state.get('waves') or []) if w.get('status') == 'applied'), None)


def direct_target(project, name):
    """(deliver_as, merge_into) of a batch that lands on the branch EAOS works on itself, unless that branch is protected."""
    why = branches.protected(project, name)
    if why: raise ValueError(f'{name} is protected ({why}): the fixes cannot land on it directly; deliver them on a new branch')
    return name, name


def merge_target(state, merge_into, continued):
    """Where the batch merges: as asked, else where the batch it continues was to merge, else the branch open now."""
    project = state['project']
    target = (merge_into or '').strip() or (continued or {}).get('merge_into') or branches.checked_out(project) or state.get('branch')
    if target and not commit_of(project, target): raise ValueError(f'no branch named {target} to merge into')
    return target
