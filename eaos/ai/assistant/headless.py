"""The person's own assistant, started headless for a run (docs/adoption/ns46-t9-command-centre.md).

An adapter knows one assistant: whether it is installed and logged in, the command that starts it on a prompt (and
resumes its session with the person's answer) with the EAOS MCP server and nothing else that writes, and how to read
its output, one JSON object per line, as the contract's events (eaos/ai/assistant/events.py). The run manager does the rest.

Claude Code: `claude -p --output-format stream-json --verbose`, the EAOS server by `--mcp-config --strict-mcp-config`,
EAOS tools plus Read, Grep and Glob allowed, and Bash, Edit, Write and the person-only EAOS tools refused.
Codex: `codex exec --json`, the EAOS server by `-c mcp_servers.eaos=...`, a read-only sandbox and no approvals.

`ask(adapter, prompt, schema, folder)` is the other way to use an assistant: one question, no tool, an answer the
assistant's own CLI holds to a JSON Schema (Claude Code `--json-schema`, Codex `--output-schema`). The planned ideal
(eaos/ai/ideal/planner.py) asks this way, and so does any AI node after it.
"""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from .events import READS, json_text, result_events, said, tool_events

PERSON_ONLY = ('accept', 'undo', 'choose_branch')


def eaos_server(run, assistant):
    """The EAOS MCP server's argv and environment for a run: this very EAOS (the Python and the package the Studio runs,
    never another `eaos` on the PATH), the person's EAOS home, and the run's id, which makes the person-only tools refuse
    (eaos/interfaces/mcp_server/server.py)."""
    import sys
    from ...core.system.launch import HEADLESS              # a run of the headless host opens no Studio either
    env = {'EAOS_STUDIO_RUN': run, 'EAOS_ASSISTANT': assistant, 'PYTHONPATH': str(Path(__file__).resolve().parents[3])}
    for name in ('EAOS_HOME', 'EAOS_OUTPUT', 'EAOS_ENGINE_TOOLS', HEADLESS):
        if os.environ.get(name): env[name] = os.environ[name]
    return [sys.executable, '-m', 'eaos', 'mcp'], env


def _event(line):
    """The JSON object one line of an assistant's stream holds, or None."""
    try: event = json.loads(line)
    except ValueError: return None
    return event if isinstance(event, dict) else None


def _events(lines):
    """The JSON objects of a stream's lines, in order."""
    return [event for event in map(_event, lines) if event is not None]


def _failed(event):
    """Whether a Claude Code result line says it failed."""
    return event.get('is_error') or event.get('subtype') not in (None, 'success')


class Adapter:
    id = name = command = None
    _detected = None

    def __init__(self, command=None):
        self.command = list(command or [self.id_command])

    def _run(self, *arguments, timeout=15):
        try: return subprocess.run(self.command + list(arguments), capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError): return None

    def detect(self, fresh=False):
        """{id, name, installed, logged_in, version}; cached a minute. A probe that does not answer in time (a busy
        computer) keeps what the last one found rather than calling a ready assistant missing."""
        if self._detected and not fresh and time.monotonic() - self._detected[0] < 60: return self._detected[1]
        version = self._run('--version')
        if version is None and self._found_before():
            self._detected = (time.monotonic(), self._detected[1])
            return self._detected[1]
        installed = bool(version and version.returncode == 0)
        found = {'id': self.id, 'name': self.name, 'installed': installed, 'logged_in': installed and self.logged_in(),
                 'version': (version.stdout.strip().splitlines() or [''])[0][:80] if installed else None}
        self._detected = (time.monotonic(), found)
        return found

    def _found_before(self):
        """Whether the last probe found the assistant installed and its command is still there."""
        return self._detected and self._detected[1]['installed'] and shutil.which(self.command[0])

    def available(self):
        found = self.detect()
        return found['installed'] and found['logged_in']

    def new_state(self):
        return {'session': None, 'resumed': False, 'pending': {}, 'final': None, 'failed': None, 'texts': [], 'eaos_results': []}

    def model(self):
        """The model this assistant uses when its stream does not say."""
        return None

    def cost(self, lines):
        """What the answer cost in US dollars, when the stream says (None otherwise)."""
        return None

    def _started(self, state):
        """The step event of the assistant's start, or of its going on with the person's answer."""
        return ('step', {'en': f'{self.name} went on', 'ar': f'{self.name} كمّل'} if state['resumed'] else {'en': f'{self.name} started', 'ar': f'بدأ {self.name}'},
                {'tool': None, 'assistant': self.name}, None)


class ClaudeCode(Adapter):
    id, name, id_command = 'claude', 'Claude Code', 'claude'

    def logged_in(self):
        done = self._run('auth', 'status')
        if done is None: return bool(self._detected and self._detected[1]['logged_in'])
        try: return bool(json.loads(done.stdout).get('loggedIn'))
        except ValueError: return done.returncode == 0

    def argv(self, prompt, run, folder, session=None, tools=None):
        """`tools`: the EAOS tools this run may call (None: every one but the person's)."""
        server, env = eaos_server(run, self.name)
        config = folder / 'mcp.json'
        config.write_text(json.dumps({'mcpServers': {'eaos': {'command': server[0], 'args': server[1:], 'env': env}}}), encoding='utf-8')
        argv = self.command + ['-p', prompt, '--output-format', 'stream-json', '--verbose', '--mcp-config', str(config), '--strict-mcp-config',
                               '--allowedTools', *([f'mcp__eaos__{tool}' for tool in tools] if tools else ['mcp__eaos']), 'Read', 'Grep', 'Glob',
                               '--disallowedTools', 'Bash', 'Edit', 'Write', 'NotebookEdit', 'WebFetch', 'WebSearch',
                               *[f'mcp__eaos__{tool}' for tool in PERSON_ONLY]]
        return argv + (['--resume', session] if session else [])

    def ask_argv(self, schema, folder, images=()):
        """One question on standard input, no MCP server, nothing kept: the answer held to `schema`, streamed as it is
        written. No tool, but Read on exactly `images` when the question is about pictures (Read elsewhere is refused;
        an absolute path in a permission rule starts with //, a single / is relative to the working folder)."""
        tools = ['--tools', 'Read', '--allowedTools', *[f'Read(/{Path(image).resolve()})' for image in images],
                 '--permission-mode', 'dontAsk'] if images else ['--tools', '']
        return self.command + ['-p', '--output-format', 'stream-json', '--verbose', '--include-partial-messages',
                               '--json-schema', json.dumps(schema), *tools, '--strict-mcp-config', '--no-session-persistence']

    def cost(self, lines):
        """`total_cost_usd` of the stream's result line."""
        for event in reversed(_events(lines)):
            if event.get('type') == 'result' and isinstance(event.get('total_cost_usd'), (int, float)):
                return float(event['total_cost_usd'])
        return None

    def answer(self, lines):
        """(answer, model, failure) from the stream of an `ask`."""
        answer, model, failure = None, None, None
        for event in _events(lines):
            model = _model_of(event) or model
            if event.get('type') == 'assistant': answer = _structured(event.get('message') or {}, answer)
            elif event.get('type') == 'result':
                if _failed(event): failure = str(event.get('result') or event.get('subtype') or 'the assistant failed')[:500]
                else: answer = _answered(event, answer)
        return answer, model, failure

    def parse(self, line, state, labels):
        """The events of one line of Claude Code's stream-json."""
        event = _event(line)
        if event is None: return []
        state['session'] = event.get('session_id') or state['session']
        kind, out = event.get('type'), []
        if kind == 'system' and event.get('subtype') == 'init': out.append(self._started(state))
        elif kind == 'assistant': out += self._said_and_called(event, state, labels)
        elif kind == 'user': out += self._results(event, state, labels)
        elif kind == 'result': self._finished(event, state)
        return out

    @staticmethod
    def _finished(event, state):
        """Keep a result line's final words, and what it says when it failed."""
        state['final'] = str(event.get('result') or '')
        if _failed(event): state['failed'] = state['final'] or str(event.get('subtype'))

    @staticmethod
    def _said_and_called(event, state, labels):
        """The events of an assistant message: its words, and each tool it calls (kept pending for its result)."""
        out = []
        for block in (event.get('message') or {}).get('content') or []:
            if block.get('type') == 'tool_use': out += _called(block, state, labels)
            elif block.get('type') == 'text' and str(block.get('text') or '').strip():
                state['texts'].append(block['text'])
                out += said(block['text'])
        return out

    @staticmethod
    def _results(event, state, labels):
        """The events of the EAOS tools' results a user message carries back."""
        out = []
        for block in (event.get('message') or {}).get('content') or []:
            if not isinstance(block, dict) or block.get('type') != 'tool_result': continue
            tool, arguments = state['pending'].pop(block.get('tool_use_id'), (None, {}))
            if tool and tool in labels:
                payload = json_text(block.get('content'))
                state['eaos_results'].append((tool, payload))
                out += result_events(tool, arguments, payload, labels)
        return out


def _model_of(event):
    """The model a Claude Code init line or assistant message names."""
    if event.get('type') == 'system' and event.get('subtype') == 'init': return event.get('model')
    if event.get('type') == 'assistant': return (event.get('message') or {}).get('model')
    return None


def _structured(message, answer):
    """The input of the message's last StructuredOutput call, else `answer`."""
    for block in message.get('content') or []:
        if isinstance(block, dict) and block.get('type') == 'tool_use' and block.get('name') == 'StructuredOutput':
            answer = block.get('input')
    return answer


def _answered(event, answer):
    """The answer after a successful result line: its structured output, else `answer`, else the JSON in its text."""
    if isinstance(event.get('structured_output'), dict): return event['structured_output']
    return _json_object(event.get('result')) if answer is None else answer


def _called(block, state, labels):
    """The events of a Claude Code tool call, kept pending for its result: shown when an EAOS or reading tool."""
    tool = str(block.get('name') or '')
    short = tool.removeprefix('mcp__eaos__')
    state['pending'][block.get('id')] = (short, block.get('input') or {})
    return tool_events(short, block.get('input'), labels) if tool.startswith('mcp__eaos__') or short in READS else []


class Codex(Adapter):
    id, name, id_command = 'codex', 'Codex', 'codex'

    def logged_in(self):
        done = self._run('login', 'status')
        if done is None: return bool(self._detected and self._detected[1]['logged_in'])
        return bool(done.returncode == 0 and 'not logged in' not in (done.stdout + done.stderr).lower())

    def argv(self, prompt, run, folder, session=None, tools=None):
        """`tools`: the EAOS tools this run may call (None: every one but the person's)."""
        server, env = eaos_server(run, self.name)
        quoted = lambda value: json.dumps(str(value))
        listed = lambda names: '[' + ', '.join(quoted(name) for name in names) + ']'
        limit = f'enabled_tools={listed(tools)}' if tools else f'disabled_tools={listed(PERSON_ONLY)}'
        table = (f'mcp_servers.eaos={{command={quoted(server[0])}, args={listed(server[1:])}, '
                 f'startup_timeout_sec=60, tool_timeout_sec=120, {limit}, env={{{", ".join(f"{k}={quoted(v)}" for k, v in env.items())}}}}}')
        options = ['--json', '--skip-git-repo-check', '-c', table, '-c', 'approval_policy="never"', '-c', 'sandbox_mode="read-only"']
        if session: return self.command + ['exec', 'resume', *options, session, prompt]
        return self.command + ['exec', *options, prompt]

    def ask_argv(self, schema, folder, images=()):
        """One question on standard input (`-`), a read-only sandbox, nothing kept: the answer held to `schema`; the
        pictures of a question about them attached with -i."""
        path = folder / 'schema.json'
        path.write_text(json.dumps(schema), encoding='utf-8')
        return self.command + ['exec', '--json', '--skip-git-repo-check', '--ephemeral', '--output-schema', str(path),
                               '-c', 'approval_policy="never"', '-c', 'sandbox_mode="read-only"',
                               *[part for image in images for part in ('-i', str(image))], '-']

    def model(self):
        """The `model` of the person's Codex configuration, when they set one."""
        import re
        try: text = (Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex') / 'config.toml').read_text(encoding='utf-8')
        except OSError: return None
        found = re.search(r'^\s*model\s*=\s*"([^"]+)"', text, re.M)
        return found.group(1) if found else None

    def answer(self, lines):
        """(answer, model, failure) from the stream of an `ask`: the last agent message is the answer."""
        answer, failure = None, None
        for event in _events(lines):
            item = event.get('item') or {}
            if event.get('type') == 'item.completed' and item.get('type') == 'agent_message':
                answer = _json_object(item.get('text'))
            elif event.get('type') in ('turn.failed', 'error'): failure = str(_codex_error(event))[:500]
        return answer, self.model(), failure

    def parse(self, line, state, labels):
        """The events of one line of `codex exec --json`."""
        event = _event(line)
        if event is None: return []
        kind, item = event.get('type'), event.get('item') or {}
        if kind == 'thread.started':
            state['session'] = event.get('thread_id') or state['session']
            return [self._started(state)]
        if kind in ('turn.failed', 'error'): state['failed'] = str(_codex_error(event))
        handler = _CODEX_ITEMS.get((kind, item.get('type')))
        return handler(item, state, labels) if handler else []


def _codex_error(event):
    """What a Codex failed turn or error line says."""
    return (event.get('error') or {}).get('message') if isinstance(event.get('error'), dict) else event.get('message') or event['type']


def _codex_call(item, state, labels):
    """The events of an EAOS tool call Codex starts."""
    return tool_events(item.get('tool'), item.get('arguments'), labels) if item.get('server') == 'eaos' else []


def _codex_result(item, state, labels):
    """The events of an EAOS tool's answer to Codex, kept with the run's results."""
    if item.get('server') != 'eaos': return []
    payload = json_text(((item.get('result') or {}).get('content')) or []) if item.get('result') else ({'error': item.get('error')} if item.get('error') else None)
    state['eaos_results'].append((item.get('tool'), payload))
    return result_events(item.get('tool'), item.get('arguments'), payload, labels)


def _codex_said(item, state, labels):
    """The events of Codex's words, the last of them its final answer."""
    if not str(item.get('text') or '').strip(): return []
    state['texts'].append(item['text'])
    state['final'] = item['text']
    return said(item['text'])


def _codex_command(item, state, labels):
    """The step event of a command Codex runs to look around."""
    return [('step', {'en': 'The assistant ran a command to look around', 'ar': 'المساعد شغّل أمرًا ليستكشف'},
             {'tool': 'command'}, str(item.get('command') or '')[:500])]


def _codex_file_change(item, state, labels):
    """The edit event of a file Codex tried to change outside EAOS (its sandbox is read only)."""
    paths = [str(c.get('path')) for c in item.get('changes') or [] if isinstance(c, dict)]
    return [('edit', {'en': 'The assistant tried to change a file outside EAOS', 'ar': 'المساعد حاول يغيّر ملفًا خارج EAOS'},
             {'card': None, 'paths': paths, 'diff': '', 'kept': False}, None)]


# Each (line type, item type) of Codex's stream that gives events, and what reads it.
_CODEX_ITEMS = {('item.started', 'mcp_tool_call'): _codex_call, ('item.completed', 'mcp_tool_call'): _codex_result,
                ('item.completed', 'agent_message'): _codex_said, ('item.started', 'command_execution'): _codex_command,
                ('item.completed', 'file_change'): _codex_file_change}


ADAPTERS = (ClaudeCode, Codex)


class AskFailed(Exception):
    """The assistant did not answer: it failed, was stopped, or said something that is not the asked JSON."""


def _json_object(text):
    """The JSON object in an answer's text (alone, or inside a ```json fence); None when there is none."""
    text = str(text or '').strip()
    if text.startswith('```'): text = text.split('\n', 1)[-1].rsplit('```', 1)[0]
    try: value = json.loads(text)
    except ValueError:
        start, end = text.find('{'), text.rfind('}')
        try: value = json.loads(text[start:end + 1]) if 0 <= start < end else None
        except ValueError: value = None
    return value if isinstance(value, dict) else None


def ask(adapter, prompt, schema, folder, cancel=None, started=None, images=()):
    """Ask the assistant one question and return {answer, model, assistant, seconds, cost_usd}.

    The prompt goes on standard input, so its size never meets the argument limit; the process runs in its own group in
    `folder` (never in the project, whose instructions are not the planner's); `started(pid)` hears its pid, so the run
    manager can pause or stop it. It works as long as it needs: `cancel` (a threading.Event) ends the whole group and
    raises AskFailed('stopped'), and only an assistant silent for eaos/core/system/process.py STUCK seconds is ended as
    stuck (Stuck). An answer that is not a JSON object raises AskFailed. The stream stays in `folder`. `images`: the
    pictures the question is about, the only files the assistant may open."""
    from ...core.system.process import wait
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stream, began = folder / 'stream.jsonl', time.monotonic()
    with open(stream, 'wb') as out, open(folder / 'stderr.log', 'wb') as err:
        process = subprocess.Popen(adapter.ask_argv(schema, folder, images), cwd=folder, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                   start_new_session=True)
        if started: started(process.pid)
        try:
            process.stdin.write(prompt.encode('utf-8'))
            process.stdin.close()
        except OSError:
            pass
        wait(process, (out, err), cancel)
    if cancel is not None and cancel.is_set(): raise AskFailed('stopped')
    lines = stream.read_text(encoding='utf-8', errors='replace').splitlines()
    answer, model, failure = adapter.answer(lines)
    if failure or answer is None:
        tail = (folder / 'stderr.log').read_text(encoding='utf-8', errors='replace')[-400:].strip()
        raise AskFailed(failure or f'no JSON answer (exit {process.returncode})' + (f': {tail}' if tail else ''))
    return {'answer': answer, 'model': model or adapter.model(), 'assistant': adapter.name, 'seconds': round(time.monotonic() - began, 1),
            'cost_usd': adapter.cost(lines)}


def installed():
    """Every adapter of this computer, by id."""
    return {cls.id: cls() for cls in ADAPTERS}
