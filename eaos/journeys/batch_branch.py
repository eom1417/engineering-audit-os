"""What delivering a batch of fixes needs besides agent_tools' delivery (fix_start, accept, the Studio): a branch's commit,
the batch waiting for the person's decision, a landing on the branch EAOS works on, and the branch a batch merges into."""
from ..core import branches
from . import guided


def commit_of(project, branch):
    """The commit of a local branch, else of origin's; '' when there is no such branch."""
    for ref in (f'refs/heads/{branch}', f'refs/remotes/origin/{branch}'):
        done = guided._git(project, 'rev-parse', '--verify', '--quiet', ref + '^{commit}')
        if done.returncode == 0: return done.stdout.strip()
    return ''


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


def decided(state, branch):
    """'accepted' or 'undone' once the person decided on the batches of `branch` (in the Studio or anywhere else: the
    state is the one truth), else None. A decision made outside the Studio left its question waiting (2026-10-23)."""
    statuses = {w.get('status') for w in state.get('waves') or [] if branch and w.get('branch') == branch}
    return None if not statuses or 'applied' in statuses else next((s for s in ('accepted', 'undone') if s in statuses), None)
