"""Runtime and operational facts the dossier needs but the code facts miss.

A static walk of source can describe what the code *is*. It cannot describe
what the code *does* in production: where it runs, who can reach it, what it
emits, what it depends on outside the codebase, and how its data shape evolves.
This extractor closes those gaps by parsing the manifests a project actually
declares (Dockerfile, compose, GitHub Actions, OpenAPI, SQLAlchemy / Django /
Rails migrations, package.json), and by walking what the entry-points already
found to flag outward calls.

Every fact is structural: derived from a parsed manifest, never from running
the system. Nothing here proves the deployment actually works. How a source
file bounds its load (query bounds, caches, rate limits, connection pools) is
read by eaos/facts/runtime_capacity.py.
"""
import json
import re
from pathlib import Path

from ..core.security import THIS_COMPUTER
from . import digest, make
from .runtime_capacity import detect_cache_policies, detect_connection_pools, detect_query_bounds, detect_rate_limits
from .source import language_of
from .yaml_lite import yaml_load


KINDS = ('cache_policy', 'ci_step', 'connection_pool', 'data_model', 'deployment_target',
         'integration_target', 'migration_step', 'observability_signal', 'query_bound',
         'rate_limit', 'resilience_policy', 'security_surface')

NAME = 'runtime'
VERSION = '1'
LIMITATIONS = [
    'Only manifests the engine has a parser for are observed; an unsupported format stays a gap, never a guess.',
    'A "security surface" is a route grouped by authentication hint: static analysis cannot decide who is allowed.',
    'A "deployment target" is whatever a manifest declares; it does not prove the deployment actually runs.',
    'A "data field" is read from the model declaration; runtime constraints (NOT NULL, FK) live in migrations.',
]


# Hosting platforms a repository declares by one manifest file: the file names the host. A Dockerfile is read for its
# ports (_dockerfile_ports); these say where the code is deployed, which the infrastructure map draws (eaos/report/studio/infra.py).
HOSTING_MANIFESTS = {'vercel.json': 'Vercel', 'netlify.toml': 'Netlify', 'fly.toml': 'Fly.io', 'railway.json': 'Railway',
                     'railway.toml': 'Railway', 'render.yaml': 'Render', 'Procfile': 'Procfile', 'nixpacks.toml': 'Nixpacks',
                     'wrangler.toml': 'Cloudflare Workers'}


def _dockerfile_ports(text):
    """EXPOSE instructions: deployment-target hints."""
    return re.findall(r'^\s*EXPOSE\s+(\d+)(?:/(?:tcp|udp))?', text, re.MULTILINE)


def _compose_services(text):
    try: return list(yaml_load(text).get('services', {}).keys())
    except (ValueError, TypeError): return []


def _github_actions(text):
    """Every step name + run argv (truncated to 240 chars) from a workflow file."""
    steps = []
    for line in text.splitlines():
        if 'name:' in line:
            steps.append(line.split('name:')[1].strip().strip('"\''))
        elif 'run:' in line and '|' not in line and '>' not in line:
            steps.append('run: ' + line.split('run:')[1].strip()[:240])
    return steps


def _package_scripts(text):
    try: return list(json.loads(text).get('scripts', {}).keys())
    except ValueError: return []


def _auth_hints(text):
    """Authentication annotations: decorators, middleware lists, comments."""
    hints = []
    for pattern, label in [(r'@login_required', 'login_required'),
                            (r'@requires_auth', 'requires_auth'),
                            (r'@authenticated', 'authenticated'),
                            (r'@jwt_required', 'jwt_required'),
                            (r'@permission_required', 'permission_required'),
                            (r'app\.use\(.*auth', 'middleware_auth'),
                            (r'@AllowAny', 'allow_any'),
                            (r'@IsAuthenticated', 'is_authenticated'),
                            (r'@router\.get.*auth', 'list_auth'),
                            (r'authenticate\(\)', 'authenticate')]:
        if re.search(pattern, text, re.IGNORECASE): hints.append(label)
    return hints


def _observability_signals(text):
    """Metrics / logs / traces: name patterns that suggest intent."""
    signals = []
    for pattern, kind in [(r'(?:counter|gauge|histogram)\s*\(', 'metric'),
                            (r'(?:logger|log)\.(?:info|debug|warn|error)\s*\(', 'log'),
                            (r'(?:start_span|with_tracer|trace\.tracer)', 'trace'),
                            (r'(?:capture_exception|except)', 'error_capture'),
                            (r'(?:Sentry\.init|with sentry_sdk)', 'sentry')]:
        if re.search(pattern, text, re.IGNORECASE): signals.append(kind)
    return signals


def _outbound_hosts(text):
    """Outbound network targets: URLs to non-RFC1918 hosts."""
    hosts = set()
    for match in re.finditer(r'https?://([A-Za-z0-9.\-]+)', text):
        host = match.group(1)
        if host not in THIS_COMPUTER: hosts.add(host)
    return sorted(hosts)


def _orm_models(text):
    """Django/SQLAlchemy/Rails model declarations: name + framework.

    A class is attributed to the most specific framework that matches its
    declaration: Django `models.Model`, then Rails `ApplicationRecord`, then
    SQLAlchemy `Base`. Overlapping position-based matches are deduped.
    """
    rows = []
    django = [(m.group(1), m.start()) for m in re.finditer(r'class\s+(\w+)\s*\(\s*models\.Model\s*\)', text)]
    rails = [(m.group(1), m.start()) for m in re.finditer(r'class\s+(\w+)\s*<\s*ApplicationRecord', text)]
    django_positions = {pos for _, pos in django}
    rails_positions = {pos for _, pos in rails}
    for name, pos in django:
        rows.append({'name': name, 'framework': 'django'})
    for name, pos in rails:
        rows.append({'name': name, 'framework': 'rails'})
    for match in re.finditer(r'class\s+(\w+)\s*\(\s*([\w.]+)\s*\)', text):
        if match.start() in django_positions or match.start() in rails_positions: continue
        rows.append({'name': match.group(1), 'framework': 'sqlalchemy'})
    return rows


def _migration_files(name):
    return 'migrate' in name or 'migration' in name or name.endswith('0001_initial.py')


# Resilience policy detection: an outbound integration_target needs timeout/retry/circuit-breaker
# to keep one service's slowness from becoming your outage.
_TIMEOUT_PATTERNS = [
    re.compile(r'timeout\s*[=:]\s*\d+', re.IGNORECASE),     # timeout=30, timeout: 30
    re.compile(r'\bTimeout\s*\('),                            # Timeout(30)
    re.compile(r'\btimeout\s*=\s*[^,\)]+'),                  # timeout=httpx_timeout()
    re.compile(r'\.timeout\s*\(\s*\d+'),                     # httpx .timeout(30)
    re.compile(r'\bctx\s+with\s+timeout', re.IGNORECASE),     # context with timeout
    re.compile(r'\.with_timeout\s*\('),                       # tokio .with_timeout()
    re.compile(r'context\s+with\s+timeout', re.IGNORECASE),    # asyncio ctx with timeout
    re.compile(r'\bhttp\.Client\s*\{[^}]*Timeout\s*:'),       # Go http.Client{Timeout: ...}
    re.compile(r'\bcontext\.With(?:Timeout|Deadline)\s*\('),  # Go bounded contexts
]
_RETRY_PATTERNS = [
    re.compile(r'\bretry\b', re.IGNORECASE),
    re.compile(r'\bRetry\b'),
    re.compile(r'\bbackoff\b', re.IGNORECASE),
    re.compile(r'\btenacity\b'),
    re.compile(r'@retry'),
    re.compile(r'@retryable'),
    re.compile(r'\bmax_retries\b'),
    re.compile(r'\bMaxRetries\b'),
    re.compile(r'\.retry\s*\('),
]
_CIRCUIT_BREAKER_PATTERNS = [
    re.compile(r'\bcircuit[_\-]?breaker\b', re.IGNORECASE),
    re.compile(r'\bCircuitBreaker\b'),
    re.compile(r'\bhystrix\b', re.IGNORECASE),
    re.compile(r'\bresilience4j\b', re.IGNORECASE),
    re.compile(r'\bpybreaker\b', re.IGNORECASE),
]


def _has_timeout(text):
    """True if any timeout pattern appears anywhere; we cannot cheaply localise to a call."""
    return any(p.search(text) for p in _TIMEOUT_PATTERNS)


def _has_retry(text):
    return any(p.search(text) for p in _RETRY_PATTERNS)


def _has_circuit_breaker(text):
    return any(p.search(text) for p in _CIRCUIT_BREAKER_PATTERNS)


# Languages whose guard vocabulary these patterns actually cover. For anything else the patterns
# would return False for every file, which reads as "no timeout" when it means "we did not look".
_RESILIENCE_LANGUAGES = ('python', 'javascript', 'typescript', 'tsx', 'go', 'java', 'kotlin', 'ruby')


def _detect_resilience_for_integration(text, host, language=None):
    """One resilience_policy fact per integration host, recording which guards are present.

    We attribute the policy to the file that makes the call; the call site is local evidence,
    the host is the global one. Unknown is the honest answer when we cannot detect: a language
    whose guard vocabulary these patterns do not cover returns unknown, never False, because
    False would claim we looked.
    """
    if language is not None and language not in _RESILIENCE_LANGUAGES:
        return {'host': host, 'has_timeout': 'unknown', 'has_retry': 'unknown',
                'has_circuit_breaker': 'unknown',
                'reason': f'no resilience vocabulary is defined for {language}'}
    return {
        'host': host,
        'has_timeout': _has_timeout(text),
        'has_retry': _has_retry(text),
        'has_circuit_breaker': _has_circuit_breaker(text),
    }


# A file's facts are (kind, line, value) rows: line is None for a fact about the whole file.
_COMPOSE_FILES = {'docker-compose.yml', 'docker-compose.yaml', 'compose.yml'}
_CODE_LANGUAGES = {'python', 'javascript', 'typescript', 'go', 'ruby'}


def _line_rows(kind, rows, keys):
    """Detector rows that carry a line, as fact rows holding only `keys`."""
    return [(kind, row['line'], {key: row[key] for key in keys}) for row in rows]


def _manifest_rows(rel, name, text):
    """The rows of the one manifest this file is, by its name."""
    deployment = _deployment_rows(name, text)
    if deployment is not None: return deployment
    if '.github/workflows/' in rel and name.endswith(('.yml', '.yaml')):
        return [('ci_step', None, {'name': step[:120]}) for step in _github_actions(text)[:40]]
    if name == 'package.json':
        return [('ci_step', None, {'name': 'npm:' + script}) for script in _package_scripts(text)]
    return []


def _deployment_rows(name, text):
    """Where a Dockerfile, compose file or hosting manifest deploys the code; None for any other file."""
    if name == 'Dockerfile' or name.endswith('.dockerfile'):
        return [('deployment_target', None, {'kind': 'dockerfile', 'port': port, 'language': 'dockerfile'})
                for port in _dockerfile_ports(text)]
    if name in _COMPOSE_FILES:
        return [('deployment_target', None, {'kind': 'compose', 'service': service}) for service in _compose_services(text)]
    if name in HOSTING_MANIFESTS:
        return [('deployment_target', None, {'kind': 'hosting', 'host': HOSTING_MANIFESTS[name]})]
    return None


def _code_rows(text, language):
    """The rows of a source file: its auth hints, signals, outbound hosts and their guards, caches, models, queries."""
    rows = [('security_surface', None, {'hint': hint, 'language': language}) for hint in _auth_hints(text)]
    rows += [('observability_signal', None, {'kind': signal, 'language': language}) for signal in _observability_signals(text)]
    for host in _outbound_hosts(text):
        rows.append(('integration_target', None, {'host': host, 'language': language}))
        rows.append(('resilience_policy', None, _detect_resilience_for_integration(text, host, language)))
    rows += _line_rows('cache_policy', detect_cache_policies(text), ('scope', 'mechanism', 'ttl_declared'))
    rows += [('data_model', None, model) for model in _orm_models(text)]
    return rows + _line_rows('query_bound', detect_query_bounds(text, language), ('bounded', 'mechanism', 'kind', 'snippet'))


def _file_rows(rel, text):
    name = Path(rel).name
    language = language_of(rel)
    rows = _manifest_rows(rel, name, text)
    if language in _CODE_LANGUAGES:
        rows += _code_rows(text, language)
    rows += _line_rows('rate_limit', detect_rate_limits(text, rel, name), ('scope', 'mechanism', 'declared_limit', 'source'))
    rows += _line_rows('connection_pool', detect_connection_pools(text), ('resource', 'declared_size', 'source'))
    if _migration_files(name):
        rows.append(('migration_step', None, {'name': name}))
    return rows


def run(target, source, symbols=None, **options):
    facts, fingerprints = [], []
    for item in source.readable():
        rel = item['path']; text = source.text(rel)
        if text is None: continue
        fingerprints.append(item['sha256'])
        for kind, line, value in _file_rows(rel, text):
            location = {'path': rel} if line is None else {'path': rel, 'start_line': line}
            facts.append(make(kind, NAME, VERSION, item['sha256'], location, value, limitations=LIMITATIONS))
    summary = {'files_observed': len(fingerprints), 'facts': len(facts),
               # Iterating a set orders by hash, which Python randomises per process: two runs over
               # an unchanged tree wrote the same counts in a different order and the fact set was
               # no longer byte-identical. A sorted tuple is the only honest order here.
               'by_kind': {kind: sum(1 for f in facts if f['kind'] == kind) for kind in KINDS},
               'interpretation': 'Runtime facts describe the operational surface the static walk cannot see. '
                                  'None proves the system actually runs that way.'}
    return {'facts': facts, 'summary': summary, 'available': True,
            'input_sha': digest(''.join(sorted(fingerprints)).encode()) if fingerprints else digest(b''),
            'reason': None}
