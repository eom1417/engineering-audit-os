"""What an AI assistant does EAOS with (docs/MCP.md): the tools behind eaos/interfaces/mcp_server.py.

The assistant is the one who thinks: it reads the evidence, reads the code, proposes how the app runs, writes
the fixes. EAOS gives it the evidence, the isolated copy and the gates, and never calls a model itself here.
Every tool returns a plain dict; one that takes longer than a tool call waits returns a job (eaos/core/jobs.py) that
`wait` follows. The person's project is only ever written through git: a branch `eaos/<branch>/wave-N`, fetched in.

State is the guided commands' own (~/.eaos/projects/<name>-<hash>/state.json), so the two ways meet: a check
started with `eaos start` is the one `overview` reads, and the other way round.
"""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import batch_finish, check_choices, guided, handover, lanes
from ..core import branches, jobs, launch, plain, toolchain
from ..live import sign_in as signing
from ..ai.readiness import NoAssistant
from ..pipeline import remedies
from .batch_branch import commit_of, direct_target, merge_target, waiting_batch
from ..analysis.finish_line import proof
from ..ai import readiness
from ..live import assist as live_assist, run_profile, setup as live_setup
from ..core import project_state

# A person's answer comes at least this long after the question: sooner, nobody was asked (EAOS_ANSWER_SECONDS: tests).
ANSWER_SECONDS, WAIT = int(os.environ.get('EAOS_ANSWER_SECONDS') or 30), 50   # WAIT: seconds a tool call waits for its job
PAGE, EVIDENCE = 30, 24     # EVIDENCE: facts shown behind one card, enough for every function its check judges


# ---------------------------------------------------------------- the project and its state

class SeveralProjects(ValueError):
    """A folder that is no project but holds several git repositories directly under it: the person says which."""
    def __init__(self, folder, projects):
        super().__init__(f'{folder} holds several projects: {", ".join(str(p) for p in projects[:10])}; pass one as `project`')
        self.projects = projects


def repositories_under(folder):
    """The git repositories directly under `folder` (one level down), sorted."""
    try: return sorted(child for child in Path(folder).iterdir() if child.is_dir() and (child / '.git').exists())
    except OSError: return []


def locate(folder):
    """The project a folder means: itself when it is one (eaos/journeys/project_state.looks_like_project); a folder with no project file
    and exactly one git repository directly under it (the assistant opened in the folder above) means that repository; with several, SeveralProjects: the
    person chooses, EAOS never guesses."""
    if not folder.is_dir() or project_state.looks_like_project(folder): return folder
    found = repositories_under(folder)
    if len(found) > 1: raise SeveralProjects(folder, found)
    return found[0] if found else folder


def _project_folder(project, new):
    """The project's folder, checked: made when it is to be built, else it must exist and look like a project."""
    folder = Path(project or os.getcwd()).expanduser().resolve()
    if not new and not (project_state.load(folder) if folder.is_dir() else None): folder = locate(folder)
    state = project_state.load(folder) if folder.is_dir() else None
    if new or (state or {}).get('mode') == 'build':
        if folder in (Path.home().resolve(), Path(folder.anchor)):
            raise ValueError(f'not a project folder: {folder} (make an empty folder for the new project and open the assistant there)')
        folder.mkdir(parents=True, exist_ok=True)
        return folder
    if not folder.is_dir(): raise ValueError(f'project folder not found: {folder}')
    if not project_state.looks_like_project(folder):
        raise ValueError(f'not a project folder: {folder} (no .git, package.json or other project file at its top; '
                         'pass the project folder as `project`)')
    return folder


def state_of(project=None, new=False):
    """The project's state, made on first use. `new`: a project still to be built from its plan, whose folder may be
    empty or not there yet (it is made); never the home folder or the disk's root."""
    folder = _project_folder(project, new)
    state = project_state.load(folder)
    if not state:
        state = {'schema_version': 1, 'project': str(folder), 'workspace': str(guided.workspace(folder)),
                 'started': _now(), 'questions': [], 'lang': guided.language()}
    # its report's folder kept from the start: a run of its app is shown only that folder (eaos/live/sandbox.py _own)
    if not state.get('outputs') and guided.outputs(state): guided.save(state)
    return state


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _head(state):
    """The last commit of the branch EAOS works on (eaos/core/branches.py)."""
    return guided.tip(state)


def tool_digest():
    """This EAOS's own code, as a fingerprint (eaos/core/build_info.py): a report made by an older EAOS is checked again."""
    from ..core.build_info import digest
    return digest()


def _current(state, head):
    """The check on record is for this code (this commit, or it plus EAOS's own merged fixes), by this EAOS."""
    return guided.same_code(state, state.get('scanned_commit'), head) and state.get('scanned_with') == tool_digest()


def _set_up(state, head):
    return guided.same_code(state, (state.get('setup') or {}).get('commit'), head)


def _report(state):
    report = guided.report_of(state)
    if not (report / 'plan.json').is_file():
        raise LookupError('this project has not been checked yet: call `audit` first')
    return report


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _job_answer(job, seconds, project):
    """A job's record as a tool answers it: the result when it ended in time, else how to follow it."""
    record = jobs.wait(job, seconds, project)
    if record['status'] == 'done': return {'job': job, 'status': 'done', **(record['result'] or {})}
    if record['status'] == 'failed':
        return {'job': job, 'status': 'failed', 'error': record['error'], 'log': record['log'],
                'what_now': guided.explain(RuntimeError(record['error']))['en']['fix']}
    return {'job': job, 'status': 'running', 'progress': record['progress'], 'started': record['started'],
            'what_now': f'Call `wait` with job="{job}" to follow it; keep going until it is done.'}


def _start(kind, state, arguments, seconds=WAIT, runner='eaos.journeys.agent_tools', watch=False):
    """Start a job once the project's running one ended (waited for up to `seconds`: eaos/journeys/lanes.py), and answer as `_job_answer`
    does. `watch`: the live Studio is opened on its map first (once, before the job writes anything), its address in `watch`."""
    route = '/scan' if kind != 'audit' or toolchain.ready(state['project']) else '/tools'
    studio = _watch(state, route) if watch and not jobs.running(state['project']) else None
    try:
        with jobs.alone(state['project'], seconds): job = jobs.start(kind, state['project'], arguments, runner=runner)
    except jobs.Busy as busy:
        return {'job': busy.record['id'], 'status': 'busy', 'kind': busy.record['kind'], 'progress': busy.record['progress'],
                'what_now': f"Another piece of work is running for this project: call `wait` with job=\"{busy.record['id']}\" first."}
    answer = _job_answer(job, seconds, state['project'])
    if studio and route == '/tools':
        answer.update(watch=studio['studio'], what_now=TOOLS_FIRST)
    elif studio:
        told = ('Tell the person the live map of this work is open in their browser.' if studio['opened_in_browser'] else
                'Before anything else, write the person a message with the `watch` address, the live map of this work, which '
                'still shows how it went once it ends and stays the same every time (it opens on this computer only).')
        answer.update(watch=studio['studio'], what_now=f"{told} {answer.get('what_now', '')}".strip())
    return answer


TOOLS_FIRST = ('Tell the person the EAOS Studio is open on "Preparing the tools" (give them the `watch` address if it did not '
               'open in their browser): every tool it installs, live; the check starts by itself once the tools it needs '
               'are ready. Then call `wait` with the job to follow it. If it fails because a tool could not be installed, '
               'the person picks Retry or "Start without it" there, or tells you, and you call `tools_check` with '
               'retry=true, or `audit` with without_tools=true.')


def _watch(state, route='/scan'):
    """open_studio on `route`, in the browser unless the Studio asked (EAOS_STUDIO_RUN); None headless or when it cannot start."""
    try: opened = {} if os.environ.get(launch.HEADLESS) else open_studio(state['project'], show=not os.environ.get('EAOS_STUDIO_RUN'), route=route)
    except Exception: return None
    return opened if 'studio' in opened else None


def open_studio(project=None, show=True, route='', address=None):
    """`open_studio`: the live Studio's address (on `route`, when given), starting its server in the background when it
    is not running. The server runs from the EAOS workspace folder with PYTHONSAFEPATH=1, so neither the folder it
    starts in nor the project (which may be EAOS's own repository) can put another `eaos` before this one. It rebuilds
    no data: a server it starts does (run_foreground), and a running one's is kept by every step that changes it, so a
    check asked for starts at once. `address`: this computer is a remote server reached at that routed address
    (launch.serve_remotely); a running Studio that answers elsewhere starts again there."""
    state = state_of(project)
    if address:
        try: pattern = launch.serve_remotely(address)
        except ValueError as problem: return {'error': str(problem), 'what_now': 'Pass the exact https address your environment routes to a port.'}
        running = launch.running(state)
        if running and running.get('remote_origin') != pattern.format(port=running['port']): launch.stop(running)
    found, started = launch.start(state)
    if not found:
        return {'error': 'the Studio server did not start in time', 'log': str(Path(state['workspace']) / 'logs/studio-server.log'),
                'what_now': 'Tell the person the live Studio could not start, and offer open_report (the report page) instead.'}
    url = launch.url_of(found, route)
    opened = launch._open(url, show)
    return {'studio': url, 'opened_in_browser': opened, 'started': started, 'live': True,
            'checked': guided.scan_done(state),
            'what_now': ('Tell the person the Studio is open in their browser' if opened else
                         'Send the person this address now, without being asked: it stays the same, and the Studio keeps '
                         'running on this server after your session ends' if found.get('remote_origin') else
                         'Give the person this address to open in their browser on this computer (it works only here)')
                        + '; it updates by itself after every check, batch, merge and decision. '
                        + ('' if guided.scan_done(state) else 'The project is not checked yet: offer audit first. ')
                        + 'Do not paste the address anywhere else.'}


def wait(job, seconds=WAIT, project=None):          # a job of this project only: another project's is not found
    return _job_answer(job, min(max(int(seconds), 0), 300), state_of(project)['project'])


# ---------------------------------------------------------------- where things are

def _branch(state):
    """The branch EAOS works on, settled: None when it is (chosen before, or no real choice: then the branch checked
    out, without a question); else the choice to put to the person (eaos/core/branches.py)."""
    if state.get('branch'): return None
    current = branches.checked_out(state['project'])
    unfinished = state.get('open_wave') or any(w.get('status') == 'applied' for w in state.get('waves') or [])
    options = None if unfinished else branches.choice(state['project'])     # work begun before: it is the checked out branch's
    if options is None:
        if current: guided.choose(state, current)
        return None
    if not (state.get('asked') or {}).get('branch'):
        state.setdefault('asked', {})['branch'] = _now()
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
    waited = asked and (datetime.now(timezone.utc) - datetime.fromisoformat(asked)).total_seconds() >= ANSWER_SECONDS
    if branches.choice(state['project']) is not None and not (str(person_said or '').strip() and waited):
        since = int((datetime.now(timezone.utc) - datetime.fromisoformat(asked)).total_seconds()) if asked else None
        why = ('no reply from the person was given' if not str(person_said or '').strip() else
               f'the question was put {since} seconds ago: nobody answers that fast, so the person has not answered yet')
        return {'status': 'needs_the_person', 'why': why, **{k: v for k, v in (_branch({**state, 'branch': None}) or {}).items() if k != 'status'},
                'what_now': 'The person chooses the branch, not you: ask them (the branches, when each changed, how far ahead, '
                            'your recommendation and why) and end your turn. When they reply, in any words (a name, or "the one '
                            'you recommend"), call choose_branch again with the branch they meant and person_said = their reply: '
                            'it is accepted then. Nothing else is wrong with the call.'}
    state.setdefault('questions', []).append({'id': 'branch', 'kind': 'choice', 'answer': branch, 'said': str(person_said)[:300] or None,
                                              'via': 'assistant'})
    state = guided.choose(state, branch)
    checked = guided.scan_done(state)
    return {'status': 'chosen', 'branch': branch, 'before': before, 'checked_before': checked,
            'commit': _head(state), 'report_for_people': str(branches.home(state) / 'REPORT.html'),
            'what_now': ('This branch was checked before: call status.' if checked else
                         'Call audit: the check runs on this branch (its own copy; the person\'s checkout is not switched).')}

def _batches(wave, retired):     # status' open and retired batches
    return {'open_batch': {k: wave.get(k) for k in ('number', 'cards', 'kept', 'failed', 'last_error', 'deliver_as', 'merge_into', 'direct', 'continues')} if wave else None, 'retired_batch': {k: retired.get(k) for k in ('number', 'why')} if retired else None}


def status(project=None):
    from ..core import ledger
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
    setup, safety, wave = state.get('setup') or {}, state.get('safety') or {}, state.get('open_wave')
    waiting = next((w for w in reversed(state.get('waves') or []) if w.get('status') == 'applied'), None)
    busy = jobs.running(state['project'])
    answer = {'project': state['project'], 'branch': state.get('branch'), 'commit': head,
              'saved_in_git': not guided._git(state['project'], 'status', '--porcelain').stdout.strip(),
              'checked': checked, 'checked_commit': state.get('scanned_commit'),
              'outputs_folder': str(guided.outputs(state)), 'report_for_people': str(branches.home(state) / 'REPORT.html') if checked else None,
              'app_runs': setup.get('ok') if _set_up(state, head) else None,
              'safety_net': safety if guided.same_code(state, safety.get('commit'), head) else None,
              'progress': ((ledger.load(state) or {}).get('totals') if checked else None),
              **_batches(wave, retired),
              'waiting_branch': waiting['branch'] if waiting else None,
              'running_job': busy['id'] if busy else None}
    if busy: step = signing.step(state, ('wait', f"a {busy['kind']} is running"))
    elif not checked: step = ('audit', 'the project has not been checked')
    elif (pending := remedies.pending(guided.report_of(state))): step = ('audit', f'again_from={pending}: a remedy EAOS knows was not tried on it yet')
    elif waiting: step = ('accept or undo', f"the fixes on {waiting['branch']} wait for the person's decision")
    elif wave and (_no_safety_net(state) or {}).get('recorded') == 0:
        step = ('fix_abandon', f"batch {wave['number']} cannot be closed: the safety net recorded nothing")
    elif wave and wave.get('last_error'):
        step = ('fix_abandon', f"batch {wave['number']} could not be finished ({wave['last_error'][:200]}): close it, its cards can be tried again")
    elif wave: step = batch_finish.open_step(wave)
    elif not _set_up(state, head): step = ('run_setup', "the app has not been run for this commit (ask the person's agreement first)")
    elif not setup.get('ok'): step = ('run_try', 'the app does not run yet: read the last failure and propose a fix')
    elif not guided.same_code(state, safety.get('commit'), head): step = ('safety_net', 'record the screens before any fix')
    elif not safety.get('passed'): step = ('none', 'the safety net recorded nothing: EAOS cannot protect this project yet, so no fix starts')
    else: step = ('fix_start', 'open the next batch of fixes')
    answer['next'] = {'tool': step[0], 'why': step[1]}
    if checked: answer.update(_older_check(state))
    answer['report'] = _fresh_report(state) if checked else None
    answer['handover'] = handover.brief(state)
    return answer


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


# ---------------------------------------------------------------- diagnosis

def audit(project=None, fresh=False, use_assistant=None, without_tools=False, assistant=None, without_ai=False, again_from=None, engines=None,
          paths=None, mode=None, sign_in=None, published=None, run_app=False, go_on=False, fixed=False, person_agreed=False):
    """`use_assistant`, `assistant`: the person's choice for the check's AI, kept (one not ready stops it, with why);
    `without_ai`: the rules alone; `again_from`: the last check goes on from that stage (`engines`: only those tools);
    `paths`, `mode`, `sign_in`, `published`, `run_app` (kept: eaos/journeys/check_choices.py); `go_on`: Retry; `fixed`: the assistant
    is fixed; `person_agreed`: their yes to a remedy's question (eaos/pipeline/remedies.py): the app runs, from setup."""
    run_app, again_from = remedies.agreed(run_app, again_from, person_agreed)
    state = state_of(project)
    asking = _branch(state)
    if asking: return asking
    if use_assistant is not None or assistant:          # the person's choice for the check's AI, kept when made now
        state = guided.choose_assistant(state, True if use_assistant is None else use_assistant, assistant, via='assistant')
    if check_choices.keep(state, mode, sign_in, run_app): guided.save(state)
    # A check on record stands until asked for anew (fresh): one started because the code moved on stopped fixes (2026-10-10).
    if guided.scan_done(state) and not fresh and not again_from and not go_on:
        return {'status': 'done', 'already_checked': True, **overview(project), **_older_check(state)}
    without_ai = check_choices.without_ai_kept(guided.report_of(state), without_ai, again_from, use_assistant is not None or assistant)
    blocked = None if without_ai else _assistant_not_ready(state, fixed)
    if blocked: return blocked
    arguments = {k: v for k, v in dict(without_tools=without_tools, without_ai=without_ai, again_from=again_from, engines=engines, paths=paths, published=signing.published(published), go_on=go_on).items() if v}
    return _start('audit', state, arguments, watch=True)


def _assistant_not_ready(state, fixed=False):
    """{status: assistant_not_ready, ...} when the person's assistant does not answer now, unless they said it is `fixed`."""
    if fixed or guided.answered(state, 'use_assistant') is False: return None      # on unless the person said no
    name = guided.chosen_assistant(state)
    if not name: return None
    found = readiness.probe(name, fresh=True)          # the person may have just fixed it
    if found['ready']: return None
    return {'status': 'assistant_not_ready', 'assistant': found, 'why': (found.get('reason') or {}).get('en') or found['code'],
            'what_now': f"The check did not start: {found['name']} is not ready. Tell the person, in their language and plain words, "
                        f"what is wrong and how to fix it: {(found.get('reason') or {}).get('en') or found['code']} Then ask them: fix it and "
                        'check again (call audit again), use the other assistant (audit with assistant=claude or codex), or start '
                        'without AI (audit with use_assistant=false). End your turn until they answer.'}


def assistant_check(project=None, fresh=False, assistant=None):
    """Before a check: each AI assistant's readiness on this computer (installed, version, signed in and answering a
    one-word question, else the exact reason and its fix), the person's choice for this project, and what the
    assistant may do in the check. `fresh` asks again instead of the answer of the last few minutes; `assistant`
    asks only that one."""
    state = state_of(project)
    rows = readiness.probe_all(fresh=fresh, names=[assistant] if assistant else None)
    said = guided.answered(state, 'use_assistant')
    chosen = guided.chosen_assistant(state)
    return {'assistants': rows, 'choice': {'use_assistant': said, 'assistant': chosen if said is not False else state.get('assistant'),
                                           'kept': said is not None},
            'permission': PERMISSION,
            'what_now': 'Show the person each assistant with its readiness; when the one they want is not ready, its reason says how to fix '
                        'it. Their choice goes to audit (use_assistant, assistant).'}


PERMISSION = {'en': 'In the check the assistant only reads the facts EAOS gives it and answers: it has no tool, changes no file and '
                    'runs nothing; everything it says stays a hypothesis tied to its evidence.',
              'ar': 'في الفحص المساعد يقرأ فقط الحقائق اللي يعطيه إياها EAOS ويجاوب: ما عنده أي أداة، وما يغيّر أي ملف، وما يشغّل '
                    'شيء؛ وكل ما يقوله يبقى فرضية مربوطة بدليلها.'}


OLDER_CHECK = ('The check on record is from an earlier commit or EAOS. Go on with it; check again (audit with fresh=true) '
               'only when the person asks for a new check.')


def _older_check(state):
    """{older_check, what_now} when the check on record is not of this code by this EAOS; else {}."""
    return {} if _current(state, _head(state)) else {'older_check': True, 'what_now_about_the_check': OLDER_CHECK}


def _audit_job(project, arguments, progress):
    """The check, once none of the tools it needs here is still being installed; without those that failed only when
    the person chose to start without them (`without_tools`)."""
    from ..report.start_here import start_here
    state = project_state.load(project)
    out = guided.report_of(state)
    without = arguments.get('without_tools')
    failed = guided.tools_for_check(state, lambda done, total: progress and progress(done, total, 'tools'), install=not without)
    if failed and not without: raise guided.ToolsMissing('these tools could not be installed: ' + '; '.join(f'{n}: {r}' for n, r in sorted(failed.items())))
    options = check_choices.options(state, progress, failed, guided.check_provider(state), guided.check_runtime(state),
                                    arguments.get('paths'), arguments.get('engines'), arguments.get('published'))
    if arguments.get('without_ai'): options['provider'] = NoAssistant('ai_skipped', 'the person started this check without AI, because their assistant was not ready')
    source = guided.source(state, state.get('scanned_commit') if arguments.get('again_from') else None)   # going on: the checked code
    read = {} if arguments.get('again_from') else {'scanned_commit': _head(state), **branches.scan_provenance(state, source)}   # taken before the scan reads: a commit made meanwhile is not in it
    from ..pipeline import check
    done = check(str(source), out, arguments.get('again_from'), state.get('scanned_dirty') is False, go_on=bool(arguments.get('go_on')), **options)
    done = remedies.apply(done, lambda stages: check(str(source), out, stages, True, **options), out, progress, guided.chosen_assistant(state), options['provider'])
    if not (out / 'START-HERE.md').is_file(): start_here(out, state.get('lang') or 'en', Path(state['project']).name)
    state = project_state.load(project)
    state.update(scanned=_now(), scanned_with=tool_digest(), **read)
    guided.retire_stale_batch(state)
    guided.publish(state)
    guided.save(state)
    return {**overview(project), **remedies.consent(done, CONSENT)}


def overview(project=None):
    from ..report.start_here import summary_counts
    state = state_of(project)
    report = _report(state)
    plan = _read(report / 'plan.json')
    tasks = plan.get('tasks') or []
    manifest = _read(report / 'run-manifest.json') if (report / 'run-manifest.json').is_file() else {}
    groups = {}
    for task in tasks: groups.setdefault(task.get('pattern') or 'generic', []).append(task)
    kinds = []
    for pattern, rows in sorted(groups.items(), key=lambda item: -len(item[1])):
        title, why = plain.problem(pattern, 'en')
        kinds.append({'kind': pattern, 'title': title, 'why': why, 'count': len(rows),
                      'fixable_automatically': sum(_ready(t) for t in rows),
                      'examples': [t['id'] for t in sorted(rows, key=lambda t: -(t.get('priority') or 0))[:3]]})
    claims = _read(report / 'dossier.json').get('claim_counts') if (report / 'dossier.json').is_file() else None
    return {'project': state['project'], 'checked_commit': state.get('scanned_commit'), 'status': manifest.get('status'),
            'incomplete_stages': [name for name, row in (manifest.get('stages') or {}).items() if row.get('status') in ('failed', 'not_reached')],
            'counts': summary_counts(report), 'claims_by_confidence': claims, 'problem_kinds': kinds,
            'milestones': [{'id': m['id'], 'name': m.get('name'), 'goal': m.get('goal'), 'cards': len(m['tasks']),
                            'fixable_automatically': sum(_ready(t) for t in tasks if t['id'] in set(m['tasks']))}
                           for m in plan.get('milestones') or []],
            'report_for_people': str(branches.home(state) / 'REPORT.html') if (branches.home(state) / 'REPORT.html').is_file() else None,
            'outputs_folder': str(guided.outputs(state)), 'technical_report': str(report),
            'next': 'Use `findings` and `finding` for the evidence, `structure` for the architecture, `plan` for the order of work.'}


def _ready(task):
    from ..core.decisions import ready
    return ready(task)


def _claims(report):
    path = report / 'dossier.json'
    return {c['id']: c for c in _read(path).get('claims') or []} if path.is_file() else {}


def findings(project=None, kind=None, path=None, text=None, fixable_only=False, limit=PAGE, offset=0, area=None, severity=None):
    report = _report(state_of(project))
    claims, rows = _claims(report), []
    from .selection import cards_in      # area and severity as the Studio's filter reads them
    only = [cards_in(report / 'studio', by, value) for by, value in (('area', area), ('severity', severity)) if value]
    for task in _read(report / 'plan.json').get('tasks') or []:
        if not _wanted(task, kind, path, text, fixable_only) or any(task['id'] not in ids for ids in only): continue
        claim = claims.get(task.get('claim_id')) or {}
        rows.append({'id': task['id'], 'title': task.get('title'), 'kind': task.get('pattern'), 'paths': (task.get('paths') or [])[:5],
                     'fixable_automatically': _ready(task), 'decision': (task.get('decision') or {}).get('kind'),
                     'confidence': claim.get('confidence'), 'priority': task.get('priority')})
    rows.sort(key=lambda r: -(r['priority'] or 0))
    offset, limit = max(int(offset), 0), min(max(int(limit), 1), 200)
    return {'total': len(rows), 'offset': offset, 'findings': rows[offset:offset + limit], 'more': offset + limit < len(rows)}


def _wanted(task, kind, path, text, fixable_only):      # each filter only when given
    return ((not kind or task.get('pattern') == kind) and (not path or any(path in p for p in task.get('paths') or [])) and (not text or text.lower() in (task.get('title') or '').lower()) and (not fixable_only or _ready(task)))


def _excerpt(root, location, around=8, limit=60):
    path = Path(root) / (location.get('path') or '')
    if not location.get('path') or not path.is_file(): return None
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    line = int(location.get('line') or location.get('start_line') or 1)
    end = int(location.get('end_line') or line)
    start, stop = max(1, line - around), min(len(lines), max(end, line) + around, line + limit)
    return {'path': location['path'], 'from_line': start, 'to_line': stop,
            'code': '\n'.join(f'{n:>5}  {lines[n - 1]}' for n in range(start, stop + 1))}


def _card_and_claim(report, id):
    """(card or None, claim or {}) of a TASK-… or CLM-… id; ValueError when it is neither."""
    tasks = {t['id']: t for t in _read(report / 'plan.json').get('tasks') or []}
    claims = _claims(report)
    task = tasks.get(id) or next((t for t in tasks.values() if t.get('claim_id') == id), None)
    claim = claims.get(id) or claims.get((task or {}).get('claim_id')) or {}
    if not task and not claim: raise ValueError(f'{id} is neither a card nor a claim of this report')
    return task, claim


def _evidence(state, report, card, claim):
    """The facts behind a card and its claim (up to EVIDENCE; shown six, an assistant missed the rest), with their code."""
    from ..facts.store import by_id
    fact_ids = list(dict.fromkeys((claim.get('fact_ids') or []) + ((card.get('evidence') or {}).get('fact_ids') or [])))
    facts = by_id(report, fact_ids[:EVIDENCE])
    return [{'fact': fact_id, 'kind': facts[fact_id].get('kind'), 'value': facts[fact_id].get('value'),
             'code': _excerpt(guided.source(state), facts[fact_id].get('location') or {})}
            for fact_id in fact_ids[:EVIDENCE] if facts.get(fact_id)]


def _what_and_why(card, claim):
    """What a finding is, why it matters, and how it is proven gone."""
    assessment = claim.get('assessment') or {}
    return {'id': card.get('id') or claim.get('id'), 'claim': claim.get('id'), 'title': card.get('title') or claim.get('statement'),
            'kind': card.get('pattern'), 'confidence': claim.get('confidence'), 'paths': card.get('paths'),
            'impact': card.get('impact') or (claim.get('impact') or {}).get('scenario'),
            'rule_broken': assessment.get('violated_invariant'), 'before': card.get('before') or assessment.get('before'),
            'after': card.get('after') or assessment.get('after'), 'suggested_change': assessment.get('proposed_change'),
            'how_it_is_proven_gone': proof(claim) or claim.get('falsifier') or ((card.get('evidence') or {}).get('falsifier'))}


def _card_work(card):
    """How a card can be worked on: fixable, by a codemod, its decision, what it waits on and what uses it."""
    decision = card.get('decision') or {}
    return {'fixable_automatically': _ready(card) if card else False,
            'has_codemod': ((card.get('codemod') or {}).get('dry_run') or {}).get('files_changed', 0) > 0,
            'decision': card.get('decision', {}).get('kind') if card else None,
            'blockers': decision.get('blockers'),
            'depends_on': card.get('prerequisites'), 'used_by': ((card.get('blast_radius') or {}).get('direct_dependents') or [])[:15]}


def finding(id, project=None):
    """One card (TASK-…) or claim (CLM-…), whole: what, why, the evidence with its code, the change, the check."""
    state = state_of(project)
    report = _report(state)
    task, claim = _card_and_claim(report, id)
    card = task or {}
    return {**_what_and_why(card, claim), **_card_work(card), 'evidence': _evidence(state, report, card, claim)}


def structure(project=None):
    state = state_of(project)
    report = _report(state)
    target = _read(report / 'target-architecture.json') if (report / 'target-architecture.json').is_file() else {}
    trim = lambda rows, n=40: (rows or [])[:n] if isinstance(rows, list) else rows
    cycles = [t['title'] for t in _read(report / 'plan.json').get('tasks') or [] if t.get('pattern') == 'import_cycle']
    return {'current_components': trim(target.get('current_components')), 'target_components': trim(target.get('target_components')),
            'forbidden_edges': trim(target.get('forbidden_edges')), 'target_edges': trim(target.get('target_edges')),
            'decisions': trim(target.get('decisions'), 20), 'gaps': trim(target.get('gap_matrix'), 40),
            'import_cycles': cycles[:30], 'import_cycle_count': len(cycles), 'limits': target.get('limits'),
            'documents': [str(report / name) for name in ('TARGET-ARCHITECTURE.md', 'CURRENT-STATE.md')
                          if (report / name).is_file()]}


def _milestone_row(m, cards, whole, tried_card, where):
    """One milestone with its cards: all of them when `whole`, else the first 25 and how many more."""
    shown = cards if whole else cards[:25]
    return {'id': m['id'], 'name': m.get('name'), 'goal': m.get('goal'), 'exit': m.get('exit'),
            'cards': [{'id': c['id'], 'title': c.get('title'), 'kind': c.get('pattern'), 'fixable_automatically': _ready(c),
                       'tried': tried_card(c), 'state': where.get(c['id'], 'open')} for c in shown],
            'more_cards': 0 if whole else max(0, len(cards) - 25)}


def plan(project=None, milestone=None):
    from ..core.ledger import keys, sync
    state = state_of(project)
    guided.reconcile(state)
    report = _report(state)
    data = _read(report / 'plan.json')
    tasks = {t['id']: t for t in data.get('tasks') or []}
    tried, ids = set(state.get('tried') or []), keys(data.get('tasks') or [])
    record = sync(state, report=report) or {}
    where = {c['id']: c['state'] for c in (record.get('cards') or {}).values() if c.get('id')}
    out = [_milestone_row(m, [tasks[i] for i in m['tasks'] if i in tasks], bool(milestone),
                          lambda c: ids.get(c['id']) in tried, where)
           for m in data.get('milestones') or [] if not milestone or m['id'] == milestone]
    return {'milestones': out, 'progress': record.get('totals'),
            'order': 'Fix in this order: milestone by milestone, the fixable cards first. Only these cards count as progress: '
                     'work outside the plan is not recorded anywhere.'}


def impact(target, project=None, depth=3):
    """What changing a file or a symbol touches, from the check's facts: who imports it, the flows and entry points through
    it, the tests that cover it, and the files that change with it in the history."""
    from ..analysis.impact import LIMITS, assess
    result = assess(_report(state_of(project)), target, depth)
    return {**result, 'limits': LIMITS}


def ask(question, project=None):
    """The check's records that answer a question, each with its place; NOT_IN_RECORDS when none does."""
    from ..ai.ask import answer
    return answer(_report(state_of(project)), question)


def tools_check(project=None, retry=False):
    """This EAOS (version, commit) and every external tool it runs: installed or not, at which version, and whether this
    project needs it (its files decide: a JavaScript linter is not needed by a Go project); what the check waits for
    here (`for_the_check`: ready, still coming, failed with why). `retry`: start the install again (the tools that
    failed are tried again; an install already running goes on)."""
    from ..core import build_info
    folder = Path(project or os.getcwd()).expanduser().resolve()
    files = toolchain.project_files(folder) if project_state.looks_like_project(folder) else None
    if retry: toolchain.prepare(folder if files is not None else None)
    rows = toolchain.doctor()['tools']
    rules = {t['name']: t for t in toolchain.registry()['tools']}
    for row in rows:
        row['needed_here'] = None if files is None else toolchain.rule_applies(rules[row['name']].get('applies', 'all'), files)
        row['for_the_check'] = bool(rules[row['name']].get('check'))
    rows.sort(key=lambda r: (r['needed_here'] is False, not r['for_the_check'], r['ok'], r['name']))
    wanted = [r for r in rows if not r['ok'] and not r['unavailable'] and r['needed_here'] is not False]
    later = [r['name'] for r in wanted if not r['for_the_check']]
    gate = toolchain.readiness(files or ())
    return {'eaos': {'version': build_info.__version__, 'commit': build_info.commit()}, 'tools_folder': str(toolchain.home()),
            'installed': sum(r['ok'] for r in rows), 'total': len(rows), 'tools': rows, 'installing': toolchain.installing(),
            'for_the_check': gate, 'missing_for_later_steps': later,
            'install': 'eaos tools install' if wanted or gate['failed'] else None}


def report_file(name='', project=None, offset=0, limit=20000):
    state = state_of(project)
    report = _report(state).resolve()
    if not name:
        return {'files': sorted(str(p.relative_to(report)) for p in report.rglob('*') if p.is_file() and p.suffix in ('.md', '.json', '.txt'))[:400]}
    path = (report / name).resolve()
    if report not in path.parents or not path.is_file(): raise ValueError(f'{name} is not a file of this report')
    text = path.read_text(encoding='utf-8', errors='replace')
    offset, limit = max(int(offset), 0), min(max(int(limit), 1000), 100000)
    return {'file': str(path), 'size': len(text), 'offset': offset, 'text': text[offset:offset + limit], 'more': offset + limit < len(text)}


def open_report(project=None, show=True):
    """REPORT.html, the four reports for people, rebuilt with the fixes so far and opened in the person's browser."""
    state = state_of(project)
    _report(state)
    guided.reconcile(state)
    page = guided.publish(state)
    guided.save(state)
    opened = False
    if show and page.suffix == '.html':
        import webbrowser
        try: opened = webbrowser.open(page.resolve().as_uri())
        except Exception: opened = False
    made = guided.report_stamp(state)
    stale = _stale(state, made)
    return {'report_for_people': str(page), 'opened_in_browser': opened, 'outputs_folder': str(guided.outputs(state)),
            'built': made.get('built'), 'version': made.get('version'), 'report_errors': made.get('errors') or [],
            'checked_commit': made.get('scanned_commit'), 'stale': stale,
            'what_now': 'Tell the person where it is' + ('' if opened else ' and how to open it (double-click the file)') + '.'
                        + (' Some parts could not be built: tell the person which, plainly (report_errors).' if made.get('errors') else '')
                        + (' The branch has moved on with new work since this check: say the report shows the code as it was '
                           'then; a new check (audit with fresh=true) runs only when the person asks for it.' if stale else '')}


def _stale(state, made):
    """{checked, now} once the branch went past the checked commit with code of its own (not only EAOS's merged fixes);
    else None."""
    checked, now = made.get('scanned_commit') or state.get('scanned_commit'), _head(state)
    if not checked or not now or guided.same_code(state, checked, now): return None
    return {'checked': checked, 'now': now}


# ---------------------------------------------------------------- running the app

CONSENT = ('May I run your app in a separate copy on this computer, with a temporary database and none of your secrets, '
           'and prepare fixes there that reach your project only as a new branch (your current branch and files stay as they are)?')


def _consented(state):
    return bool((state.get('consent') or {}).get('run_and_fix'))


def run_setup(project=None, person_agreed=False):
    state = state_of(project)
    if not person_agreed and not _consented(state):
        return {'status': 'needs_agreement', 'ask_the_person': CONSENT,
                'what_now': 'Ask the person this, in their language. Only if they say yes, call run_setup again with person_agreed=true.'}
    head = _head(state)
    if not head: raise RuntimeError(f"{state['project']}: fatal: not a git repository")
    check_choices.agree_to_run(state, 'assistant')
    guided.save(state)
    runtime = project_state.runtime_of(state)
    who = guided._git(state['project'], 'config', 'user.name').stdout.strip() or os.environ.get('USER') or 'the owner'
    source = guided.source(state)
    live_setup.authorize(source, runtime, who)
    detected = live_setup.detect(source, guided.report_of(state))
    (runtime / 'setup').mkdir(parents=True, exist_ok=True)
    (runtime / 'setup/detected.json').write_text(json.dumps(detected, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    run_profile.write_profile(runtime, live_setup.kept(runtime, detected['profile']))     # its secrets kept: a session holds
    return _start('run_try', state, {'proposal': None, 'mode': 'lock'}, watch=True)


def run_try(proposal=None, mode='lock', project=None):
    """Try the assistant's proposal (see live_assist.ASSIST_SYSTEM for its fields), refused when unsafe."""
    state = state_of(project)
    runtime = project_state.runtime_of(state)
    if not (runtime / 'run.json').is_file(): return {'status': 'not_set_up', 'what_now': 'Call run_setup first.'}
    if mode not in ('lock', 'baseline'): raise ValueError("mode is 'lock' (the app as developers run it) or 'baseline' (the production build)")
    refused = run_profile.safe(proposal or {})
    if refused:
        return {'status': 'refused', 'reasons': refused,
                'rules': 'Every address is 127.0.0.1 or localhost; commands start with npm, npx, pnpm, yarn, bun, node, corepack, python, '
                         'pip, uv, poetry, uvicorn or gunicorn; '
                         'nothing deploys or reaches a hosted service; no real secret. Use {database_url} and {run_dir}.'}
    return _start('run_try', state, {'proposal': proposal, 'mode': mode})


def _limitations(profile, record, runtime, missing):
    """The profile's limitations, the ones a run decides again replaced by what this run found."""
    unset = [n for n in (_read(runtime / 'setup/detected.json')['facts'].get('env_names') or []) if n not in profile['env'] and n != 'NODE_ENV']
    limitations = [l for l in profile.get('limitations') or [] if not l.startswith(('run without a value', 'screens that need', 'the app could not'))]
    if unset and record['ok']: limitations.append('run without a value for: ' + ', '.join(unset[:12]))
    if missing: limitations.append('screens that need these values are not recorded: ' + ', '.join(missing))
    if not record['ok']: limitations.append('the app could not be made to answer: ' + (record.get('failure') or '')[:300])
    return sorted(set(limitations))


def _lock_run(project, runtime, report, record, profile, attempt):
    """After a run as developers run it: the profile's values and limitations, and the project's setup record.
    The fixtures the screens need and nobody gave."""
    needs = live_setup.fixtures_needed(report) if (report / 'plan.json').is_file() else []
    known = {**profile.get('env', {}), **record.get('fixtures', {})}
    missing = [name for name in needs if name not in known]
    if record.get('fixtures'):
        profile.setdefault('env', {}).update({k: str(v) for k, v in record['fixtures'].items()})
    profile['limitations'] = _limitations(profile, record, runtime, missing)
    run_profile.write_profile(runtime, profile)
    state = project_state.load(project)
    state['setup'] = {'commit': _head(state), 'ok': record['ok'], 'attempts': attempt, 'limitations': profile['limitations']}
    state.pop('safety', None)
    guided.save(state)
    return missing


def _production_build(source, runtime, answer, progress):
    """Build and start the production version once, to measure speed later; the profile as it is after."""
    progress(1, 2, 'building and starting the production version, to measure speed later')
    base = live_setup.verify(source, runtime, 1, mode='baseline')
    profile = _read(runtime / 'run.json')
    profile['baseline']['verified'] = base['ok']
    run_profile.write_profile(runtime, profile)
    answer['production_build_runs'] = base['ok']
    if not base['ok']: answer['production_failure'] = (base.get('failure') or '')[-2500:]
    return profile


def _first_page(page):
    if not page: return None
    return {'status': page.get('status'), 'url': page.get('url'), 'text': (page.get('text') or '')[:800],
            'others': [{k: o.get(k) for k in ('path', 'status', 'url')} for o in page.get('others') or []],
            'errors': (page.get('errors') or [])[:5]}


def _run_what_now(ok, mode):
    if ok and mode == 'lock': return 'The app runs: call safety_net.'
    if ok: return 'The production build runs.'
    return ('Read the failure and the code, then call run_try with a proposal: {"env": {...complete environment...}, '
            '"start": [...], "install": [[...]], "prepare": [[...]], "database": "postgres"|"none", '
            '"seed_script": "<node script that signs in and saves storage state>", "fixtures": {...}}'
            + (' (mode="baseline", with "build": [[...]] too)' if mode == 'baseline' else ''))


def _run_job(project, arguments, progress):
    runtime, report = project_state.runtime_of(state := project_state.load(project)), guided.report_of(state)
    mode, proposal = arguments.get('mode') or 'lock', arguments.get('proposal')
    if proposal: run_profile.apply(runtime, proposal, mode=mode)
    attempt = len(list((runtime / 'setup').glob(f"{'baseline-' if mode == 'baseline' else ''}attempt-*.json"))) + 1
    progress(0, 1, 'installing and starting the app in the isolated copy')
    source = guided.source(state)
    record = live_setup.verify(source, runtime, attempt, report if (report / 'plan.json').is_file() else None, mode=mode)
    profile = _read(runtime / 'run.json')
    answer = {'mode': mode, 'attempt': attempt, 'runs': record['ok']}
    if mode == 'baseline':
        profile.setdefault('baseline', {})['verified'] = record['ok']
        run_profile.write_profile(runtime, profile)
    else:
        answer['fixtures_missing'] = _lock_run(project, runtime, report, record, profile, attempt)
        if record['ok'] and (profile.get('baseline') or {}).get('build') and 'verified' not in profile['baseline']:
            profile = _production_build(source, runtime, answer, progress)
    answer['first_page'] = _first_page(record.get('page') or {})
    if not record['ok']:
        answer['failure'] = (record.get('failure') or '')[-3000:]
        folder = profile.get('app') or '.'
        answer['code_that_raised_it'] = live_assist.relevant_source(source, folder, record.get('failure') or '', limit=2, context=30)[:8000]
    if record.get('seed_output'): answer['seed_output'] = record['seed_output'][-1500:]
    answer['profile'] = {k: profile.get(k) for k in ('app', 'install', 'prepare', 'start', 'port', 'env', 'database', 'seed', 'checks', 'baseline', 'limitations')}
    answer['what_now'] = _run_what_now(record['ok'], mode)
    return answer


def safety_net(project=None):
    state = state_of(project)
    if not _set_up(state, _head(state)): return {'status': 'not_set_up', 'what_now': 'Call run_setup first.'}
    return _start('safety_net', state, {}, watch=True)


def _safety_job(project, arguments, progress):
    state = project_state.load(project)
    outcome = guided.safety_run(state, lambda n: progress(n - 1, 2, 'recording every screen' if n == 1 else 'measuring speed under load'))
    outcome['record'] = str(project_state.runtime_of(state) / 'behavior-lock/results.json')
    outcome['what_now'] = 'Call fix_start to open a batch of fixes.'
    return outcome


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
    if not _set_up(state, _head(state)): return {'status': 'not_set_up', 'what_now': 'Call run_setup first.'}
    if unsafe := _no_safety_net(state): return unsafe
    waiting = waiting_batch(state)
    if waiting and waiting['branch'] != deliver_as:
        return {'status': 'waiting_decision', 'branch': waiting['branch'],
                'what_now': f"The fixes on {waiting['branch']} wait for the person's decision: ask them, then accept or undo; "
                            f"or, if they want this batch on the same branch, call fix_start again with deliver_as={waiting['branch']}."}
    return None


def _chosen(state, cards, size):
    """(why nothing opens, or None; the batch's cards): those asked for, else the next ready ones."""
    from .waves import next_batch, plan as read_plan, too_early, with_prerequisites
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
    if not guided.same_code(state, safety.get('commit'), _head(state)):
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
    from .waves import change, commit, drop_last, open_batch, plan as read_plan
    from .execute import new_breakage
    from ..live.sandbox import head
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
        text = staged.get(relative) if relative in staged else (path.read_text(encoding='utf-8') if path.is_file() else None)
        if text is None: raise ValueError(f'{relative}: does not exist; send its whole content instead')
        find, replace = edit.get('find'), edit.get('replace')
        if not isinstance(find, str) or not isinstance(replace, str) or not find:
            raise ValueError(f'{relative}: an edit needs `find` and `replace`, or `content`, or `delete`')
        if text.count(find) != 1: raise ValueError(f'{relative}: the text to find occurs {text.count(find)} times, not once')
        staged[relative] = text.replace(find, replace, 1)
    for relative, text in staged.items():
        path = _inside(root, relative)
        if text is None:
            if path.is_file(): path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
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
    from .waves import commit, drop_last, edit_gates, plan as read_plan
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
            from .waves import without
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


def accept(project=None, person_agreed=False, merge_into=None, delete_after=True):
    """The waiting branch into the branch the person chose (`merge_into`; by default the one the fix preview named, else
    the person's current branch); then its branch is deleted (unless `delete_after` is false: it stays, merged) and the
    report brought up to date, in the same call (eaos/journeys/guided.merge)."""
    from ..core.ledger import load
    state = state_of(project)
    guided.reconcile(state)
    wave = waiting_batch(state)
    if wave is None: return {'status': 'nothing_waiting', 'progress': (load(state) or {}).get('totals')}
    into = (merge_into or '').strip() or None
    if into and not commit_of(state['project'], into): return {'status': 'error', 'error': f'no branch named {into} to merge into'}
    if into == wave['branch']: return {'status': 'error', 'error': 'a branch cannot be merged into itself'}
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
    from .waves import undo as drop
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


JOBS = {'audit': _audit_job, 'run_try': _run_job, 'safety_net': _safety_job, 'fix_start': _fix_start_job,
        'fix_edit': _fix_edit_job, 'fix_finish': batch_finish.finish_job}
