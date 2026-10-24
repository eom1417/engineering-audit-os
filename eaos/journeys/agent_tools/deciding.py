"""The person's decision on the branch a batch handed over: accept (merged where they chose) or undo."""
from .. import guided
from ...core import branches
from ..batch_branch import commit_of
from ...core.project_state import waiting_batch
from ...core import project_state
from .project import state_of


def _merge_problem(state, wave, into):
    """Why the waiting batch cannot be merged into `into` (None: the branch the fix preview named), else None: the
    Studio's rule too (M3.3), a protected branch never."""
    if not into: return None
    if not commit_of(state['project'], into): return f'no branch named {into} to merge into'
    if into == wave['branch']: return 'a branch cannot be merged into itself'
    why = branches.blocked_target(state['project'], into)
    return f"{into} is protected ({why['en']}): choose another branch to merge into" if why else None


def accept(project=None, person_agreed=False, merge_into=None, delete_after=True):
    """The waiting branch into the branch the person chose (`merge_into`; by default the one the fix preview named, else
    the person's current branch); then its branch is deleted (unless `delete_after` is false: it stays, merged) and the
    report brought up to date, in the same call (eaos/journeys/guided.merge)."""
    from ...core.ledger import load
    state = state_of(project)
    guided.reconcile(state)
    wave = waiting_batch(state)
    if wave is None: return {'status': 'nothing_waiting', 'progress': (load(state) or {}).get('totals')}
    into = (merge_into or '').strip() or None
    if (problem := _merge_problem(state, wave, into)): return {'status': 'error', 'error': problem}
    if not person_agreed:
        return {'status': 'needs_agreement', 'ask_the_person': f"Take the fixes on {wave['branch']} into {into or wave.get('merge_into') or 'your current branch'}?",
                'what_now': 'Only if the person says yes, call accept again with person_agreed=true.'}
    outcome = guided.merge(state, wave, into=into, delete_after=delete_after is not False)
    if outcome == 'unsaved_changes': return {'status': 'unsaved_changes', 'what_now': 'The project has unsaved changes; ask the person to save (commit) them first.'}
    if outcome == 'conflict':
        return {'status': 'conflict', 'branch': wave['branch'],
                'what_now': f"The person's branch changed in the same places since the fixes; nothing was merged. Ask whether to merge "
                            f"{wave['branch']} by hand, resolving the conflict; once it is merged, `status` records it and deletes the branch."}
    state = project_state.load(state['project'])
    page = branches.home(state) / 'REPORT.html'
    deleted = not guided._branch_exists(state, wave['branch'])
    return {'status': 'accepted', 'branch': wave['branch'], 'merged_into': into or wave.get('merge_into') or state.get('branch'),
            'branch_deleted': deleted, 'progress': (load(state) or {}).get('totals'), 'report_for_people': str(page),
            'what_now': (f"Done: the branch is merged{' and deleted' if deleted else ' and kept, as the person chose'}, and the report is "
                         'up to date. Tell the person the progress in plain words (closed of total, percent), then fix_start opens '
                         'the next batch (no new check is needed).')}


def undo(project=None, person_agreed=False):
    from ..waves import undo as drop
    state = state_of(project)
    guided.reconcile(state)
    wave = waiting_batch(state)
    if wave is None: return {'status': 'nothing_to_undo'}
    if not person_agreed: return {'status': 'needs_agreement', 'ask_the_person': f"Throw away the fixes on {wave['branch']}? None of them reaches the project.",
                                  'what_now': 'Only if the person says yes, call undo again with person_agreed=true.'}
    outcome = drop(state['project'], wave['branch'])
    if outcome == 'merged': return {'status': 'merged', 'what_now': 'It is merged already; undoing it is a git revert, the person\'s decision.'}
    for each in [w for w in state.get('waves') or [] if w.get('status') == 'applied' and w.get('branch') == wave['branch']]: each['status'] = 'undone'  # every batch on it
    guided.save(state)
    guided.publish(state)
    return {'status': 'undone', 'branch': wave['branch']}
