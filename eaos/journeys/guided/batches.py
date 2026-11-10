"""The batches handed over and the branch EAOS works on: a batch closed, a stale one retired, a branch taken in, the
branch chosen.
"""

from ...core.project import branches, jobs
from ...core.project.state import waiting_batch
from .project import PUBLISHERS, _branch_exists, _git, fresh, publish, report_of, save_after_report, same_code, save, tip
from ...core.system.clock import now


def close_batch(state, status, why='', via='assistant'):
    """Close the open batch without handing anything over: its copy is removed, it is recorded in `waves` with `status`
    (abandoned, superseded) and `why`; the ledger and the records follow, so its cards can be picked again at once."""
    with fresh(state):
        wave = state.get('open_wave')
        if not wave: return None
        record = {'number': wave['number'], 'base': wave.get('base'), 'cards': wave['cards'], 'kept': {},
                  'failed': wave.get('failed') or {} if status == 'abandoned' else {}, 'branch': None, 'status': status, 'via': via,
                  'keys': wave.get('keys') or {}, **{k: wave[k] for k in ('deliver_as', 'merge_into', 'base_branch') if k in wave}}
        if why: record['why'] = why
        state.setdefault('waves', []).append(record)
        state.pop('open_wave', None)
        save(state)
    publish(state)
    return record


class StaleBatch(Exception):
    """A change stopped because the batch does not fit. Leaving lanes.changing this way saves nothing. `answer`:
    the refusal."""

    def __init__(self, answer):
        super().__init__(answer['why'])
        self.answer = answer


def why_stale(state):
    """Why the open batch does not fit, or None, and None under its own work (retiring a batch mid hand-over would
    fail with KeyError 'open_wave'). It only says: `status` reports this, and retire_stale_batch acts on it."""
    wave = state.get('open_wave')
    if not wave or jobs.fixing(state['project']): return None
    return _no_longer_fits(state, wave)


def _no_longer_fits(state, wave):
    """Its base is not the code of the branch EAOS works on now (a commit of the person's came after it), or the
    check on record numbered its cards again (a card id of the batch is another problem now); else None."""
    now = tip(state)
    # a batch continued on a work branch: its branch's commit
    built_on = wave.get('source_commit') or wave.get('base')
    if now and not same_code(state, built_on, now) and not wave.get('kept'):    # kept changes go on: their merge says
        return f"the code moved on since the batch opened (it was built on {str(built_on)[:12]}, the branch is at {now[:12]})"
    return _renumbered(state, wave)


def stale_refusal(state):
    """What a tool or job that changes the open batch answers when it does not fit, the batch as it was; else
    None. Refusing removes nothing, so another job running hides nothing here, and a batch's own job can ask."""
    wave = state.get('open_wave')
    if not (wave and (why := _no_longer_fits(state, wave))): return None
    return {'status': 'stale_batch', 'batch': wave['number'], 'why': why,
            'what_now': 'The batch is as it was: it no longer fits, so it takes no change. fix_start closes it and opens the next '
                        'one; fix_abandon only closes it; its cards can be picked again. A helper of this batch closes nothing: '
                        'it says so and ends its turn. A job still running ends first: fix_start closes nothing under it.'}


def refuse_if_stale(state):
    if stop := stale_refusal(state): raise StaleBatch(stop)


def retire_stale_batch(state):
    """The open batch closed as superseded, with why, when it does not fit; its copy goes with it. Only what the
    person asked to work does this, `fix_start` and every check: reading where things stand removes nothing. The
    record, or None."""
    why = why_stale(state)
    return close_batch(state, 'superseded', why, via='eaos') if why else None


def _renumbered(state, wave):
    """Why the open batch does not fit when the check on record numbered its cards again; else None."""
    if not (wave.get('keys') and (report_of(state) / 'plan.json').is_file()): return None
    from ..fix.waves import plan as read_plan
    try: keys = {t['id']: t['key'] for t in read_plan(report_of(state))['tasks']}
    except (OSError, ValueError, KeyError): return None
    if any(keys.get(card) != key for card, key in wave['keys'].items()):
        return 'a new check numbered the cards again: the batch\'s cards are other problems now'
    return None


def reconcile(state, tidy=True):
    """Bring the state up to what git says, however the person or their assistant merged: a batch whose branch (or
    whose last commit) is in the current branch is accepted; one whose branch is gone without that is undone. With
    `tidy`, an accepted batch's branch is deleted: what only reads where things stand passes False. When something
    changed, the ledger and the report follow at once, with no lock held. `state` itself becomes what is on disk.
    The changed batches."""
    if not (tidy or _something_to_settle(state)): return []     # a read with nothing to settle writes nothing
    with fresh(state):
        changed = [wave for wave in state.get('waves') or [] if _settle(state, wave, tidy)]
        if changed: save(state)
    if changed:
        if state.get('mode') in PUBLISHERS: PUBLISHERS[state['mode']](state)
        else:
            publish(state, event='merged')
        save_after_report(state)
    return changed


def _something_to_settle(state):
    return any(_settle(state, dict(wave), False) for wave in state.get('waves') or [])


def _drop_branch(state, wave):
    """A merged batch's branch goes, unless the person chose to keep it after merging; the branches of each kind it was
    split into go in any case (eaos/journeys/fix/split.py): all of them are in it."""
    from ..fix.split import drop
    if not wave.get('keep_branch'): _git(state['project'], 'branch', '-D', wave['branch'])
    drop(state['project'], wave)


def _settle(state, wave, tidy):
    """Whether git just accepted the batch (its branch, or its last commit, is in the branch it goes into) or undid it
    (its branch is gone without that); with `tidy`, an accepted batch's branch is deleted unless the person keeps it."""
    branch, status = wave.get('branch'), wave.get('status')
    if not branch or status not in ('applied', 'superseded', 'accepted'): return False
    exists = _branch_exists(state, branch)
    last, inside = _in_target(state, wave, exists)
    if tidy and inside and exists: _drop_branch(state, wave)
    if status == 'accepted': return False
    if inside:                                          # merged into the branch EAOS works on
        wave.update(status='accepted', merged_at=now(), tip=last)
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
    save(state)         # the choices made for this merge: reconcile goes on from what is on disk
    reconcile(state)
    return 'merged'


def _merge_choices(state, wave, into, delete_after):
    """Where the batch goes and whether its branch stays, set on it and on every batch continued on its branch."""
    for each in [w for w in state.get('waves') or [] if w.get('status') == 'applied' and w.get('branch') == wave['branch']] + [wave]:
        # batches continued on one branch go in together
        if into or wave.get('merge_into'): each['merge_into'] = into or wave['merge_into']
        if not delete_after: each['keep_branch'] = True


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
    save(state)         # the choices made for this merge: reconcile goes on from what is on disk
    reconcile(state)
    return 'merged'


def choose(state, name, said=None, via=None):
    """Work on the branch `name` from now on: what this branch had (its check, run, batches) is kept aside, and what
    `name` had before comes back. A branch only on origin gets its local branch, at the same commit. The new state.
    `via` (the assistant or the interface): the person answered the branch question there,
    in the words `said`; the answer is
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
    """The first choice of a branch: work done before it was on the branch checked out then. True when that is
    `name`."""
    had = any(k in state for k in branches.KEYS)
    state['branch'] = state['home_branch'] = (branches.checked_out(project) if had else None) or name
    return state['branch'] == name
