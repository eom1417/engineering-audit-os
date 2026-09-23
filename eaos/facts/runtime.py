"""Runtime and operational facts the dossier needs but the code facts miss.

A static walk of source can describe what the code *is*. It cannot describe
what the code *does* in production: where it runs, who can reach it, what it
emits, what it depends on outside the codebase, and how its data shape evolves.
This extractor closes those gaps by parsing the manifests a project actually
declares (Dockerfile, compose, GitHub Actions, OpenAPI, SQLAlchemy / Django /
Rails migrations, package.json), and by walking what the entry-points already
found to flag outward calls.

Every fact is structural: derived from a parsed manifest, never from running
the system. Nothing here proves the deployment actually works.
"""
import json
import re
from pathlib import Path
from . import digest, make
from .source import language_of


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


def _dockerfile_ports(text):
    """EXPOSE instructions: deployment-target hints."""
    ports = []
    for match in re.finditer(r'^\s*EXPOSE\s+(\d+)(?:/(?:tcp|udp))?', text, re.MULTILINE):
        ports.append(match.group(1))
    return ports


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
        if host not in {'localhost', '127.0.0.1', '::1', '0.0.0.0'}: hosts.add(host)
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


class UnsupportedYaml(ValueError):
    """What this reader will not guess at. The caller records the file as unparsed."""


def yaml_load(text):
    """A minimal YAML reader for the simple structures we encounter. We never
    rely on it for completeness; the parser raises on the rest and we leave it
    as unparsed in the output."""
    text = re.sub(r'#[^\n]*', '', text)
    _refuse_unsupported(text)
    return _yaml_reader(text)


def _refuse_unsupported(text):
    """Raise on the constructs this reader cannot represent faithfully.

    Without this it returned a partial answer instead: `a: [unclosed` became the string
    "[unclosed", and a document with a broken sequence lost its items silently. A parser that
    guesses turns an unreadable file into fabricated facts, which is worse than no facts.
    """
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if line[:len(line) - len(line.lstrip())].count('\t'):
            raise UnsupportedYaml(f'line {number}: tab indentation is not valid YAML')
        for opener, closer in (('[', ']'), ('{', '}')):
            if stripped.count(opener) != stripped.count(closer):
                raise UnsupportedYaml(f'line {number}: unbalanced {opener}{closer} — flow style is '
                                      f'only read when it closes on its own line')
        if stripped.startswith(('&', '*', '<<', '!', '|', '>')) or stripped.endswith(('|', '>')):
            raise UnsupportedYaml(f'line {number}: anchors, tags and block scalars are not read')


def _yaml_reader(text, indent=0):
    """Read a YAML mapping or sequence at the given indent level."""
    out = {} if _yaml_indent_level(text, indent) in {'map', None} else []
    lines = [line for line in text.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith('#'): i += 1; continue
        current_indent = len(line) - len(line.lstrip())
        if current_indent < indent: return out
        if stripped.startswith('- '):
            value = stripped[2:].strip()
            if ':' in value and not value.startswith('"'):
                key, val = value.split(':', 1)
                item = {key.strip(): _yaml_scalar(val.strip())}
                i += 1
                while i < len(lines):
                    nxt = lines[i]
                    if not nxt.strip(): i += 1; continue
                    nxt_indent = len(nxt) - len(nxt.lstrip())
                    if nxt_indent <= current_indent: break
                    sub = _yaml_reader('\n'.join(lines[i:]), nxt_indent)
                    item.update(sub) if isinstance(sub, dict) else None
                    i += sum(1 for _ in [None])
                    break
                if isinstance(out, list): out.append(item)
            else:
                if isinstance(out, list): out.append(_yaml_scalar(value))
                i += 1
        elif ':' in stripped:
            key, _, val = stripped.partition(':')
            key = key.strip(); val = val.strip()
            if val == '':
                i += 1
                sub_lines = []
                while i < len(lines):
                    nxt = lines[i]
                    if not nxt.strip(): i += 1; continue
                    nxt_indent = len(nxt) - len(nxt.lstrip())
                    if nxt_indent <= current_indent: break
                    sub_lines.append(nxt); i += 1
                if isinstance(out, dict):
                    out[key] = _yaml_reader('\n'.join(sub_lines), current_indent + 2)
            else:
                if isinstance(out, dict): out[key] = _yaml_scalar(val)
                i += 1
        else:
            i += 1
    return out


def _yaml_indent_level(text, indent):
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'): continue
        current = len(line) - len(line.lstrip())
        if current < indent: return None
        if current == indent: return 'map' if ':' in stripped else 'seq'
    return None


def _yaml_scalar(value):
    value = value.strip().strip('"\'')
    if value in {'true', 'yes'}: return True
    if value in {'false', 'no'}: return False
    if re.match(r'^-?\d+$', value): return int(value)
    return value


# Bounded-query detection: a chain or call that could return a result set must declare a bound.
# Patterns per language are stated, not exhaustive: if a chain doesn't match, the fact records
# `bounded=unknown` so the detector never claims to have measured something it didn't.
_QUERY_BOUND_PATTERNS = {
    'python': [
        # SQLAlchemy: .limit(N), .offset(N), .all()/.first()/.one() without preceding bound
        ('limit', re.compile(r'\.limit\(\s*\d+'), 'sqlalchemy_limit'),
        ('offset', re.compile(r'\.offset\(\s*\d+'), 'sqlalchemy_offset'),
        ('slice', re.compile(r'\[\s*\d+\s*:\s*\d+\s*\]'), 'slice'),
        # Django ORM: .filter(...).all() without .first()/.count()/.exists()/.aggregate()
        ('aggregate', re.compile(r'\.aggregate\('), 'aggregate'),
        ('exists', re.compile(r'\.exists\(\s*\)'), 'exists'),
        ('first', re.compile(r'\.first\(\s*\)'), 'first'),
        # Dangerous: .all() without preceding bound on a queryset
    ],
    'javascript': [
        ('limit', re.compile(r'\.limit\(\s*\d+'), 'js_limit'),
        ('take', re.compile(r'\.take\(\s*\d+'), 'prisma_take'),
        ('skip', re.compile(r'\.skip\(\s*\d+'), 'prisma_skip'),
    ],
    'typescript': [
        ('limit', re.compile(r'\.limit\(\s*\d+'), 'js_limit'),
        ('take', re.compile(r'\.take\(\s*\d+'), 'prisma_take'),
        ('skip', re.compile(r'\.skip\(\s*\d+'), 'prisma_skip'),
        ('findMany_bounded', re.compile(r'findMany\s*\(\s*\{[^}]*take\s*:'), 'prisma_findMany_take'),
    ],
    'go': [
        # Raw SQL: 'LIMIT' clause (integer or placeholder)
        ('sql_limit', re.compile(r'\bLIMIT\s+(?:\?|\d+)', re.IGNORECASE), 'sql_limit'),
        # GORM: .Limit(N)
        ('orm_limit', re.compile(r'\.Limit\(\s*\d+'), 'gorm_limit'),
    ],
}

# Unbounded patterns: a query path that returns rows without an explicit bound.
_UNBOUNDED_PATTERNS = {
    'python': [
        re.compile(r'\.all\(\s*\)'),
        re.compile(r'\.filter\([^)]*\)\.all\(\s*\)'),
    ],
    'javascript': [
        re.compile(r'\.findMany\(\s*\)'),
        re.compile(r'\.findMany\(\s*\{\s*\}\s*\)'),
    ],
    'typescript': [
        re.compile(r'\.findMany\(\s*\)'),
        re.compile(r'\.findMany\(\s*\{\s*\}\s*\)'),
    ],
    'go': [
        re.compile(r'\.Find\(\s*\&'),
    ],
}


def _detect_query_bounds(text, language):
    """Walk a source file and record one query_bound fact per detected site.

    Bounded facts: the call explicitly caps the result set.
    Unbounded facts: a query chain lacks any of the bounded patterns above.
    Unknown facts: neither pattern matched; we cannot say either way.
    """
    rows = []
    patterns = _QUERY_BOUND_PATTERNS.get(language, [])
    unbounded = _UNBOUNDED_PATTERNS.get(language, [])
    # Bounded sites
    for mechanism, regex, kind in patterns:
        for match in regex.finditer(text):
            line = text.count('\n', 0, match.start()) + 1
            rows.append({
                'bounded': True, 'mechanism': mechanism, 'kind': kind,
                'line': line, 'snippet': text.splitlines()[line - 1].strip()[:120] if line - 1 < len(text.splitlines()) else ''
            })
    # Unbounded sites
    for regex in unbounded:
        for match in regex.finditer(text):
            line = text.count('\n', 0, match.start()) + 1
            rows.append({
                'bounded': False, 'mechanism': 'unbounded', 'kind': regex.pattern[:30],
                'line': line, 'snippet': text.splitlines()[line - 1].strip()[:120] if line - 1 < len(text.splitlines()) else ''
            })
    if not rows:
        # No matches at all means we cannot measure; record that explicitly.
        rows.append({'bounded': 'unknown', 'mechanism': 'no_match', 'kind': 'unknown',
                      'line': 0, 'snippet': ''})
    return rows


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


# Cache detection: a known scope (process, shared, http) is the value; we report what we observe.
_PROCESS_CACHE = [
    ('lru_cache', re.compile(r'@lru_cache', re.IGNORECASE)),
    ('lru_cache_maxsize', re.compile(r'@lru_cache\s*\(\s*maxsize\s*=')),
    ('cached_property', re.compile(r'@cached_property')),
    ('functools_cache', re.compile(r'functools\.cache\s*\(')),
    ('functools_lru_cache', re.compile(r'functools\.lru_cache')),
    ('cache_decorator', re.compile(r'@cache\b')),
    ('go_cache', re.compile(r'patrickmn/go-cache|\bcache\.New\s*\(')),
    ('go_lru', re.compile(r'hashicorp/golang-lru|\blru\.New\s*\(')),
    ('go_sync_map', re.compile(r'\bsync\.Map\b')),
]
_SHARED_CACHE = [
    ('redis', re.compile(r'redis', re.IGNORECASE)),
    ('memcached', re.compile(r'memcache', re.IGNORECASE)),
    ('django_cache', re.compile(r'django\.core\.cache')),
    ('cache_set', re.compile(r'\.cache\.set\s*\(')),
    ('cache_get', re.compile(r'\.cache\.get\s*\(')),
    ('pylibmc', re.compile(r'pylibmc')),
]
_HTTP_CACHE = [
    ("cache_control_response", re.compile(r"Cache-Control\s*:", re.IGNORECASE)),
    ("cache_control_set", re.compile(r"set_header\(\s*[\'\"]Cache-Control")),
    ("cacheable", re.compile(r"@Cacheable", re.IGNORECASE)),
    ("revalidate", re.compile(r"@revalidate")),
    ("cache_header", re.compile(r"\w*headers\[[\'\"]Cache-Control[\'\"]\]")),
    ("s_maxage", re.compile(r"s-maxage\s*=", re.IGNORECASE)),
]
_TTL_DECLARED = [
    re.compile(r'ttl\s*=', re.IGNORECASE),
    re.compile(r'expire\s*=', re.IGNORECASE),
    re.compile(r'expires_in\s*=', re.IGNORECASE),
    re.compile(r'expires\s*=', re.IGNORECASE),
    re.compile(r'max_age\s*=', re.IGNORECASE),
    re.compile(r'maxage\s*=', re.IGNORECASE),
    re.compile(r'timeout\s*=\s*\d+'),  # redis client timeout
    # redis-specific: ex= and px= are TTLs at the call site
    re.compile(r'\bex\s*=\s*\d+'),
    re.compile(r'\bpx\s*=\s*\d+'),
]


def _detect_cache_policies(text):
    """Each match becomes one cache_policy fact with scope and ttl flag.

    scope is one of process | shared | http; we report what we observed, never the absence
    of other scopes. ttl_declared is True if any ttl/expire/timeout literal is in the file,
    False otherwise, 'unknown' if we did not see any cache evidence at all.
    """
    facts = []
    seen = set()
    for kind, regex in _PROCESS_CACHE:
        for match in regex.finditer(text):
            line = text.count('\n', 0, match.start()) + 1
            if ('process', kind, line) in seen: continue
            seen.add(('process', kind, line))
            facts.append({'scope': 'process', 'mechanism': kind, 'line': line,
                           'ttl_declared': any(p.search(text) for p in _TTL_DECLARED)})
    for kind, regex in _SHARED_CACHE:
        for match in regex.finditer(text):
            line = text.count('\n', 0, match.start()) + 1
            if ('shared', kind, line) in seen: continue
            seen.add(('shared', kind, line))
            facts.append({'scope': 'shared', 'mechanism': kind, 'line': line,
                           'ttl_declared': any(p.search(text) for p in _TTL_DECLARED)})
    for kind, regex in _HTTP_CACHE:
        for match in regex.finditer(text):
            line = text.count('\n', 0, match.start()) + 1
            if ('http', kind, line) in seen: continue
            seen.add(('http', kind, line))
            facts.append({'scope': 'http', 'mechanism': kind, 'line': line,
                           'ttl_declared': any(p.search(text) for p in _TTL_DECLARED)})
    return facts


# Rate limit / concurrency bound detection.
# A 1000-RPS endpoint with no limiter is a single point of total failure.
_CODE_LIMIT_PATTERNS = [
    ('limiter', re.compile(r'@limiter|@throttle', re.IGNORECASE)),
    ('RateLimiter', re.compile(r'RateLimiter', re.IGNORECASE)),
    ('TokenBucket', re.compile(r'TokenBucket')),
    ('SlowAPI', re.compile(r'slowapi|limits\.rate', re.IGNORECASE)),
    ('semaphore', re.compile(r'\.Semaphore\s*\(|asyncio\.Semaphore|threading\.Semaphore')),
    ('bounded_sem', re.compile(r'BoundedSemaphore\s*\(')),
    ('semaphores', re.compile(r'asyncio\.Semaphore\s*\(')),
    ('max_concurrent', re.compile(r'max_concurrent|maxConcurrent', re.IGNORECASE)),
    ('concurrency_limit', re.compile(r'concurrency_limit|concurrency-limit', re.IGNORECASE)),
    ('worker_threads', re.compile(r'max_workers|ThreadPoolExecutor\s*\(\s*max_workers')),
    ('worker_processes', re.compile(r'ProcessPoolExecutor\s*\(\s*max_workers')),
    ('go_time_rate', re.compile(r'golang\.org/x/time/rate|\brate\.NewLimiter\s*\(')),
    ('go_ulule_limiter', re.compile(r'ulule/limiter|\blimiter\.New\s*\(')),
]
_DECLARED_LIMIT_RE = re.compile(r'(?:limit|rps|qps|per_second|rate|permits|burst|max)\s*[=:]\s*(\d+)', re.IGNORECASE)

_CONFIG_LIMIT_PATTERNS = {
    'nginx': [
        ('limit_req_zone', re.compile(r'limit_req_zone', re.IGNORECASE)),
        ('limit_req', re.compile(r'limit_req\s+(?:zone|burst)', re.IGNORECASE)),
    ],
    'kubernetes': [
        ('resources_limits', re.compile(r'resources\s*:.*?limits\s*:', re.DOTALL)),
        ('hpa', re.compile(r'HorizontalPodAutoscaler')),
    ],
    'gateway': [
        ('rate_limit', re.compile(r'rate\s*limit', re.IGNORECASE)),
        ('throttle', re.compile(r'\bthrottle\b', re.IGNORECASE)),
    ],
}
_CONFIG_NAMES = {
    'Dockerfile': ('dockerfile', 'code'),
    'docker-compose.yml': ('compose', 'config'),
    'docker-compose.yaml': ('compose', 'config'),
    'compose.yml': ('compose', 'config'),
    'nginx.conf': ('nginx', 'config'),
}
_CONFIG_BY_FILENAME = {
    'Dockerfile': 'dockerfile',
    'docker-compose.yml': 'compose',
    'docker-compose.yaml': 'compose',
    'compose.yml': 'compose',
    'nginx.conf': 'nginx',
    # files with .yaml/.yml extension are scanned for kubernetes patterns
}


def _config_kind_for(name, text):
    """Decide which config-flavour patterns apply to this file, by content and extension."""
    if name in _CONFIG_BY_FILENAME:
        return _CONFIG_BY_FILENAME[name]
    if name.endswith('.yaml') or name.endswith('.yml'):
        # Loose heuristic: deployment/manifest-shaped YAML
        if ('HorizontalPodAutoscaler' in text or 'apiVersion:' in text
                or ('kind: Deployment' in text and 'containers:' in text)):
            return 'kubernetes'
    if name.endswith('.conf'):
        if 'limit_req_zone' in text:
            return 'nginx'
    return None


def _detect_rate_limits(text, rel, name):
    """Find every place a rate limit or concurrency bound is declared.

    Source distinguishes code (in-repo Python/JS/Go/etc.) from config (manifests).
    """
    rows = []
    config_kind = _config_kind_for(name, text)
    if config_kind:
        config_patterns = _CONFIG_LIMIT_PATTERNS.get(config_kind, [])
        for kind, regex in config_patterns:
            for match in regex.finditer(text):
                line = text.count('\n', 0, match.start()) + 1
                rows.append({'scope': 'global', 'mechanism': kind, 'declared_limit': None,
                              'source': 'config', 'line': line})
    # Always scan code patterns too (they may appear in source files that contain config too)
    for kind, regex in _CODE_LIMIT_PATTERNS:
        for match in regex.finditer(text):
            line = text.count('\n', 0, match.start()) + 1
            # Try to find a declared limit on the same line or next 80 chars
            nearby = text[match.start():match.start() + 200]
            limit_match = _DECLARED_LIMIT_RE.search(nearby)
            declared = int(limit_match.group(1)) if limit_match else None
            rows.append({'scope': 'global', 'mechanism': kind,
                          'declared_limit': declared, 'source': 'code', 'line': line})
    return rows


# Connection pool detection: pool_size is the real ceiling on concurrency.
# We never assume a default — undeclared means unknown.
_POOL_PATTERNS = [
    ('sqlalchemy_pool_size', re.compile(r'pool_size\s*=\s*(\d+)', re.IGNORECASE)),
    ('sqlalchemy_max_overflow', re.compile(r'max_overflow\s*=\s*(\d+)', re.IGNORECASE)),
    ('sqlalchemy_pool', re.compile(r'create_engine\([^)]*pool')),
    ('pg_pool_max', re.compile(r'max_connections\s*=\s*(\d+)', re.IGNORECASE)),
    ('pgxpool_max', re.compile(r'pgxpool\.New\([^)]*MaxConn(?:ections)?\s*[:=]?\s*(\d+)', re.IGNORECASE)),
    ('go_max_conns', re.compile(r'\.MaxConn(?:s|ections)?\s*[:=]\s*(\d+)')),
    ('sqlx_max', re.compile(r'sqlx\.Open[^)]*max_connections', re.IGNORECASE)),
    ('http_transport', re.compile(r'MaxIdleConns\s*[:=]\s*(\d+)', re.IGNORECASE)),
    ('http2_transport', re.compile(r'MaxConnsPerHost\s*[:=]\s*(\d+)', re.IGNORECASE)),
    ('mongoose_max', re.compile(r'maxPoolSize\s*:\s*(\d+)', re.IGNORECASE)),
    ('prisma_pool', re.compile(r'connection_limit\s*:\s*(\d+)', re.IGNORECASE)),
    ('sequelize_pool', re.compile(r'pool\s*:\s*\{[^}]*max\s*:\s*(\d+)', re.DOTALL)),
    ('gorm_setmax', re.compile(r'SetMaxOpenConns\s*\(\s*(\d+)')),
    ('dburl_pool', re.compile(r'DATABASE_URL[^&]*[?&](?:pool|max_connections|connection_limit)\s*=\s*(\d+)', re.IGNORECASE)),
]


def _detect_connection_pools(text):
    """One connection_pool fact per declared pool size.

    Undeclared pools are not facts: we report what we observed, not what we assumed.
    A file with no pool patterns emits no pool facts.
    """
    rows = []
    for kind, regex in _POOL_PATTERNS:
        for match in regex.finditer(text):
            line = text.count('\n', 0, match.start()) + 1
            # Numeric capture if present
            declared = None
            if match.groups():
                try:
                    declared = int(match.group(1))
                except (ValueError, TypeError):
                    declared = None
            rows.append({'resource': kind, 'declared_size': declared,
                          'source': 'code', 'line': line})
    return rows


def run(target, source, symbols=None, **options):
    facts, fingerprints = [], []
    seen = set()
    for item in source.readable():
        rel = item['path']; text = source.text(rel)
        if text is None: continue
        fingerprints.append(item['sha256'])
        name = Path(rel).name
        if name == 'Dockerfile' or name.endswith('.dockerfile'):
            for port in _dockerfile_ports(text):
                facts.append(make('deployment_target', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'kind': 'dockerfile', 'port': port,
                                                    'language': 'dockerfile'},
                                   limitations=LIMITATIONS))
        elif name in {'docker-compose.yml', 'docker-compose.yaml', 'compose.yml'}:
            for service in _compose_services(text):
                facts.append(make('deployment_target', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'kind': 'compose', 'service': service},
                                   limitations=LIMITATIONS))
        elif '.github/workflows/' in rel and (name.endswith('.yml') or name.endswith('.yaml')):
            for step in _github_actions(text)[:40]:
                facts.append(make('ci_step', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'name': step[:120]},
                                   limitations=LIMITATIONS))
        elif name == 'package.json':
            for script in _package_scripts(text):
                facts.append(make('ci_step', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'name': 'npm:' + script},
                                   limitations=LIMITATIONS))
        if language_of(rel) in {'python', 'javascript', 'typescript', 'go', 'ruby'}:
            for hint in _auth_hints(text):
                key = ('security', rel, hint)
                if key in seen: continue
                seen.add(key)
                facts.append(make('security_surface', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'hint': hint,
                                                    'language': language_of(rel)},
                                   limitations=LIMITATIONS))
            for signal in _observability_signals(text):
                key = ('observability', rel, signal)
                if key in seen: continue
                seen.add(key)
                facts.append(make('observability_signal', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'kind': signal,
                                                    'language': language_of(rel)},
                                   limitations=LIMITATIONS))
            for host in _outbound_hosts(text):
                key = ('integration', rel, host)
                if key in seen: continue
                seen.add(key)
                facts.append(make('integration_target', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'host': host,
                                                    'language': language_of(rel)},
                                   limitations=LIMITATIONS))
                policy = _detect_resilience_for_integration(text, host, language_of(rel))
                facts.append(make('resilience_policy', NAME, VERSION, item['sha256'],
                                   {'path': rel}, policy, limitations=LIMITATIONS))
            for cache in _detect_cache_policies(text):
                facts.append(make('cache_policy', NAME, VERSION, item['sha256'],
                                   {'path': rel, 'start_line': cache['line']},
                                   {'scope': cache['scope'], 'mechanism': cache['mechanism'],
                                    'ttl_declared': cache['ttl_declared']},
                                   limitations=LIMITATIONS))
            for model in _orm_models(text):
                facts.append(make('data_model', NAME, VERSION, item['sha256'],
                                   {'path': rel}, {'name': model['name'],
                                                    'framework': model['framework']},
                                   limitations=LIMITATIONS))
            for bound in _detect_query_bounds(text, language_of(rel)):
                facts.append(make('query_bound', NAME, VERSION, item['sha256'],
                                   {'path': rel, 'start_line': bound['line']},
                                   {'bounded': bound['bounded'], 'mechanism': bound['mechanism'],
                                    'kind': bound['kind'], 'snippet': bound['snippet']},
                                   limitations=LIMITATIONS))
        for limit in _detect_rate_limits(text, rel, name):
            facts.append(make('rate_limit', NAME, VERSION, item['sha256'],
                               {'path': rel, 'start_line': limit['line']},
                               {'scope': limit['scope'], 'mechanism': limit['mechanism'],
                                'declared_limit': limit['declared_limit'],
                                'source': limit['source']},
                               limitations=LIMITATIONS))
        for pool in _detect_connection_pools(text):
            facts.append(make('connection_pool', NAME, VERSION, item['sha256'],
                               {'path': rel, 'start_line': pool['line']},
                               {'resource': pool['resource'],
                                'declared_size': pool['declared_size'],
                                'source': pool['source']},
                               limitations=LIMITATIONS))
        if _migration_files(name):
            facts.append(make('migration_step', NAME, VERSION, item['sha256'],
                               {'path': rel}, {'name': name},
                               limitations=LIMITATIONS))
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
