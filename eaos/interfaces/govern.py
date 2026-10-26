"""Governance without the Studio: the terminal's commands (eaos check, watch, waiting, fix, branches...) and the
assistant's governance tools (eaos/interfaces/mcp_server/govern.py), both thin callers of the Studio's own core, `Actions` and its
`BranchControl` (eaos/interfaces/studio_actions), so no rule is written twice and every surface sees the same runs.

Who starts a run. The Studio's dispatcher is a thread of whatever builds `Actions` (runs.py, `dispatch.lock`). The
callers here build it without that thread (`core`): a command never starts a run it would not live to follow. What
they queue is started by the project's Studio when it runs, else by one headless host (`eaos govern`, no HTTP), woken
on demand (`wake`), gone HOST_IDLE seconds after the queue is empty and no run is active. An answer that lets a run go
on is given in a host too: the work it starts lives in the process that answered.

What only the person decides: accept, undo, the branch, merging, deleting, protecting and cleaning up branches, a Fix
that accepts itself, and every answer waiting for them. A command shows what will happen and asks (or takes --yes); a
tool needs the person's word (person_agreed, or person_said ANSWER_SECONDS after the question was shown) and the
preview's confirm token; inside a run the Studio started (EAOS_STUDIO_RUN) each is refused, --yes or not
(mcp_server.refuse_in_studio_run, PERSON_ONLY).
"""
import fcntl
import functools
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from ..journeys import guided
from ..live.access import sign_in
from ..core.system.launch import HEADLESS
from ..core.project.runs import ACTIVE, RETRYABLE
from ..core.project import state as project_state
from .govern_words import WORDS, text_of

SIGN_IN = 'sign-in'          # what waits for the person while the check waits for their sign-in (eaos/live/access/sign_in.py)
HOST_IDLE = int(os.environ.get('EAOS_HOST_IDLE') or 120)   # seconds the host stays once nothing is queued or active (tests: less)
# What a branch change previews, then does (BranchControl's methods), and the body both take.
BRANCH_OPS = {'merge': ('preview_merge', 'merge'), 'delete': ('preview_delete', 'delete'), 'protect': ('preview_protect', 'protect'),
              'unprotect': ('preview_protect', 'protect'), 'cleanup': ('preview_cleanup', 'cleanup')}


# ---------------------------------------------------------------- the core, and who starts its runs

@functools.lru_cache(maxsize=8)
def _core(project):
    from .studio_actions import Actions
    return Actions(project, dispatch=False, lang=(project_state.load(project) or {}).get('lang') or 'ar')


def core(project=None):
    """The project's `Actions` without its dispatcher, one per project and process: a preview's confirm token is spent
    by the same locks that made it."""
    from ..journeys.agent_tools import state_of
    return _core(state_of(project)['project'])


def _held(path):
    """Whether a process holds the lock file at `path` (tried without waiting, and let go at once)."""
    with open(path, 'a+') as handle:
        try: fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError: return True
    return False


def wake(project, answer=None):
    """The host that starts the project's queued runs, unless the project's Studio or a host already runs; with `answer`
    (question, option, text), a host that gives it first, whatever runs. True when one was started."""
    from ..core.system import launch
    actions, state = core(project), project_state.load(core(project).project)
    if not answer and (_held(actions.store.folder / 'host.lock') or launch.running(state)): return False
    question, option, text = answer or (None, None, None)
    argv = [sys.executable, '-m', 'eaos', 'govern', str(actions.project), *(['--answer', question] if question else []),
            *(['--option', option] if option else []), *(['--text', text] if text else [])]
    launch.detach(state, argv, launch.own_env(**{HEADLESS: '1'}), 'govern.log', 'wb')   # one host's words, written again by the next
    return True


def host(project, answer=None, idle=HOST_IDLE):
    """`eaos govern`: the project's runs started and followed without the Studio, by this process's dispatcher while it
    holds `dispatch.lock` (a Studio that holds it starts them instead), until nothing is queued, active or followed here
    for `idle` seconds. `answer` (question, option, text) is given first; a second host with no answer leaves at once."""
    from .studio_actions import Actions
    os.environ[HEADLESS] = '1'
    actions = Actions(project, lang=(project_state.load(Path(project).resolve()) or {}).get('lang') or 'ar')
    try:
        if answer: actions.manager.answer(*answer, via='terminal')
        with open(actions.store.folder / 'host.lock', 'a+') as lock:
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                if not answer: return 0
            quiet = time.monotonic()
            while time.monotonic() - quiet < idle:
                if _busy(actions): quiet = time.monotonic()
                time.sleep(1)
    finally:
        actions.close()
    return 0


def _busy(actions):
    """Work in hand: a run this process follows, a queued run, or a run still active."""
    return bool(actions.manager.watched or actions.store.queue()
                or any(row.get('state') in ACTIVE and not row.get('read') for row in actions.store.all()))


# ---------------------------------------------------------------- what only the person decides

_SHOWN = {}         # what waits for the person -> when an assistant was shown it (`waiting`), in this process


def shown(ident):
    """An assistant was shown what waits under `ident` now (the first time counts): `heard` measures from then."""
    _SHOWN.setdefault(ident, time.monotonic())


def heard(ident, person_said):
    """None when `person_said` is the person's own answer to `ident`: given, and ANSWER_SECONDS or more after the
    question was shown to the assistant; else why not (agent_tools.choose_branch's rule)."""
    from ..journeys.agent_tools import ANSWER_SECONDS
    if not str(person_said or '').strip(): return 'no reply from the person was given'
    if ident not in _SHOWN: return 'this was never shown to you: list it with waiting, ask the person, then answer'
    since = time.monotonic() - _SHOWN[ident]
    return None if since >= ANSWER_SECONDS else f'the question was shown {int(since)} seconds ago: the person has not answered yet'


# ---------------------------------------------------------------- the check and the runs

def ai_inputs(assistant):
    """The check's AI as the person chose it: none, a named assistant, or the one kept (None)."""
    if not assistant: return {}
    return {'use_assistant': False} if assistant == 'none' else {'use_assistant': True, 'assistant': assistant}


def check_inputs(paths=None, mode=None, assistant=None, sign_in=None, published=None, run_app=None, again_from=None):
    """A new check (always fresh: a check asked for is a new one), of these paths, in this mode, with this AI, signing in
    to the app this way (kept), reading the published address named for this check, the app run when agreed (kept);
    `again_from`: the last check goes on from that stage instead (the Studio's "Redo from here")."""
    chosen = {'paths': list(paths or []), 'mode': mode, 'sign_in': sign_in, 'published': published, 'run_app': run_app, 'again_from': again_from}
    return {'fresh': not again_from, **{key: value for key, value in chosen.items() if value}, **ai_inputs(assistant)}


def estimate(project, inputs):
    """The check's preview (eaos/journeys/check_choices.py estimate): its minutes, and what it offers."""
    shown = core(project).preview('audit', {'inputs': inputs})
    return {'estimate': shown['estimate'], 'check': shown.get('check')}


def start_check(project, inputs, lang=None):
    """The check queued, as the Studio queues it, and its host woken."""
    actions = core(project)
    record = actions.create({'action': 'audit', 'inputs': inputs, **({'lang': lang} if lang else {})})
    wake(actions.project)
    return actions.public(record)


def chosen_run(actions, run=None, *preferences):
    """The run asked for, else the newest in the first of `preferences` (tuples of states; None: any) that has one."""
    if run: return actions.store.load(run)
    rows = [row for row in actions.store.all() if not row.get('read')]
    for states in preferences:
        found = next((row for row in rows if states is None or row.get('state') in states), None)
        if found: return found
    raise LookupError('no such run here: eaos runs lists them')


CONTROLS = {'stop': (*ACTIVE, 'queued'), 'pause': ('running',), 'resume': ('paused',), 'retry': RETRYABLE}


def control(project, operation, run=None):
    """Stop, pause, resume or retry a run (the newest it applies to by default), as the Studio's buttons do; a retried
    run wakes the host. The stop's last resort (a kill after the grace) is waited for here, before this process ends."""
    actions = core(project)
    record = chosen_run(actions, run, CONTROLS[operation])
    before = set(threading.enumerate())
    done = actions.run_operation(record['id'], operation, {}, f'/api/runs/{record["id"]}/{operation}')['run']
    for thread in set(threading.enumerate()) - before: thread.join(10)
    if operation == 'retry': wake(actions.project)
    return done


def progress(actions, record):
    """Where a run is: its stage (done of total), the minutes left at its pace so far, and what the assistant used."""
    last = next((e['data'] for e in reversed(actions.store.events(record['id'])) if e['kind'] == 'progress'), {})
    done, total = last.get('done') or 0, last.get('total') or 0
    used = _used(actions, record) or {}
    return {'stage': last.get('stage'), 'done': done, 'total': total, **_pace(record, done, total),
            'cost_usd': used.get('cost_usd'), 'tokens': sum(used.get(k) or 0 for k in ('input', 'cache_write', 'output', 'thinking'))}


def _pace(record, done, total):
    """{seconds, minutes_left}: how long the run has worked, and what is left of it at its pace so far."""
    began = datetime.fromisoformat(record['started']) if record.get('started') else None
    elapsed = (datetime.now(timezone.utc) - began).total_seconds() if began else 0
    running = done and total and record.get('state') == 'running'
    return {'seconds': round(elapsed) if began else None,
            'minutes_left': round(elapsed / done * (total - done) / 60) if running else None}


def _used(actions, record):
    """What a run's assistant used so far (eaos/core/system/usage.py); a check's, the calls of the check under way."""
    from ..core.system.usage import of_check, of_run
    found = of_run(actions.store.path(record['id']))
    if found or record.get('action') != 'audit' or not record.get('started'): return found
    if (record.get('inputs') or {}).get('use_assistant') is False: return None     # never the cost of a check before it
    return of_check(guided.report_of(project_state.load(actions.project))).get('total')


def show_run(project, run=None):
    """One run (the active one by default): its record, where it is, and its last events."""
    actions = core(project)
    record = chosen_run(actions, run, ACTIVE, ('queued',), None)
    return {'run': actions.public(record), 'progress': progress(actions, record), 'events': actions.store.events(record['id'])[-15:]}


# ---------------------------------------------------------------- what waits for the person

def waiting(project):
    """Everything waiting for the person: the runs' questions, the report's questions not answered yet, the branch
    handed over for accept or undo, and the sign-in a check waits for."""
    from ..core.project.state import waiting_batch
    actions = core(project)
    rows = _questions(actions)
    state = project_state.load(actions.project) or {}
    wave = waiting_batch(state)
    if wave: rows.append({'id': wave['branch'], 'kind': 'branch', 'text': WORDS['branch_waits'], 'branch': wave['branch'],
                          'options': [{'id': 'accept', 'label': 'eaos accept'}, {'id': 'undo', 'label': 'eaos undo'}]})
    if state.get('workspace') and sign_in.asked(state['workspace']):
        rows.append({'id': SIGN_IN, 'kind': 'sign_in', 'text': WORDS['sign_in_waits'],
                     'options': [{'id': SIGN_IN, 'label': 'eaos sign-in'}, {'id': sign_in.SIGNED_OUT, 'label': WORDS['signed_out_option']}]})
    return [{**row, 'text': {lang: text_of(row['text'], lang).format(branch=row.get('branch')) for lang in ('en', 'ar')}} for row in rows]


def _questions(actions):
    """The runs' questions, then the report's questions not answered yet, as waiting lists them."""
    rows = [{'id': q['id'], 'kind': 'question', 'run': q.get('run'), 'text': q.get('text'), 'options': q.get('options') or [],
             'recommendation': q.get('recommendation')} for q in actions.questions()]
    return rows + [{'id': d['id'], 'kind': 'decision', 'scope': d['scope'], 'text': d['question'].get('question'),
                    'options': d['question'].get('options') or [], 'recommendation': d['question'].get('recommended_option')}
                   for d in actions.report_decisions() if not d['response'] and d['question'].get('state', 'waiting') == 'waiting']


def signing_in(project):
    """What the check asks while it waits for the person to sign in to their app (eaos/live/access/sign_in.py asked), or None."""
    return sign_in.asked(project_state.load(core(project).project)['workspace'])


def answer(project, ident, option=None, text=None, assistant=None):
    """The person's answer to what waits under `ident`: a report question here (its review run queued for `assistant`,
    the host woken); a run's question in a host, where the work it lets go on lives (it is checked here first)."""
    actions = core(project)
    row = next((r for r in waiting(project) if r['id'] == ident), None)
    if row is None: raise LookupError(f'nothing waits for an answer under {ident}: eaos waiting lists what does')
    if row['kind'] == 'branch': raise LookupError('a branch is taken in with eaos accept, or thrown away with eaos undo')
    if row['kind'] == 'sign_in':
        if option != sign_in.SIGNED_OUT: raise LookupError('the person signs in with eaos sign-in, or in the Studio\'s Waiting for you')
        sign_in.answer(project_state.load(actions.project)['workspace'], sign_in.SIGNED_OUT)
        return {'status': 'answered'}
    if row['kind'] == 'decision':
        decided = actions.answer_decision(ident, {'scope': row['scope'], 'option': option, 'text': text, 'assistant': assistant})
        wake(actions.project)
        return {'status': 'answered', 'decision': decided}
    return _answer_run(actions, row, option, text)


def _answer_run(actions, row, option, text):
    """A run's question answered in a host (where the work it lets go on lives), checked here first; answered once the
    run took it within twenty seconds, else handed over."""
    ident = row['id']
    actions.manager._checked(ident, option, text)
    wake(actions.project, (ident, option, text))
    end = time.monotonic() + 20
    while time.monotonic() < end and not any(a['id'] == ident for a in actions.store.load(row['run']).get('answered') or []): time.sleep(0.25)
    record = actions.store.load(row['run'])
    return {'status': 'answered' if any(a['id'] == ident for a in record.get('answered') or []) else 'handed_over', 'run': actions.public(record)}


# ---------------------------------------------------------------- the verbs on a selection

def selection_of(ids=(), group=None):
    """The Studio's selection (eaos/journeys/fix/selection.py) from card ids, or a group as by=value."""
    if group:
        by, _, value = str(group).partition('=')
        return {'kind': 'group', 'group': {'by': by.strip(), 'value': value.strip()}}
    return {'kind': 'cards', 'cards': [str(i) for i in ids or []]}


def verb_preview(project, verb, selection, auto_accept=False, assistant=None):
    """What the verb would do, as the Studio's preview says it (cards, files, batches, estimate, risk, confirm token)."""
    return core(project).preview(verb, {'verb': verb, 'selection': selection, 'assistant': assistant,
                                        'inputs': {'auto_accept': True} if auto_accept else {}})


def verb_start(project, preview, confirm=None, assistant=None):
    """The run its preview showed, with that preview's confirm token (a Fix's), queued, and the host woken."""
    from .studio_actions import _where_of
    actions = core(project)
    record = actions.create({'verb': preview['verb'], 'selection': preview['selection'], 'assistant': assistant, 'confirm': confirm,
                             'inputs': {'auto_accept': True} if preview.get('auto_accept') else {}, 'where': _where_of(preview.get('where'))})
    wake(actions.project)
    return actions.public(record)


# ---------------------------------------------------------------- branches

def _branch_body(operation, name=None, target=None):
    return {'merge': {'source': name, 'target': target}, 'delete': {'branch': name}, 'protect': {'branch': name, 'protected': True},
            'unprotect': {'branch': name, 'protected': False}, 'cleanup': {}}[operation]


def _control(project):
    control = core(project).branches
    if not control.is_repo(): raise LookupError('this project folder is not a git repository')
    return control


def branch_preview(project, operation, name=None, target=None):
    """What a branch change would do (BranchControl's preview), with its confirm token(s) when it can happen."""
    return getattr(_control(project), BRANCH_OPS[operation][0])(_branch_body(operation, name, target))


def branch_change(project, operation, preview, confirm, confirm_unmerged=None):
    """The change its preview showed, at the heads it showed, with that preview's confirm token(s)."""
    body = {**_branch_body(operation, preview.get('branch') or preview.get('source'), preview.get('target')), **preview,
            'confirm': confirm, 'confirm_unmerged': confirm_unmerged, 'unchecked': bool(preview.get('needs_unchecked_ack')), 'unchecked_ack': True}
    return getattr(_control(project), BRANCH_OPS[operation][1])(body)


def restore(project, recovery):
    return _control(project).restore({'recovery': recovery})


# ---------------------------------------------------------------- history, comparison, use, freshness

def _section(project, name):
    from ..journeys.fix.selection import studio_folder
    folder = studio_folder(core(project).project)
    try: return json.loads((folder / f'{name}.json').read_text(encoding='utf-8')) if folder else None
    except (OSError, ValueError): return None


def history(project):
    """Every check on record, oldest first (studio/history.json: eaos/report/studio/history.py), and what changed between."""
    found = _section(project, 'history') or {}
    return {'scans': found.get('scans') or [], 'events': (found.get('events') or [])[-20:], 'missing': found.get('missing') or []}


def _delta(before, after):
    return round(after - before, 4) if isinstance(before, (int, float)) and isinstance(after, (int, float)) else None


def compare(project, first, second):
    """Two checks of the history side by side: the score, the open cards (each severity) and the cards closed between."""
    found = _section(project, 'history') or {}
    scans = {scan['id']: scan for scan in found.get('scans') or []}
    missing = next((name for name in (first, second) if name not in scans), None)
    if missing: raise LookupError(f'no check named {missing}: eaos history lists them')
    a, b = scans[first], scans[second]
    opened = a.get('open') or {}, b.get('open') or {}
    return {'from': a, 'to': b, 'score': _delta(a.get('score'), b.get('score')), 'open': _delta(a.get('open_total'), b.get('open_total')),
            'severity': {s: _delta(opened[0].get(s), opened[1].get(s)) for s in opened[1]},
            'closed': _delta(a.get('closed'), b.get('closed')), 'closed_between': _closed_between(found, a, b)[:50]}


def _closed_between(found, a, b):
    """The cards closed after the check `a` and up to the check `b` (not those new in between)."""
    return [c for c in found.get('cards') or [] if a['at'] < (c.get('at') or '') <= b['at'] and not c.get('new')]


def usage(project):
    """What the assistant used: the last check stage by stage, every run, and the chat (Actions.usage)."""
    return core(project).usage()
