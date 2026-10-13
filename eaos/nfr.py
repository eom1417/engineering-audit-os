"""The load plans the baseline stage runs: one k6 script per load scenario in intake.json (nfr/k6/<scenario>.js),
ramping virtual users to the scenario's users, thresholds from its p95 and error rate, over every GET route that
needs no fixture. Nothing from the project runs here."""
import json
import re
from pathlib import Path
from string import Template

TEMPLATES = Path(__file__).resolve().parent / 'templates'
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
    from .lock_specs import PARAM, kind_of, path_of, surfaces
    known = surfaces(report)
    found = []
    for feature in (_load(Path(report) / 'features.json', {}) or {}).get('features') or []:
        for path in (_loadable(surface, known, kind_of, path_of, PARAM) for surface in feature.get('surfaces') or []):
            if path and path not in found: found.append(path)
    return found


def _loadable(surface, known, kind_of, path_of, param):
    """The path of a page or GET route that needs no fixture; None for any other surface."""
    kind, method, _ = kind_of(surface, known)
    path = path_of(surface) if surface != '*' else None
    # A hash route (/#/x) is drawn by the browser: a request only ever reaches the page that serves it.
    return path if kind in ('page', 'http') and method == 'GET' and path and '#' not in path and not param.search(path) else None


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
    for host, paths in sorted(_hosts(report, unreachable).items()):
        variable = re.sub(r'[^A-Z0-9]+', '_', host.upper()).strip('_') + '_UPSTREAM'
        found.append((host, variable, [f['name'] for f in features if paths & set(f.get('files') or [])]))
    return found


def _counted_host(host, path, unreachable):
    """A real outside host named by code the running program reaches, outside the tests."""
    if '.' not in host or NOT_HOSTS.search(host) or host.endswith('.supabase.co'): return False
    return path not in unreachable and not re.search(r'(^|/)(tests?|__tests__|fixtures)/', path)


def _hosts(report, unreachable):
    """{host: the files that name it}."""
    hosts = {}
    for fact in _facts(report, 'integration_target'):
        host, path = (fact.get('value') or {}).get('host') or '', (fact.get('location') or {}).get('path') or ''
        if _counted_host(host, path, unreachable): hosts.setdefault(host, set()).add(path)
    return hosts


def scenarios(report):
    return [s for s in (_load(Path(report) / 'intake.json', {}) or {}).get('scenarios') or []]


def write(report):
    """The k6 scripts; returns their paths relative to the report."""
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
        template = Template((TEMPLATES / 'k6/load.js').read_text(encoding='utf-8'))
        for scenario in load:
            script = folder / 'k6' / f"{scenario['id'].lower()}.js"
            script.write_text(template.substitute(scenario=scenario['id'], source=scenario['source'],
                                                  stimulus=scenario['stimulus'].replace('*/', ''), users=users,
                                                  p95=scenario['measure']['threshold'], error_rate=error_rate,
                                                  paths=json.dumps(paths[:50])), encoding='utf-8')
            written.append(script.relative_to(report).as_posix())
    return written
