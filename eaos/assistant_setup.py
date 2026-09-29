"""`eaos assistant install`: teach the person's AI assistant to use EAOS, with one command and no file to edit.

For Claude Code: the skill in ~/.claude/skills/eaos/SKILL.md, and the EAOS MCP server registered for the user
(`claude mcp add --scope user eaos -- <eaos> mcp`). For Codex: the same guide between two marker lines in
~/.codex/AGENTS.md (the rest of that file is left as it is), and the MCP server in ~/.codex/config.toml.
For both, a session-start hook (~/.claude/settings.json, ~/.codex/hooks.json) that runs `eaos handover --hook`: when EAOS
has work open in the folder, a new session is told at once where it stopped (eaos/handover.hook_context), so the
other assistant goes on after a usage limit. Codex asks the person once to trust a new hook; Claude Code does not.
Running it again replaces EAOS's own part and nothing else. Both assistants read eaos/templates/assistants/.
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent / 'templates/assistants'
BEGIN, END = '<!-- EAOS: begin (eaos assistant install) -->', '<!-- EAOS: end -->'


def eaos_command():
    """The argv that starts this EAOS: its installed command, or this Python running the package."""
    found = shutil.which('eaos')
    return [found] if found else [sys.executable, '-m', 'eaos']


def _hook():
    return {'type': 'command', 'command': ' '.join(shlex.quote(part) for part in eaos_command() + ['handover', '--hook']), 'timeout': 20}


def add_session_hook(path):
    """EAOS's SessionStart hook in a hooks file of Claude Code's shape ({"hooks": {"SessionStart": [{"hooks": [...]}]}}),
    replacing an older EAOS hook and keeping everything else in the file as it is."""
    path = Path(path)
    try: data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    except ValueError: return None                       # a file the person broke is theirs to fix: never overwritten
    groups = (data.setdefault('hooks', {})).setdefault('SessionStart', [])
    for group in groups:
        group['hooks'] = [h for h in group.get('hooks') or [] if 'handover --hook' not in str(h.get('command', ''))]
    groups[:] = [g for g in groups if g.get('hooks')] + [{'hooks': [_hook()]}]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def claude(home):
    skill = home / '.claude/skills/eaos/SKILL.md'
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text((TEMPLATES / 'claude-skill.md').read_text(encoding='utf-8'), encoding='utf-8')
    if shutil.which('claude'):
        listed = subprocess.run(['claude', 'mcp', 'get', 'eaos'], capture_output=True, text=True, env={**os.environ, 'HOME': str(home)})
        if listed.returncode != 0:
            subprocess.run(['claude', 'mcp', 'add', '--scope', 'user', 'eaos', '--', *eaos_command(), 'mcp'],
                           capture_output=True, text=True, env={**os.environ, 'HOME': str(home)})
    add_session_hook(home / '.claude/settings.json')
    return skill


def codex(home):
    agents = home / '.codex/AGENTS.md'
    agents.parent.mkdir(parents=True, exist_ok=True)
    text = agents.read_text(encoding='utf-8') if agents.is_file() else ''
    if BEGIN in text and END in text:
        text = text[:text.index(BEGIN)].rstrip('\n') + text[text.index(END) + len(END):]
    block = f"{BEGIN}\n{(TEMPLATES / 'guide.md').read_text(encoding='utf-8').strip()}\n{END}\n"
    agents.write_text((text.rstrip('\n') + '\n\n' if text.strip() else '') + block, encoding='utf-8')
    config = home / '.codex/config.toml'
    current = config.read_text(encoding='utf-8') if config.is_file() else ''
    if '[mcp_servers.eaos]' not in current:
        argv = eaos_command() + ['mcp']
        quoted = ', '.join(f'"{part}"' for part in argv[1:])
        config.write_text(current.rstrip('\n') + ('\n\n' if current.strip() else '')
                          + f'[mcp_servers.eaos]\ncommand = "{argv[0]}"\nargs = [{quoted}]\n'
                          # a tool call may wait up to a minute for a long job, and its first start imports the SDK
                          + 'startup_timeout_sec = 30\ntool_timeout_sec = 120\n', encoding='utf-8')
    add_session_hook(home / '.codex/hooks.json')
    return agents


def install(home=None):
    """The assistants taught: ['Claude Code', 'Codex'], those whose command is on this computer."""
    home = Path(home or Path.home())
    done = []
    if shutil.which('claude'):
        claude(home); done.append('Claude Code')
    if shutil.which('codex'):
        codex(home); done.append('Codex')
    return done
