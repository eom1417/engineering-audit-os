"""What an AI assistant does EAOS with (docs/MCP.md): the tools behind eaos/mcp_server.py.

The assistant is the one who thinks: it reads the evidence, reads the code, proposes how the app runs, writes
the fixes. EAOS gives it the evidence, the isolated copy and the gates, and never calls a model itself here.
Every tool returns a plain dict; one that takes longer than a tool call waits returns a job (eaos/jobs.py) that
`wait` follows. The person's project is only ever written through git: a branch `eaos/wave-N`, fetched in.

State is the guided commands' own (~/.eaos/projects/<name>-<hash>/state.json), so the two ways meet: a check
started with `eaos start` is the one `overview` reads, and the other way round.
"""
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import branches, guided, handover, jobs, plain

# A person's answer comes at least this long after the question: sooner, nobody was asked (EAOS_ANSWER_SECONDS: tests).
ANSWER_SECONDS = int(os.environ.get('EAOS_ANSWER_SECONDS') or 30)
WAIT = 50                   # seconds a tool call waits for its job before answering with the job to follow
PAGE = 30


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
    """The project a folder means: itself when it is one (eaos/guided.looks_like_project); a folder with no project file
    and exactly one git repository directly under it (the assistant opened in the folder above) means that repository; with several, SeveralProjects: the
    person chooses, EAOS never guesses."""
    if not folder.is_dir() or guided.looks_like_project(folder): return folder
    found = repositories_under(folder)
    if len(found) > 1: raise SeveralProjects(folder, found)
    return found[0] if found else folder


def project_state(project=None, new=False):
    """The project's state, made on first use. `new`: a project still to be built from its plan, whose folder may be
    empty or not there yet (it is made); never the home folder or the disk's root."""
    folder = Path(project or os.getcwd()).expanduser().resolve()
    if not new and not (guided.load(folder) if folder.is_dir() else None): folder = locate(folder)
    state = guided.load(folder) if folder.is_dir() else None
    if new or (state or {}).get('mode') == 'build':
        if folder in (Path.home().resolve(), Path(folder.anchor)):
            raise ValueError(f'not a project folder: {folder} (make an empty folder for the new project and open the assistant there)')
        folder.mkdir(parents=True, exist_ok=True)
    elif not folder.is_dir(): raise ValueError(f'project folder not found: {folder}')
    elif not guided.looks_like_project(folder):
        raise ValueError(f'not a project folder: {folder} (no .git, package.json or other project file at its top; '
                         'pass the project folder as `project`)')
    state = guided.load(folder)
    if not state:
        state = {'schema_version': 1, 'project': str(folder), 'workspace': str(guided.workspace(folder)),
                 'started': _now(), 'questions': [], 'lang': guided.language()}
        guided.save(state)
    return state


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _head(state):
    """The last commit of the branch EAOS works on (eaos/branches.py)."""
    return guided.tip(state)


def tool_digest():
    """This EAOS's own code, as a fingerprint (eaos/build_info.py): a report made by an older EAOS is checked again."""
    from .build_info import digest
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


def _job_answer(job, seconds=WAIT):
    """A job's record as a tool answers it: the result when it ended in time, else how to follow it."""
    record = jobs.wait(job, seconds)
    if record['status'] == 'done': return {'job': job, 'status': 'done', **(record['result'] or {})}
    if record['status'] == 'failed':
        return {'job': job, 'status': 'failed', 'error': record['error'], 'log': record['log'],
                'what_now': guided.explain(RuntimeError(record['error']))['en']['fix']}
    return {'job': job, 'status': 'running', 'progress': record['progress'], 'started': record['started'],
            'what_now': f'Call `wait` with job="{job}" to follow it; keep going until it is done.'}


def _start(kind, state, arguments, seconds=WAIT, runner='eaos.agent_tools'):
    busy = jobs.running(state['project'])
    if busy:
        return {'job': busy['id'], 'status': 'busy', 'kind': busy['kind'], 'progress': busy['progress'],
                'what_now': f"Another piece of work is running for this project: call `wait` with job=\"{busy['id']}\" first."}
    return _job_answer(jobs.start(kind, state['project'], arguments, runner=runner), seconds)


def wait(job, seconds=WAIT):
    return _job_answer(job, min(max(int(seconds), 0), 300))


# ---------------------------------------------------------------- where things are

def _branch(state):
    """The branch EAOS works on, settled: None when it is (chosen before, or no real choice: then the branch checked
    out, without a question); else the choice to put to the person (eaos/branches.py)."""
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
    state = project_state(project)
    options = branches.choice(state['project'])
    return {'working_branch': state.get('branch'), 'checked_out': branches.checked_out(state['project']),
            'main_branch': branches.default_branch(state['project']),
            'branches': (options or {}).get('branches') or branches.inventory(state['project']),
            'recommended': (options or {}).get('recommended'),
            'with_a_report': sorted({state.get('home_branch'), *(state.get('by_branch') or {})} - {None}),
            'what_now': 'choose_branch moves the work to another branch; each branch keeps its own check, fixes and progress.'}


def choose_branch(branch, project=None, person_said=''):
    """`person_said`: the person's own words in answer to which branch (their reply, as they wrote it)."""
    state = project_state(project)
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

def status(project=None):
    from . import ledger
    try: state = project_state(project)
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
    head = _head(state)
    report = guided.report_of(state)
    checked = guided.scan_done(state)
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
              'open_batch': {k: wave[k] for k in ('number', 'cards', 'kept', 'failed')} if wave else None,
              'waiting_branch': waiting['branch'] if waiting else None,
              'running_job': busy['id'] if busy else None}
    if busy: step = ('wait', f"a {busy['kind']} is running")
    elif not checked: step = ('audit', 'the project has not been checked')
    elif not _current(state, head): step = ('audit', 'the project or EAOS changed since the last check: call audit with fresh=true')
    elif waiting: step = ('accept or undo', f"the fixes on {waiting['branch']} wait for the person's decision")
    elif wave: step = ('fix_edit, then fix_finish', f"batch {wave['number']} is open")
    elif not _set_up(state, head): step = ('run_setup', "the app has not been run for this commit (ask the person's agreement first)")
    elif not setup.get('ok'): step = ('run_try', 'the app does not run yet: read the last failure and propose a fix')
    elif not guided.same_code(state, safety.get('commit'), head): step = ('safety_net', 'record the screens before any fix')
    else: step = ('fix_start', 'open the next batch of fixes')
    answer['next'] = {'tool': step[0], 'why': step[1]}
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

def audit(project=None, fresh=False):
    state = project_state(project)
    asking = _branch(state)
    if asking: return asking
    head = _head(state)
    if guided.scan_done(state) and not fresh and _current(state, head):
        return {'status': 'done', 'already_checked': True, **overview(project)}
    if fresh:
        import shutil
        shutil.rmtree(guided.report_of(state), ignore_errors=True)
    return _start('audit', state, {})


def _audit_job(project, arguments, progress):
    from .pipeline import execute, resume
    from .start_here import start_here
    state = guided.load(project)
    out = guided.report_of(state)
    options = dict(language=state.get('lang') or 'en', engines=[], site=True, progress=progress)
    source = guided.source(state)
    # What the scan reads, taken before it reads it: a commit made during a long scan is not in this report.
    read = {'scanned_commit': _head(state), **branches.scan_provenance(state, source)}
    try:
        (resume if (out / 'run-manifest.json').is_file() else execute)(str(source), out, **options)
    except ValueError:                      # the source changed since a partial run: start afresh
        import shutil
        shutil.rmtree(out, ignore_errors=True)
        execute(str(source), out, **options)
    if not (out / 'START-HERE.md').is_file(): start_here(out, state.get('lang') or 'en', Path(state['project']).name)
    state = guided.load(project)
    state.update(scanned=_now(), scanned_with=tool_digest(), **read)
    guided.publish(state)
    guided.save(state)
    return overview(project)


def overview(project=None):
    from .start_here import summary_counts
    state = project_state(project)
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
    from .waves import ready
    return ready(task)


def _claims(report):
    path = report / 'dossier.json'
    return {c['id']: c for c in _read(path).get('claims') or []} if path.is_file() else {}


def findings(project=None, kind=None, path=None, text=None, fixable_only=False, limit=PAGE, offset=0):
    state = project_state(project)
    report = _report(state)
    claims = _claims(report)
    rows = []
    for task in _read(report / 'plan.json').get('tasks') or []:
        if kind and task.get('pattern') != kind: continue
        if path and not any(path in p for p in task.get('paths') or []): continue
        if text and text.lower() not in (task.get('title') or '').lower(): continue
        if fixable_only and not _ready(task): continue
        claim = claims.get(task.get('claim_id')) or {}
        rows.append({'id': task['id'], 'title': task.get('title'), 'kind': task.get('pattern'), 'paths': (task.get('paths') or [])[:5],
                     'fixable_automatically': _ready(task), 'decision': (task.get('decision') or {}).get('kind'),
                     'confidence': claim.get('confidence'), 'priority': task.get('priority')})
    rows.sort(key=lambda r: -(r['priority'] or 0))
    offset, limit = max(int(offset), 0), min(max(int(limit), 1), 200)
    return {'total': len(rows), 'offset': offset, 'findings': rows[offset:offset + limit],
            'more': offset + limit < len(rows)}


def _facts_index(report):
    index = {}
    for path in sorted((report / 'facts').glob('*.json')):
        try: data = _read(path)
        except (OSError, ValueError): continue
        for fact in data.get('facts') or []:
            if isinstance(fact, dict) and fact.get('id'): index[fact['id']] = fact
    return index


def _excerpt(root, location, around=8, limit=60):
    path = Path(root) / (location.get('path') or '')
    if not location.get('path') or not path.is_file(): return None
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    line = int(location.get('line') or location.get('start_line') or 1)
    end = int(location.get('end_line') or line)
    start, stop = max(1, line - around), min(len(lines), max(end, line) + around, line + limit)
    return {'path': location['path'], 'from_line': start, 'to_line': stop,
            'code': '\n'.join(f'{n:>5}  {lines[n - 1]}' for n in range(start, stop + 1))}


def finding(id, project=None):
    """One card (TASK-…) or claim (CLM-…), whole: what, why, the evidence with its code, the change, the check."""
    state = project_state(project)
    report = _report(state)
    tasks = {t['id']: t for t in _read(report / 'plan.json').get('tasks') or []}
    claims = _claims(report)
    task = tasks.get(id) or next((t for t in tasks.values() if t.get('claim_id') == id), None)
    claim = claims.get(id) or claims.get((task or {}).get('claim_id')) or {}
    if not task and not claim: raise ValueError(f'{id} is neither a card nor a claim of this report')
    facts = _facts_index(report)
    fact_ids = list(dict.fromkeys((claim.get('fact_ids') or []) + (((task or {}).get('evidence') or {}).get('fact_ids') or [])))
    evidence = []
    for fact_id in fact_ids[:6]:
        fact = facts.get(fact_id)
        if not fact: continue
        evidence.append({'fact': fact_id, 'kind': fact.get('kind'), 'value': fact.get('value'),
                         'code': _excerpt(guided.source(state), fact.get('location') or {})})
    assessment = claim.get('assessment') or {}
    card = task or {}
    return {'id': card.get('id') or claim.get('id'), 'claim': claim.get('id'), 'title': card.get('title') or claim.get('statement'),
            'kind': card.get('pattern'), 'confidence': claim.get('confidence'), 'paths': card.get('paths'),
            'impact': card.get('impact') or (claim.get('impact') or {}).get('scenario'),
            'rule_broken': assessment.get('violated_invariant'), 'before': card.get('before') or assessment.get('before'),
            'after': card.get('after') or assessment.get('after'), 'suggested_change': assessment.get('proposed_change'),
            'how_it_is_proven_gone': claim.get('falsifier') or ((card.get('evidence') or {}).get('falsifier')),
            'fixable_automatically': _ready(card) if card else False,
            'has_codemod': ((card.get('codemod') or {}).get('dry_run') or {}).get('files_changed', 0) > 0,
            'decision': card.get('decision', {}).get('kind') if card else None,
            'blockers': (card.get('decision') or {}).get('blockers'),
            'depends_on': card.get('prerequisites'), 'used_by': ((card.get('blast_radius') or {}).get('direct_dependents') or [])[:15],
            'evidence': evidence}


def structure(project=None):
    state = project_state(project)
    report = _report(state)
    target = _read(report / 'target-architecture.json') if (report / 'target-architecture.json').is_file() else {}
    trim = lambda rows, n=40: (rows or [])[:n] if isinstance(rows, list) else rows
    cycles = [t['title'] for t in _read(report / 'plan.json').get('tasks') or [] if t.get('pattern') == 'import_cycle']
    return {'current_components': trim(target.get('current_components')), 'target_components': trim(target.get('target_components')),
            'forbidden_edges': trim(target.get('forbidden_edges')), 'target_edges': trim(target.get('target_edges')),
            'decisions': trim(target.get('decisions'), 20), 'gaps': trim(target.get('gap_matrix'), 40),
            'import_cycles': cycles[:30], 'import_cycle_count': len(cycles), 'limits': target.get('limits'),
            'documents': [str(report / name) for name in ('TARGET-ARCHITECTURE.md', 'SYSTEM-MAP.md', 'COUPLING-ATLAS.md', 'CURRENT-STATE.md')
                          if (report / name).is_file()]}


def plan(project=None, milestone=None):
    from .ledger import sync
    state = project_state(project)
    guided.reconcile(state)
    report = _report(state)
    data = _read(report / 'plan.json')
    tasks = {t['id']: t for t in data.get('tasks') or []}
    tried = set(state.get('tried') or [])
    record = sync(state, report=report) or {}
    where = {c['id']: c['state'] for c in (record.get('cards') or {}).values() if c.get('id')}
    out = []
    for m in data.get('milestones') or []:
        if milestone and m['id'] != milestone: continue
        cards = [tasks[i] for i in m['tasks'] if i in tasks]
        out.append({'id': m['id'], 'name': m.get('name'), 'goal': m.get('goal'), 'exit': m.get('exit'),
                    'cards': [{'id': c['id'], 'title': c.get('title'), 'kind': c.get('pattern'), 'fixable_automatically': _ready(c),
                               'tried': c['id'] in tried, 'state': where.get(c['id'], 'open')} for c in (cards if milestone else cards[:25])],
                    'more_cards': 0 if milestone else max(0, len(cards) - 25)})
    return {'milestones': out, 'progress': record.get('totals'),
            'order': 'Fix in this order: milestone by milestone, the fixable cards first. Only these cards count as progress: '
                     'work outside the plan is not recorded anywhere.'}


def impact(target, project=None, depth=3):
    """What changing a file or a symbol touches, from the check's facts: who imports it, the flows and entry points through
    it, the tests that cover it, and the files that change with it in the history."""
    from .impact import LIMITS, assess
    result = assess(_report(project_state(project)), target, depth)
    return {**result, 'limits': LIMITS}


def ask(question, project=None):
    """The check's records that answer a question, each with its place; NOT_IN_RECORDS when none does."""
    from .ask import answer
    return answer(_report(project_state(project)), question)


def tools_check(project=None):
    """This EAOS (version, commit) and every external tool it runs: installed or not, at which version, and whether this
    project needs it (its files decide: a JavaScript linter is not needed by a Go project); what this project needs
    first, and the one command that installs what it misses."""
    from . import build_info, toolchain
    folder = Path(project or os.getcwd()).expanduser().resolve()
    files = toolchain.project_files(folder) if guided.looks_like_project(folder) else None
    rows = toolchain.doctor()['tools']
    rules = {t['name']: t.get('applies', 'all') for t in toolchain.registry()['tools']}
    for row in rows:
        row['needed_here'] = None if files is None else toolchain.rule_applies(rules.get(row['name'], 'all'), files)
        row['for_the_check'] = any(stage <= 'S07' for stage in row['stages'])   # eaos tools install --stage assessment
    rows.sort(key=lambda r: (r['needed_here'] is False, not r['for_the_check'], r['ok'], r['name']))
    wanted = [r for r in rows if not r['ok'] and not r['unavailable'] and r['needed_here'] is not False]
    for_check, later = [r['name'] for r in wanted if r['for_the_check']], [r['name'] for r in wanted if not r['for_the_check']]
    return {'eaos': {'version': build_info.__version__, 'commit': build_info.commit()}, 'tools_folder': str(toolchain.home()),
            'installed': sum(r['ok'] for r in rows), 'total': len(rows), 'tools': rows,
            'missing_for_the_check': for_check, 'missing_for_later_steps': later,
            'install': ('eaos tools install --stage assessment' if for_check else
                        f"eaos tools install {' '.join(later)}" if later else None)}


def report_file(name='', project=None, offset=0, limit=20000):
    state = project_state(project)
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
    state = project_state(project)
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
                           'then, and offer a new check (audit with fresh=true).' if stale else '')}


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
    state = project_state(project)
    if not person_agreed and not _consented(state):
        return {'status': 'needs_agreement', 'ask_the_person': CONSENT,
                'what_now': 'Ask the person this, in their language. Only if they say yes, call run_setup again with person_agreed=true.'}
    from . import live_setup
    head = _head(state)
    if not head: raise RuntimeError(f"{state['project']}: fatal: not a git repository")
    state['consent'] = {'run_and_fix': True, 'at': _now()}
    state.setdefault('questions', []).append({'id': 'run_and_fix', 'kind': 'yes_no', 'answer': True, 'via': 'assistant'})
    guided.save(state)
    runtime = guided.runtime_of(state)
    who = guided._git(state['project'], 'config', 'user.name').stdout.strip() or os.environ.get('USER') or 'the owner'
    source = guided.source(state)
    live_setup.authorize(source, runtime, who)
    detected = live_setup.detect(source)
    (runtime / 'setup').mkdir(parents=True, exist_ok=True)
    (runtime / 'setup/detected.json').write_text(json.dumps(detected, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    if detected['profile'] is None:
        return {'status': 'cannot_run', 'limitations': detected['limitations']}
    live_setup.write_profile(runtime, detected['profile'])
    return _start('run_try', state, {'proposal': None, 'mode': 'lock'})


def run_try(proposal=None, mode='lock', project=None):
    """Try the assistant's proposal (see live_setup.ASSIST_SYSTEM for its fields), refused when unsafe."""
    from . import live_setup
    state = project_state(project)
    runtime = guided.runtime_of(state)
    if not (runtime / 'run.json').is_file(): return {'status': 'not_set_up', 'what_now': 'Call run_setup first.'}
    if mode not in ('lock', 'baseline'): raise ValueError("mode is 'lock' (the app as developers run it) or 'baseline' (the production build)")
    refused = live_setup.safe(proposal or {})
    if refused:
        return {'status': 'refused', 'reasons': refused,
                'rules': 'Every address is 127.0.0.1 or localhost; commands are npm, npx, pnpm, yarn, bun, node or corepack only; '
                         'nothing deploys or reaches a hosted service; no real secret. Use {database_url} and {run_dir}.'}
    return _start('run_try', state, {'proposal': proposal, 'mode': mode})


def _run_job(project, arguments, progress):
    from . import live_setup
    state = guided.load(project)
    runtime, report = guided.runtime_of(state), guided.report_of(state)
    mode, proposal = arguments.get('mode') or 'lock', arguments.get('proposal')
    if proposal: live_setup.apply(runtime, proposal, mode=mode)
    attempt = len(list((runtime / 'setup').glob(f"{'baseline-' if mode == 'baseline' else ''}attempt-*.json"))) + 1
    progress(0, 1, 'installing and starting the app in the isolated copy')
    source = guided.source(state)
    record = live_setup.verify(source, runtime, attempt, report if (report / 'plan.json').is_file() else None, mode=mode)
    profile = _read(runtime / 'run.json')
    answer = {'mode': mode, 'attempt': attempt, 'runs': record['ok']}
    if mode == 'baseline':
        profile.setdefault('baseline', {})['verified'] = record['ok']
        live_setup.write_profile(runtime, profile)
    else:
        needs = live_setup.fixtures_needed(report) if (report / 'plan.json').is_file() else []
        known = {**profile.get('env', {}), **record.get('fixtures', {})}
        missing = [name for name in needs if name not in known]
        if record.get('fixtures'):
            profile.setdefault('env', {}).update({k: str(v) for k, v in record['fixtures'].items()})
        unset = [n for n in (_read(runtime / 'setup/detected.json')['facts'].get('env_names') or []) if n not in profile['env'] and n != 'NODE_ENV']
        limitations = [l for l in profile.get('limitations') or [] if not l.startswith(('run without a value', 'screens that need', 'the app could not'))]
        if unset and record['ok']: limitations.append('run without a value for: ' + ', '.join(unset[:12]))
        if missing: limitations.append('screens that need these values are not recorded: ' + ', '.join(missing))
        if not record['ok']: limitations.append('the app could not be made to answer: ' + (record.get('failure') or '')[:300])
        profile['limitations'] = sorted(set(limitations))
        live_setup.write_profile(runtime, profile)
        state = guided.load(project)
        state['setup'] = {'commit': _head(state), 'ok': record['ok'], 'attempts': attempt, 'limitations': profile['limitations']}
        state.pop('safety', None)
        guided.save(state)
        answer['fixtures_missing'] = missing
        if record['ok'] and (profile.get('baseline') or {}).get('build') and 'verified' not in profile['baseline']:
            progress(1, 2, 'building and starting the production version, to measure speed later')
            base = live_setup.verify(source, runtime, 1, mode='baseline')
            profile = _read(runtime / 'run.json')
            profile['baseline']['verified'] = base['ok']
            live_setup.write_profile(runtime, profile)
            answer['production_build_runs'] = base['ok']
            if not base['ok']: answer['production_failure'] = (base.get('failure') or '')[-2500:]
    page = record.get('page') or {}
    answer['first_page'] = {'status': page.get('status'), 'url': page.get('url'), 'text': (page.get('text') or '')[:800],
                            'others': [{k: o.get(k) for k in ('path', 'status', 'url')} for o in page.get('others') or []],
                            'errors': (page.get('errors') or [])[:5]} if page else None
    if not record['ok']:
        answer['failure'] = (record.get('failure') or '')[-3000:]
        folder = profile.get('app') or '.'
        answer['code_that_raised_it'] = live_setup.relevant_source(source, folder, record.get('failure') or '', limit=2, context=30)[:8000]
    if record.get('seed_output'): answer['seed_output'] = record['seed_output'][-1500:]
    answer['profile'] = {k: profile.get(k) for k in ('app', 'install', 'prepare', 'start', 'port', 'env', 'database', 'seed', 'checks', 'baseline', 'limitations')}
    answer['what_now'] = ('The app runs: call safety_net.' if record['ok'] and mode == 'lock' else
                          'Read the failure and the code, then call run_try with a proposal: {"env": {...complete environment...}, '
                          '"start": [...], "install": [[...]], "prepare": [[...]], "database": "postgres"|"none", '
                          '"seed_script": "<node script that signs in and saves storage state>", "fixtures": {...}}'
                          + (' (mode="baseline", with "build": [[...]] too)' if mode == 'baseline' else '') if not record['ok'] else
                          'The production build runs.')
    return answer


def safety_net(project=None):
    state = project_state(project)
    setup = state.get('setup') or {}
    if not _set_up(state, _head(state)): return {'status': 'not_set_up', 'what_now': 'Call run_setup first.'}
    return _start('safety_net', state, {})


def _safety_job(project, arguments, progress):
    state = guided.load(project)
    outcome = guided.safety_run(state, lambda n: progress(n - 1, 2, 'recording every screen' if n == 1 else 'measuring speed under load'))
    outcome['record'] = str(guided.runtime_of(state) / 'behavior-lock/results.json')
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


def fix_start(project=None, cards=None, size=10):
    from .waves import next_batch, plan as read_plan, ready
    state = project_state(project)
    guided.reconcile(state)
    if state.get('open_wave'):
        wave = state['open_wave']
        return {'status': 'open', 'batch': wave['number'], 'kept': list(wave['kept']), 'failed': wave['failed'],
                'to_do': [c for c in wave['cards'] if c not in wave['kept'] and c not in wave['failed']],
                'what_now': 'This batch is already open: fix the cards left with fix_edit (or fix_skip), then fix_finish.'}
    if not _consented(state): return {'status': 'needs_agreement', 'ask_the_person': CONSENT,
                                      'what_now': 'Ask the person; if they agree, call run_setup with person_agreed=true.'}
    if not _set_up(state, _head(state)): return {'status': 'not_set_up', 'what_now': 'Call run_setup first.'}
    waiting = next((w for w in reversed(state.get('waves') or []) if w.get('status') == 'applied'), None)
    if waiting: return {'status': 'waiting_decision', 'branch': waiting['branch'],
                        'what_now': f"The fixes on {waiting['branch']} wait for the person's decision: ask them, then accept or undo."}
    report = _report(state)
    known = {t['id']: t for t in read_plan(report)['tasks']}
    chosen = list(dict.fromkeys(cards)) if cards else next_batch(report, state.get('tried') or [], size=min(max(int(size), 1), 25))
    unknown = [c for c in chosen if c not in known]
    if unknown: raise ValueError(f'not cards of this plan: {", ".join(unknown[:5])}')
    undecided = [c for c in chosen if not ready(known[c])]
    if undecided:
        return {'error': f'{", ".join(undecided[:5])} need(s) a decision by the person before any fix (not ready): no batch '
                         'was opened', 'needs_decision': undecided,
                'what_now': 'Explain the decision each card needs (see `finding`), plainly, and leave it out of the batch; '
                            'call fix_start again with ready cards only, or with no cards for the next ready batch.'}
    if not chosen: return {'status': 'nothing_to_fix', 'what_now': 'No fixable card is left; the rest need the person\'s decision (see plan).'}
    return _start('fix_start', state, {'cards': chosen})


def _fix_start_job(project, arguments, progress):
    from .waves import change, commit, drop_last, open_batch, plan as read_plan
    from .execute import new_breakage
    from . import live_setup
    from .sandbox import head
    state = guided.load(project)
    report, runtime = guided.report_of(state), guided.runtime_of(state)
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
            'opened': _now(), 'keys': {c: cards[c]['key'] for c in arguments['cards']}}
    automatic = [c for c in arguments['cards'] if ((cards[c].get('codemod') or {}).get('dry_run') or {}).get('files_changed', 0) > 0]
    for index, card_id in enumerate(automatic, 1):
        progress(index, len(automatic) + 1, f'automatic fix of {card_id}')
        try:
            tool, _ = change(cards[card_id], root, report, None)
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
    state = guided.load(project)
    state['open_wave'] = wave
    guided.save(state)
    guided.publish(state)
    return {'batch': number, 'copy': str(root), 'fixed_automatically': list(wave['kept']), 'failed': wave['failed'],
            'to_do': [_brief(cards[c]) for c in arguments['cards'] if c not in wave['kept'] and c not in wave['failed']],
            'what_now': 'For each card in to_do: read it with `finding`, read the code with fix_read, then send the change with '
                        'fix_edit. Keep every feature, route and behaviour. When every card is kept or skipped, call fix_finish.'}


def _inside(root, relative):
    path = (Path(root) / relative).resolve()
    if Path(root).resolve() not in path.parents or '.git' in path.relative_to(Path(root).resolve()).parts:
        raise ValueError(f'{relative}: not a file of the project')
    return path


def fix_read(path, project=None, start=1, end=None):
    state = project_state(project)
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
    state = project_state(project)
    wave = _open(state)
    if card not in wave['cards']: raise ValueError(f"{card} is not in batch {wave['number']}: {', '.join(wave['cards'])}")
    if card in wave['kept']: return {'status': 'already_kept', 'what_now': 'This card is already fixed in the batch.'}
    if not edits: raise ValueError('no edit was sent')
    return _start('fix_edit', state, {'card': card, 'edits': edits, 'summary': summary})


def _fix_edit_job(project, arguments, progress):
    import tempfile
    from .execute import new_breakage
    from .facts.run import collect
    from .waves import batch_acceptance, commit, drop_last, plan as read_plan
    state = guided.load(project)
    wave, report = state['open_wave'], guided.report_of(state)
    root, card_id = Path(wave['root']), arguments['card']
    card = next(t for t in read_plan(report)['tasks'] if t['id'] == card_id)
    try:
        changed = _apply(root, arguments['edits'])
        commit(root, card, 'assistant')
    except (ValueError, RuntimeError, OSError, UnicodeDecodeError) as problem:
        guided._git(root, 'checkout', '--quiet', '--', '.')
        guided._git(root, 'clean', '-fdq')
        return {'card': card_id, 'kept': False, 'why': f'the edit could not be applied: {problem}',
                'what_now': 'Nothing changed. Read the file again with fix_read and send a corrected edit.'}
    progress(0, 1, 'checking the change: the problem is gone, nothing broke, no endpoint disappeared')
    with tempfile.TemporaryDirectory(prefix='eaos-edit-facts-') as out:
        collect(root.resolve(), out)
        broke = new_breakage(report, root, collected=out)
        exit_code = batch_acceptance(report, [card], root, collected=out).get(card_id)
    diff = guided._git(root, 'show', '--stat', '--format=', 'HEAD').stdout.strip()
    state = guided.load(project)
    wave = state['open_wave']
    if broke or exit_code not in (0, None):
        drop_last(root)
        why = (f'it broke something: {"; ".join(broke[:3])}' if broke else
               "the problem is still there: the card's own check still finds it" + (f' (exit {exit_code})' if exit_code else ''))
        return {'card': card_id, 'kept': False, 'why': why, 'files': changed,
                'what_now': 'The change was taken back. Fix the cause and send fix_edit again, or fix_skip with the reason.'}
    wave['kept'][card_id] = guided._git(root, 'rev-parse', 'HEAD').stdout.strip()
    wave['tools'][card_id] = 'assistant'
    wave['failed'].pop(card_id, None)
    wave.setdefault('summaries', {})[card_id] = arguments.get('summary') or ''
    guided.save(state)
    left = [c for c in wave['cards'] if c not in wave['kept'] and c not in wave['failed']]
    return {'card': card_id, 'kept': True, 'files': changed, 'diff': diff, 'left': left,
            'what_now': 'Next card with fix_edit.' if left else 'Every card is done: call fix_finish.'}


def fix_skip(card, reason, project=None):
    state = project_state(project)
    wave = _open(state)
    if card not in wave['cards']: raise ValueError(f"{card} is not in batch {wave['number']}")
    if card in wave['kept']:
        from .waves import rebuild
        wave['kept'].pop(card)
        rebuild(wave['root'], wave['base'], list(wave['kept'].values()))
    wave['failed'][card] = f'skipped: {reason}'[:300]
    guided.save(state)
    left = [c for c in wave['cards'] if c not in wave['kept'] and c not in wave['failed']]
    return {'card': card, 'skipped': True, 'left': left}


def fix_finish(project=None):
    state = project_state(project)
    wave = _open(state)
    left = [c for c in wave['cards'] if c not in wave['kept'] and c not in wave['failed']]
    if left: return {'status': 'cards_left', 'left': left, 'what_now': 'Fix them with fix_edit or skip them with fix_skip first.'}
    return _start('fix_finish', state, {})


def _fix_finish_job(project, arguments, progress):
    from .waves import apply as hand_over, finish_batch
    state = guided.load(project)
    wave = state['open_wave']
    report, runtime = guided.report_of(state), guided.runtime_of(state)
    steps = {'acceptance': (0, "every problem is gone, all changes together"), 'gates': (1, "the project's own checks and every screen"),
             'bisect': (2, 'finding the change that broke something')}
    summary = finish_batch(report, guided.source(state), runtime, wave['number'], Path(wave['root']), wave['base'], wave['cards'],
                           wave['kept'], wave['failed'], wave['tools'], lock=True,
                           say=lambda kind, *_: progress(steps[kind][0], 3, steps[kind][1]) if kind in steps else None)
    state = guided.load(project)
    record = {'number': wave['number'], 'base': wave['base'], 'cards': wave['cards'], 'kept': summary['kept'], 'failed': summary['failed'],
              'branch': summary['branch'], 'stat': summary['stat'], 'status': 'empty', 'via': 'assistant', 'keys': wave.get('keys') or {}}
    if summary['kept']:
        hand_over(state['project'], summary)
        record['status'] = 'applied'
        record['tip'] = guided._git(state['project'], 'rev-parse', summary['branch']).stdout.strip()
        state['applied'] = True
    state.setdefault('waves', []).append(record)
    state['tried'] = sorted(set(state.get('tried') or []) | set(wave['cards']))
    state.pop('open_wave', None)
    guided.save(state)
    guided.publish_fixes(state, record)
    guided.save(state)
    files = guided._git(state['project'], 'diff', '--stat', f"{wave['base']}..{summary['branch']}").stdout.strip() if summary['kept'] else ''
    return {'batch': wave['number'], 'branch': summary['branch'] if summary['kept'] else None, 'kept': summary['kept'],
            'failed': summary['failed'], 'changes': summary['stat'], 'files': files[-4000:],
            'what_now': (f"Tell the person, in plain words, what was fixed and that it is on the branch {summary['branch']}; "
                         "their current branch is unchanged. Ask whether to take it in (accept) or throw it away (undo). "
                         "The report counts these fixes as done only once they are taken in."
                         if summary['kept'] else 'No change passed every gate; nothing reached the project.')}


def accept(project=None, person_agreed=False):
    """The waiting branch into the person's current branch; then its branch is deleted and the report brought up to
    date, in the same call (eaos/guided.merge)."""
    from .ledger import load
    state = project_state(project)
    guided.reconcile(state)
    wave = next((w for w in reversed(state.get('waves') or []) if w.get('status') == 'applied'), None)
    if wave is None: return {'status': 'nothing_waiting', 'progress': (load(state) or {}).get('totals')}
    if not person_agreed:
        return {'status': 'needs_agreement', 'ask_the_person': f"Take the fixes on {wave['branch']} into your current branch?",
                'what_now': 'Only if the person says yes, call accept again with person_agreed=true.'}
    outcome = guided.merge(state, wave)
    if outcome == 'unsaved_changes':
        return {'status': 'unsaved_changes', 'what_now': 'The project has unsaved changes; ask the person to save (commit) them first.'}
    if outcome == 'conflict':
        return {'status': 'conflict', 'branch': wave['branch'],
                'what_now': f"The person's branch changed in the same places since the fixes; nothing was merged. Ask whether to merge "
                            f"{wave['branch']} by hand, resolving the conflict; once it is merged, `status` records it and deletes the branch."}
    state = guided.load(state['project'])
    page = branches.home(state) / 'REPORT.html'
    return {'status': 'accepted', 'branch': wave['branch'], 'branch_deleted': not guided._branch_exists(state, wave['branch']),
            'progress': (load(state) or {}).get('totals'), 'report_for_people': str(page),
            'what_now': 'Done: the branch is merged and deleted, and the report is up to date. Tell the person the progress in '
                        'plain words (closed of total, percent), then fix_start opens the next batch (no new check is needed).'}


def undo(project=None):
    from .waves import undo as drop
    state = project_state(project)
    guided.reconcile(state)
    wave = next((w for w in reversed(state.get('waves') or []) if w.get('status') == 'applied'), None)
    if wave is None: return {'status': 'nothing_to_undo'}
    outcome = drop(state['project'], wave['branch'])
    if outcome == 'merged': return {'status': 'merged', 'what_now': 'It is merged already; undoing it is a git revert, the person\'s decision.'}
    wave['status'] = 'undone'
    guided.save(state)
    guided.publish(state)
    return {'status': 'undone', 'branch': wave['branch']}


JOBS = {'audit': _audit_job, 'run_try': _run_job, 'safety_net': _safety_job, 'fix_start': _fix_start_job,
        'fix_edit': _fix_edit_job, 'fix_finish': _fix_finish_job}
