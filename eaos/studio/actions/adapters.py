"""The person's own assistant, started headless for a run (docs/adoption/ns46-t9-command-centre.md).

An adapter knows one assistant: whether it is installed and logged in, the command that starts it on a prompt (and
resumes its session with the person's answer) with the EAOS MCP server and nothing else that writes, and how to read
its output, one JSON object per line, as the contract's events. The run manager does the rest.

Claude Code: `claude -p --output-format stream-json --verbose`, the EAOS server by `--mcp-config --strict-mcp-config`,
EAOS tools plus Read, Grep and Glob allowed, and Bash, Edit, Write and the person-only EAOS tools refused.
Codex: `codex exec --json`, the EAOS server by `-c mcp_servers.eaos=...`, a read-only sandbox and no approvals.

`ask(adapter, prompt, schema, folder)` is the other way to use an assistant: one question, no tool, an answer the
assistant's own CLI holds to a JSON Schema (Claude Code `--json-schema`, Codex `--output-schema`). The planned ideal
(eaos/studio/ideal.py) asks this way, and so does any AI node after it.
"""
import difflib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

PERSON_ONLY = ('accept', 'undo', 'choose_branch')
READS = {'finding': 'id', 'fix_read': 'path', 'build_read': 'path', 'report_file': 'name', 'Read': 'file_path', 'Grep': 'pattern', 'Glob': 'pattern'}
EDITS = ('fix_edit', 'build_edit')


def eaos_server(run, assistant):
    """The EAOS MCP server's argv and environment for a run: this very EAOS (the Python and the package the Studio runs,
    never another `eaos` on the PATH), the person's EAOS home, and the run's id, which makes the person-only tools refuse
    (eaos/mcp_server.py)."""
    import sys
    env = {'EAOS_STUDIO_RUN': run, 'EAOS_ASSISTANT': assistant, 'PYTHONPATH': str(Path(__file__).resolve().parents[3])}
    for name in ('EAOS_HOME', 'EAOS_OUTPUT', 'EAOS_ENGINE_TOOLS'):
        if os.environ.get(name): env[name] = os.environ[name]
    return [sys.executable, '-m', 'eaos', 'mcp'], env


def _diff(edit):
    path = edit.get('path') or '?'
    if edit.get('delete'): return f'--- a/{path}\n+++ /dev/null\n(deleted)\n'
    if 'content' in edit:
        lines = str(edit['content']).splitlines(keepends=True)
        return ''.join(difflib.unified_diff([], lines, 'a/' + path, 'b/' + path))
    return ''.join(difflib.unified_diff(str(edit.get('find') or '').splitlines(keepends=True),
                                        str(edit.get('replace') or '').splitlines(keepends=True), 'a/' + path, 'b/' + path))


def tool_events(tool, arguments, labels):
    """The events of an EAOS (or read-only built-in) tool call, as it starts: (kind, text, data, detail)."""
    arguments = arguments or {}
    label = labels.get(tool) or {'en': tool, 'ar': tool}
    if tool in EDITS:
        edits = [e for e in arguments.get('edits') or [] if isinstance(e, dict)]
        paths = sorted({str(e.get('path')) for e in edits if e.get('path')})
        card = arguments.get('card')
        return [('edit', {'en': f"Changing {', '.join(paths) or 'files'} for {card}", 'ar': f"يعدّل {', '.join(paths) or 'ملفات'} للبطاقة {card}"},
                 {'card': card, 'paths': paths, 'diff': ''.join(_diff(e) for e in edits), 'kept': None, 'summary': arguments.get('summary')}, None)]
    if tool in READS:
        what = str(arguments.get(READS[tool]) or '')
        return [('read', {'en': f"{label['en']}: {what}", 'ar': f"{label['ar']}: {what}"}, {'path': what, 'tool': tool}, None)]
    card = arguments.get('card') or arguments.get('id')
    shown = {k: v for k, v in arguments.items() if k not in ('project', 'edits', 'spec', 'proposal', 'text') and v not in (None, '', [], {})}
    return [('step', {'en': label['en'] + (f': {card}' if card else ''), 'ar': label['ar'] + (f': {card}' if card else '')},
             {'tool': tool, 'card': card}, json.dumps(shown, ensure_ascii=False)[:2000] if shown else None)]


def result_events(tool, arguments, payload, labels=None):
    """The events an EAOS tool's answer gives: a check's verdict, a job's progress, an error the assistant will read.
    A tool's error is said plainly (which step could not answer, and that the assistant goes on); its technical words
    are the detail."""
    if not isinstance(payload, dict): return []
    out = []
    if payload.get('error'):
        label = (labels or {}).get(tool) or {'en': tool, 'ar': tool}
        out.append(('error', {'en': f"\u201c{label['en']}\u201d could not answer this time; the assistant reads why and goes on",
                              'ar': f"\u00ab{label['ar']}\u00bb ما قدر يجاوب هالمرة؛ المساعد يقرأ السبب ويكمل"},
                    {'reason': str(payload['error'])[:2000], 'tool': tool, 'recoverable': True,
                     'what_now': {'en': 'Nothing to do: the assistant goes on.', 'ar': 'ما عليك شي: المساعد يكمل.'}},
                    str(payload['error'])[:2000] + (f"\n{payload['what_now']}" if payload.get('what_now') else '')))
        return out
    progress = payload.get('progress')
    if isinstance(progress, dict) and progress.get('total'):
        out.append(('progress', {'en': f"{progress.get('stage') or tool}: {progress.get('done')} of {progress.get('total')}",
                                 'ar': f"{progress.get('stage') or tool}: {progress.get('done')} من {progress.get('total')}"},
                    {'batch': payload.get('batch'), 'done': progress.get('done'), 'total': progress.get('total'), 'stage': progress.get('stage')}, None))
    result = payload.get('result') if isinstance(payload.get('result'), dict) else payload
    if isinstance(result.get('kept'), bool):
        card = result.get('card') or (arguments or {}).get('card')
        why = str(result.get('why') or '')[:400]
        out.append(('check', {'en': f"{card}: {'the change passed its checks' if result['kept'] else 'the change was taken back: ' + why}",
                              'ar': f"{card}: {'التغيير نجح في الفحص' if result['kept'] else 'التغيير أُرجع: ' + why}"},
                    {'name': 'card gates', 'card': card, 'passed': result['kept'], 'summary': why}, None))
    if result.get('branch') and tool in ('fix_finish', 'build_finish', 'wait'):
        out.append(('check', {'en': f"Handed over on the branch {result['branch']}", 'ar': f"سُلّم على الفرع {result['branch']}"},
                    {'name': 'batch gates', 'passed': True, 'summary': f"branch {result['branch']}", 'branch': result['branch']}, None))
    return out


def said(text):
    """The assistant's words as a `say` event, without the question block (the question has its own event)."""
    from .prompts import QUESTION
    words = QUESTION.sub('', str(text or '')).strip()
    return [('say', {'en': words, 'ar': words}, {'words': words}, None)] if words else []


def _json_text(content):
    """The JSON an MCP tool answered, from a tool_result's content (text, or a list of text parts; maybe wrapped in {"result"})."""
    if isinstance(content, list): content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))
    if isinstance(content, dict): content = json.dumps(content)
    try: value = json.loads(content)
    except (TypeError, ValueError): return None
    if isinstance(value, dict) and set(value) == {'result'} and isinstance(value['result'], str):
        try: value = json.loads(value['result'])
        except ValueError: return None
    return value


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
        if version is None and self._detected and self._detected[1]['installed'] and shutil.which(self.command[0]):
            self._detected = (time.monotonic(), self._detected[1])
            return self._detected[1]
        installed = bool(version and version.returncode == 0)
        found = {'id': self.id, 'name': self.name, 'installed': installed, 'logged_in': installed and self.logged_in(),
                 'version': (version.stdout.strip().splitlines() or [''])[0][:80] if installed else None}
        self._detected = (time.monotonic(), found)
        return found

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

    def ask_argv(self, schema, folder):
        """One question on standard input, no tool, no MCP server, nothing kept: the answer held to `schema`, streamed
        as it is written."""
        return self.command + ['-p', '--output-format', 'stream-json', '--verbose', '--include-partial-messages',
                               '--json-schema', json.dumps(schema), '--tools', '', '--strict-mcp-config', '--no-session-persistence']

    def cost(self, lines):
        """`total_cost_usd` of the stream's result line."""
        for line in reversed(lines):
            try: event = json.loads(line)
            except ValueError: continue
            if isinstance(event, dict) and event.get('type') == 'result' and isinstance(event.get('total_cost_usd'), (int, float)):
                return float(event['total_cost_usd'])
        return None

    def answer(self, lines):
        """(answer, model, failure) from the stream of an `ask`."""
        answer, model, failure = None, None, None
        for line in lines:
            try: event = json.loads(line)
            except ValueError: continue
            if not isinstance(event, dict): continue
            if event.get('type') == 'system' and event.get('subtype') == 'init': model = event.get('model') or model
            elif event.get('type') == 'assistant':
                model = (event.get('message') or {}).get('model') or model
                for block in (event.get('message') or {}).get('content') or []:
                    if isinstance(block, dict) and block.get('type') == 'tool_use' and block.get('name') == 'StructuredOutput':
                        answer = block.get('input')
            elif event.get('type') == 'result':
                if event.get('is_error') or event.get('subtype') not in (None, 'success'):
                    failure = str(event.get('result') or event.get('subtype') or 'the assistant failed')[:500]
                elif isinstance(event.get('structured_output'), dict): answer = event['structured_output']
                elif answer is None: answer = _json_object(event.get('result'))
        return answer, model, failure

    def parse(self, line, state, labels):
        """The events of one line of Claude Code's stream-json."""
        try: event = json.loads(line)
        except ValueError: return []
        if not isinstance(event, dict): return []
        state['session'] = event.get('session_id') or state['session']
        kind, out = event.get('type'), []
        if kind == 'system' and event.get('subtype') == 'init':
            out.append(('step', {'en': 'Claude Code went on', 'ar': 'Claude Code كمّل'} if state['resumed'] else {'en': 'Claude Code started', 'ar': 'بدأ Claude Code'},
                        {'tool': None, 'assistant': self.name}, None))
        elif kind == 'assistant':
            for block in (event.get('message') or {}).get('content') or []:
                if block.get('type') == 'tool_use':
                    tool = str(block.get('name') or '')
                    short = tool[len('mcp__eaos__'):] if tool.startswith('mcp__eaos__') else tool
                    state['pending'][block.get('id')] = (short, block.get('input') or {})
                    if tool.startswith('mcp__eaos__') or short in READS: out += tool_events(short, block.get('input'), labels)
                elif block.get('type') == 'text' and str(block.get('text') or '').strip():
                    state['texts'].append(block['text'])
                    out += said(block['text'])
        elif kind == 'user':
            for block in (event.get('message') or {}).get('content') or []:
                if not isinstance(block, dict) or block.get('type') != 'tool_result': continue
                tool, arguments = state['pending'].pop(block.get('tool_use_id'), (None, {}))
                if tool and tool in labels:
                    payload = _json_text(block.get('content'))
                    state['eaos_results'].append((tool, payload))
                    out += result_events(tool, arguments, payload, labels)
        elif kind == 'result':
            state['final'] = str(event.get('result') or '')
            if event.get('is_error') or event.get('subtype') not in (None, 'success'):
                state['failed'] = state['final'] or str(event.get('subtype'))
        return out


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

    def ask_argv(self, schema, folder):
        """One question on standard input (`-`), a read-only sandbox, nothing kept: the answer held to `schema`."""
        path = folder / 'schema.json'
        path.write_text(json.dumps(schema), encoding='utf-8')
        return self.command + ['exec', '--json', '--skip-git-repo-check', '--ephemeral', '--output-schema', str(path),
                               '-c', 'approval_policy="never"', '-c', 'sandbox_mode="read-only"', '-']

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
        for line in lines:
            try: event = json.loads(line)
            except ValueError: continue
            if not isinstance(event, dict): continue
            item = event.get('item') or {}
            if event.get('type') == 'item.completed' and item.get('type') == 'agent_message':
                answer = _json_object(item.get('text'))
            elif event.get('type') in ('turn.failed', 'error'):
                failure = str((event.get('error') or {}).get('message') if isinstance(event.get('error'), dict) else event.get('message') or event['type'])[:500]
        return answer, self.model(), failure

    def parse(self, line, state, labels):
        """The events of one line of `codex exec --json`."""
        try: event = json.loads(line)
        except ValueError: return []
        if not isinstance(event, dict): return []
        kind, item, out = event.get('type'), event.get('item') or {}, []
        if kind == 'thread.started':
            state['session'] = event.get('thread_id') or state['session']
            out.append(('step', {'en': 'Codex went on', 'ar': 'Codex كمّل'} if state['resumed'] else {'en': 'Codex started', 'ar': 'بدأ Codex'},
                        {'tool': None, 'assistant': self.name}, None))
        elif kind == 'item.started' and item.get('type') == 'mcp_tool_call' and item.get('server') == 'eaos':
            out += tool_events(item.get('tool'), item.get('arguments'), labels)
        elif kind == 'item.completed' and item.get('type') == 'mcp_tool_call' and item.get('server') == 'eaos':
            payload = _json_text(((item.get('result') or {}).get('content')) or []) if item.get('result') else ({'error': item.get('error')} if item.get('error') else None)
            state['eaos_results'].append((item.get('tool'), payload))
            out += result_events(item.get('tool'), item.get('arguments'), payload, labels)
        elif kind == 'item.completed' and item.get('type') == 'agent_message' and str(item.get('text') or '').strip():
            state['texts'].append(item['text'])
            state['final'] = item['text']
            out += said(item['text'])
        elif kind == 'item.started' and item.get('type') == 'command_execution':
            out.append(('step', {'en': 'The assistant ran a command to look around', 'ar': 'المساعد شغّل أمرًا ليستكشف'},
                        {'tool': 'command'}, str(item.get('command') or '')[:500]))
        elif kind == 'item.completed' and item.get('type') == 'file_change':
            paths = [str(c.get('path')) for c in item.get('changes') or [] if isinstance(c, dict)]
            out.append(('edit', {'en': 'The assistant tried to change a file outside EAOS', 'ar': 'المساعد حاول يغيّر ملفًا خارج EAOS'},
                        {'card': None, 'paths': paths, 'diff': '', 'kept': False}, None))
        elif kind in ('turn.failed', 'error'):
            state['failed'] = str((event.get('error') or {}).get('message') if isinstance(event.get('error'), dict) else event.get('message') or kind)
        return out


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


def ask(adapter, prompt, schema, folder, cancel=None, started=None):
    """Ask the assistant one question and return {answer, model, assistant, seconds, cost_usd}.

    The prompt goes on standard input, so its size never meets the argument limit; the process runs in its own group in
    `folder` (never in the project, whose instructions are not the planner's); `started(pid)` hears its pid, so the run
    manager can pause or stop it. It works as long as it needs: `cancel` (a threading.Event) ends the whole group and
    raises AskFailed('stopped'), and only an assistant silent for eaos/runtime/provider.py STUCK seconds is ended as
    stuck (Stuck). An answer that is not a JSON object raises AskFailed. The stream stays in `folder`."""
    from ...runtime.provider import wait
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stream, began = folder / 'stream.jsonl', time.monotonic()
    with open(stream, 'wb') as out, open(folder / 'stderr.log', 'wb') as err:
        process = subprocess.Popen(adapter.ask_argv(schema, folder), cwd=folder, stdin=subprocess.PIPE, stdout=out, stderr=err,
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
