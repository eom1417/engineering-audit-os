"""The load baseline: every k6 scenario, run on the original code before any change (runtime/performance.json).

A number without its conditions cannot be compared, so the file carries them: the build that ran (a build,
never the development server), the warm-up, the virtual users, the duration and the machine. `after`
(NS22) is written by record_after() only beside a `before` taken under the same conditions.

The project runs from its run profile (eaos/live_run.py); a profile may override build, start and env under
`baseline`, for a project whose lock runs on its development server but whose load must hit its build.
"""
import json
import os
import re
from pathlib import Path

from .artifact_contracts import contracts, validate
from .live_run import LiveRun

THRESHOLD = re.compile(r"p\(95\)<(\d+(?:\.\d+)?)")
FAILED = re.compile(r"rate<(\d+(?:\.\d+)?)")
STAGES = re.compile(r"duration:\s*'(\d+)([sm])',\s*target:\s*(\d+)")


def machine():
    """What the run had, not what the host has: a container's cgroup limits win over the host's totals."""
    cpus = os.cpu_count() or 0
    try:
        quota, period = Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if quota != 'max': cpus = min(cpus, max(1, round(int(quota) / int(period))))
    except (OSError, ValueError): pass
    try: memory = round(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 2 ** 30, 1)
    except (ValueError, OSError, AttributeError): memory = None
    try:
        limit = Path('/sys/fs/cgroup/memory.max').read_text().strip()
        if limit != 'max': memory = round(int(limit) / 2 ** 30, 1)
    except (OSError, ValueError): pass
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


def run_baseline(report, target, runtime):
    """Run every nfr/k6 script of the report against the project's build; write runtime/performance.json."""
    report, runtime = Path(report), Path(runtime)
    scripts = sorted((report / 'nfr/k6').glob('*.js'))
    if not scripts: raise RuntimeError(f'{report}/nfr/k6 holds no scenario: the lock stage writes them')
    live = LiveRun(target, runtime, 'S05')
    override = live.profile.get('baseline') or {}
    for key in ('install', 'build', 'prepare', 'start', 'port', 'health', 'env', 'seed', 'start_timeout'):
        if key in override: live.profile[key] = override[key]
    if not live.profile.get('build'): raise RuntimeError('the load baseline needs a build (run.json build or baseline.build): never the development server')
    scenarios, conditions = [], None
    out = runtime / 'runtime'
    out.mkdir(parents=True, exist_ok=True)
    try:
        live.setup()
        base = live.start()
        for argv in live.profile.get('seed') or []: live.run(argv, env={'BASE_URL': base})
        for script in scripts:
            threshold, vus, duration, warmup = shape(script)
            conditions = conditions or {'build': ' && '.join(' '.join(argv) for argv in live.profile['build']),
                                        'warmup_s': warmup, 'vus': vus, 'duration_s': duration, 'machine': machine()}
            export = out / f'k6-{script.stem}.json'
            live.sandbox.run(['k6', 'run', '--quiet', '--summary-export', str(export), str(script)], timeout=duration + 600,
                             network=True, env={**live.extra(), 'BASE_URL': base})
            scenarios.append({'id': script.stem.upper(), 'script': f'nfr/k6/{script.name}', 'threshold': threshold,
                              'before': summary(export), 'after': None})
    finally:
        live.stop()
        live.record('runtime/baseline-log.json')
    record = {'schema_version': 1, 'conditions': conditions, 'scenarios': scenarios,
              'limitations': ["each scenario requests the paths its k6 script lists (the application's pages); an endpoint "
                              'that needs a signed-in session answers what it answers without one, and is not loaded as a user would'],
              'run': {'start': ' '.join(live.profile['start']), 'env': sorted(live.profile.get('env') or {})}}
    problems = validate(record, contracts()['runtime-performance'])
    if problems: raise RuntimeError(f'runtime/performance.json would break its contract: {problems[0]}')
    (out / 'performance.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return record


def record_after(runtime, scenario_id, after, conditions):
    """Write a scenario's `after` (NS22): refused without its `before`, or under other conditions."""
    path = Path(runtime) / 'runtime/performance.json'
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('conditions') != conditions:
        raise ValueError('after must run under the conditions of before: ' + json.dumps(record.get('conditions')))
    row = next((s for s in record['scenarios'] if s['id'] == scenario_id), None)
    if not row or not row.get('before'): raise ValueError(f'{scenario_id}: no before, so no after')
    row['after'] = after
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return record
