"""Which AI assistant EAOS uses on this machine: the one the person already signed in to. No key, no config file.

$EAOS_ASSISTANT (claude or codex) chooses, and `none` turns every assistant off; otherwise Claude Code, then Codex, whichever is installed first. A project's
own choice (eaos/journeys/guided/ `chosen_assistant`) is passed as `name`. Whether the one chosen really answers is
eaos/ai/assistant/readiness.py.
"""
import os
import shutil
import sys

ADAPTERS = {'claude': 'eaos.ai.assistant.claude_adapter', 'codex': 'eaos.ai.assistant.codex_adapter'}


def available():
    """The assistants installed here, in the order EAOS prefers them."""
    wanted = os.environ.get('EAOS_ASSISTANT')
    if wanted == 'none': return []                       # this computer's choice: no assistant at all
    names = [wanted] if wanted in ADAPTERS else list(ADAPTERS)
    return [name for name in names if shutil.which(name)]


def provider(max_calls=20, name=None):
    """(name, provider) for assistant `name` when it is installed, else for the preferred installed one; (None, None) when
    there is none. The provider's config names its assistant (`assistant`), so the AI nodes ask the same one."""
    from .assistant.command import Provider
    found = [name] if name in ADAPTERS and shutil.which(name) else [] if name in ADAPTERS else available()
    if not found: return None, None
    name = found[0]
    return name, Provider({'kind': 'command', 'argv': [sys.executable, '-m', ADAPTERS[name]], 'max_calls': max_calls, 'assistant': name})
