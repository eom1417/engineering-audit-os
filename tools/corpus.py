"""The compatibility corpus (docs/STANDARDS.md §5, M0.3): real open-source apps pinned in tools/corpus.json, each
checked as a person would (`eaos check --path look --run-app`, no assistant), recording whether the app ran and which of
its expected screens EAOS pictured. A change to running apps or finding screens never lowers the pass rate.

    python tools/corpus.py [name ...] [--record]

Each app is fetched at its commit into a scratch folder under $EAOS_CORPUS (tools/dev_paths.py), checked, and the
folder removed; only the result stays. Without --record it refuses when an app that passed now fails; with --record
it writes the results into tools/corpus.json. Run it as a background job: an app takes minutes.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dev_paths import CORPUS  # noqa: E402  (beside this file)

CATALOG = ROOT / 'tools' / 'corpus.json'
EAOS = Path(sys.executable).parent / 'eaos'
LIMIT = 45 * 60                                # seconds one app's check may take


def git(*args, cwd):
    subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=600)


def fetch(app, folder):
    """The app at its commit in folder/app, as a repository of its own (its subfolder when it has one)."""
    source = folder / 'source'
    source.mkdir()
    git('init', '-q', cwd=source)
    git('remote', 'add', 'origin', app['repository'], cwd=source)
    # Only the commit, and only the subfolder's files: an app inside a large repository (Next.js) costs its own size.
    git('fetch', '-q', '--depth', '1', '--filter=blob:none', 'origin', app['commit'], cwd=source)
    if app.get('subdir'): git('sparse-checkout', 'set', app['subdir'], cwd=source)
    git('checkout', '-q', 'FETCH_HEAD', cwd=source)
    shutil.copytree(source / app.get('subdir', ''), folder / 'app', ignore=shutil.ignore_patterns('.git'))
    shutil.rmtree(source)
    git('init', '-q', cwd=folder / 'app')
    git('add', '.', cwd=folder / 'app')
    git('-c', 'user.name=corpus', '-c', 'user.email=corpus@eaos', 'commit', '-qm', app['commit'], cwd=folder / 'app')


def screen(url):
    """A pictured page as the catalog names screens: '/#/about' for a hash route, else its path without a final /."""
    parts = urlsplit(url)
    path = parts.path.rstrip('/') or '/'
    return f'{path}#{parts.fragment}' if parts.fragment.startswith('/') else path


def _read(path):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, StopIteration): return {}


def _why(technical, setup, ran, missing):
    """Why an app did not pass: what its setup said, or the expected screens not pictured."""
    if ran: return 'not pictured: ' + ', '.join(missing) if missing else ''
    stage = (_read(technical / 'run-manifest.json').get('stages') or {}).get('setup') or {}
    return '; '.join(map(str, setup.get('limitations') or [])) or stage.get('reason') or 'the app did not start'


def result(output, expected, seconds, error=''):
    """What the check of one app showed: ran, the expected screens pictured and missing, passed, and why not."""
    technical = next(output.rglob('run-manifest.json'), output / 'none').parent
    setup = _read(technical / 'live' / 'setup.json')
    rows = _read(technical / 'live' / 'screens.json').get('rows') or []
    pictured = sorted({screen(row.get('landed') or row['url']) for row in rows})   # where it landed: a redirect is not the page
    missing = [route for route in expected if (route.rstrip('/') or '/') not in pictured]
    ran = bool(setup.get('ok'))
    why = error or _why(technical, setup, ran, missing)
    return {'date': date.today().isoformat(), 'ran': ran, 'pictured': pictured, 'missing': missing,
            'passed': ran and not missing, 'seconds': round(seconds), **({'why': why[:400]} if why else {})}


def check(app):
    CORPUS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=CORPUS, prefix=f"{app['name']}-") as scratch:
        folder, began, error = Path(scratch), time.monotonic(), ''
        environment = {**os.environ, 'EAOS_HOME': str(folder / 'home'), 'EAOS_OUTPUT': str(folder / 'output')}
        try:
            fetch(app, folder)
            subprocess.run([str(EAOS), 'check', '--path', 'look', '--run-app', '--assistant', 'none', '--lang', 'en', '--watch'],
                           cwd=folder / 'app', env=environment, capture_output=True, timeout=LIMIT)
        except (subprocess.SubprocessError, OSError) as failed:
            error = f'{type(failed).__name__}: {str(failed)[-300:]}'
        return result(folder / 'output', app['screens'], time.monotonic() - began, error)


def _line(app, now):
    shown = f"pictured {len(app['screens']) - len(now['missing'])}/{len(app['screens'])}"
    return f"{app['name']:24} ran={now['ran']!s:5} {shown} {'PASS' if now['passed'] else 'FAIL ' + now.get('why', '')[:150]}"


def main(names, record=False):
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    worse = []
    for app in catalog['apps']:
        if names and app['name'] not in names: continue
        now = check(app)
        print(_line(app, now), flush=True)
        if (app.get('result') or {}).get('passed') and not now['passed']: worse.append(app['name'])
        if record: app['result'] = now
    run = [app for app in catalog['apps'] if app.get('result')]
    print(f"corpus: {sum(app['result']['passed'] for app in run)} of {len(run)} apps pass")
    if record: CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    if worse: print('REFUSED, passed before and fail now: ' + ', '.join(worse))
    return 1 if worse and not record else 0


if __name__ == '__main__':
    sys.exit(main([arg for arg in sys.argv[1:] if not arg.startswith('--')], '--record' in sys.argv))
