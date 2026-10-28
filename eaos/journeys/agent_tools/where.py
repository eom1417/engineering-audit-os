"""Where the work stands: the branch EAOS works on (the person chooses it), and `status`, the next tool to call."""
from datetime import datetime, timezone

from ..fix import finish as batch_finish
from .. import guided, handover
from ...core.project import branches, jobs
from ...live.access import sign_in as signing
from ...pipeline import remedies
from ...core.project.state import waiting_batch
from .fixing import _no_safety_net
from .project import ANSWER_SECONDS, SeveralProjects, _current, _head, state_of, tool_digest
from ...core.system.clock import now


# ---------------------------------------------------------------- where things are

def _branch(state):
    """The branch EAOS works on, settled: None when it is (chosen before, or no real choice: then the branch checked
    out, without a question); else the choice to put to the person (eaos/core/project/branches.py)."""
    if state.get('branch'): return None
    current = branches.checked_out(state['project'])
    unfinished = state.get('open_wave') or waiting_batch(state) is not None
    options = None if unfinished else branches.choice(state['project'])     # work begun before: it is the checked out branch's
    if options is None:
        if current: guided.choose(state, current)
        return None
    if not (state.get('asked') or {}).get('branch'):
        state.setdefault('asked', {})['branch'] = now()
        guided.save(state)
    return {'status': 'needs_branch', 'branches': options['branches'][:15], 'recommended': options['recommended'],
            'main_branch': options['main'], 'checked_out': current,
            'ask_the_person': 'Which branch should EAOS check and fix? The check, the fixes, the progress and every merge '
                              'will follow that branch.',
            'what_now': 'Ask the person in their language, in plain words: list the branches with when each last changed and how '
                        'far each is ahead of the main branch, and say which you recommend and why (the branch where the '
                        'work goes on, usually the one furthest ahead). Then end your turn: do not call choose_branch until they answer, then call it with person_said = their reply. Their '
                        'checkout is not switched.'}


def branches_of(project=None):
    state = state_of(project)
    options = branches.choice(state['project'])
    return {'working_branch': state.get('branch'), 'checked_out': branches.checked_out(state['project']),
            'main_branch': branches.default_branch(state['project']),
            'branches': (options or {}).get('branches') or branches.inventory(state['project']),
            'recommended': (options or {}).get('recommended'),
            'with_a_report': sorted({state.get('home_branch'), *(state.get('by_branch') or {})} - {None}),
            'what_now': 'choose_branch moves the work to another branch; each branch keeps its own check, fixes and progress.'}


def choose_branch(branch, project=None, person_said=''):
    """`person_said`: the person's own words in answer to which branch (their reply, as they wrote it)."""
    state = state_of(project)
    before = state.get('branch')
    asked = (state.get('asked') or {}).get('branch')
    if branches.choice(state['project']) is not None and (why := _unanswered(asked, person_said)):
        return {'status': 'needs_the_person', 'why': why, **{k: v for k, v in (_branch({**state, 'branch': None}) or {}).items() if k != 'status'},
                'what_now': 'The person chooses the branch, not you: ask them (the branches, when each changed, how far ahead, '
                            'your recommendation and why) and end your turn. When they reply, in any words (a name, or "the one '
                            'you recommend"), call choose_branch again with the branch they meant and person_said = their reply: '
                            'it is accepted then. Nothing else is wrong with the call.'}
    state = guided.choose(state, branch, person_said, via='assistant')
    checked = guided.scan_done(state)
    return {'status': 'chosen', 'branch': branch, 'before': before, 'checked_before': checked,
            'commit': _head(state), 'report_for_people': str(branches.home(state) / 'REPORT.html'),
            'what_now': ('This branch was checked before: call status.' if checked else
                         'Call audit: the check runs on this branch (its own copy; the person\'s checkout is not switched).')}


def _unanswered(asked, person_said):
    """Why `person_said` is not yet the person's answer to the branch question asked at `asked`; None when it is."""
    if not str(person_said or '').strip(): return 'no reply from the person was given'
    since = (datetime.now(timezone.utc) - datetime.fromisoformat(asked)).total_seconds() if asked else None
    if since is not None and since >= ANSWER_SECONDS: return None
    return (f'the question was put {None if since is None else int(since)} seconds ago: nobody answers that fast, so the '
            'person has not answered yet')

def _batches(wave, retired):     # status' open and retired batches
    return {'open_batch': {k: wave.get(k) for k in ('number', 'cards', 'kept', 'failed', 'last_error', 'deliver_as', 'merge_into', 'direct', 'continues')} if wave else None, 'retired_batch': {k: retired.get(k) for k in ('number', 'why')} if retired else None}


def status(project=None):
    try: state = state_of(project)
    except SeveralProjects as several:
        return {'status': 'needs_project', 'projects': [str(p) for p in several.projects],
                'what_now': 'This folder holds several projects. Ask the person which one to work on (list them by name), '
                            'end your turn, then call status again with project = the folder they chose.'}
    asking = _branch(state)
    if asking:
        return {'project': state['project'], 'branch': None, **asking, 'next': {'tool': 'choose_branch', 'why': 'the project has '
                'more than one branch with different code: the person chooses which one EAOS works on'},
                'handover': handover.brief(state)}
    guided.reconcile(state)
    retired, head, checked = guided.retire_stale_batch(state), _head(state), guided.scan_done(state)
    waiting = waiting_batch(state)
    busy = jobs.running(state['project'])
    answer = {**_facts(state, head, checked), **_batches(state.get('open_wave'), retired),
              'waiting_branch': waiting['branch'] if waiting else None,
              'running_job': busy['id'] if busy else None}
    step = _next_step(state, head, checked, busy, waiting)
    answer['next'] = {'tool': step[0], 'why': step[1]}
    if checked: answer.update(_older_check(state))
    answer['report'] = _fresh_report(state) if checked else None
    answer['handover'] = handover.brief(state)
    return answer


def _facts(state, head, checked):
    """status' facts about the project: its commit, whether it is saved in git, checked, run and protected."""
    from ...core.project import ledger
    setup, safety = state.get('setup') or {}, state.get('safety') or {}
    return {'project': state['project'], 'branch': state.get('branch'), 'commit': head,
            'saved_in_git': not guided._git(state['project'], 'status', '--porcelain').stdout.strip(),
            'checked': checked, 'checked_commit': state.get('scanned_commit'),
            'outputs_folder': str(guided.outputs(state)), 'report_for_people': str(branches.home(state) / 'REPORT.html') if checked else None,
            'app_runs': setup.get('ok') if guided.set_up(state, head) else None,
            'safety_net': safety if guided.safety_holds(state, head) else None,
            'progress': ((ledger.load(state) or {}).get('totals') if checked else None)}


def _next_step(state, head, checked, busy, waiting):
    """(tool, why): the next tool status points to."""
    if busy: return signing.step(state, ('wait', f"a {busy['kind']} is running"))
    if not checked: return ('audit', 'the project has not been checked')
    if (pending := remedies.pending(guided.report_of(state))): return ('audit', f'again_from={pending}: a remedy EAOS knows was not tried on it yet')
    if waiting: return ('accept or undo', f"the fixes on {waiting['branch']} wait for the person's decision")
    return _batch_step(state, state.get('open_wave')) or _setup_step(state, head)


def _batch_step(state, wave):
    """The step an open batch asks for: closing it when it cannot be finished, else finishing it; None without one."""
    if not wave: return None
    if (_no_safety_net(state) or {}).get('recorded') == 0:
        return ('fix_abandon', f"batch {wave['number']} cannot be closed: the safety net recorded nothing")
    if wave.get('last_error'):
        return ('fix_abandon', f"batch {wave['number']} could not be finished ({wave['last_error'][:200]}): close it, its cards can be tried again")
    return batch_finish.open_step(wave)


def _setup_step(state, head):
    """The step before any fix: run the app, record its safety net, then open a batch."""
    setup, safety = state.get('setup') or {}, state.get('safety') or {}
    if not guided.set_up(state, head): return ('run_setup', "the app has not been run for this commit (ask the person's agreement first)")
    if not setup.get('ok'): return ('run_try', 'the app does not run yet: read the last failure and propose a fix')
    if not guided.safety_holds(state, head): return ('safety_net', 'record the screens before any fix')
    if not safety.get('passed'): return ('none', 'the safety net recorded nothing: EAOS cannot protect this project yet, so no fix starts')
    return ('fix_start', 'open the next batch of fixes')


def _fresh_report(state):
    """REPORT.html as it stands, rebuilt first when an older EAOS made it (after an update the person sees the new page at
    once, from the check on record, before any new check): {page, built, version, commit, rebuilt, errors}."""
    made = guided.report_stamp(state)
    rebuilt = made.get('digest') != tool_digest()
    if rebuilt:
        guided.publish(state)
        made = guided.report_stamp(state)
    return {'page': str(branches.home(state) / 'REPORT.html'), 'rebuilt': rebuilt,
            **{k: made.get(k) for k in ('built', 'version', 'commit', 'errors')}}


OLDER_CHECK = ('The check on record is from an earlier commit or EAOS. Go on with it; check again (audit with fresh=true) '
               'only when the person asks for a new check.')


def _older_check(state):
    """{older_check, what_now} when the check on record is not of this code by this EAOS; else {}."""
    return {} if _current(state, _head(state)) else {'older_check': True, 'what_now_about_the_check': OLDER_CHECK}
