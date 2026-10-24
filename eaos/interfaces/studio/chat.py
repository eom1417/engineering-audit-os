"""The person's assistant beside the Studio: a conversation that reads, explains and diagnoses, and does what the person
asks.

Its assistant may call only EAOS's reading tools (READ_TOOLS: the status, the findings, the plan, a report's files)
and read the project's files; what it does comes back as a proposal: a Studio action (docs/studio-actions.json, with its
inputs) or a control of a run (CONTROLS), which the Studio runs the way its own buttons do: the action's preview and the
one-slot queue.

Direct control, on unless the person turned it off (kept by the server, never by a browser): the Studio runs the
assistant's proposals at once, every action and the controls of a run (the owner, 2026-10-21: an assistant that only
proposes is of no use; it must do what the person asks, as one does in a terminal). Only what cannot be undone
(CONFIRMED: merging a branch, throwing one away) still waits for the person's press. Each turn may ask
a model (MODELS: quick by default, balanced, or the assistant's own for a deep diagnosis). A turn runs on its own
thread: start() answers at once, and progress() says what the assistant reads now and the answer as it is written.
A conversation goes on in the assistant's own session (resumed turn by turn); each turn, with what it used
(eaos/core/usage.py), is kept under the runs' folder (chat/<session>/turns.jsonl).
"""
import json
import re
import subprocess
import threading
import uuid
from datetime import datetime, timezone

from ...core.usage import from_stream

READ_TOOLS = ('status', 'branches', 'menu', 'impact', 'ask', 'assistant_check', 'overview', 'findings', 'finding', 'structure',
              'plan', 'report_file', 'fix_read', 'build_read', 'design_brief')
CONTROLS = ('retry', 'stop', 'pause', 'resume')
# The run controls as the person reads them on the button they pressed (en, ar).
PRESSED = {'pause': ('Pause', 'أوقف مؤقتًا'), 'resume': ('Resume', 'كمّل'), 'stop': ('Stop', 'أوقف'), 'retry': ('Try again', 'أعد المحاولة')}
CONFIRMED = ('accept', 'undo')     # what cannot be undone waits for the person's press, direct control or not
MODELS = {'quick': 'haiku', 'balanced': 'sonnet', 'deep': None}     # Claude's; None: the assistant's own
LIMIT = 900                 # seconds one turn may take
RUN_EVENTS = 40             # a run's last events given with a diagnosis
SESSION = re.compile(r'^[A-Za-z0-9-]{8,80}$')
NOTE = re.compile(r'<notification_summary>.*?</notification_summary>', re.S)     # a host's own instructions, never the person's
ANSWER = re.compile(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)')
TURNS = {}                  # turn id -> {folder, done, result, error}
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['answer', 'proposals'], 'properties': {
    'answer': {'type': 'string'},
    'proposals': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                                             'required': ['kind', 'action', 'inputs', 'run', 'why'], 'properties': {
        'kind': {'enum': ['action', 'control']}, 'action': {'type': 'string'}, 'inputs': {'type': 'object'},
        'run': {'type': ['string', 'null']}, 'why': {'type': 'string'}}}}}}
RULES = '''You are the person's assistant inside EAOS Studio, beside the work it is doing on their project. Answer in
{language}, in plain words for a person who is not a developer; be short and concrete.

Read with EAOS's reading tools (status, findings, finding, plan, report_file, overview...) and the project's files, and do
what the person asks: never answer that you cannot when an action or a control below does it. You do it by proposing
it; a proposal is either
{{"kind": "action", "action": "<one of the actions below>", "inputs": {{...its inputs...}}, "run": null, "why": "<one line, in {language}>"}}
or {{"kind": "control", "action": "retry"|"stop"|"pause"|"resume", "inputs": {{}}, "run": "<run id>", "why": "<one line, in {language}>"}}.
{control} Only one piece of work runs at a time and the rest waits its turn: when the person
wants something now (a new check while one runs, say), stop the running one first (a control "stop" with its run id, from
`status`), then propose theirs. A new check is the action "audit" with {{"fresh": true}}, from nothing; a stopped check
goes on with the control "retry" on its run. Return JSON: {{"answer": "...", "proposals": [...]}}.

The actions: {actions}

Where the person is: {context}
'''


def start(actions, body):
    """Begin one turn on its own thread: {'turn': id}. `body`: {message, session?, context?, model?}."""
    message = str(body.get('message') or '').strip()[:8000]
    if not message: raise ValueError('the message is empty')
    session = body.get('session') if SESSION.match(str(body.get('session') or '')) else None
    name = actions._assistant(None, True)
    if name not in actions.adapters: raise LookupError('no assistant is signed in on this computer: sign in to Claude Code or Codex')
    adapter, direct = actions.adapters[name], control(actions)['on']
    folder = actions.store.folder / 'chat' / (session or datetime.now(timezone.utc).strftime('new-%Y%m%d-%H%M%S-%f'))
    folder.mkdir(parents=True, exist_ok=True)
    prompt = (('(Direct control is on.) ' if direct else '') + _runs(actions) + message) if session else _opening(actions, body.get('context'), message, direct)
    argv = adapter.argv(prompt, 'chat', folder, session=session, tools=READ_TOOLS)
    if adapter.id == 'claude': argv += _claude_options(body)
    turn = uuid.uuid4().hex
    TURNS[turn] = {'folder': folder, 'done': False, 'result': None, 'error': None}
    threading.Thread(target=_turn, args=(actions, adapter, turn, argv, message, session, direct), daemon=True).start()
    return {'turn': turn}


def _claude_options(body):
    """Claude Code's own options for a turn: the answer's schema, the answer as it is written, the model asked."""
    model = MODELS.get(body.get('model'), MODELS['quick'])
    return ['--json-schema', json.dumps(SCHEMA), '--include-partial-messages'] + (['--model', model] if model else [])


def _turn(actions, adapter, turn, argv, message, session, direct):
    record = TURNS[turn]
    stream = record['folder'] / 'stream.jsonl'
    try:
        with open(stream, 'wb') as out:
            subprocess.run(argv, cwd=actions.project, stdout=out, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=LIMIT)
        lines = stream.read_text(encoding='utf-8', errors='replace').splitlines()
        answer, _, failure = adapter.answer(lines)
        if failure or not isinstance(answer, dict): raise LookupError(f'the assistant did not answer: {failure or "no answer"}')
        proposals = _allowed(actions, answer.get('proposals'))
        result = {'session': _session(lines) or session, 'answer': NOTE.sub('', str(answer.get('answer') or '')).strip(), 'proposals': proposals,
                  'done': _done_at_once(actions, proposals) if direct else [],
                  'assistant': adapter.name, 'usage': from_stream(lines)}
        with open(record['folder'] / 'turns.jsonl', 'a', encoding='utf-8') as log:
            log.write(json.dumps({'at': _now().isoformat(timespec='seconds'), 'message': message, **result}, ensure_ascii=False) + '\n')
        record['result'] = result
    except Exception as problem:                       # the conversation says why; the Studio goes on
        record['error'] = str(problem)[:500]
    record['done'] = True


def _done_at_once(actions, proposals):
    """Under direct control: each proposal that need not wait for the person's press, run now; what came of each."""
    return [done for p in proposals if _direct(p) if (done := _execute(actions, p))]


def progress(actions, turn):
    """{done, reading, partial, result, error} of a turn: what the assistant reads now and its answer so far."""
    record = TURNS.get(turn)
    if record is None: raise LookupError(f'this turn of the conversation is gone (the Studio restarted): {turn}')
    try: lines = (record['folder'] / 'stream.jsonl').read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError: lines = []
    reading, partial = _live(lines)
    return {'done': record['done'], 'reading': reading[-3:], 'partial': partial, 'result': record['result'], 'error': record['error']}


def _live(lines):
    """(the tools called so far, the answer written so far) from a Claude Code stream with partial messages."""
    reading, structured, buffer = [], set(), {}
    for inner in filter(None, map(_partial, lines)):
        delta = inner.get('delta') or {}
        if (block := _tool_started(inner)):
            if block.get('name') == 'StructuredOutput': structured.add(inner.get('index'))
            else: reading.append(str(block.get('name') or '').removeprefix('mcp__eaos__'))
        elif delta.get('type') == 'input_json_delta' and inner.get('index') in structured:
            buffer[inner.get('index')] = buffer.get(inner.get('index'), '') + str(delta.get('partial_json') or '')
    found = ANSWER.search(''.join(buffer.values()))
    return reading, _unescaped(found.group(1)) if found else ''


def _tool_started(inner):
    """The tool call a partial-message event starts (its content block), or None."""
    block = inner.get('content_block') or {}
    return block if inner.get('type') == 'content_block_start' and block.get('type') == 'tool_use' else None


def _partial(line):
    """The partial-message event of one stream line, or None."""
    try: event = json.loads(line)
    except ValueError: return None
    inner = event.get('event') if isinstance(event, dict) and event.get('type') == 'stream_event' else None
    return inner if isinstance(inner, dict) else None


def _unescaped(text):
    for end in (len(text), len(text) - 1):
        try: return json.loads('"' + text[:end] + '"')
        except ValueError: continue
    return text.replace('\\n', '\n')


def control(actions, body=None):
    """Direct control: {'on', 'confirmed'}, on unless the person turned it off; `body` {'on': true|false} turns it."""
    path = actions.store.folder / 'chat' / 'control-off'
    if body is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if body.get('on'): path.unlink(missing_ok=True)
        else: path.touch()
    return {'on': not path.exists(), 'confirmed': list(CONFIRMED)}


def _direct(proposal):
    return proposal['kind'] == 'control' or proposal['action'] not in CONFIRMED


def _execute(actions, proposal):
    """One proposal run by the Studio itself, as its own buttons run it: {proposal, run} or {proposal, error}."""
    try:
        if proposal['kind'] == 'control': run = getattr(actions.manager, proposal['action'])(proposal['run'])
        else:
            seen = actions.preview(proposal['action'], {'inputs': proposal['inputs']})
            run = actions.create({'action': proposal['action'], 'inputs': proposal['inputs'], 'confirm': seen.get('confirm')})
        return {'proposal': proposal, 'run': run.get('id')}
    except Exception as problem:
        # one that needs the person's own confirmation stays the proposal they confirm, not a refusal in their chat
        if getattr(problem, 'extra', {}).get('needs') == 'confirm': return None
        return {'proposal': proposal, 'error': str(problem)[:300]}


def _now():
    return datetime.now(timezone.utc)


def _opening(actions, context, message, direct=False):
    listed = '; '.join(f"{a['id']} ({a.get('description', {}).get('en', '') if isinstance(a.get('description'), dict) else ''})"[:160]
                       for a in actions.contract['actions'])
    language = 'Arabic (plain, Gulf-friendly)' if actions.lang == 'ar' else 'English'
    said = (f"Direct control is on: the Studio runs your proposals at once; say plainly what you set going. Only "
            f"{', '.join(CONFIRMED)} wait for the person's press." if direct else 'The person turned direct control off: they confirm each '
            'proposal and the Studio runs it.')
    return (RULES.format(language=language, actions=listed, context=json.dumps(context or {}, ensure_ascii=False)[:2000], control=said)
            + _run_log(actions, (context or {}).get('run')) + '\n' + _runs(actions) + 'The person: ' + message)


def _runs(actions):
    """The runs going on or waiting now, with their ids, so a control names the right one (it once said it stopped a
    check it had no id for, and the new one waited behind it)."""
    from ...core.store import ACTIVE
    now = [f"{r['id']} {r.get('action')} {r.get('state')}" for r in actions.store.all() if r.get('state') in (*ACTIVE, 'queued')]
    return f"Runs now: {'; '.join(now) if now else 'none'}.\n"


def _run_log(actions, run):
    """The run the person is looking at, for a diagnosis: its state, why it ended, its last events, and where its whole
    stream is to read, while it is kept (eaos/core/store.py trim)."""
    if not _run_exists(actions, run): return ''
    record, stream = actions.store.load(str(run)), actions.store.path(str(run)) / 'stream.jsonl'
    events = [f"{e.get('kind')}: {(e.get('text') or {}).get('en', '')}"[:300] for e in actions.store.events(str(run), 0)[-RUN_EVENTS:]]
    return (f"\nThe run {run}: {record.get('state')}; {json.dumps(record.get('error') or record.get('reason') or '', ensure_ascii=False)[:600]}"
            f"\nIts last events:\n" + '\n'.join(events) + (f"\nIts whole stream: {stream}\n" if stream.is_file() else
                                                             '\nIts details were trimmed: only its record is kept.\n'))


def _session(lines):
    """The assistant's own session (Claude Code's session_id, Codex's thread_id), so the next turn goes on in it."""
    for line in lines:
        try: event = json.loads(line)
        except ValueError: continue
        if isinstance(event, dict) and (event.get('session_id') or event.get('thread_id')):
            return event.get('session_id') or event.get('thread_id')
    return None


def _allowed(actions, proposals):
    """The proposals the Studio can run: a known action, or a control of a known run."""
    known = {a['id'] for a in actions.contract['actions']}
    return [kept for item in (proposals if isinstance(proposals, list) else []) if (kept := _proposal(actions, item, known))][:4]


def _proposal(actions, item, known):
    """One proposal as the Studio runs it: a known action with its inputs, or a control of a known run; None."""
    if not isinstance(item, dict): return None
    if item.get('kind') == 'action' and item.get('action') in known:
        return {'kind': 'action', 'action': item['action'], 'inputs': item.get('inputs') if isinstance(item.get('inputs'), dict) else {},
                'why': str(item.get('why') or '')[:300]}
    if item.get('kind') == 'control' and item.get('action') in CONTROLS and _run_exists(actions, item.get('run')):
        return {'kind': 'control', 'action': item['action'], 'run': item['run'], 'why': str(item.get('why') or '')[:300]}
    return None


def _run_exists(actions, run):
    try: return bool(run) and bool(actions.store.load(str(run)))
    except (KeyError, OSError, ValueError): return False


def pressed(operation):
    """{en, ar} of the person pressing one of the run controls, its button named as they read it."""
    en, ar = PRESSED[operation]
    return {'en': f'You pressed {en}', 'ar': f'ضغطت «{ar}»'}
