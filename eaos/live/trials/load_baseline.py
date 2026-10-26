"""The load baseline: every k6 scenario, run on the original code before any change (runtime/performance.json).

A number without its conditions cannot be compared, so the file carries them: the build that ran (a build,
never the development server), the warm-up, the virtual users, the duration and the machine. `after`
(NS22) is written by record_after() only beside a `before` taken under the same conditions.

The project runs from its run profile (eaos/live/app/run.py); a profile may override build, start, env and the folder it
starts in under `baseline`, for a project whose lock runs on its development server but whose load must hit its build.
`baseline.headers` are sent with every request, each a value or {"file": path} the started program wrote (a session's
token, read once it answers), so a route behind a sign-in is loaded as a user would load it, not as a refusal. Each
route is asked once first: one that answers with a stream (text/event-stream, it never ends) or refuses without a
value it needs (a 4xx: a file's name, an id) is left out, and the record says which and why; a load on it would measure
its own timeout or refusal, not the program.
"""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from ...core.contracts.artifact_rules import contracts, validate
from ...core.system.web import opened
from ..app.run import LiveRun
from .load_plans import load_paths

THRESHOLD = re.compile(r"p\(95\)<(\d+(?:\.\d+)?)")
FAILED = re.compile(r"rate<(\d+(?:\.\d+)?)")
STAGES = re.compile(r"duration:\s*'(\d+)([sm])',\s*target:\s*(\d+)")


def machine():
    """What the run had, not what the host has: a container's cgroup limits win over the host's totals."""
    from ...core.system.resources import capacity
    cpus, memory, _ = capacity()
    memory = round(memory / 2 ** 30, 1) if memory is not None else None
    return f'{cpus} CPU, {memory} GiB RAM, {os.uname().sysname} {os.uname().machine}'


def shape(script):
    """(threshold, vus, duration_s, warmup_s) read from a generated k6 script."""
    text = Path(script).read_text(encoding='utf-8')
    stages = [(int(n) * (60 if unit == 'm' else 1), int(target)) for n, unit, target in STAGES.findall(text)]
    threshold = {'p95_ms': float((THRESHOLD.search(text) or [0, 0])[1]), 'error_rate': float((FAILED.search(text) or [0, 0])[1])}
    return threshold, max((t for _, t in stages), default=0), sum(s for s, _ in stages), (stages[0][0] if stages else 0)


def summary(path):
    """(p95_ms, error_rate) from `k6 run --summary-export`."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))['metrics']
    return {'p95_ms': round(float(data['http_req_duration']['p(95)']), 1),
            'error_rate': round(float(data.get('http_req_failed', {}).get('value', 0.0)), 4)}


NOT_FOUND = b'404'


def _answer(url):
    """The body a GET answers; NOT_FOUND when the route is not served; None when it answers otherwise (a sign-in asked)."""
    try:
        with opened(url, timeout=10) as response: return response.read()
    except urllib.error.HTTPError as answer: return NOT_FOUND if answer.code == 404 else None
    except (OSError, ValueError): return None


def headers(live):
    """{name: value} of the profile's baseline.headers, a file's value read from the started copy's app folder."""
    folder = (live.sandbox.copy / (live.profile.get('app') or '.')).resolve()
    sent = {}
    for name, value in ((live.profile.get('baseline') or {}).get('headers') or {}).items():
        if isinstance(value, dict):
            path = (folder / value['file']).resolve()
            if not path.is_relative_to(live.sandbox.copy.resolve()): raise RuntimeError(f'baseline header {name}: {path} is outside the copy')
            value = path.read_text(encoding='utf-8').strip()
        sent[name] = str(value)
    return sent


def loadable(base, paths, sent):
    """(the paths a load requests, {path left out: why}), from asking each once (module docstring)."""
    kept, left = [], {}
    for path in paths:
        try:
            with opened(f'{base}{path}', sent, timeout=10) as response:
                if response.headers.get_content_type() == 'text/event-stream': left[path] = 'a stream that never ends'
                else: kept.append(path)
        except urllib.error.HTTPError as answer:
            if answer.code < 500: left[path] = f'answers {answer.code} without a value it needs'
            else: kept.append(path)                       # a server error is what the load must measure
        except (OSError, ValueError) as problem:
            left[path] = f'no answer ({problem})'[:120]
    return kept, left


class PagesOnly(RuntimeError):
    """The started app serves its pages only: a load on it would not measure the program."""


def refuse_a_page_server(report, base):
    """The load must hit the program, not a server of its pages alone: when most server routes of the code answer
    with the very page `/` answers (a front-end server's fallback), or are not found, the baseline would measure the
    wrong program. Counted as served, a route vite preview did not find let it pass the setup, and the check, knowing more
    routes, refused it too late to ask the assistant (EAOS, 2026-10-15)."""
    from .load_plans import server_routes
    if not report: return
    routes, page = [r for r in server_routes(report) if r != '/'], _answer(f'{base}/')
    if page is not None and sum(_answer(f'{base}{route}') in (page, NOT_FOUND) for route in routes) * 2 > len(routes):
        raise PagesOnly(f'the started app serves only its pages: its {len(routes)} server routes ({", ".join(routes[:3])}...) '
                           'answer with the page itself, so a load on it would not measure the program. Propose a baseline '
                           'whose start runs the real server, serving the built pages and these routes (run_try with mode="baseline", '
                           'its "app" the folder that server starts in, and "headers" the token its routes need).')


def run_baseline(report, target, runtime):
    """Run every nfr/k6 script of the report against the project's build; write runtime/performance.json."""
    report, runtime = Path(report), Path(runtime)
    scripts = sorted((report / 'nfr/k6').glob('*.js'))
    if not scripts: raise RuntimeError(f'{report}/nfr/k6 holds no scenario: the lock stage writes them')
    live = LiveRun(target, runtime, 'S05', mode='baseline')
    if not (live.profile.get('baseline') or {}).get('verified'):     # a plain Node server's production has no build step
        raise RuntimeError('the load baseline runs only the production run the setup verified (run.json baseline): never the development server')
    scenarios, conditions = [], None
    out = runtime / 'runtime'
    out.mkdir(parents=True, exist_ok=True)
    try:
        live.setup()
        base = live.start()
        live.seed(base)
        refuse_a_page_server(report, base)
        sent = headers(live)
        paths, left = loadable(base, load_paths(report), sent)
        if not paths: raise RuntimeError(f'no route answers a plain request: {left}')
        for script in scripts:
            threshold, vus, duration, warmup = shape(script)
            conditions = conditions or _conditions(live, warmup, vus, duration)
            export = out / f'k6-{script.stem}.json'
            _, _, err = live.sandbox.run(['k6', 'run', '--quiet', '--summary-export', str(export), str(script)], timeout=duration + 600,
                                         network=True, env={**live.extra(), 'BASE_URL': base, 'PATHS': json.dumps(paths), 'HEADERS': json.dumps(sent)})
            if not export.is_file(): raise RuntimeError(f'k6 did not run {script.name}: {err.strip()[-300:]}')     # never "no such file"
            scenarios.append({'id': script.stem.upper(), 'script': f'nfr/k6/{script.name}', 'threshold': threshold,
                              'before': summary(export), 'after': None})
    finally:
        live.stop()
        live.record('runtime/baseline-log.json')
    record = {'schema_version': 1, 'conditions': conditions, 'scenarios': scenarios,
              'limitations': _limitations(paths, sent, left),
              'run': {'start': ' '.join(live.profile['start']), 'env': sorted(live.profile.get('env') or {})}}
    problems = validate(record, contracts()['runtime-performance'])
    if problems: raise RuntimeError(f'runtime/performance.json would break its contract: {problems[0]}')
    (out / 'performance.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return record


def _conditions(live, warmup, vus, duration):
    """The load's conditions: the build it ran, its warm-up, users and duration, and the machine."""
    return {'build': ' && '.join(' '.join(argv) for argv in live.profile['build']),
            'warmup_s': warmup, 'vus': vus, 'duration_s': duration, 'machine': machine()}


def _limitations(paths, sent, left):
    """What the load does not measure: the paths it requests, with or without headers, and the ones left out."""
    return ([f"each scenario requests {len(paths)} paths the program serves" +
             (f", with the headers {', '.join(sorted(sent))}" if sent else "; an endpoint that needs a signed-in "
              "session answers what it answers without one, and is not loaded as a user would")] +
            [f'left out: {path}, {why}' for path, why in left.items()])
