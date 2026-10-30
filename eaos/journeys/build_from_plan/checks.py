"""The project's own scripts run on the copy of a milestone being built: install when the manifests changed, then
typecheck, lint and test, and on the last milestone its browser journeys (e2e); and the repository's craft of the whole
copy at a milestone's proof (M8.7)."""
import json
import os
import subprocess
from pathlib import Path

CHECK_SCRIPTS = ('typecheck', 'lint', 'test')


def _git(where, *args):
    return subprocess.run(['git', '-C', str(where), *args], capture_output=True, text=True)


def _checks(root, build, progress, browsers=None):
    """The project's own scripts, on the copy: install when the manifests changed, then typecheck, lint and test; with
    `browsers` (the last milestone) its browser journeys too, e2e, with its own Playwright's browsers in that folder."""
    root = Path(root)
    manifest = root / 'package.json'
    if not manifest.is_file(): return [], build
    scripts = json.loads(manifest.read_text(encoding='utf-8')).get('scripts') or {}
    stamp = ''.join(sorted(_git(root, 'ls-files', '-s', '--', '*package.json', 'package-lock.json').stdout.split()))
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'LANG', 'TMPDIR', 'PLAYWRIGHT_BROWSERS_PATH')}
    env.update(CI='1', NODE_ENV='test')
    if build.get('installed') != stamp or not (root / 'node_modules').is_dir():
        failure = _install(root, env, progress)
        if failure: return [failure], build
        build = {**build, 'installed': stamp}
    failed = _scripts_failed(root, env, scripts, progress)
    if browsers and not failed: failed = list(filter(None, [_journeys(root, {**env, 'PLAYWRIGHT_BROWSERS_PATH': str(browsers)}, scripts, progress)]))
    return failed, build


def _scripts_failed(root, env, scripts, progress):
    """The problems of the check scripts (CHECK_SCRIPTS), each run in turn."""
    return [problem for index, script in enumerate(CHECK_SCRIPTS, start=1)
            for problem in [_run_script(root, env, scripts, script, lambda text, n=index: progress(n, 4, text))] if problem]


def _journeys(root, env, scripts, progress):
    """The project's browser journeys (npm run e2e), its own Playwright's browsers fetched once into the project's run
    folder: never EAOS's, read only and of another version (a real build: EAOS's screens never pictured)."""
    progress(3, 4, 'fetching the browsers of the project\'s own journeys')
    done = subprocess.run(['npx', 'playwright', 'install', 'chromium'], cwd=root, capture_output=True, text=True, timeout=1800, env=env)
    if done.returncode: return {'gate': 'e2e', 'where': 'package.json', 'what': 'its Playwright browsers could not be fetched: ' + (done.stdout + done.stderr)[-800:]}
    return _run_script(root, env, scripts, 'e2e', lambda text: progress(3, 4, text))


def _install(root, env, progress):
    """npm install in the copy; the problem when it fails, else None."""
    progress(0, 4, 'installing the libraries')
    done = subprocess.run(['npm', 'install', '--no-audit', '--no-fund', '--loglevel=error'], cwd=root, capture_output=True,
                          text=True, timeout=1800, env=env)
    if done.returncode:
        return {'gate': 'install', 'where': 'package.json', 'what': 'npm install failed: ' + (done.stdout + done.stderr)[-1500:]}
    return None


def _run_script(root, env, scripts, script, say):
    """One of the project's check scripts; the problem when it is missing or fails, else None."""
    if script not in scripts:
        return {'gate': 'scripts', 'where': 'package.json', 'what': f'there is no "{script}" script: the skeleton declares it'}
    say(f'npm run {script}')
    done = subprocess.run(['npm', 'run', script], cwd=root, capture_output=True, text=True, timeout=1800, env=env)
    if done.returncode:
        return {'gate': script, 'where': 'package.json', 'what': f'npm run {script} failed: ' + (done.stdout + done.stderr)[-2000:]}
    return None


def _milestone_proof(state, root, out, step, problems):
    """`problems` with what the repository's craft adds at a milestone's proof; none left, the extension guide of what is
    built so far (M18.3) is written and committed on the copy. `step`: (the card, or None at the proof; the last milestone?)."""
    card, closing = step
    problems = problems + [p for p in _milestone_tidy(root, out, card, closing) if p not in problems]
    if card is None and not problems: _keep_guide(state, root, out)
    return problems


def _keep_guide(state, root, out):
    from ...analysis.layers import check
    from ...analysis.repair import project_guide
    drawn = project_guide.extending.draft(root, out, project_guide.tracked(root), check(root, out), project_guide.pinned_ids(state['project']))
    written = project_guide.write(root, drawn)
    if written:
        _git(root, 'add', '--', *written)
        _git(root, '-c', 'user.name=EAOS', '-c', 'user.email=eaos@localhost', 'commit', '-q', '-m', 'The extension guide, kept with what was built (EAOS)')


def _milestone_tidy(root, out, card, closing):
    """A milestone's proof (not the last: it reads every file) holds the whole copy to the repository's craft (M8.7)."""
    from ...analysis.repair.gates import tidy
    return tidy(None, out, _git(root, 'ls-files').stdout.split()) if card is None and not closing else []
