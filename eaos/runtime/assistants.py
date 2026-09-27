"""Which AI assistant EAOS uses on this machine: the one the person already signed in to. No key, no config file.

$EAOS_ASSISTANT (claude or codex) chooses; otherwise Claude Code, then Codex, whichever is installed first.
"""
import os
import shutil
import sys

ADAPTERS = {'claude': 'eaos.runtime.claude_adapter', 'codex': 'eaos.runtime.codex_adapter'}


def available():
    """The assistants installed here, in the order EAOS prefers them."""
    wanted = os.environ.get('EAOS_ASSISTANT')
    names = [wanted] if wanted in ADAPTERS else list(ADAPTERS)
    return [name for name in names if shutil.which(name)]


def provider(max_calls=20, timeout=600):
    """(name, provider) for the preferred installed assistant, or (None, None)."""
    from .provider import Provider
    found = available()
    if not found: return None, None
    name = found[0]
    return name, Provider({'kind': 'command', 'argv': [sys.executable, '-m', ADAPTERS[name]],
                           'timeout_seconds': timeout, 'max_calls': max_calls})
