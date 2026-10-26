"""What the Studio's branch control is built on: git run safely, a branch name checked, a refusal in plain words."""
import os
import re
import subprocess
from datetime import datetime, timezone


RECOVERY = 'refs/eaos-recovery/'
EAOS_NAME, EAOS_EMAIL = 'EAOS', 'eaos@localhost'
COMMITS_SHOWN, FILES_SHOWN, REFS_SHOWN = 50, 200, 400
DIFF_LIMIT = 64 * 1024
NAME = re.compile(r'[^\x00-\x20\x7f~^:?*\[\\]{1,200}')


class Blocked(LookupError):
    """A change that cannot happen now, with every reason in plain words."""

    def __init__(self, reasons, needs=None):
        super().__init__('; '.join(reason['en'] for reason in reasons))
        self.reasons, self.needs = reasons, needs


def say(en, ar, code):
    return {'code': code, 'en': en, 'ar': ar}


def git(project, *args, timeout=60, env=None):
    """git -C project <args> as argv; a timeout is an exit code of 124, never an exception."""
    environment = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_OPTIONAL_LOCKS': '0', 'LC_ALL': 'C', **(env or {})}
    try:
        return subprocess.run(['git', '-C', str(project), *args], capture_output=True, text=True, timeout=timeout, env=environment)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, '', 'git timed out')


def _out(project, *args):
    done = git(project, *args)
    return done.stdout.strip() if done.returncode == 0 else None


def _eaos_env():
    return {'GIT_AUTHOR_NAME': EAOS_NAME, 'GIT_AUTHOR_EMAIL': EAOS_EMAIL, 'GIT_COMMITTER_NAME': EAOS_NAME, 'GIT_COMMITTER_EMAIL': EAOS_EMAIL}


def valid_name(project, name):
    """The branch name as given, when git accepts it as a branch name; ValueError otherwise (a leading dash, a control
    character, `..`, a shell metacharacter git refuses, or a name git would rewrite)."""
    if not isinstance(name, str) or name.startswith('-') or not NAME.fullmatch(name):
        raise ValueError('not a valid branch name')
    done = git(project, 'check-ref-format', '--branch', name)
    if done.returncode or done.stdout.strip() != name: raise ValueError('not a valid branch name')
    return name


def work_of(record):
    """The work branch a run made or worked on: its result's branch, except for a branch operation (select, merge,
    delete, ...), whose result names the branches it acted on, not a branch of its own."""
    if record.get('branch_op'): return None
    return (record.get('result') or {}).get('branch') or record.get('work_branch')


def _when(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec='seconds')


def _roles(kind, name, known):
    """What a branch is to the project: open in its folder, the one analysed, the report's, the base, the default."""
    local, context = kind == 'local', known['context']
    return [role for role, on in (('checkout', local and name == known['head']['branch']),
                                  ('analysis', local and name == context['analysis']['branch']),
                                  ('report', local and name == context['report']['branch']),
                                  ('base', local and name == known['base']),
                                  ('default', name == known['default']['name'])) if on]
