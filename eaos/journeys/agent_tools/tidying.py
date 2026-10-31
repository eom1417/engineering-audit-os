"""The batches of their own an assistant runs, never mixed with fix cards (no batch of fixes may be open or waiting):

    moves_propose, moves_make       the layout (M8.5, eaos/journeys/fix/move_batch.py): the tree "today → proposed"
                                    first, then the moves the person accepted, made and proved
    context_propose, context_make   the assistants' context (M8.6, eaos/journeys/fix/context_batch.py): what the trim
                                    would do first, then the trim, every instruction kept

Each kept batch waits on a branch of its own for the person's accept or undo, like any batch."""
from .. import guided
from ...core.project import branches, state as project_state
from ...core.project.state import waiting_batch
from .project import _head, _report, _start, state_of
from .running import CONSENT, _consented
from ...core.system.clock import now

SAID = {'moves': ('the moves passed the move gate (the same public surface, every test back with its name and result, the '
                  'build and every screen)'),
        'context': 'the context is lighter and every instruction is still said once (the done items kept in the archive)'}


def moves_propose(project=None):
    """The moves the repository's findings and the target shape draw, as one tree, each with its reason."""
    from ..fix.move_batch import proposal
    state = state_of(project)
    drawn = proposal(_report(state), guided.source(state))
    return {**drawn, 'what_now': ('Show the person the tree (today → proposed) and the reason of each move, in plain words, '
                                  'and what `limits` says. '
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


def context_propose(project=None, private_to=None):
    """What a trim of the assistants' context would do, and the tokens every session would save; nothing written."""
    from ..fix.context_batch import proposal
    state = state_of(project)
    drawn = proposal(guided.source(state), private_to, guided.report_of(state))
    return {**drawn, 'what_now': ('Tell the person, plainly, what the trim does (the done items it archives, the lines said twice it '
                                  'keeps once, the paths it fixes) and the tokens saved, and the extension guide it writes (`guide`: '
                                  'its file and recipes, with one line in the context files pointing at it). Lines in `personal` are their own ways: ask '
                                  'whether to move them to a private file they name (private_to). Then context_make with '
                                  'person_agreed=true.')}


def context_make(project=None, private_to=None, person_agreed=False):
    """Trim the context in an isolated copy, every instruction kept; a job."""
    state = state_of(project)
    stop = _not_now(state)
    if stop: return stop[0]
    if not person_agreed:
        return {'status': 'needs_agreement', 'ask_the_person': "Trim the assistants' context and write the project's extension guide on a new branch, every instruction kept?",
                'what_now': 'Only if the person says yes, call context_make again with person_agreed=true.'}
    return _start('context_make', state, {'private_to': private_to}, watch=True)


def design_propose(project=None, agreed=None):
    """What a batch of the look would do: raw values named as tokens, nothing written; `agreed`, values the person agreed to merge."""
    from ..fix.tokens_batch import proposal
    state = state_of(project)
    drawn = proposal(guided.source(state), agreed, guided.report_of(state))
    return {**drawn, 'what_now': ('Tell the person, plainly: how many values, in how many files, where the one tokens file goes; no assistant is asked and nothing '
                                  'may look different, which EAOS proves element by element. `you_can_agree` are near colours and sizes off the scale: show each with how '
                                  'often it is used; only those they accept go in `agreed`, and only those may change. Then design_make with person_agreed=true.')}


def design_make(project=None, agreed=None, person_agreed=False):
    """Name the look's values in an isolated copy, kept only when proved; a job."""
    state = state_of(project)
    stop = _not_now(state)
    if stop: return stop[0]
    if not person_agreed:
        return {'status': 'needs_agreement', 'ask_the_person': "Name your look's values as tokens on a new branch? It is proved that nothing looks different" + (
                ', but for the merges you agreed to.' if agreed else '.'),
                'what_now': 'Only if the person says yes, call design_make again with person_agreed=true.'}
    return _start('design_make', state, {'agreed': agreed or []}, watch=True)


def _design_job(project, arguments, progress):
    from ..fix.tokens_batch import make
    progress(0, 1, "naming the look's values")
    return _own_batch(project, 'design', lambda state, batch: make({**batch, 'agreed': arguments.get('agreed'), 'report': guided.report_of(state)}))


def project_map(project=None, person_agreed=False):
    """GitNexus's area skills and MCP for the project's assistant, only with the person's yes: its index in the project's
    run folder, its skills in .claude/skills, which this repository alone stops git from taking (.git/info/exclude)."""
    if not person_agreed:
        return {'status': 'needs_agreement', 'ask_the_person': 'Build a map of this project for your assistant (about a minute, no tokens; '
                'its index stays outside the project, its short skills in .claude/skills, which git will not take) and register its tools? The licence of GitNexus allows no commercial use: say no for a commercial project; its guide does not need the map.',
                'what_now': 'Only if the person says yes, call project_map again with person_agreed=true.'}
    from ...analysis.repair import project_guide
    state = state_of(project)
    made = project_guide.give_map(state['project'], project_state.runtime_of(state) / 'map')
    return {**made, 'what_now': 'Tell the person the map is built and how to refresh it (this tool again); read a gitnexus-area skill before changing that area.'}


def _chosen(state, moves):
    """(why nothing starts, or None; the moves of the proposal the person named, each one the tool can make)."""
    from ..fix.move_batch import proposal
    drawn = {m['id']: m for m in proposal(_report(state), guided.source(state))['moves']}
    named = list(moves or [])
    chosen = [drawn[i] for i in named if i in drawn]
    return _not_chosen(named, drawn, chosen), chosen


def _not_chosen(named, drawn, chosen):
    """Why the moves named cannot start: an id no longer proposed (an id names its two places, never another move),
    none named, or one the tool cannot make; else None."""
    if (gone := [i for i in named if i not in drawn]):
        return {'status': 'error', 'error': f"no longer proposed: {', '.join(gone[:5])}; call moves_propose again"}
    if not chosen: return {'status': 'error', 'error': 'no move of the proposal was named: call moves_propose and pass the ids the person accepted'}
    if (cannot := [m['id'] for m in chosen if m['refused']]):
        return {'status': 'error', 'error': f"these moves cannot be made: {', '.join(cannot)} (see `refused` in moves_propose)"}
    return None


def _not_now(state):
    """(why no batch of its own may start: no agreement to run the app, or a batch open or waiting; []), or None."""
    if not _consented(state): return {'status': 'needs_agreement', 'ask_the_person': CONSENT,
                                      'what_now': 'Ask the person; if they agree, call run_setup with person_agreed=true.'}, []
    if not guided.set_up(state, _head(state)): return {'status': 'not_set_up', 'what_now': 'Call run_setup first.'}, []
    if state.get('open_wave') or waiting_batch(state):
        return {'status': 'batch_waiting', 'what_now': 'A batch is open or waits for the person\'s decision: a batch of moves or of the '
                                                       'context never mixes with another. Finish it, accept it or undo it first.'}, []
    return None


def _moves_job(project, arguments, progress):
    from ..fix.move_batch import make
    steps = {'before': 'the tests before the moves', 'moves': 'moving the files', 'gate': 'the move gate'}
    return _own_batch(project, 'moves', lambda state, batch: make({
        **batch, 'report': guided.report_of(state), 'moves': arguments['moves'],
        'say': lambda step: progress(list(steps).index(step), len(steps), steps[step])}))


def _context_job(project, arguments, progress):
    from ..fix.context_batch import make
    progress(0, 1, "trimming the assistants' context")
    return _own_batch(project, 'context', lambda state, batch: make({**batch, 'private_to': arguments.get('private_to'),
                                                                  'report': guided.report_of(state), 'project': state['project']}))


def _own_batch(project, kind, made):
    """A batch of its own made by `made(state, batch)`, then handed over as a branch waiting for the person's decision."""
    from ..fix.waves import apply as hand_over
    state = project_state.load(project)
    number = sum(1 for w in state.get('waves') or [] if w.get('kind') == kind) + 1
    working = state.get('branch') or branches.checked_out(state['project']) or 'HEAD'
    summary = made(state, {'target': guided.source(state), 'runtime': project_state.runtime_of(state), 'number': number,
                           'deliver_as': f'eaos/{branches.slug(working)}/{kind}-{number}'})
    if not summary['kept']:
        return {'batch': number, 'branch': None, 'refused': summary['refused'],
                'what_now': 'Tell the person, plainly, that the batch was refused as a whole and why (refused): nothing reached their project.'}
    hand_over(state['project'], summary)
    state = project_state.load(project)
    state.setdefault('waves', []).append({
        'number': len(state.get('waves') or []) + 1, 'kind': kind, 'cards': [], 'kept': summary['kept'], 'failed': {},
        'items': summary['items'], 'base': summary['base'], 'branch': summary['branch'], 'stat': summary['stat'], 'status': 'applied',
        'opened': now(), 'merge_into': working, 'base_branch': working,
        'tip': guided._git(state['project'], 'rev-parse', summary['branch']).stdout.strip()})
    guided.save(state)
    return {'batch': number, 'branch': summary['branch'], 'kept': summary['kept'], 'changes': summary['stat'],
            'what_now': (f"Tell the person {SAID[kind]}, and that it waits on the branch {summary['branch']}; their current branch is "
                         'unchanged. Ask whether to take it in (accept) or throw it away (undo).')}
