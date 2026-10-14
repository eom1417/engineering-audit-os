"""Where a batch of fixes goes (the fix preview, fix_start, accept): the branch it arrives on, the branch it merges into,
and the EAOS work branches still waiting for the person's decision, which a new batch may continue on."""
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


def waiting_on(state, name):
    """The batch waiting for the person's decision on the EAOS work branch `name` (applied, its branch still there and
    not merged): a new batch may continue on it. None otherwise."""
    if not name or not guided._branch_exists(state, name): return None
    return next((w for w in reversed(state.get('waves') or []) if w.get('status') == 'applied' and w.get('branch') == name), None)


def work_branches(state):
    """The EAOS work branches of the branch EAOS works on that wait for the person's decision: a new batch may continue
    on any of them (the fix preview offers them)."""
    names = dict.fromkeys(w.get('branch') for w in state.get('waves') or [] if w.get('status') == 'applied' and w.get('branch'))
    return [name for name in names if waiting_on(state, name)]


def delivery(state, deliver_as=None, merge_into=None):
    """Where a new batch goes, as the fix preview shows it: (deliver_as, merge_into). deliver_as is
    `eaos/<branch>/wave-N` by default: N counts the batches of the branch EAOS works on, and the branch's name keeps a
    second branch's batch 1 from overwriting the first's waiting one; merge_into is the branch open in the project
    folder (else the branch EAOS works on). deliver_as may also be an EAOS work branch waiting for the person's decision
    (the batch continues on it, on top of its commits; it merges where that batch was to merge), or the branch EAOS
    works on itself: direct, the batch lands on it once every gate passed (never on a protected branch), so merge_into
    is that branch. ValueError for a name git refuses, a branch that already exists, or a protected direct target."""
    project = state['project']
    working = state.get('branch') or branches.checked_out(project) or 'HEAD'
    name = (deliver_as or '').strip() or f"eaos/{branches.slug(working)}/wave-{len(state.get('waves') or []) + 1}"
    if guided._git(project, 'check-ref-format', '--branch', name).returncode: raise ValueError(f'{name} is not a valid branch name')
    if name == working: return _direct(project, name)
    continued = waiting_on(state, name)
    if guided._branch_exists(state, name) and not continued:
        raise ValueError(f'a branch named {name} already exists and is not an EAOS work branch waiting for a decision: choose another name')
    return name, _merge_target(state, merge_into, continued)


def _direct(project, name):
    """The batch lands on the branch EAOS works on itself, unless that branch is protected."""
    why = branches.protected(project, name)
    if why: raise ValueError(f'{name} is protected ({why}): the fixes cannot land on it directly; deliver them on a new branch')
    return name, name


def _merge_target(state, merge_into, continued):
    """Where the batch merges: as asked, else where the batch it continues was to merge, else the branch open now."""
    project = state['project']
    target = (merge_into or '').strip() or (continued or {}).get('merge_into') or branches.checked_out(project) or state.get('branch')
    if target and not commit_of(project, target): raise ValueError(f'no branch named {target} to merge into')
    return target
