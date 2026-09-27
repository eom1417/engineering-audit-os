"""`eaos assistant install`: teach the person's AI assistant to use EAOS, with one command and no file to edit.

For Claude Code: the skill in ~/.claude/skills/eaos/SKILL.md, and the EAOS MCP server registered for the user
(`claude mcp add --scope user eaos -- <eaos> mcp`). For Codex: the same guide between two marker lines in
~/.codex/AGENTS.md (the rest of that file is left as it is), and the MCP server in ~/.codex/config.toml.
Running it again replaces EAOS's own part and nothing else. Both assistants read eaos/templates/assistants/.
"""
import os
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


def claude(home):
    skill = home / '.claude/skills/eaos/SKILL.md'
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text((TEMPLATES / 'claude-skill.md').read_text(encoding='utf-8'), encoding='utf-8')
    if shutil.which('claude'):
        listed = subprocess.run(['claude', 'mcp', 'get', 'eaos'], capture_output=True, text=True, env={**os.environ, 'HOME': str(home)})
        if listed.returncode != 0:
            subprocess.run(['claude', 'mcp', 'add', '--scope', 'user', 'eaos', '--', *eaos_command(), 'mcp'],
                           capture_output=True, text=True, env={**os.environ, 'HOME': str(home)})
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
                          + f'[mcp_servers.eaos]\ncommand = "{argv[0]}"\nargs = [{quoted}]\n', encoding='utf-8')
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
