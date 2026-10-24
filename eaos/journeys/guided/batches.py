"""The batches handed over and the branch EAOS works on: a batch closed, a stale one retired, a branch taken in, the
branch chosen.
"""
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ...core import branches, jobs
from ...core.project_state import runtime_of, waiting_batch
from .project import PUBLISHERS, _branch_exists, _git, publish, report_of, same_code, save, tip


def close_batch(state, status, why='', via='assistant'):
    """Close the open batch without handing anything over: its copy is removed, it is recorded in `waves` with `status`
    (abandoned, superseded) and `why`; the ledger and the Studio follow, so its cards can be picked again at once."""
    wave = state.get('open_wave')
    if not wave: return None
    root, runtime = Path(wave.get('root') or '/').resolve(), runtime_of(state).resolve()
    if runtime in root.parents: shutil.rmtree(root, ignore_errors=True)
    record = {'number': wave['number'], 'base': wave.get('base'), 'cards': wave['cards'], 'kept': {},
              'failed': wave.get('failed') or {} if status == 'abandoned' else {}, 'branch': None, 'status': status, 'via': via,
              'keys': wave.get('keys') or {}, **{k: wave[k] for k in ('deliver_as', 'merge_into', 'base_branch') if k in wave}}
    if why: record['why'] = why
    state.setdefault('waves', []).append(record)
    state.pop('open_wave', None)
    save(state)
    publish(state)
    return record


def retire_stale_batch(state):
    """The open batch, retired (superseded, with why) when it no longer fits: its base is not the code of the branch EAOS
    works on now (a commit of the person's came after it), or the check on record numbered its cards again (a card id
    of the batch is another problem now). Called by `status`, `fix_start` and after every check. The record, or None."""
    wave = state.get('open_wave')
    # never under its own work (a status call retired a batch mid hand-over: KeyError 'open_wave', two hours lost)
    if not wave or jobs.fixing(state['project']): return None
    now, why = tip(state), None
    built_on = wave.get('source_commit') or wave.get('base')         # a batch continued on a work branch: its branch's commit
    if now and not same_code(state, built_on, now) and not wave.get('kept'):    # kept changes go on: their merge says
        why = f"the code moved on since the batch opened (it was built on {str(built_on)[:12]}, the branch is at {now[:12]})"
    else: why = _renumbered(state, wave)
    return close_batch(state, 'superseded', why, via='eaos') if why else None


def _renumbered(state, wave):
    """Why the open batch no longer fits when the check on record numbered its cards again; else None."""
    if not (wave.get('keys') and (report_of(state) / 'plan.json').is_file()): return None
    from ..waves import plan as read_plan
    try: keys = {t['id']: t['key'] for t in read_plan(report_of(state))['tasks']}
    except (OSError, ValueError, KeyError): return None
    if any(keys.get(card) != key for card, key in wave['keys'].items()):
        return 'a new check numbered the cards again: the batch\'s cards are other problems now'
    return None


def reconcile(state):
    """Bring the state up to what git says, however the person or their assistant merged: a batch whose branch (or
    whose last commit) is in the current branch is accepted, and its branch deleted; one whose branch is gone without
    that is undone. When something changed, the ledger and REPORT.html follow at once. The changed batches."""
    changed = [wave for wave in state.get('waves') or [] if _settle(state, wave)]
    if changed:
        save(state)
        if state.get('mode') in PUBLISHERS: PUBLISHERS[state['mode']](state)
        else:
            publish(state, event='merged')
        save(state)
    return changed


def _settle(state, wave):
    """Whether git just accepted the batch (its branch, or its last commit, is in the branch it goes into) or undid it
    (its branch is gone without that); an accepted batch's branch is deleted unless the person keeps it."""
    branch, status = wave.get('branch'), wave.get('status')
    if not branch or status not in ('applied', 'superseded', 'accepted'): return False
    exists = _branch_exists(state, branch)
    last, inside = _in_target(state, wave, exists)
    drop = exists and not wave.get('keep_branch')       # the person may have chosen to keep it after merging
    if drop and inside: _git(state['project'], 'branch', '-D', branch)       # merged: its branch goes
    if status == 'accepted': return False
    if inside:                                          # merged into the branch EAOS works on
        wave.update(status='accepted', merged_at=datetime.now(timezone.utc).isoformat(timespec='seconds'), tip=last)
        return True
    if exists or status != 'applied': return False
    wave['status'] = 'undone'
    return True


def _in_target(state, wave, exists):
    """(the batch's last commit, whether it is in the branch the batch goes into)."""
    last = _git(state['project'], 'rev-parse', wave['branch']).stdout.strip() if exists else wave.get('tip')
    into = f"refs/heads/{wave['merge_into']}" if wave.get('merge_into') else branches.ref(state)
    return last, bool(last) and not _git(state['project'], 'merge-base', '--is-ancestor', last, into).returncode


def merge(state, wave, into=None, delete_after=True):
    """The batch's branch into `into` (the person's choice at accept), else the branch it was to be merged into
    (wave['merge_into'], chosen in the fix preview), else the branch EAOS works on: a fast-forward when it can, else a
    merge commit when git merges it cleanly (a conflict is taken back, and nothing changes); then reconcile deletes the
    branch (kept when `delete_after` is false) and updates the ledger and the report. 'merged', 'unsaved_changes' or
    'conflict'."""
    project = state['project']
    _merge_choices(state, wave, into, delete_after)
    into = wave.get('merge_into') or state.get('branch')
    if into and branches.checked_out(project) != into: return _merge_elsewhere(state, wave, into)
    if _git(project, 'status', '--porcelain', '--untracked-files=no').stdout.strip(): return 'unsaved_changes'
    if _git(project, 'merge', '--ff-only', '--quiet', wave['branch']).returncode:
        done = _git(project, '-c', 'user.name=EAOS', '-c', 'user.email=eaos@localhost', 'merge', '--no-edit', '--quiet',
                    '-m', f"Merge {wave['branch']}: EAOS batch {wave.get('number')}", wave['branch'])
        if done.returncode:
            _git(project, 'merge', '--abort')
            return 'conflict'
    reconcile(state)
    return 'merged'


def _merge_choices(state, wave, into, delete_after):
    """Where the batch goes and whether its branch stays, set on it and on every batch continued on its branch."""
    for each in [w for w in state.get('waves') or [] if w.get('status') == 'applied' and w.get('branch') == wave['branch']] + [wave]:
        if into or wave.get('merge_into'): each['merge_into'] = into or wave['merge_into']     # batches continued on one branch
        if not delete_after: each['keep_branch'] = True                                       # go in together


def _merge_elsewhere(state, wave, into):
    """The same merge into a branch that is not the one checked out, made by git without a checkout (merge-tree), then
    the branch moved to it only if nobody moved it meanwhile. The person's checkout and files are not touched."""
    project, ref = state['project'], f'refs/heads/{into}'
    before = _git(project, 'rev-parse', '--verify', '--quiet', ref).stdout.strip()
    wave_tip = _git(project, 'rev-parse', wave['branch']).stdout.strip()
    if not before or not wave_tip: return 'conflict'
    if not _git(project, 'merge-base', '--is-ancestor', before, wave_tip).returncode: after = wave_tip
    else:
        tree = _git(project, 'merge-tree', '--write-tree', before, wave_tip)
        if tree.returncode: return 'conflict'
        made = _git(project, '-c', 'user.name=EAOS', '-c', 'user.email=eaos@localhost', 'commit-tree', tree.stdout.split()[0],
                    '-p', before, '-p', wave_tip, '-m', f"Merge {wave['branch']}: EAOS batch {wave.get('number')}")
        if made.returncode: return 'conflict'
        after = made.stdout.strip()
    if _git(project, 'update-ref', '-m', f"EAOS: merge {wave['branch']}", ref, after, before).returncode: return 'conflict'
    reconcile(state)
    return 'merged'


def choose(state, name, said=None, via=None):
    """Work on the branch `name` from now on: what this branch had (its check, run, batches) is kept aside, and what
    `name` had before comes back. A branch only on origin gets its local branch, at the same commit. The new state.
    `via` (the assistant, the Studio): the person answered the branch question there, in the words `said`; the answer is
    kept with the state's questions, whoever asked."""
    if via: _keep_answer(state, name, said, via)
    if state.get('branch') == name: return state
    project = state['project']
    _finished(state, project, name)
    _local_branch(project, name)
    if not state.get('branch') and _first_choice(state, project, name):
        save(state)
        return state
    state.setdefault('by_branch', {})[state['branch']] = {k: state.pop(k) for k in branches.KEYS if k in state}
    state.update(state['by_branch'].pop(name, {}))
    state['branch'] = name
    save(state)
    return state


def _keep_answer(state, name, said, via):
    """The person's answer to the branch question, kept with the state's questions."""
    state.setdefault('questions', []).append({'id': 'branch', 'kind': 'choice', 'answer': name, 'said': str(said or '')[:300] or None,
                                              'via': via})


def _finished(state, project, name):
    """ValueError while the work on the branch EAOS works on is not finished (an open batch, a waiting branch): it does
    not move to `name` then."""
    working_on = state.get('branch') or branches.checked_out(project)
    if working_on != name and (state.get('open_wave') or waiting_batch(state) is not None):
        raise ValueError(f"the work on {working_on} is not finished: close the open batch, and accept or undo the "
                         'waiting branch, before moving to another branch')


def _local_branch(project, name):
    """The branch `name` in the project: a branch only on origin gets its local branch, at the same commit."""
    if not _git(project, 'rev-parse', '--verify', '--quiet', f'refs/heads/{name}').returncode: return
    if _git(project, 'rev-parse', '--verify', '--quiet', f'refs/remotes/origin/{name}').returncode:
        raise ValueError(f'no branch named {name} in this project')
    _git(project, 'branch', '--quiet', '--track', name, f'origin/{name}')


def _first_choice(state, project, name):
    """The first choice of a branch: work done before it was on the branch checked out then. True when that is `name`."""
    had = any(k in state for k in branches.KEYS)
    state['branch'] = state['home_branch'] = (branches.checked_out(project) if had else None) or name
    return state['branch'] == name
