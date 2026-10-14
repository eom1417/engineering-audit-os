"""The person's assistant beside the Studio: a conversation that reads, explains and diagnoses, and proposes; it never
changes anything itself.

Its assistant may call only EAOS's reading tools (READ_TOOLS: the status, the findings, the plan, a report's files)
and read the project's files; every tool that works (a check, a fix, run_try...) is out of its reach. What it would do
comes back as a proposal: a Studio action (docs/studio-actions.json, with its inputs) or a control of a run (CONTROLS).
The Studio shows each as a card the person confirms, and runs it the way its own buttons do: the action's preview,
the one-slot queue, the steps only the person may take. So a batch running beside the conversation is never touched by
it, and every change has the person's yes behind it. A conversation goes on in the assistant's own session (resumed
turn by turn); each turn, with what it used (eaos/usage.py), is kept under the runs' folder (chat/<session>/turns.jsonl).
"""
import json
import re
import subprocess
from datetime import datetime, timezone

from ...usage import from_stream

READ_TOOLS = ('status', 'branches', 'menu', 'impact', 'ask', 'assistant_check', 'overview', 'findings', 'finding', 'structure',
              'plan', 'report_file', 'fix_read', 'build_read')
CONTROLS = ('retry', 'stop', 'pause', 'resume')
LIMIT = 900                 # seconds one turn may take
RUN_EVENTS = 40             # a run's last events given with a diagnosis
QUICK = 'haiku'             # a question costs a fifteenth of the deep model's; a diagnosis asks with `deep`
SESSION = re.compile(r'^[A-Za-z0-9-]{8,80}$')
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['answer', 'proposals'], 'properties': {
    'answer': {'type': 'string'},
    'proposals': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                                             'required': ['kind', 'action', 'inputs', 'run', 'why'], 'properties': {
        'kind': {'enum': ['action', 'control']}, 'action': {'type': 'string'}, 'inputs': {'type': 'object'},
        'run': {'type': ['string', 'null']}, 'why': {'type': 'string'}}}}}}
RULES = '''You are the person's assistant inside EAOS Studio, beside the work it is doing on their project. Answer in
{language}, in plain words for a person who is not a developer; be short and concrete.

You may read, never change: call EAOS's reading tools (status, findings, finding, plan, report_file, overview...) and read
the project's files. When something should be done, do not say you did it: propose it. A proposal is either
{{"kind": "action", "action": "<one of the actions below>", "inputs": {{...its inputs...}}, "run": null, "why": "<one line>"}}
or {{"kind": "control", "action": "retry"|"stop"|"pause"|"resume", "inputs": {{}}, "run": "<run id>", "why": "<one line>"}}.
The person confirms each one and the Studio runs it. A batch may be running now: reading is always fine, but never
propose what would compete with it; say it waits for the batch instead. Return JSON: {{"answer": "...", "proposals": [...]}}.

The actions: {actions}

Where the person is: {context}
'''


def reply(actions, body):
    """One turn: {session, answer, proposals, assistant, usage}. `body`: {message, session?, context?, deep?}: `deep` asks
    the assistant's own model (a diagnosis), else Claude's smallest answers (a question)."""
    message = str(body.get('message') or '').strip()[:8000]
    if not message: raise ValueError('the message is empty')
    session = body.get('session') if SESSION.match(str(body.get('session') or '')) else None
    name = actions._assistant(None, True)
    if name not in actions.adapters: raise LookupError('no assistant is signed in on this computer: sign in to Claude Code or Codex')
    adapter = actions.adapters[name]
    folder = actions.store.folder / 'chat' / (session or datetime.now(timezone.utc).strftime('new-%Y%m%d-%H%M%S-%f'))
    folder.mkdir(parents=True, exist_ok=True)
    prompt = message if session else _opening(actions, body.get('context'), message)
    argv = adapter.argv(prompt, 'chat', folder, session=session, tools=READ_TOOLS)
    if adapter.id == 'claude': argv += ['--json-schema', json.dumps(SCHEMA)] + ([] if body.get('deep') else ['--model', QUICK])
    stream = folder / 'stream.jsonl'
    with open(stream, 'wb') as out:
        subprocess.run(argv, cwd=actions.project, stdout=out, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=LIMIT)
    lines = stream.read_text(encoding='utf-8', errors='replace').splitlines()
    answer, _, failure = adapter.answer(lines)
    if failure or not isinstance(answer, dict): raise LookupError(f'the assistant did not answer: {failure or "no answer"}')
    turn = {'session': _session(lines) or session, 'answer': str(answer.get('answer') or ''),
            'proposals': _allowed(actions, answer.get('proposals')), 'assistant': adapter.name, 'usage': from_stream(lines)}
    with open(folder / 'turns.jsonl', 'a', encoding='utf-8') as log:
        log.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'message': message, **turn}, ensure_ascii=False) + '\n')
    return turn


def _opening(actions, context, message):
    listed = '; '.join(f"{a['id']} ({a.get('description', {}).get('en', '') if isinstance(a.get('description'), dict) else ''})"[:160]
                       for a in actions.contract['actions'])
    language = 'Arabic (plain, Gulf-friendly)' if actions.lang == 'ar' else 'English'
    return (RULES.format(language=language, actions=listed, context=json.dumps(context or {}, ensure_ascii=False)[:2000])
            + _run_log(actions, (context or {}).get('run')) + '\nThe person: ' + message)


def _run_log(actions, run):
    """The run the person is looking at, for a diagnosis: its state, why it ended, its last events, and where its whole
    stream is to read."""
    if not _run_exists(actions, run): return ''
    record = actions.store.load(str(run))
    events = [f"{e.get('kind')}: {(e.get('text') or {}).get('en', '')}"[:300] for e in actions.store.events(str(run), 0)[-RUN_EVENTS:]]
    return (f"\nThe run {run}: {record.get('state')}; {json.dumps(record.get('error') or record.get('reason') or '', ensure_ascii=False)[:600]}"
            f"\nIts last events:\n" + '\n'.join(events) + f"\nIts whole stream: {actions.store.path(str(run)) / 'stream.jsonl'}\n")


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
