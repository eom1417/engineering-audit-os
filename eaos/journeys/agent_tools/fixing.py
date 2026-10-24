"""A batch of fixes: opened on the cards chosen (fix_start), the assistant's reads and edits checked as they come
(fix_read, fix_edit, fix_skip), and closed (fix_finish, fix_abandon).
"""
import subprocess
from pathlib import Path

from .. import batch_finish, guided, lanes
from ...core import branches, jobs
from ..batch_branch import commit_of, direct_target, merge_target
from ...core.project_state import waiting_batch
from ...live import setup as live_setup
from ...core import project_state
from .evidence import _ready
from .project import WAIT, _head, _now, _read, _report, _start, state_of
from .running import CONSENT, _consented


# ---------------------------------------------------------------- fixing

def _open(state):
    wave = state.get('open_wave')
    if not wave: raise LookupError('no batch is open: call fix_start first')
    return wave


def _brief(card):
    return {'id': card['id'], 'title': card.get('title'), 'kind': card.get('pattern'), 'paths': card.get('paths'),
            'before': card.get('before'), 'after': card.get('after'), 'impact': card.get('impact')}


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
    if name == working: return direct_target(project, name)
    continued = waiting_on(state, name)
    if guided._branch_exists(state, name) and not continued:
        raise ValueError(f'a branch named {name} already exists and is not an EAOS work branch waiting for a decision: choose another name')
    return name, merge_target(state, merge_into, continued)


def fix_start(project=None, cards=None, size=10, base=None, deliver_as=None, merge_into=None, base_commit=None, assistants=1):
    """Open the next batch. As the fix preview set it: `base`, the branch to build on (by default the branch EAOS works
    on; another one becomes the branch EAOS works on, as choose_branch does); `deliver_as`, the new branch the fixes
    arrive on (default `eaos/<branch>/wave-N`), or an EAOS work branch waiting for a decision (the batch continues on
    it), or the base branch itself (direct: the batch lands on it once it passes, no branch is left); `merge_into`, the branch accept merges them into (default the branch
    open in the project folder); `base_commit`, the commit the preview showed for `base`: when the branch moved since,
    nothing opens (status base_moved) and the preview is made again. `assistants`: how many fix it at once (eaos/journeys/lanes.py)."""
    state = state_of(project)
    guided.reconcile(state)
    guided.retire_stale_batch(state)
    if state.get('open_wave'): return _still_open(state['open_wave'])
    stop, state = _on_base(state, base, base_commit)
    if stop: return stop
    try: deliver_as, merge_into = delivery(state, deliver_as, merge_into)
    except ValueError as problem: return {'status': 'error', 'error': str(problem)}
    stop = _not_ready(state, deliver_as)
    if stop: return stop
    stop, chosen = _chosen(state, cards, size)
    return stop or _start('fix_start', state, {'cards': chosen, 'deliver_as': deliver_as, 'merge_into': merge_into, 'assistants': assistants}, watch=True)


def _still_open(wave):
    return {'status': 'open', 'batch': wave['number'], 'kept': list(wave['kept']), 'failed': wave['failed'],
            'to_do': [c for c in wave['cards'] if c not in wave['kept'] and c not in wave['failed']],
            'what_now': 'This batch is already open: fix the cards left with fix_edit (or fix_skip), then fix_finish.'}


def _on_base(state, base, base_commit):
    """(why nothing opens, or None; the state on `base`): the branch named, still at the commit the preview showed."""
    working = state.get('branch') or branches.checked_out(state['project'])
    base = (base or '').strip() or working
    now = commit_of(state['project'], base) if base else _head(state)
    if base and not now: return {'status': 'error', 'error': f'no branch named {base} in this project'}, state
    if base_commit and not (now or '').startswith(str(base_commit).strip()):
        return {'status': 'base_moved', 'branch': base, 'expected': base_commit, 'now': now,
                'what_now': f'The branch {base} moved since the preview (it was at {str(base_commit)[:12]}, it is at {(now or "")[:12]} '
                            'now): nothing was opened. Show the preview again, so the person confirms the batch on the code as it is.'}, state
    if base and base != working:
        try: state = guided.choose(state, base)
        except ValueError as problem: return {'status': 'error', 'error': str(problem)}, state
    return None, state


def _not_ready(state, deliver_as):
    """Why no batch may open yet: no agreement, no run, no safety net, or fixes waiting for a decision elsewhere."""
    if not _consented(state): return {'status': 'needs_agreement', 'ask_the_person': CONSENT,
                                      'what_now': 'Ask the person; if they agree, call run_setup with person_agreed=true.'}
    if not guided.set_up(state, _head(state)): return {'status': 'not_set_up', 'what_now': 'Call run_setup first.'}
    if unsafe := _no_safety_net(state): return unsafe
    waiting = waiting_batch(state)
    if waiting and waiting['branch'] != deliver_as:
        return {'status': 'waiting_decision', 'branch': waiting['branch'],
                'what_now': f"The fixes on {waiting['branch']} wait for the person's decision: ask them, then accept or undo; "
                            f"or, if they want this batch on the same branch, call fix_start again with deliver_as={waiting['branch']}."}
    return None


def _chosen(state, cards, size):
    """(why nothing opens, or None; the batch's cards): those asked for, else the next ready ones."""
    from ..waves import next_batch, plan as read_plan, too_early, with_prerequisites
    report = _report(state)
    known = {t['id']: t for t in read_plan(report)['tasks']}
    chosen = with_prerequisites(report, state, list(dict.fromkeys(cards))) if cards else next_batch(report, state, size=min(max(int(size), 1), 25))
    unknown = [c for c in chosen if c not in known]
    if unknown: raise ValueError(f'not cards of this plan: {", ".join(unknown[:5])}')
    undecided = [c for c in chosen if not _ready(known[c])]
    if undecided:
        return {'error': f'{", ".join(undecided[:5])} need(s) a decision by the person before any fix (not ready): no batch '
                         'was opened', 'needs_decision': undecided,
                'what_now': 'Explain the decision each card needs (see `finding`), plainly, and leave it out of the batch; '
                            'call fix_start again with ready cards only, or with no cards for the next ready batch.'}, chosen
    if early := too_early(state, [known[c] for c in chosen]): return early, chosen
    if not chosen: return {'status': 'nothing_to_fix', 'what_now': 'No fixable card is left; the rest need the person\'s decision (see plan).'}, chosen
    return None, chosen


def _no_safety_net(state):
    """Why no batch may open (the safety net is missing or recorded nothing: fix_finish would refuse every change); None."""
    safety = state.get('safety') or {}
    if not guided.safety_holds(state, _head(state)):
        return {'status': 'no_safety_net', 'what_now': 'Call safety_net first: it records what the program does today.'}
    if safety.get('passed'): return None
    why = '; '.join(f"{row.get('path') or 'the app'}: {row.get('reason') or row.get('status')}" for row in (safety.get('skipped') or [])[:3]) or 'the lock has no page: the code names none and the running app could not be crawled (did it start and answer?)'
    return {'status': 'no_safety_net', 'recorded': 0, 'specs': safety.get('screens', 0), 'why': why,
            'what_now': 'The safety net recorded nothing, so no fix could be checked: no batch was opened. Tell the person '
                        'plainly that EAOS cannot protect this project yet and why (why); do not retry the fixes.'}


def fix_abandon(project=None):
    """Close the open batch without handing anything over: its copy is removed and its cards can be picked again."""
    state = state_of(project)
    if stop := lanes.not_yours(state): return stop
    wave = _open(state)
    guided.close_batch(state, 'abandoned', wave.get('last_error') or '')
    return {'status': 'abandoned', 'batch': wave['number'], 'cards': wave['cards'],
            'what_now': 'Tell the person the batch was closed and nothing in their project changed.'}


def _fix_start_job(project, arguments, progress):
    from ..waves import change, commit, drop_last, open_batch, plan as read_plan
    from ..execute import new_breakage
    from ...live.sandbox import head
    state = project_state.load(project)
    report, runtime = guided.report_of(state), project_state.runtime_of(state)
    number = len(state.get('waves') or []) + 1
    grant = runtime / 'authorization.json'
    granted = _read(grant).get('commit') if grant.is_file() else None
    source = guided.source(state)
    if granted != head(source) and guided.same_code(state, granted):     # a merged batch: the agreement still holds
        live_setup.authorize(source, runtime, _read(grant).get('granted_by') or 'the owner')
    progress(0, 1, 'copying the project into the isolated copy')
    root, base = open_batch(source, runtime, number)
    cards = {t['id']: t for t in read_plan(report)['tasks'] if t['id'] in set(arguments['cards'])}
    wave = {'number': number, 'root': str(root), 'base': base, 'cards': arguments['cards'], 'kept': {}, 'failed': {}, 'tools': {},
            'opened': _now(), 'keys': {c: cards[c]['key'] for c in arguments['cards']},
            'base_branch': state.get('branch') or branches.checked_out(state['project']),
            'deliver_as': arguments.get('deliver_as'), 'merge_into': arguments.get('merge_into')}
    if not wave['deliver_as']: wave['deliver_as'], wave['merge_into'] = delivery(state, None, wave['merge_into'])
    if wave['deliver_as'] == wave['base_branch']:
        # direct: the batch is still built and checked here, handed over on a branch of its own and merged into the base
        # branch at once by fix_finish, which deletes that branch
        wave.update(direct=True, merge_into=wave['base_branch'], deliver_as=delivery(state, None, wave['base_branch'])[0])
    elif waiting_on(state, wave['deliver_as']):
        # continue on an EAOS work branch waiting for a decision: the copy starts from its tip, the kept commits go on top
        tip = commit_of(state['project'], wave['deliver_as'])
        fetched = guided._git(root, 'fetch', '--quiet', str(state['project']), f"+refs/heads/{wave['deliver_as']}:refs/eaos/continued")
        if fetched.returncode or guided._git(root, 'reset', '--hard', '--quiet', tip).returncode:
            raise RuntimeError(f"could not start from {wave['deliver_as']}: {fetched.stderr[-300:]}")
        wave.update(base=tip, source_commit=base, continues=wave['deliver_as'])
    automatic = [c for c in arguments['cards'] if ((cards[c].get('codemod') or {}).get('dry_run') or {}).get('files_changed', 0) > 0]
    for index, card_id in enumerate(automatic, 1):
        progress(index, len(automatic) + 1, f'automatic fix of {card_id}')
        try:
            tool, _ = change(cards[card_id], root, report)
            sha = commit(root, cards[card_id], tool)
            broke = new_breakage(report, root)
            if broke:
                drop_last(root)
                wave['failed'][card_id] = f'its automatic fix broke something: {broke[0]}'
                continue
            wave['kept'][card_id], wave['tools'][card_id] = sha, tool
        except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as problem:
            guided._git(root, 'reset', '--hard', '--quiet', 'HEAD')
            guided._git(root, 'clean', '-fdq')
            wave['failed'][card_id] = f'{type(problem).__name__}: {problem}'[:300]
    helpers = lanes.open_lanes(wave, cards, arguments.get('assistants'))
    state = project_state.load(project)
    state['open_wave'] = wave
    guided.save(state)
    guided.publish(state)
    return {'batch': number, 'copy': str(root), 'fixed_automatically': list(wave['kept']), 'failed': wave['failed'],
            'to_do': [_brief(cards[c]) for c in lanes.mine(wave, lanes.untried(wave, arguments['cards']))],
            'what_now': 'For each card in to_do: read it with `finding`, read the code with fix_read, then send the change with '
                        'fix_edit. Keep every feature, route and behaviour. When every card is kept or skipped, call fix_finish.',
            **lanes.told(helpers)}


def _inside(root, relative):
    path = (Path(root) / relative).resolve()
    if Path(root).resolve() not in path.parents or '.git' in path.relative_to(Path(root).resolve()).parts:
        raise ValueError(f'{relative}: not a file of the project')
    return path


def fix_read(path, project=None, start=1, end=None):
    state = state_of(project)
    root = _open(state)['root']
    file = _inside(root, path)
    if file.is_dir():
        return {'folder': path, 'entries': sorted(p.name + ('/' if p.is_dir() else '') for p in file.iterdir())[:500]}
    if not file.is_file(): raise ValueError(f'{path} does not exist in the copy')
    lines = file.read_text(encoding='utf-8', errors='replace').splitlines()
    start = max(int(start or 1), 1)
    end = min(int(end or len(lines)), len(lines), start + 1999)
    return {'path': path, 'lines': len(lines), 'from_line': start, 'to_line': end,
            'text': '\n'.join(f'{n:>5}  {lines[n - 1]}' for n in range(start, end + 1))}


def _kept(path):
    """A file's text with its own line ends: read as text, a Windows file came back with \\n, and the edit wrote every
    line of it back changed."""
    with path.open(encoding='utf-8', newline='') as file: return file.read()


def _line_ends(text, find, replace):
    """`find` and `replace` with the file's own line ends: fix_read shows a Windows file's lines without their \\r, and
    the text an assistant copies from them has none."""
    if '\r\n' in text and '\r\n' not in find and find.replace('\n', '\r\n') in text:
        return find.replace('\n', '\r\n'), replace.replace('\r\n', '\n').replace('\n', '\r\n')
    return find, replace


def _not_once(relative, times):
    """Why an edit was refused, and what to do: read the lines again, they are not what the edit remembers."""
    if not times:
        return (f'{relative}: the text to find is not in the file as it is now: read those lines again with fix_read (an '
                'earlier edit, or a change taken back, may have changed them) and copy `find` from them, without the line numbers')
    return f'{relative}: the text to find occurs {times} times, not once: take more lines around it so it is found once'


def _apply(root, edits):
    """Each edit: {path, find, replace} (find occurs exactly once), {path, content} (the whole file, new or not),
    or {path, delete: true}. All or nothing."""
    staged = {}
    for edit in edits:
        path = _inside(root, edit.get('path') or '')
        relative = edit['path']
        if edit.get('delete'): staged[relative] = None; continue
        if 'content' in edit:
            if not isinstance(edit['content'], str): raise ValueError(f'{relative}: content must be text')
            staged[relative] = edit['content']; continue
        text = staged.get(relative) if relative in staged else (_kept(path) if path.is_file() else None)
        if text is None: raise ValueError(f'{relative}: does not exist; send its whole content instead')
        find, replace = edit.get('find'), edit.get('replace')
        if not isinstance(find, str) or not isinstance(replace, str) or not find:
            raise ValueError(f'{relative}: an edit needs `find` and `replace`, or `content`, or `delete`')
        find, replace = _line_ends(text, find, replace)
        if text.count(find) != 1: raise ValueError(_not_once(relative, text.count(find)))
        staged[relative] = text.replace(find, replace, 1)
    for relative, text in staged.items():
        path = _inside(root, relative)
        if text is None:
            if path.is_file(): path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', encoding='utf-8', newline='') as out: out.write(text)
    return sorted(staged)


def fix_edit(card, edits, summary='', project=None):
    state = state_of(project)
    wave = _open(state)
    if card == batch_finish.REPAIR and not wave.get('gates_failed'): raise ValueError('no repair is asked: fix_finish asks for one when needed')
    if card != batch_finish.REPAIR and card not in wave['cards']: raise ValueError(f"{card} is not in batch {wave['number']}: {', '.join(wave['cards'])}")
    if card in wave['kept']: return {'status': 'already_kept', 'what_now': 'This card is already fixed in the batch.'}
    if not edits: raise ValueError('no edit was sent')
    return lanes.take(state['project'], card, edits) or _start('fix_edit', state, {'card': card, 'edits': edits, 'summary': summary})


def _fix_edit_job(project, arguments, progress):
    from ..waves import commit, drop_last, edit_gates, plan as read_plan
    state = project_state.load(project)
    wave, report = state['open_wave'], guided.report_of(state)
    root, card_id = Path(wave['root']), arguments['card']
    repair = card_id == batch_finish.REPAIR
    card = batch_finish.repair_card(wave) if repair else next(t for t in read_plan(report)['tasks'] if t['id'] == card_id)
    try:
        changed = _apply(root, arguments['edits'])
        commit(root, card, 'assistant')
    except (ValueError, RuntimeError, OSError, UnicodeDecodeError) as problem:
        guided._git(root, 'checkout', '--quiet', '--', '.')
        guided._git(root, 'clean', '-fdq')
        return {'card': card_id, 'kept': False, 'why': f'the edit could not be applied: {problem}',
                'what_now': 'Nothing changed. Read the file again with fix_read and send a corrected edit.'}
    progress(0, 1, 'checking the change: the problem is gone, nothing broke, no endpoint disappeared')
    broke, exit_code, still = edit_gates((report, guided.source(state), project_state.runtime_of(state)), root, card, changed, repair)
    diff = guided._git(root, 'show', '--stat', '--format=', 'HEAD').stdout.strip()
    if broke or exit_code not in (0, None):
        drop_last(root)
        why = (f'it broke something or broke the code laws: {"; ".join(broke[:3])}' if broke else
               "the problem is still there: the card's own check still finds it" + (f': {still}' if still else f' (exit {exit_code})'))
        return {'card': card_id, 'kept': False, 'why': why, 'files': changed,
                'what_now': 'The change was taken back. Fix the cause and send fix_edit again, or fix_skip with the reason.'}
    if repair: return batch_finish.repaired(project_state.load(project), root, changed, diff)
    with lanes.changing(project) as state:
        wave = state['open_wave']
        wave['kept'][card_id] = guided._git(root, 'rev-parse', 'HEAD').stdout.strip()
        wave['tools'][card_id] = 'assistant'
        wave['failed'].pop(card_id, None)
        wave.setdefault('summaries', {})[card_id] = arguments.get('summary') or ''
    left = lanes.mine(wave, lanes.untried(wave, wave['cards']))
    return {'card': card_id, 'kept': True, 'files': changed, 'diff': diff, 'left': left, 'what_now': lanes.next_step(wave, left)}


def fix_skip(card, reason, project=None):
    project = state_of(project)['project']
    with jobs.alone(project, WAIT), lanes.changing(project) as state:      # no change is checked while its copy is rebuilt
        wave = _open(state)
        if card not in wave['cards']: raise ValueError(f"{card} is not in batch {wave['number']}")
        if card in wave['kept']:
            from ..waves import without
            without(wave, card)
        wave['failed'][card] = f'skipped: {reason}'[:300]
    return {'card': card, 'skipped': True, 'left': lanes.mine(wave, lanes.untried(wave, wave['cards']))}


def fix_finish(project=None, leave_out=False):
    """Hand the batch over. When its changes pass one by one but fail the project's checks together, the answer asks
    for a repair on top of them (fix_edit with card REPAIR) instead of leaving sound cards out; `leave_out`, or after
    REPAIRS repairs, the cards responsible are found and left out."""
    state = state_of(project)
    if stop := lanes.not_yours(state) or lanes.finish_wait(state['project']): return stop
    wave = _open(state_of(project))
    left = [c for c in wave['cards'] if c not in wave['kept'] and c not in wave['failed']]
    if left: return {'status': 'cards_left', 'left': left, 'what_now': 'Fix them with fix_edit or skip them with fix_skip first.'}
    return _start('fix_finish', state, {'leave_out': bool(leave_out)})
