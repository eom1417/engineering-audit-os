"""A batch of moves (M8.5, eaos/journeys/fix/move_batch.py), as an assistant runs it: the tree "today → proposed" first
(moves_propose), then the moves the person accepted, made and proved on a branch of their own (moves_make), which waits
for the person's accept or undo like any batch. Never mixed with fix cards: no batch of fixes may be open or waiting."""
from .. import guided
from ...core.project import branches, state as project_state
from ...core.project.state import waiting_batch
from .project import _head, _now, _report, _start, state_of
from .running import CONSENT, _consented


def moves_propose(project=None):
    """The moves the repository's findings and the target shape draw, as one tree, each with its reason."""
    from ..fix.move_batch import proposal
    state = state_of(project)
    drawn = proposal(_report(state), guided.source(state))
    return {**drawn, 'what_now': ('Show the person the tree (today → proposed) and the reason of each move, in plain words. '
                                  'Ask which moves they accept; then call moves_make with their ids and person_agreed=true. '
                                  'Nothing moves without their choice.' if drawn['moves'] else
                                  'Nothing to move: tell the person the layout needs no move.')}


def moves_make(project=None, moves=None, person_agreed=False):
    """Make the accepted moves (their ids from moves_propose) in an isolated copy and prove them; a job."""
    state = state_of(project)
    stop, chosen = _not_now(state) or _chosen(state, moves)
    if stop: return stop
    if not person_agreed:
        return {'status': 'needs_agreement', 'ask_the_person': f'Move {len(chosen)} file(s) on a new branch, proved to change nothing?',
                'what_now': 'Only if the person says yes, call moves_make again with person_agreed=true.'}
    return _start('moves_make', state, {'moves': [{k: m[k] for k in ('id', 'from', 'to')} for m in chosen]}, watch=True)


def _chosen(state, moves):
    """(why nothing starts, or None; the moves of the proposal the person named, each one the tool can make)."""
    from ..fix.move_batch import proposal
    drawn = {m['id']: m for m in proposal(_report(state), guided.source(state))['moves']}
    chosen = [drawn[i] for i in moves or [] if i in drawn]
    if not chosen: return {'status': 'error', 'error': 'no move of the proposal was named: call moves_propose and pass the ids the person accepted'}, []
    if (cannot := [m['id'] for m in chosen if m['refused']]):
        return {'status': 'error', 'error': f"these moves cannot be made: {', '.join(cannot)} (see `refused` in moves_propose)"}, []
    return None, chosen


def _not_now(state):
    """(why no batch of moves may start: no agreement to run the app, or a batch open or waiting; []), or None."""
    if not _consented(state): return {'status': 'needs_agreement', 'ask_the_person': CONSENT,
                                      'what_now': 'Ask the person; if they agree, call run_setup with person_agreed=true.'}, []
    if not guided.set_up(state, _head(state)): return {'status': 'not_set_up', 'what_now': 'Call run_setup first.'}, []
    if state.get('open_wave') or waiting_batch(state):
        return {'status': 'batch_waiting', 'what_now': 'A batch of fixes is open or waits for the person\'s decision: moves never mix '
                                                       'with fixes. Finish it, accept it or undo it first.'}, []
    return None


def _moves_job(project, arguments, progress):
    from ..fix.move_batch import make
    from ..fix.waves import apply as hand_over
    state = project_state.load(project)
    number = sum(1 for w in state.get('waves') or [] if w.get('kind') == 'moves') + 1
    working = state.get('branch') or branches.checked_out(state['project']) or 'HEAD'
    steps = {'before': 'the tests before the moves', 'moves': 'moving the files', 'gate': 'the move gate'}
    summary = make({'report': guided.report_of(state), 'target': guided.source(state), 'runtime': project_state.runtime_of(state),
                    'number': number, 'moves': arguments['moves'], 'deliver_as': f'eaos/{branches.slug(working)}/moves-{number}',
                    'say': lambda step: progress(list(steps).index(step), len(steps), steps[step])})
    if not summary['kept']:
        return {'batch': number, 'branch': None, 'refused': summary['refused'],
                'what_now': 'Tell the person, plainly, that the moves were refused as a whole and why (refused): nothing reached their project.'}
    hand_over(state['project'], summary)
    state = project_state.load(project)
    state.setdefault('waves', []).append({
        'number': len(state.get('waves') or []) + 1, 'kind': 'moves', 'cards': [], 'kept': summary['kept'], 'failed': {},
        'moves': summary['moves'], 'base': summary['base'], 'branch': summary['branch'], 'stat': summary['stat'], 'status': 'applied',
        'opened': _now(), 'merge_into': working, 'base_branch': working,
        'tip': guided._git(state['project'], 'rev-parse', summary['branch']).stdout.strip()})
    guided.save(state)
    return {'batch': number, 'branch': summary['branch'], 'moved': summary['kept'], 'changes': summary['stat'],
            'what_now': (f"Tell the person the moves passed the move gate (the same public surface, every test back with its name "
                         f"and result, the build and every screen) and wait on the branch {summary['branch']}; their current branch "
                         'is unchanged. Ask whether to take it in (accept) or throw it away (undo).')}
