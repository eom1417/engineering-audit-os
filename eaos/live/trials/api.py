"""The API tried against the running app (M6.7): Schemathesis (MIT, pinned, a fixed seed, a time budget) over the
project's own OpenAPI, or one EAOS writes from the endpoint table (eaos/analysis/layers/endpoints.py) and marks as derived.

Its checks: an endpoint that answers without the sign-in its route requires (`ignored_auth`), one user reaching another's
object (`object_level_authorization`, with the two test accounts of the run as peers), bad input accepted
(`negative_data_rejection`) and a server error on any input (`not_a_server_error`). Each failure is a finding with the
request and the response that proved it. The app runs in its isolated copy with a database of its own: whatever the
trial writes is thrown away with it.
"""
import json
import re
from pathlib import Path

from ...core.system.process import run_command
from ...core.toolchain import home

CHECKS = 'not_a_server_error,ignored_auth,negative_data_rejection,object_level_authorization'
SEED = 1
BUDGET = 240                     # seconds of fuzzing at most; the whole trial is shown before it starts
OWN_SPECS = ('openapi.json', 'openapi.yaml', 'openapi.yml', 'swagger.json', 'swagger.yaml', 'api.yaml', 'docs/openapi.yaml',
             'docs/openapi.json', 'spec/openapi.yaml', 'public/openapi.json')
PARAM = re.compile(r':(\w+)|\[(\w+)\]|<(?:\w+:)?(\w+)>')
# Schemathesis' failure titles, as the rule each is (eaos/analysis/layers/catalog.py).
RULES = {'ignored_auth': 'ignored-authentication', 'object_level_authorization': 'other-user-object',
         'negative_data_rejection': 'bad-input-accepted', 'not_a_server_error': 'server-error-on-input'}


def own_spec(root):
    """The project's own OpenAPI file, or None."""
    return next((Path(root) / name for name in OWN_SPECS if (Path(root) / name).is_file()), None)


def _openapi_path(route):
    return PARAM.sub(lambda m: '{' + next(g for g in m.groups() if g) + '}', str(route))


def derived(endpoints):
    """An OpenAPI document written from the endpoint table: every HTTP route with its parameters, a JSON body for a
    write, and the session cookie on the routes that check one."""
    paths = {}
    for row in endpoints:
        route = str(row['route'])
        if route.startswith('action:') or row['framework'] == 'supabase_edge': continue
        path = _openapi_path(route)
        for method in (['get'] if row['method'] == 'ANY' else [row['method'].lower()]):
            operation = {'operationId': f"{method}_{re.sub(r'[^A-Za-z0-9]+', '_', path).strip('_') or 'root'}",
                         'responses': {'default': {'description': 'any'}},
                         'parameters': [{'name': name, 'in': 'path', 'required': True, 'schema': {'type': 'string'}}
                                        for name in re.findall(r'\{(\w+)\}', path)]}
            if method in ('post', 'put', 'patch'):
                operation['requestBody'] = {'content': {'application/json': {'schema': {'type': 'object'}}}}
            if row.get('authentication'): operation['security'] = [{'session': []}]
            paths.setdefault(path, {})[method] = operation
    return {'openapi': '3.0.3', 'info': {'title': 'Derived by EAOS from the code', 'version': '0', 'x-eaos-derived': True},
            'paths': paths, 'components': {'securitySchemes': {'session': {'type': 'apiKey', 'in': 'header', 'name': 'Cookie'}}}}


def _stored_token(data):
    """A bearer token the browser keeps in local storage under a name that says so, or None."""
    items = [item for origin in data.get('origins') or [] for item in origin.get('localStorage') or []]
    return next((token for item in items if re.search(r'token|auth|session', item.get('name', ''), re.I)
                 for token in [_token(item.get('value'))] if token), None)


def headers(state):
    """The request headers of a saved browser session: its cookies, and a bearer token it keeps in local storage."""
    try: data = json.loads(Path(state).read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError): return {}
    cookies = '; '.join(f"{c['name']}={c['value']}" for c in data.get('cookies') or [])
    token = _stored_token(data)
    return {**({'Cookie': cookies} if cookies else {}), **({'Authorization': f'Bearer {token}'} if token else {})}


def _token(value):
    try: value = json.loads(value)
    except (ValueError, TypeError): pass
    if isinstance(value, dict): value = value.get('access_token') or value.get('token')
    return value if isinstance(value, str) and value.count('.') == 2 else None


def _wfc(folder, identities):
    """The Web Fuzzing Commons file of the run's accounts, one entry per identity with its fixed headers."""
    path = Path(folder) / 'accounts.json'
    path.write_text(json.dumps({'schemaVersion': '0.2.0', 'auth': [
        {'name': name, 'fixedHeaders': [{'name': key, 'value': value} for key, value in sent.items()]}
        for name, sent in identities.items() if sent]}), encoding='utf-8')
    return path


def run(folder, spec, base, identities, budget=BUDGET):
    """Schemathesis over `spec` against `base` as the run's accounts: {'failures': [...], 'ran': bool, 'why': ...}."""
    binary = home() / 'bin' / 'schemathesis'
    if not binary.is_file(): return {'ran': False, 'why': 'Schemathesis is not installed: eaos tools install --only schemathesis', 'failures': []}
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    report = folder / 'schemathesis.ndjson'
    argv = [str(binary), 'run', str(spec), '--url', base, '--checks', CHECKS, '--seed', str(SEED), '--max-time', str(budget),
            '--max-examples', '20', '--workers', '1', '--report', 'ndjson', '--report-ndjson-path', str(report),
            '--no-color', '--request-timeout', '10', '--output-sanitize', 'true', '--generation-database', 'none',
            '--generation-with-security-parameters', 'false']
    named = {name: sent for name, sent in identities.items() if sent}
    if named:
        wfc = _wfc(folder, named)
        config = folder / 'schemathesis.toml'
        config.write_text(f'[auth.wfc]\npath = "{wfc}"\n' + (f'peers = {json.dumps(sorted(named))}\n' if len(named) > 1 else ''), encoding='utf-8')
        argv[1:1] = ['--config-file', str(config)]
    try:
        done = run_command(argv, budget + 300, cwd=folder)
        if not report.is_file(): return {'ran': False, 'why': (done.stderr or done.stdout).strip()[-300:], 'failures': []}
        return {'ran': True, 'failures': failures(report), 'peers': sorted(named)}
    finally:
        tidy(folder)


def tidy(folder):
    """What the trial wrote beside the report and nobody reads again: Schemathesis' report and caches, and the accounts'
    sessions (a session is a secret)."""
    import shutil
    for name in ('schemathesis.ndjson', 'accounts.json', 'schemathesis.toml'): (Path(folder) / name).unlink(missing_ok=True)
    for name in ('.hypothesis', '.schemathesis'): shutil.rmtree(Path(folder) / name, ignore_errors=True)


def _recorders(report):
    for line in Path(report).read_text(encoding='utf-8', errors='replace').splitlines():
        try: recorder = (json.loads(line).get('ScenarioFinished') or {}).get('recorder')
        except ValueError: continue
        if recorder: yield recorder


def _failed_checks(recorder):
    """(case id, check) of every failed check of one scenario that is one of RULES."""
    return [(case, check) for case, checks in (recorder.get('checks') or {}).items() for check in checks
            if check.get('status') == 'failure' and check.get('name') in RULES and not _auth_only(check)]


def failures(report):
    """[{check, method, path, request, status, response, title}] of the run's failed checks, one per check and route."""
    found = {}
    for recorder in _recorders(report):
        for case, check in _failed_checks(recorder):
            failure = _failure(check, (recorder.get('interactions') or {}).get(case) or {}, recorder.get('label'))
            found.setdefault((failure['check'], failure['method'], failure['path']), failure)
    return list(found.values())


METHODS = ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS')


def _auth_only(check):
    """Bad input that is only a missing sign-in: the ignored_auth check says that one."""
    message = str(((check.get('failure_info') or {}).get('failure') or {}).get('message') or '')
    return check['name'] == 'negative_data_rejection' and bool(re.search(r'Missing `[^`]+` at (cookie|header)', message))


def _text(content):
    """A recorded body as text (Schemathesis keeps it base64)."""
    import base64
    if isinstance(content, dict) and '$base64' in content:
        try: return base64.b64decode(content['$base64']).decode('utf-8', errors='replace')
        except ValueError: return ''
    return str(content or '')


def _failure(check, interaction, label):
    request, response = interaction.get('request') or {}, interaction.get('response') or {}
    failure = (check.get('failure_info') or {}).get('failure') or {}
    method, _, path = str(label or '').partition(' ')
    if method not in METHODS:                       # a stateful scenario: the request names its route
        from urllib.parse import urlsplit
        method, path = str(request.get('method', '')).upper(), urlsplit(str(request.get('uri', ''))).path
    return {'check': check['name'], 'method': method, 'path': path,
            'request': f"{request.get('method', method)} {request.get('uri', path)} {_text(request.get('body'))[:300]}".strip(),
            'status': response.get('status_code'), 'response': _text(response.get('content'))[:400],
            'title': str(failure.get('title') or check['name'])[:200], 'detail': str(failure.get('message') or '')[:400]}
