"""The behaviour lock's folder in the sandbox copy (eaos/live/behavior_lock.py runs it): the report's specs, the
browser config that reaches loopback only, EAOS's stream reporter and pytest settings, and what the first pass
recorded, kept for every later run and put back where the tools look for it."""
import json
import os
import shutil
from pathlib import Path

# ── NS26: the lock, run on the original code ────────────────────────────────────────────────────────────
# The browser reaches loopback only: Chromium sends every other host to a proxy nobody answers on, so a
# page's call to production or a third party fails inside the run instead of leaving the machine.
LOCK_CONFIG = """import base from './playwright.config';

// Written by EAOS for a run in the sandbox: the generated config, with every non-loopback host refused.
// Loopback is named in the bypass list: every other host goes to a proxy nobody answers on.
const offline = { launchOptions: { args: ['--proxy-server=http://127.0.0.1:9', '--proxy-bypass-list=127.0.0.1;localhost;[::1]'] } };
export default {
  ...base,
  reporter: [['json', { outputFile: process.env.EAOS_LOCK_REPORT }], ['./stream-reporter.mjs', { outputFile: process.env.EAOS_LOCK_STREAM }]],
  use: { ...base.use, ...offline },
  projects: (base.projects ?? []).map((project) => ({ ...project, use: { ...project.use, ...offline } })),
};
"""

# The approval tests run from the copy's root with this file as their settings: the project's pytest settings and
# conftest files stay out.
APPROVALS_INI = "[pytest]\n# Written by EAOS: the lock's approval tests, run without the project's pytest settings.\n"
# EAOS's stream reporter: a line per test as it begins and ends (eaos/live/lock_results.py Screens follows it).
REPORTER = Path(__file__).resolve().parents[1] / 'templates/screens/stream-reporter.mjs'


def _prepare(live, report, recorded=None):
    """The lock folder in the sandbox copy: the report's specs, the offline config, and what the original recorded
    in `recorded` (behavior-lock/ of the runtime folder) if given."""
    lock = live.sandbox.copy / '.eaos-lock'
    shutil.rmtree(lock, ignore_errors=True)
    shutil.copytree(Path(report) / 'behavior-lock', lock)
    (lock / 'lock.config.ts').write_text(LOCK_CONFIG, encoding='utf-8')
    shutil.copyfile(REPORTER, lock / REPORTER.name)
    # The specs import @playwright/test, which most projects do not install; ES modules ignore NODE_PATH. The
    # lock always runs EAOS's pinned Playwright, the version its installed browsers belong to.
    from ..core.toolchain import home
    # its real path: in the run's own view the tools are shown at their name and at their real path, two mounts, and the
    # runner (found on PATH through the same links) loads Playwright from the real one: one copy, never two
    modules = Path(os.path.realpath(home() / 'node/node_modules'))
    if modules.is_dir() and not (lock / 'node_modules').exists(): (lock / 'node_modules').symlink_to(modules, target_is_directory=True)
    # Its own package.json: a project declaring "type": "module" must not change how the lock's files load.
    (lock / 'package.json').write_text('{"private": true, "type": "commonjs"}\n', encoding='utf-8')
    (lock / '.auth').mkdir(exist_ok=True)
    (lock / '.auth/user.json').write_text(json.dumps({'cookies': [], 'origins': []}), encoding='utf-8')
    if (lock / 'approvals').is_dir(): (lock / 'pytest.ini').write_text(APPROVALS_INI, encoding='utf-8')
    if recorded is not None: _restore(Path(recorded), lock)
    return lock


def _keep(lock, recorded):
    """What the first pass recorded, kept in `recorded` for every later run: the screens' snapshots (snapshots/) and
    the approved interfaces (approved/). A folder exists only when something was recorded in it."""
    shutil.rmtree(recorded / 'snapshots', ignore_errors=True)
    if (lock / '__screenshots__').is_dir(): shutil.copytree(lock / '__screenshots__', recorded / 'snapshots')
    shutil.rmtree(recorded / 'approved', ignore_errors=True)
    for path in sorted((lock / 'approvals').glob('*.approved.txt')):
        (recorded / 'approved').mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, recorded / 'approved' / path.name)


def _restore(recorded, lock):
    """The recording kept by _keep(), put back where the tools look for it."""
    if (recorded / 'snapshots').is_dir():
        shutil.rmtree(lock / '__screenshots__', ignore_errors=True)
        shutil.copytree(recorded / 'snapshots', lock / '__screenshots__')
    if not (lock / 'approvals').is_dir(): return
    for path in sorted((recorded / 'approved').glob('*.approved.txt')):
        shutil.copyfile(path, lock / 'approvals' / path.name)
