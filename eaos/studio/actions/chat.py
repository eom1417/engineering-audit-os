"""The person's assistant beside the Studio: a conversation that reads, explains and diagnoses, and proposes.

Its assistant may call only EAOS's reading tools (READ_TOOLS: the status, the findings, the plan, a report's files)
and read the project's files; every tool that works (a check, a fix, run_try...) is out of its reach. What it would do
comes back as a proposal: a Studio action (docs/studio-actions.json, with its inputs) or a control of a run (CONTROLS).
The Studio shows each as a card the person confirms, and runs it the way its own buttons do: the action's preview,
the one-slot queue, the steps only the person may take. So a batch running beside the conversation is never touched by
it, and every change has the person's yes behind it.

Direct control, the person's choice for an hour (CONTROL_HOURS, kept by the server, never by a browser): the Studio
runs the assistant's proposals at once, still through its own preview and queue, and only DIRECT actions and the
controls of a run; the person's own steps (accept, undo, choosing a branch) and editing code never. Each turn may ask
a model (MODELS: quick by default, balanced, or the assistant's own for a deep diagnosis). A turn runs on its own
thread: start() answers at once, and progress() says what the assistant reads now and the answer as it is written.
A conversation goes on in the assistant's own session (resumed turn by turn); each turn, with what it used
(eaos/usage.py), is kept under the runs' folder (chat/<session>/turns.jsonl).
"""
import json
import re
import subprocess
import threading
import uuid
from datetime import datetime, timedelta, timezone

from ...usage import from_stream

READ_TOOLS = ('status', 'branches', 'menu', 'impact', 'ask', 'assistant_check', 'overview', 'findings', 'finding', 'structure',
              'plan', 'report_file', 'fix_read', 'build_read', 'design_brief')
CONTROLS = ('retry', 'stop', 'pause', 'resume')
# What direct control may run by itself: a check, the app's run and its speed, the plans of the assistant's nodes, a note.
DIRECT = ('audit', 'tools_check', 'run_setup', 'run_try', 'safety_net', 'replan_ideal', 'run_nodes', 'note')
CONTROL_HOURS = 1
MODELS = {'quick': 'haiku', 'balanced': 'sonnet', 'deep': None}     # Claude's; None: the assistant's own
LIMIT = 900                 # seconds one turn may take
RUN_EVENTS = 40             # a run's last events given with a diagnosis
SESSION = re.compile(r'^[A-Za-z0-9-]{8,80}$')
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

You may read, never change: call EAOS's reading tools (status, findings, finding, plan, report_file, overview...) and read
the project's files. When something should be done, propose it. A proposal is either
{{"kind": "action", "action": "<one of the actions below>", "inputs": {{...its inputs...}}, "run": null, "why": "<one line>"}}
or {{"kind": "control", "action": "retry"|"stop"|"pause"|"resume", "inputs": {{}}, "run": "<run id>", "why": "<one line>"}}.
{control} A batch may be running now: reading is always fine, but never
propose what would compete with it; say it waits for the batch instead. Return JSON: {{"answer": "...", "proposals": [...]}}.

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
    prompt = (('(Direct control is on.) ' if direct else '') + message) if session else _opening(actions, body.get('context'), message, direct)
    argv = adapter.argv(prompt, 'chat', folder, session=session, tools=READ_TOOLS)
    model = MODELS.get(body.get('model'), MODELS['quick'])
    if adapter.id == 'claude': argv += ['--json-schema', json.dumps(SCHEMA), '--include-partial-messages'] + (['--model', model] if model else [])
    turn = uuid.uuid4().hex
    TURNS[turn] = {'folder': folder, 'done': False, 'result': None, 'error': None}
    threading.Thread(target=_turn, args=(actions, adapter, turn, argv, message, session, direct), daemon=True).start()
    return {'turn': turn}


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
        result = {'session': _session(lines) or session, 'answer': str(answer.get('answer') or ''), 'proposals': proposals,
                  'done': [_execute(actions, p) for p in proposals if direct and _direct(p)],
                  'assistant': adapter.name, 'usage': from_stream(lines)}
        with open(record['folder'] / 'turns.jsonl', 'a', encoding='utf-8') as log:
            log.write(json.dumps({'at': _now().isoformat(timespec='seconds'), 'message': message, **result}, ensure_ascii=False) + '\n')
        record['result'] = result
    except Exception as problem:                       # the conversation says why; the Studio goes on
        record['error'] = str(problem)[:500]
    record['done'] = True


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
        block, delta = inner.get('content_block') or {}, inner.get('delta') or {}
        if inner.get('type') == 'content_block_start' and block.get('type') == 'tool_use':
            if block.get('name') == 'StructuredOutput': structured.add(inner.get('index'))
            else: reading.append(str(block.get('name') or '').removeprefix('mcp__eaos__'))
        elif delta.get('type') == 'input_json_delta' and inner.get('index') in structured:
            buffer[inner.get('index')] = buffer.get(inner.get('index'), '') + str(delta.get('partial_json') or '')
    found = ANSWER.search(''.join(buffer.values()))
    return reading, _unescaped(found.group(1)) if found else ''


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
    """Direct control: {'on', 'until'}; `body` {'on': true|false} turns it on for CONTROL_HOURS, or off."""
    path = actions.store.folder / 'chat' / 'control.json'
    if body is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if body.get('on'): path.write_text(json.dumps({'until': (_now() + timedelta(hours=CONTROL_HOURS)).isoformat()}), encoding='utf-8')
        else: path.unlink(missing_ok=True)
    try: until = datetime.fromisoformat(json.loads(path.read_text(encoding='utf-8'))['until'])
    except (OSError, ValueError, KeyError): until = None
    return {'on': bool(until and until > _now()), 'until': until.isoformat() if until and until > _now() else None, 'actions': list(DIRECT)}


def _direct(proposal):
    return proposal['kind'] == 'control' or proposal['action'] in DIRECT


def _execute(actions, proposal):
    """One proposal run by the Studio itself, as its own buttons run it: {proposal, run} or {proposal, error}."""
    try:
        if proposal['kind'] == 'control': run = getattr(actions.manager, proposal['action'])(proposal['run'])
        else:
            seen = actions.preview(proposal['action'], {'inputs': proposal['inputs']})
            run = actions.create({'action': proposal['action'], 'inputs': proposal['inputs'], 'confirm': seen.get('confirm')})
        return {'proposal': proposal, 'run': run.get('id')}
    except Exception as problem:
        return {'proposal': proposal, 'error': str(problem)[:300]}


def _now():
    return datetime.now(timezone.utc)


def _opening(actions, context, message, direct=False):
    listed = '; '.join(f"{a['id']} ({a.get('description', {}).get('en', '') if isinstance(a.get('description'), dict) else ''})"[:160]
                       for a in actions.contract['actions'])
    language = 'Arabic (plain, Gulf-friendly)' if actions.lang == 'ar' else 'English'
    said = (f"Direct control is on: the Studio runs at once your proposals of {', '.join(DIRECT)} and the runs' controls; say "
            'plainly what you set going. Any other proposal the person confirms.' if direct else 'The person confirms each one and the Studio runs it.')
    return (RULES.format(language=language, actions=listed, context=json.dumps(context or {}, ensure_ascii=False)[:2000], control=said)
            + _run_log(actions, (context or {}).get('run')) + '\nThe person: ' + message)


def _run_log(actions, run):
    """The run the person is looking at, for a diagnosis: its state, why it ended, its last events, and where its whole
    stream is to read, while it is kept (eaos/studio/actions/store.py trim)."""
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
    out = []
    for item in proposals if isinstance(proposals, list) else []:
        if not isinstance(item, dict): continue
        if item.get('kind') == 'action' and item.get('action') in known:
            out.append({'kind': 'action', 'action': item['action'], 'inputs': item.get('inputs') if isinstance(item.get('inputs'), dict) else {},
                        'why': str(item.get('why') or '')[:300]})
        elif item.get('kind') == 'control' and item.get('action') in CONTROLS and _run_exists(actions, item.get('run')):
            out.append({'kind': 'control', 'action': item['action'], 'run': item['run'], 'why': str(item.get('why') or '')[:300]})
    return out[:4]


def _run_exists(actions, run):
    try: return bool(run) and bool(actions.store.load(str(run)))
    except (KeyError, OSError, ValueError): return False
