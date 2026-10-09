"""The real command-centre trial (indicator F15, NS46.T11) and the live owner-controls evidence (NS46.T17).

    python tools/studio_trial.py <project> [--source PATH|URL] [--assistant claude|codex] [--lang ar|en]
                                 [--measure DIR] [--skip controls,views]

From the Studio alone, the way the owner uses it: a copy of the project (git clone of --source; EAOS itself defaults to
this checkout, a corpus project to its pinned clone under $EAOS_CORPUS) gets its own EAOS home, `eaos studio` serves it
on 127.0.0.1, and a real Chromium (Playwright from the EAOS toolchain, driven by studio/scripts/trial.mjs) does
everything by clicking: check the project, answer report decisions (an option, a typed answer, the keyboard alone, a
send that fails and keeps its draft), pick a group of cards and fix it with the real assistant chosen in the preview,
answer the assistant's questions in the inbox (the run question first with a typed answer that must not count as
consent), accept the branch behind its confirmation, then explain, plan and verify runs with the queue controls
(reorder, pause, resume, stop, retry). Between the browser phases this script restarts the server, re-exports the
data, starts a second project's server, and probes the HTTP API (token, Host, CSRF, Origin, confirm tokens,
idempotent and concurrent answers). The screen gate (eaos/screens/audit.py: overflow, layout width, first scroll,
axe, 44 px targets) runs on the decisions page at phone, tablet and desktop, Arabic and English, light and dark.

Project code runs only when the run question is answered yes, and the trial answers yes only for EAOS itself (this
repository, run from a frozen copy) or a project the owner authorized in docs/north-star.json `live_corpus`;
otherwise it answers No and records why. No mock: a missing assistant, a refused login or a broken step is a failure.

Writes, under --measure (default $EAOS_MEASURE):
    studio/<project>/trial.json          F15, judged by acceptance ns46_studio.CommandCentreTrial
    owner-controls/<project>/trial.json  NS46.T17, judged by acceptance owner_controls.OwnerControls
and the screenshots, videos, phase logs and API evidence beside them.

    python tools/studio_trial.py check <work> <what> [args]    the browser's callbacks (JSON on stdout)
    python tools/studio_trial.py serve <report> <project> <port> <record>    a second project's server
"""
import argparse
import concurrent.futures
from http.client import HTTPConnection
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
import dev_paths  # noqa: E402

ASSISTANTS = {'claude': 'Claude Code', 'codex': 'Codex'}
PYTHON = sys.executable
TOOL = Path(__file__).resolve()
DRIVER = ROOT / 'studio/scripts/trial.mjs'
# Typed answers: leading and trailing spaces, a newline, both scripts, and the word "yes" that must never become consent
RUN_ANSWER = '  نعم؟ yes — but first explain what will run on my computer,\nand where it runs.  '
DECISION_ANSWER = 'Keep both for now; decide after the next check.\nنقرر بعد الفحص القادم.'
KEYBOARD_ANSWER = 'Typed with the keyboard only: decide after the batch is reviewed.'
DRAFT_ANSWER = 'This draft must survive a failed send.\nمسودة يجب أن تبقى بعد فشل الإرسال.'
MAX_GROUP = 4            # a group the assistant fixes in one sitting
LIMITS = {'scan': 3 * 3600, 'decisions': 1800, 'persist': 600, 'fix': 4 * 3600, 'controls': 2 * 3600}


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _load(path, default=None):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def _write(path, data, private=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    if private: path.chmod(0o600)
    return path


def shipped():
    return (_load(ROOT / 'eaos/data/studio/SOURCE.json') or {}).get('source_sha256')


def state_words():
    return json.loads((ROOT / 'docs/studio-actions.json').read_text(encoding='utf-8'))['lifecycle']['states']


# ---------------------------------------------------------------- what may run, and on what

def authorization(name, record=None):
    """Whether the trial may say yes to running the project's code: EAOS itself, or a project of `live_corpus`."""
    if name == 'EAOS':
        return {'run_code': True, 'why': 'EAOS itself: the repository under development, run from a frozen copy'}
    record = record if record is not None else json.loads((ROOT / 'docs/north-star.json').read_text(encoding='utf-8'))
    for spec in record.get('live_corpus') or []:
        if spec.get('name') == name and spec.get('authorization'):
            return {'run_code': True, 'why': spec['authorization'], 'commit': spec.get('commit'), 'source': spec.get('source')}
    return {'run_code': False, 'why': f'{name} is not in docs/north-star.json live_corpus: the trial answers No to running its code'}


def default_source(name):
    if name == 'EAOS': return str(ROOT)
    pinned = dev_paths.CORPUS / name
    return str(pinned) if pinned.is_dir() else None


# ---------------------------------------------------------------- what to pick in the report

def recommended_option(decision):
    """The option the recommendation names, as the Studio shows it (studio/src/components/Story.tsx): the explicit id,
    else the one option whose label opens the recommendation; None rather than a guess."""
    options = decision.get('options') or []
    if decision.get('recommended_option'):
        return next((o for o in options if o.get('id') == decision['recommended_option']), None)
    text = str(decision.get('recommendation') or '').strip()
    found = []
    for option in options:
        label = str(option.get('label') or '').strip()
        rest = text[len(label):]
        if label and text.startswith(label) and (not rest or rest[0] in ' \t:،,.-–'): found.append(option)
    return found[0] if len(found) == 1 else None


def pick_decisions(rows):
    """Distinct waiting report questions for each live case: {role: row}. `recommended` needs a recommendation and a
    second option; the others any waiting question with options."""
    waiting = [r for r in rows if not r.get('response') and (r.get('question') or {}).get('state', 'waiting') == 'waiting'
               and len((r.get('question') or {}).get('options') or []) >= 2]
    chosen, used = {}, set()
    rec = next((r for r in waiting if recommended_option(r['question'])), None)
    if rec:
        chosen['recommended'] = rec
        used.add(rec['id'])
    for role in ('custom', 'keyboard', 'draft', 'concurrent'):
        row = next((r for r in waiting if r['id'] not in used), None)
        if row:
            chosen[role] = row
            used.add(row['id'])
    return chosen


def _studio_rows(studio, name):
    data = _load(Path(studio) / f'{name}.json') or {}
    return data


def fixable_cards(studio):
    cards = (_studio_rows(studio, 'cards').get('cards') or [])
    return [c for c in cards if c.get('fixable') and not c.get('needs_decision') and c.get('state', 'open') == 'open']


def choose_group(studio, limit=MAX_GROUP):
    """The smallest whole group the Studio offers (studio/src/command/groups.ts: area, severity, plan step) with two to
    `limit` cards, every one fixable and needing no decision; else two such cards picked one by one."""
    cards = _studio_rows(studio, 'cards').get('cards') or []
    ok = {c['id'] for c in fixable_cards(studio)}
    groups = []
    for by, key in (('step', 'milestone'), ('area', 'category'), ('severity', 'severity')):
        values = {}
        for card in cards:
            if card.get(key): values.setdefault(card[key], []).append(card['id'])
        for value, ids in values.items():
            if 2 <= len(ids) <= limit and set(ids) <= ok: groups.append((len(ids), by, value, ids))
    if groups:
        size, by, value, ids = sorted(groups)[0]
        return {'kind': 'step' if by == 'step' else 'group', 'by': by, 'value': value, 'cards': ids}
    picked = [c['id'] for c in sorted(fixable_cards(studio), key=lambda c: ({'high': 0, 'medium': 1, 'low': 2}.get(c.get('severity'), 3), c['id']))][:2]
    return {'kind': 'cards', 'by': None, 'value': None, 'cards': picked}


# ---------------------------------------------------------------- judging

def case(case_id, passed, evidence, notes=''):
    return {'id': case_id, 'pass': bool(passed), 'kind': 'live', 'evidence': evidence, 'notes': notes}


def understood(seen, lang):
    """Every run state the trial saw on screen, said in the plain words of the contract in the page's language."""
    words = state_words()
    return {state: bool(text) and text.strip() == words.get(state, {}).get(lang) for state, text in (seen or {}).items()}


def steps_per_task(actions):
    """The person's clicks and typed answers per task (check, fix, each answer, accept)."""
    tasks = [task for task, count in (actions or {}).items() if count]
    return round(sum(actions.values()) / len(tasks), 2) if tasks else None


# ---------------------------------------------------------------- the HTTP API, as any client sees it

def http(port, method, path, headers=None, body=None, host=None, timeout=60):
    connection = HTTPConnection('127.0.0.1', port, timeout=timeout)
    sent = {'Host': host or f'127.0.0.1:{port}', **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        sent['Content-Type'] = 'application/json'
    try:
        connection.request(method, path, body=data, headers=sent)
        response = connection.getresponse()
        raw = response.read()
    except OSError as problem:
        return None, {'error': str(problem)}
    finally:
        connection.close()
    try: payload = json.loads(raw) if raw else None
    except ValueError: payload = {'raw': raw[:300].decode('utf-8', 'replace')}
    return response.status, payload


class Api:
    def __init__(self, info):
        self.port, self.token = info['port'], info['token']
        self.origin = f'http://127.0.0.1:{self.port}'
        self.csrf = (self.get('/api/session')[1] or {}).get('csrf')

    def get(self, path):
        return http(self.port, 'GET', path, {'X-EAOS-Token': self.token})

    def post(self, path, body=None, **changed):
        headers = {'X-EAOS-Token': self.token, 'X-EAOS-CSRF': self.csrf or '', 'Origin': self.origin}
        for key, value in changed.items():
            name = {'token': 'X-EAOS-Token', 'csrf': 'X-EAOS-CSRF', 'origin': 'Origin'}[key]
            if value is None: headers.pop(name, None)
            else: headers[name] = value
        return http(self.port, 'POST', path, headers, body if body is not None else {})


# ---------------------------------------------------------------- the servers

class Server:
    """`eaos studio` on the project (main), or the same server app on another project (create_app via `serve`)."""

    def __init__(self, work, name, project, home, port, report=None):
        self.work, self.name, self.project, self.home, self.port, self.report = Path(work), name, Path(project), Path(home), port, report
        self.info_path = self.work / f'server-{name}.json'
        self.process = None
        self.starts = 0

    def env(self):
        return {**os.environ, 'EAOS_HOME': str(self.home), 'PYTHONPATH': str(ROOT)}

    def start(self, timeout=60):
        self.starts += 1
        log = open(self.work / f'server-{self.name}.log', 'ab')
        if self.report is None:
            argv = [PYTHON, '-m', 'eaos', 'studio', str(self.project), '--no-open', '--port', str(self.port)]
        else:
            record = self.work / f'record-{self.name}.json'
            record.unlink(missing_ok=True)
            argv = [PYTHON, str(TOOL), 'serve', str(self.report), str(self.project), str(self.port), str(record)]
        self.process = subprocess.Popen(argv, cwd=self.work, env=self.env(), stdout=log, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, start_new_session=True)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            record = self._record()
            if record and http(self.port, 'GET', '/api/session', {'X-EAOS-Token': record['token']})[0] == 200:
                info = {'name': self.name, 'port': self.port, 'token': record['token'], 'pid': self.process.pid,
                        'base': f'http://127.0.0.1:{self.port}/', 'started': now(), 'starts': self.starts}
                _write(self.info_path, info, private=True)
                return info
            if self.process.poll() is not None: break
            time.sleep(0.3)
        raise RuntimeError(f'the {self.name} Studio server did not answer on port {self.port} (see {self.work}/server-{self.name}.log)')

    def _record(self):
        if self.report is not None: return _load(self.work / f'record-{self.name}.json')
        for path in sorted((self.home / 'studio').glob('*.json')):
            record = _load(path) or {}
            if record.get('port') == self.port and record.get('token'): return record
        return None

    def stop(self):
        if not self.process or self.process.poll() is not None: return
        try: os.killpg(self.process.pid, signal.SIGTERM)
        except OSError: pass
        try: self.process.wait(15)
        except subprocess.TimeoutExpired:
            try: os.killpg(self.process.pid, signal.SIGKILL)
            except OSError: pass
            self.process.wait(5)

    def restart(self):
        self.stop()
        return self.start()


def free_port():
    import socket
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def serve_main(report, project, port, record):
    from eaos.api.server import Keys, bind, create_app, serve
    sock = bind(int(port))
    app = create_app(Path(report), project=Path(project), keys=Keys(port=sock.getsockname()[1]))
    _write(record, {'port': app.state.ctx.keys.port, 'token': app.state.ctx.keys.token, 'pid': os.getpid()}, private=True)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try: serve(app, sock)
    except KeyboardInterrupt: pass
    return 0


# ---------------------------------------------------------------- the project's state, read as EAOS reads it

def _guided(home, project):
    os.environ['EAOS_HOME'] = str(home)
    from eaos import guided
    return guided, guided.load(Path(project).resolve()) or {}


def _runs_folder(home, project):
    guided, _ = _guided(home, project)
    return guided.workspace(Path(project).resolve()) / 'runs'


def _run_record(home, project, run):
    return _load(_runs_folder(home, project) / run / 'run.json') or _load(_runs_folder(home, project) / f'{run}.json') or {}


def _events(home, project, run):
    """A run's events as the store keeps them (the API's events route is a live stream that ends only with the run)."""
    events = []
    try:
        with open(_runs_folder(home, project) / run / 'events.jsonl', encoding='utf-8') as lines:
            for line in lines:
                try: events.append(json.loads(line))
                except ValueError: pass
    except OSError: pass
    return events


def check(work, what, *args):
    """The browser's callbacks: what only the server side can see, at the moment the browser asks."""
    work = Path(work)
    context = _load(work / 'context.json')
    home, project = context['home'], context['project']
    api = Api(_load(work / 'server-main.json'))
    if what == 'consent':
        _, state = _guided(home, project)
        return {'consent': bool((state.get('consent') or {}).get('run_and_fix')), 'at': now()}
    if what == 'custom-run':
        run, question = args[0], args[1]
        record = (api.get(f'/api/runs/{run}')[1] or {}).get('run') or {}
        answered = next((a for a in record.get('answered') or [] if a.get('id') == question), None)
        _, state = _guided(home, project)
        return {'answered': answered, 'exact': bool(answered) and answered.get('text') == RUN_ANSWER and answered.get('option') is None,
                'consent': bool((state.get('consent') or {}).get('run_and_fix')), 'state': record.get('state'),
                'clarifying': bool(record.get('pending_question')), 'at': now()}
    if what == 'run-answer-idempotent':
        run, question, option = args[0], args[1], args[2]
        before = len([e for e in _events(home, project, run) if e.get('kind') == 'answer'])
        same = api.post(f'/api/questions/{question}/answer', {'option': option})
        other = next((o['id'] for o in (_question_of(home, project, run, question) or {}).get('options', []) if o['id'] != option), 'no-such-option')
        conflict = api.post(f'/api/questions/{question}/answer', {'option': other})
        after = len([e for e in _events(home, project, run) if e.get('kind') == 'answer'])
        return {'same_status': same[0], 'conflict_status': conflict[0], 'conflict': (conflict[1] or {}).get('error'),
                'answer_events_before': before, 'answer_events_after': after, 'at': now()}
    if what == 'guards':
        run = args[0]
        no_confirm = api.post(f'/api/runs/{run}/accept', {})
        forged = api.post(f'/api/runs/{run}/accept', {'confirm': 'x.9999999999.' + '0' * 64})
        undo = api.post(f'/api/runs/{run}/undo', {})
        preview = api.post('/api/actions/undo/preview', {'inputs': {}})
        token = ((preview[1] or {}).get('confirm') or {}).get('token')
        wrong_action = api.post(f'/api/runs/{run}/accept', {'confirm': token}) if token else (None, None)
        _, state = _guided(home, project)
        waiting = [w.get('branch') for w in state.get('waves') or [] if w.get('status') == 'applied']
        return {'accept_without_confirm': no_confirm[0], 'accept_forged_confirm': forged[0], 'undo_without_confirm': undo[0],
                'accept_with_undo_token': wrong_action[0], 'branch_still_waiting': waiting, 'at': now()}
    if what == 'undo-after-accept':
        run = args[0]
        preview = api.post('/api/actions/undo/preview', {'inputs': {}})
        token = ((preview[1] or {}).get('confirm') or {}).get('token')
        status, payload = api.post(f'/api/runs/{run}/undo', {'confirm': token})
        result = (payload or {}).get('result') or {}
        reuse = api.post(f'/api/runs/{run}/undo', {'confirm': token})
        return {'status': status, 'result': {k: result.get(k) for k in ('status', 'error', 'what_now')},
                'outcome': ((payload or {}).get('run') or {}).get('outcome'), 'reused_token_status': reuse[0], 'at': now()}
    if what == 'kill-run':
        run = args[0]
        record = (api.get(f'/api/runs/{run}')[1] or {}).get('run') or {}
        pid = _run_pid(home, project, run)
        if pid:
            try: os.killpg(os.getpgid(pid), signal.SIGKILL)
            except OSError:
                try: os.kill(pid, signal.SIGKILL)
                except OSError: pid = None
        return {'killed': pid, 'state': record.get('state'), 'at': now()}
    if what == 'queue':
        listed = api.get('/api/runs?all=1')[1] or {}
        return {'queue': listed.get('queue') or [], 'runs': len(listed.get('runs') or []), 'at': now()}
    raise SystemExit(f'unknown check {what}')


def _question_of(home, project, run, question):
    for event in _events(home, project, run):
        if event.get('kind') == 'question' and (event.get('data') or {}).get('id') == question: return event['data']
    return None


def _run_pid(home, project, run):
    folder = _runs_folder(home, project)
    for path in (folder / run / 'run.json', folder / f'{run}.json'):
        record = _load(path)
        if record and record.get('pid'): return int(record['pid'])
    for path in folder.rglob('*.json'):
        record = _load(path)
        if isinstance(record, dict) and record.get('id') == run and record.get('pid'): return int(record['pid'])
    return None


# ---------------------------------------------------------------- the browser

def browser(phase, work, out, given, limit):
    """One phase of studio/scripts/trial.mjs; its result (phase.json) or the reason it has none."""
    folder = Path(out) / 'phases'
    folder.mkdir(parents=True, exist_ok=True)
    given = {**given, 'limit_ms': limit * 1000}
    _write(folder / f'{phase}.input.json', given)
    env = {**os.environ, 'EAOS_TRIAL_PHASE': phase, 'EAOS_TRIAL_WORK': str(work), 'EAOS_TRIAL_OUT': str(out),
           'EAOS_TRIAL_INPUT': str(folder / f'{phase}.input.json'), 'EAOS_TRIAL_PYTHON': PYTHON, 'EAOS_TRIAL_TOOL': str(TOOL)}
    began = time.monotonic()
    with open(folder / f'{phase}.log', 'w', encoding='utf-8') as log:
        try:
            done = subprocess.run(['node', str(DRIVER)], env=env, stdout=log, stderr=subprocess.STDOUT, timeout=limit)
            code = done.returncode
        except subprocess.TimeoutExpired:
            code = 'timeout'
    result = _load(folder / f'{phase}.json') or {'ok': False, 'errors': [f'{phase}: the browser wrote no result']}
    result.update(exit=code, seconds=round(time.monotonic() - began, 1))
    _write(folder / f'{phase}.json', result)
    print(f'[{now()}] browser phase {phase}: exit {code}, ok {result.get("ok")}, {result["seconds"]} s', flush=True)
    return result


# ---------------------------------------------------------------- the live cases the API alone proves

def auth_case(api, port):
    session = api.get('/api/session')
    probes = {
        'session_with_token': session[0],
        'no_token': http(port, 'GET', '/api/session')[0],
        'wrong_token': http(port, 'GET', '/api/session', {'X-EAOS-Token': 'x' * 43})[0],
        'foreign_host': http(port, 'GET', '/api/session', {'X-EAOS-Token': api.token}, host='evil.example')[0],
        'post_without_csrf': api.post('/api/runs', {'action': 'status'}, csrf=None)[0],
        'post_wrong_csrf': api.post('/api/runs', {'action': 'status'}, csrf='y' * 43)[0],
        'post_foreign_origin': api.post('/api/runs', {'action': 'status'}, origin='http://evil.example')[0],
        'post_without_origin': api.post('/api/runs', {'action': 'status'}, origin=None)[0],
        'answer_without_token': api.post('/api/decisions/x/answer', {'option': 'a'}, token=None)[0],
    }
    expected = {'session_with_token': 200, 'no_token': 401, 'wrong_token': 401, 'foreign_host': 421, 'post_without_csrf': 403,
                'post_wrong_csrf': 403, 'post_foreign_origin': 403, 'post_without_origin': 403, 'answer_without_token': 401}
    wrong = {k: v for k, v in probes.items() if v != expected[k]}
    return case('auth_origin_csrf', not wrong, {'probes': probes, 'expected': expected, 'wrong': wrong})


def concurrency_case(api, row, work):
    """The same answer sent six times at once: one saved answer, one run; a different answer then refused."""
    if not row: return case('idempotency_concurrent_answers', False, {}, 'the report has no fifth waiting question with options')
    option = row['question']['options'][0]['id']
    body = {'scope': row['scope'], 'option': option, 'text': None}
    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        answers = list(pool.map(lambda _: api.post(f"/api/decisions/{row['id']}/answer", body), range(6)))
    runs = {((p or {}).get('decision') or {}).get('response', {}).get('run') for _, p in answers}
    conflict = api.post(f"/api/decisions/{row['id']}/answer", {'scope': row['scope'], 'option': row['question']['options'][1]['id'], 'text': None})
    authority = api.post(f"/api/decisions/{row['id']}/answer", {'scope': row['scope'], 'option': row['question']['options'][0].get('label'), 'text': None})
    both = api.post(f"/api/decisions/{row['id']}/answer", {'scope': row['scope'], 'option': option, 'text': 'and words'})
    blank = api.post(f"/api/decisions/{row['id']}/answer", {'scope': row['scope'], 'option': None, 'text': '   \n '})
    long = api.post(f"/api/decisions/{row['id']}/answer", {'scope': row['scope'], 'option': None, 'text': 'x' * 4001})
    stale = api.post(f"/api/decisions/{row['id']}/answer", {'scope': 'stale-' + row['scope'], 'option': option, 'text': None})
    rows = (api.get('/api/decisions')[1] or {}).get('decisions') or []
    saved = next((r for r in rows if r['id'] == row['id']), {})
    all_runs = (api.get('/api/runs?all=1')[1] or {}).get('runs') or []
    made = [r['id'] for r in all_runs if r['id'] in runs]
    evidence = {'decision': row['id'], 'statuses': [s for s, _ in answers], 'runs': sorted(r for r in runs if r), 'runs_created': made,
                'conflicting_answer': conflict[0], 'label_as_option': authority[0], 'option_and_text': both[0], 'blank_text': blank[0],
                'text_4001': long[0], 'stale_scope': stale[0], 'saved_label': (saved.get('response') or {}).get('label'),
                'source_label': row['question']['options'][0].get('label'), 'history': (saved.get('response') or {}).get('history')}
    passed = (all(s == 200 for s, _ in answers) and len(runs) == 1 and len(made) == 1 and conflict[0] == 409
              and authority[0] == 400 and both[0] == 400 and blank[0] == 400 and long[0] == 400 and stale[0] == 409
              and evidence['saved_label'] == evidence['source_label'])
    _write(Path(work) / 'evidence/concurrency.json', evidence)
    return case('idempotency_concurrent_answers', passed, evidence)


def republish(home, project):
    """The exporter again, as after any check or batch: the Studio data rewritten from the ledger."""
    code = ('import os,sys; from pathlib import Path; from eaos import guided; s = guided.load(Path(sys.argv[1]).resolve()); '
            'guided.reconcile(s); guided.publish(s); guided.save(s); print("ok")')
    done = subprocess.run([PYTHON, '-c', code, str(project)], env={**os.environ, 'EAOS_HOME': str(home), 'PYTHONPATH': str(ROOT)},
                          capture_output=True, text=True, timeout=900)
    return done.returncode == 0, (done.stdout + done.stderr)[-600:]


def reconcile_isolation_case(api, main, other_server, answered_ids, home, project):
    before = {r['id']: (r['scope'], (r.get('response') or {}).get('run'), (r.get('response') or {}).get('text'), (r.get('response') or {}).get('option'))
              for r in (api.get('/api/decisions')[1] or {}).get('decisions') or []}
    published, log = republish(home, project)
    after_rows = (api.get('/api/decisions')[1] or {}).get('decisions') or []
    after = {r['id']: (r['scope'], (r.get('response') or {}).get('run'), (r.get('response') or {}).get('text'), (r.get('response') or {}).get('option')) for r in after_rows}
    kept = [i for i in answered_ids if before.get(i) and before.get(i) == after.get(i) and before[i][1]]
    other = other_server.start()
    try:
        other_api = Api(other)
        rows = (other_api.get('/api/decisions')[1] or {}).get('decisions') or []
        leaked = [r['id'] for r in rows if r.get('response')]
        other_runs = (other_api.get('/api/runs?all=1')[1] or {}).get('runs') or []
        cross = {'main_token_on_other': http(other['port'], 'GET', '/api/decisions', {'X-EAOS-Token': main['token']})[0],
                 'other_token_on_main': http(main['port'], 'GET', '/api/decisions', {'X-EAOS-Token': other['token']})[0],
                 'main_csrf_on_other': other_api.post(f"/api/decisions/{answered_ids[0] if answered_ids else 'x'}/answer",
                                                      {'scope': 'x', 'option': 'x'}, csrf=api.csrf)[0]}
        same_questions = sorted(r['id'] for r in rows) == sorted(after)
    finally:
        other_server.stop()
    evidence = {'republished': published, 'publish_log': log if not published else '', 'answered': answered_ids, 'kept_after_republish': kept,
                'other_project_questions_same': same_questions, 'other_project_answers_leaked': leaked, 'other_project_runs': len(other_runs),
                'cross_tokens': cross}
    passed = (published and answered_ids and len(kept) == len(answered_ids) and same_questions and not leaked and not other_runs
              and cross['main_token_on_other'] == 401 and cross['other_token_on_main'] == 401 and cross['main_csrf_on_other'] in (401, 403))
    return case('refresh_reconciliation_project_isolation', passed, evidence)


# ---------------------------------------------------------------- the trial

def views(info, out, lang_order=('ar', 'en')):
    """The screen gate on the live decisions page, every viewport × language × theme."""
    from eaos.screens import audit
    variants = [{'name': f'{lang}-{theme}', 'lang': lang, 'theme': theme, 'color_scheme': theme, 'storage': {},
                 'query': {'lang': lang, 'theme': theme}} for lang in lang_order for theme in ('light', 'dark')]
    sizes = [{'name': 'phone', 'width': 390, 'height': 844}, {'name': 'tablet', 'width': 768, 'height': 1024},
             {'name': 'desktop', 'width': 1440, 'height': 900}]
    page = {'url': f"{info['base']}#token={info['token']}", 'name': 'decisions', 'wait_for': 'main#main',
            'actions': [{'click': 'a[href="#/decisions"]', 'wait': 1500}]}
    found = audit.page_audit([page], sizes, variants, Path(out) / 'views')
    rows = []
    for row in found.get('rows') or []:
        lang, theme = row['variant'].split('-')
        rows.append({'viewport': row['viewport'], 'lang': lang, 'theme': theme, 'pass': row.get('status') == 'observed' and not row.get('failures'),
                     'screenshot': row.get('screenshot'), 'failures': row.get('failures'), 'width': row.get('width'),
                     'layout_width': row.get('layout_width'), 'scroll': row.get('scroll')})
    return {'status': found.get('status'), 'reason': found.get('reason'), 'tools': found.get('tools'), 'views': rows}


def clone(source, where):
    subprocess.run(['git', 'clone', '--quiet', '--no-hardlinks', str(source), str(where)], check=True)
    if subprocess.run(['git', '-C', str(where), 'symbolic-ref', '-q', 'HEAD'], capture_output=True).returncode:
        subprocess.run(['git', '-C', str(where), 'checkout', '--quiet', '-B', 'main'], check=True)
    for key, value in (('user.name', 'EAOS trial owner'), ('user.email', 'owner@trial.invalid')):
        subprocess.run(['git', '-C', str(where), 'config', key, value], check=True)
    return subprocess.run(['git', '-C', str(where), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()


def trial(name, source, assistant, lang, measure, skip=()):
    started, began = now(), time.monotonic()
    allowed = authorization(name)
    studio_out = Path(measure) / 'studio' / name
    controls_out = Path(measure) / 'owner-controls' / name
    shutil.rmtree(studio_out, ignore_errors=True)
    shutil.rmtree(controls_out, ignore_errors=True)
    work = studio_out / 'work'
    (work / 'evidence').mkdir(parents=True)
    project, other, home, other_home = work / 'project', work / 'other', work / 'home', work / 'other-home'
    commit = clone(source, project)
    clone(source, other)
    home.mkdir(); other_home.mkdir()
    _write(work / 'context.json', {'project': str(project), 'home': str(home), 'name': name, 'assistant': assistant, 'lang': lang,
                                   'run_code': allowed['run_code'], 'answers': {'run': RUN_ANSWER, 'decision': DECISION_ANSWER,
                                                                                'keyboard': KEYBOARD_ANSWER, 'draft': DRAFT_ANSWER}})
    main = Server(work, 'main', project, home, free_port())
    failures, cases, screenshots, videos = [], {}, [], []
    info = main.start()
    api = Api(info)
    cases['auth_origin_csrf'] = auth_case(api, info['port'])
    detected = {a['id']: a for a in (api.get('/api/assistants')[1] or {}).get('assistants') or []}
    if not (detected.get(assistant) or {}).get('logged_in'):
        failures.append(f'{ASSISTANTS[assistant]} is not installed and logged in here: {detected.get(assistant)}')

    # 1. the check, from the empty Studio
    branch = subprocess.run(['git', '-C', str(project), 'rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True, text=True).stdout.strip()
    scan = browser('scan', work, studio_out, {'lang': lang, 'branch': branch}, LIMITS['scan'])
    screenshots += scan.get('screenshots') or []
    videos += [v for v in [scan.get('video')] if v]
    failures += scan.get('errors') or []
    manifest = api.get('/api/manifest')
    audited = bool(scan.get('audit_done')) and manifest[0] == 200
    studio = _studio_folder(home, project)

    # 2. report decisions: option, typed, keyboard, failed send; then reload, re-export, restart and another project
    rows = (api.get('/api/decisions')[1] or {}).get('decisions') or []
    picked = pick_decisions(rows)
    decided = browser('decisions', work, studio_out, {'lang': lang, 'picked': {k: {'id': v['id'], 'scope': v['scope'],
                      'recommended': (recommended_option(v['question']) or {}).get('id'),
                      'options': [o['id'] for o in v['question']['options']]} for k, v in picked.items()}}, LIMITS['decisions']) if audited else {}
    screenshots += decided.get('screenshots') or []
    failures += decided.get('errors') or []
    cases['idempotency_concurrent_answers'] = concurrency_case(api, picked.get('concurrent'), work)
    answered = [picked[k]['id'] for k in ('recommended', 'custom', 'keyboard', 'draft') if k in picked and (decided.get(k) or {}).get('saved')]
    saved_rows = {r['id']: r for r in (api.get('/api/decisions')[1] or {}).get('decisions') or []}
    other_server = Server(work, 'other', other, other_home, free_port(), report=studio.parent if studio else None)
    cases['refresh_reconciliation_project_isolation'] = (reconcile_isolation_case(api, info, other_server, answered, home, project) if studio
                                                         else case('refresh_reconciliation_project_isolation', False, {}, 'no report'))
    info = main.restart()
    api = Api(info)
    persisted = browser('persist', work, studio_out, {'lang': lang, 'answered': answered}, LIMITS['persist']) if answered else {}
    screenshots += persisted.get('screenshots') or []
    after_restart = {r['id']: r for r in (api.get('/api/decisions')[1] or {}).get('decisions') or []}
    custom_row = saved_rows.get((picked.get('custom') or {}).get('id')) or {}
    response = custom_row.get('response') or {}
    cases['report_save_queue_reload_restart'] = case('report_save_queue_reload_restart', bool(
        (decided.get('custom') or {}).get('saved') and (decided.get('custom') or {}).get('after_reload')
        and response.get('text') == DECISION_ANSWER and response.get('option') is None and response.get('run')
        and [h['event'] for h in response.get('history') or []][:2] == ['saved', 'queued']
        and (after_restart.get(custom_row.get('id')) or {}).get('response', {}).get('text') == DECISION_ANSWER
        and (persisted.get('shown') or {}).get(custom_row.get('id'))), {
            'decision': custom_row.get('id'), 'browser': decided.get('custom'), 'response': response,
            'after_restart': (after_restart.get(custom_row.get('id')) or {}).get('response'), 'after_restart_on_screen': persisted.get('shown'),
            'server_starts': main.starts})
    rec = decided.get('recommended') or {}
    cases['recommendation_separate_selection'] = case('recommendation_separate_selection', bool(
        rec.get('recommended_blue') and rec.get('recommended_tag') and rec.get('nothing_selected_before')
        and rec.get('saved') and rec.get('chosen') and rec.get('chosen') != rec.get('recommended')
        and rec.get('recommendation_still_shown')), rec)
    keyboard = decided.get('keyboard') or {}
    cases['keyboard_accessibility'] = case('keyboard_accessibility', bool(keyboard.get('saved') and keyboard.get('keyboard_only')
                                                                         and keyboard.get('focus_visible')), keyboard)
    lang_rows = decided.get('languages') or {}
    ids_same = {r['id']: r['scope'] for r in rows} == {r['id']: r['scope'] for r in after_restart.values()}
    cases['authoritative_ids_language_identity'] = case('authoritative_ids_language_identity', bool(
        ids_same and lang_rows.get('same_cards') and lang_rows.get('answered_in_both')
        and cases['idempotency_concurrent_answers']['evidence'].get('label_as_option') == 400), {
            'scopes_unchanged_after_restart': ids_same, 'browser': lang_rows,
            'label_as_option_status': cases['idempotency_concurrent_answers']['evidence'].get('label_as_option')})

    # 3. a group fixed by the real assistant, its questions answered in the inbox, the branch accepted
    group = choose_group(studio) if studio else {'kind': None, 'cards': []}
    fixed = browser('fix', work, studio_out, {'lang': lang, 'group': group, 'assistant': assistant, 'assistant_name': ASSISTANTS[assistant],
                                             'run_code': allowed['run_code']},
                    LIMITS['fix']) if audited and len(group['cards']) >= 2 else {'errors': ['no group of two fixable cards to fix']}
    screenshots += fixed.get('screenshots') or []
    videos += [v for v in [fixed.get('video')] if v]
    failures += fixed.get('errors') or []
    if not allowed['run_code']: failures.append(allowed['why'])
    run = (api.get(f"/api/runs/{fixed['run']}")[1] or {}).get('run') if fixed.get('run') else {}
    result = (run or {}).get('result') or {}
    guided, state = _guided(home, project)
    accepted_waves = [w for w in state.get('waves') or [] if w.get('status') == 'accepted']
    merged = bool(accepted_waves) and bool(result.get('branch'))
    custom = fixed.get('custom_run') or {}
    cases['waiting_custom_exact_text'] = case('waiting_custom_exact_text', bool(custom.get('exact') and custom.get('typed_in_inbox')), custom)
    consent = fixed.get('consent') or {}
    cases['binary_custom_no_consent'] = case('binary_custom_no_consent', bool(
        custom.get('binary') and custom.get('exact') and custom.get('consent') is False and consent.get('restored')
        and consent.get('before_yes') is False), {'custom': custom, 'consent': consent})
    guards = fixed.get('guards') or {}
    undo = fixed.get('undo_after_accept') or {}
    cases['diff_tests_accept_undo_guards'] = case('diff_tests_accept_undo_guards', bool(
        merged and (result.get('diff_stat') or {}).get('files') and result.get('tests') and fixed.get('result_on_screen')
        and guards.get('accept_without_confirm') == 403 and guards.get('accept_forged_confirm') == 403
        and guards.get('undo_without_confirm') == 403 and guards.get('accept_with_undo_token') == 403
        and run.get('outcome') == 'accepted' and undo.get('outcome') != 'undone' and undo.get('reused_token_status') == 403), {
            'run': fixed.get('run'), 'branch': result.get('branch'), 'diff_stat': result.get('diff_stat'), 'tests': result.get('tests'),
            'cards_closed': result.get('cards_closed'), 'guards': guards, 'outcome': (run or {}).get('outcome'), 'undo_after_accept': undo,
            'accepted_waves': [w.get('branch') for w in accepted_waves]})

    # 4. explain, plan and verify through the queue: reorder, pause, resume, stop, retry, a run that dies and its retry
    controls = browser('controls', work, studio_out, {'lang': lang, 'assistant': assistant, 'assistant_name': ASSISTANTS[assistant],
                                                     'cards': [c['id'] for c in fixable_cards(studio)][-2:] if studio else []},
                       LIMITS['controls']) if audited and 'controls' not in skip else {'errors': ['controls skipped']}
    screenshots += controls.get('screenshots') or []
    failures += controls.get('errors') or []
    draft = decided.get('draft') or {}
    retry = controls.get('retry') or {}
    cases['failure_retry_draft_retention'] = case('failure_retry_draft_retention', bool(
        draft.get('failed_visibly') and draft.get('draft_kept') and draft.get('saved_after_retry')
        and retry.get('failed') and retry.get('retried_same_run') and retry.get('no_duplicate')), {'draft': draft, 'retry': retry})
    queue = controls.get('queue') or {}
    cases['scan_explain_plan_fix_queue_controls'] = case('scan_explain_plan_fix_queue_controls', bool(
        audited and merged and controls.get('explain_done') and controls.get('plan_reached') and queue.get('reordered')
        and queue.get('paused') and queue.get('resumed') and queue.get('stopped')), {
            'audit_run': scan.get('audit_run'), 'fix_run': fixed.get('run'), 'explain': controls.get('explain'), 'plan': controls.get('plan'),
            'verify': controls.get('verify'), 'queue': queue})

    # 5. the screens, every way the owner may open them
    seen = views(info, controls_out) if 'views' not in skip else {'views': []}
    main.stop()
    words_seen = {**(scan.get('states_seen') or {}), **(fixed.get('states_seen') or {}), **(controls.get('states_seen') or {})}
    understood_map = understood(words_seen, lang)
    understood_map['questions'] = bool(fixed.get('questions_text_ok'))
    understood_map['result'] = bool(fixed.get('result_on_screen'))
    actions = {'scan': scan.get('actions') or 0, 'fix': fixed.get('actions_fix') or 0, 'answers': fixed.get('actions_answers') or 0,
               'accept': fixed.get('actions_accept') or 0}
    digest = shipped()
    completed = now()
    record = {
        'schema_version': 1, 'kind': 'studio-trial', 'project': name, 'source': {'path': str(source), 'commit': commit},
        'authorization': allowed, 'assistant': ASSISTANTS[assistant] if run and run.get('assistant') == assistant else None,
        'assistant_asked': ASSISTANTS[assistant], 'assistant_detected': detected.get(assistant), 'mocked': False, 'lang': lang,
        'studio_source_sha256': digest, 'started_at': started, 'completed_at': completed, 'minutes': round((time.monotonic() - began) / 60, 1),
        'audited': audited, 'audit_run': scan.get('audit_run'), 'selection': {'kind': group.get('kind'), 'by': group.get('by'),
                                                                             'value': group.get('value'), 'cards': fixed.get('selected') or []},
        'run': fixed.get('run'), 'branch': result.get('branch'), 'cards_fixed': list(result.get('cards_closed') or []) if merged else [],
        'cards_closed': list(result.get('cards_closed') or []), 'questions_answered_in_inbox': fixed.get('answered_in_inbox') or 0,
        'accepted': merged and (run or {}).get('outcome') == 'accepted', 'typed_to_assistant': 0,
        'typed_in_studio': fixed.get('typed_in_studio') or 0, 'failures': failures, 'understood': understood_map, 'states_seen': words_seen,
        'time_to_first_action_s': scan.get('first_action_s'), 'steps_per_task': steps_per_task(actions), 'actions': actions,
        'screenshots': [s for s in screenshots if s and Path(s).is_file()], 'video': next((v for v in reversed(videos) if Path(v).is_file()), None),
        'videos': videos, 'owner_controls': str(controls_out / 'trial.json'),
    }
    _write(studio_out / 'trial.json', record)
    controls_record = {
        'schema_version': 1, 'kind': 'owner-controls', 'project': name, 'assistant': record['assistant'], 'mocked': False,
        'studio_source_sha256': digest, 'started_at': started, 'completed_at': completed, 'authorization': allowed,
        'cases': [cases[c] for c in sorted(cases)], 'views': seen.get('views') or [], 'views_gate': {k: seen.get(k) for k in ('status', 'reason', 'tools')},
        'studio_trial': str(studio_out / 'trial.json'),
    }
    _write(controls_out / 'trial.json', controls_record)
    return record, controls_record


def _studio_folder(home, project):
    guided, state = _guided(home, project)
    if not state: return None
    folder = guided.report_of(state) / 'studio'
    return folder if (folder / 'manifest.json').is_file() else None


def summary(record, controls):
    import north_star_studio as judge
    passed, why = judge.trial_passed(record)
    print(json.dumps({k: record.get(k) for k in ('project', 'assistant', 'audited', 'selection', 'cards_fixed', 'questions_answered_in_inbox',
                                                 'accepted', 'understood', 'time_to_first_action_s', 'steps_per_task', 'minutes')}, ensure_ascii=False))
    print(f"F15 trial: {'PASS' if passed else 'not yet: missing ' + why}")
    for row in controls['cases']:
        print(f"  {'pass' if row['pass'] else 'FAIL'}  {row['id']}" + (f"  ({row['notes']})" if row.get('notes') else ''))
    views_ok = sum(1 for v in controls['views'] if v['pass'])
    print(f"  views passing the screen gate: {views_ok}/{len(controls['views'])}")
    for failure in record['failures'][:12]: print(f'  failure: {str(failure)[:300]}')
    return 0 if passed and all(row['pass'] for row in controls['cases']) else 1


def main(argv):
    if argv[:1] == ['check']:
        print(json.dumps(check(argv[1], argv[2], *argv[3:]), ensure_ascii=False))
        return 0
    if argv[:1] == ['serve']:
        return serve_main(*argv[1:5])
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('project', help='the name the trial is recorded under (EAOS, FleetManageWeb, chief-ops, ...)')
    parser.add_argument('--source', help='the git repository to copy (default: this checkout for EAOS, else $EAOS_CORPUS/<project>)')
    parser.add_argument('--assistant', choices=sorted(ASSISTANTS), default='claude')
    parser.add_argument('--lang', choices=('ar', 'en'), default='ar')
    parser.add_argument('--measure', default=str(dev_paths.MEASURE))
    parser.add_argument('--skip', default='', help='comma-separated: controls, views')
    args = parser.parse_args(argv)
    source = args.source or default_source(args.project)
    if not source: parser.error(f'no source for {args.project}: pass --source')
    record, controls = trial(args.project, source, args.assistant, args.lang, args.measure, tuple(filter(None, args.skip.split(','))))
    return summary(record, controls)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
