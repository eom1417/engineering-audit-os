"""Load, fault and live-scan plans, written in their tools' own formats before anything runs.

  nfr/k6/<scenario>.js     one k6 script per load scenario in intake.json: ramping virtual users to the
                           scenario's users, thresholds from its p95 and error rate, over every GET route
                           that needs no fixture. `k6 inspect` judges it.
  nfr/toxiproxy.json       one proxy per external dependency the facts show (Supabase, the project's own API,
                           each integration host), in toxiproxy-server -config form. The upstream is an
                           environment variable the run stage resolves (${SUPABASE_UPSTREAM}); no host is written.
  nfr/experiments.json     latency 2000 ms, timeout and down for every proxy, with the behaviour expected
                           (from a quality scenario, else the declared default) and the features it touches.
  nfr/zap.yaml             an OWASP ZAP Automation Framework plan: spider from BASE_URL, request every route,
                           wait for the passive scan, report as JSON. YAML is written as JSON, which YAML reads.

Toxiproxy and ZAP cannot check a file without running; their shape is checked instead (eaos/emit/shape.py),
and validation.json says so with tool = "schema". Nothing from the project runs here.
"""
import json
import re
import sys
from pathlib import Path

from .base import Emitted, render

DEFAULT_EXPECTED = 'the user sees an error message within 5 seconds, and no blank page'
TOXICS = (('latency', {'latency': 2000}), ('timeout', {'timeout': 0}), ('down', {}))
NOT_HOSTS = re.compile(r'(^|\.)(w3\.org|xmlns\.com|schema\.org|example\.(com|org))$|^\.+$')


def _load(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def _facts(report, kind):
    rows = []
    for path in sorted((Path(report) / 'facts').glob('*.json')):
        rows += [f for f in (_load(path, {}) or {}).get('facts') or [] if isinstance(f, dict) and f.get('kind') == kind]
    return rows


def routes(report):
    """GET routes a load or scan can call without a fixture, as URLs."""
    from ..behavior_lock import PARAM, kind_of, path_of, surfaces
    known = surfaces(report)
    found = []
    for feature in (_load(Path(report) / 'features.json', {}) or {}).get('features') or []:
        for surface in feature.get('surfaces') or []:
            kind, method, _ = kind_of(surface, known)
            path = path_of(surface) if surface != '*' else None
            if kind in ('page', 'http') and method == 'GET' and path and not PARAM.search(path) and path not in found:
                found.append(path)
    return found


def dependencies(report):
    """[(name, upstream variable, features)] for every external dependency the facts show."""
    features = (_load(Path(report) / 'features.json', {}) or {}).get('features') or []
    clients = {(f.get('value') or {}).get('client') for f in _facts(report, 'data_access')}
    # A host named only in a module nothing reaches (facts/deadcode) is not a dependency of the running program.
    unreachable = {(f.get('location') or {}).get('path') for f in _facts(report, 'engine_finding')
                   if (f.get('value') or {}).get('rule') == 'unreachable-module'}
    found = []
    if 'supabase' in clients:
        found.append(('supabase', 'SUPABASE_UPSTREAM', [f['name'] for f in features if f.get('tables')]))
    if 'http' in clients:
        found.append(('api', 'API_UPSTREAM', [f['name'] for f in features if f.get('endpoints')]))
    hosts = {}
    for fact in _facts(report, 'integration_target'):
        host, path = (fact.get('value') or {}).get('host') or '', (fact.get('location') or {}).get('path') or ''
        if ('.' not in host or NOT_HOSTS.search(host) or host.endswith('.supabase.co') or path in unreachable
                or re.search(r'(^|/)(tests?|__tests__|fixtures)/', path)):
            continue
        hosts.setdefault(host, set()).add(path)
    for host, paths in sorted(hosts.items()):
        variable = re.sub(r'[^A-Z0-9]+', '_', host.upper()).strip('_') + '_UPSTREAM'
        found.append((host, variable, [f['name'] for f in features if paths & set(f.get('files') or [])]))
    return found


def scenarios(report):
    return [s for s in (_load(Path(report) / 'intake.json', {}) or {}).get('scenarios') or []]


def write(report):
    report = Path(report)
    folder = report / 'nfr'
    written = []
    rows = scenarios(report)
    load = [s for s in rows if s['kind'] == 'load']
    error_rate = next((s['measure']['threshold'] for s in rows if s['kind'] == 'latency'), 0.01)
    paths = routes(report)
    if load and paths:
        (folder / 'k6').mkdir(parents=True, exist_ok=True)
        users = next((int(d) for d in re.findall(r'^(\d+)', load[0]['stimulus'])), 100)
        for scenario in load:
            script = folder / 'k6' / f"{scenario['id'].lower()}.js"
            script.write_text(render('k6/load.js', scenario=scenario['id'], source=scenario['source'],
                                     stimulus=scenario['stimulus'].replace('*/', ''), users=users,
                                     p95=scenario['measure']['threshold'], error_rate=error_rate,
                                     paths=json.dumps(paths[:50])), encoding='utf-8')
            written.append(Emitted(script.relative_to(report).as_posix(), 'k6', ('k6', 'inspect', '{path}')))
    found = dependencies(report)
    if found:
        folder.mkdir(parents=True, exist_ok=True)
        proxies = [{'name': name, 'listen': f'127.0.0.1:{26000 + index}', 'upstream': '${' + variable + '}', 'enabled': True}
                   for index, (name, variable, _) in enumerate(found)]
        (folder / 'toxiproxy.json').write_text(json.dumps(proxies, indent=1) + '\n', encoding='utf-8')
        expected = next((f"{s['response']} ({s['id']})" for s in rows if s['kind'] == 'availability'), DEFAULT_EXPECTED)
        experiments = [{'id': f'EXP-{index:03d}', 'dependency': name, 'proxy': name, 'toxic': toxic, 'params': params,
                        'expected': DEFAULT_EXPECTED if toxic != 'latency' else expected, 'features': touched}
                       for index, (name, toxic, params, touched) in enumerate(
                           ((n, t, p, f) for n, _, f in found for t, p in TOXICS), 1)]
        (folder / 'experiments.json').write_text(json.dumps({'schema_version': 1, 'experiments': experiments}, ensure_ascii=False,
                                                            indent=1) + '\n', encoding='utf-8')
        written += [Emitted('nfr/toxiproxy.json', 'schema', (sys.executable, '-m', 'eaos.emit.shape', 'toxiproxy', '{path}')),
                    Emitted('nfr/experiments.json', 'schema', (sys.executable, '-m', 'eaos.emit.shape', 'experiments', '{path}'))]
    if paths:
        folder.mkdir(parents=True, exist_ok=True)
        plan = {'env': {'contexts': [{'name': 'eaos', 'urls': ['${BASE_URL}']}],
                        'parameters': {'failOnError': True, 'progressToStdout': False}},
                'jobs': [{'type': 'spider', 'parameters': {'context': 'eaos', 'maxDuration': 5}},
                         {'type': 'requestor', 'requests': [{'url': '${BASE_URL}' + path, 'method': 'GET'} for path in paths[:100]]},
                         {'type': 'passiveScan-wait', 'parameters': {'maxDuration': 10}},
                         {'type': 'report', 'parameters': {'template': 'traditional-json', 'reportFile': 'zap-report'}}]}
        (folder / 'zap.yaml').write_text(json.dumps(plan, indent=1) + '\n', encoding='utf-8')
        written.append(Emitted('nfr/zap.yaml', 'schema', (sys.executable, '-m', 'eaos.emit.shape', 'zap', '{path}')))
    return written
