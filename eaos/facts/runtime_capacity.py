"""How a source file bounds its load, for the runtime facts (eaos/facts/runtime.py): the bounds its queries declare,
its caches, its rate limits and concurrency bounds, and its connection pools. Each detector reports what it observed,
never what it assumed.
"""
import re


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


def detect_query_bounds(text, language):
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


def detect_cache_policies(text):
    """Each match becomes one cache_policy fact with scope and ttl flag.

    scope is one of process | shared | http; we report what we observed, never the absence
    of other scopes. ttl_declared is True if any ttl/expire/timeout literal is in the file,
    False otherwise, 'unknown' if we did not see any cache evidence at all.
    """
    facts = []
    seen = set()
    for scope, patterns in (('process', _PROCESS_CACHE), ('shared', _SHARED_CACHE), ('http', _HTTP_CACHE)):
        for kind, regex in patterns:
            for match in regex.finditer(text):
                line = text.count('\n', 0, match.start()) + 1
                if (scope, kind, line) in seen: continue
                seen.add((scope, kind, line))
                facts.append({'scope': scope, 'mechanism': kind, 'line': line,
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


def detect_rate_limits(text, rel, name):
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


def detect_connection_pools(text):
    """One connection_pool fact per declared pool size.

    Undeclared pools are not facts: we report what we observed, not what we assumed.
    A file with no pool patterns emits no pool facts.
    """
    # a pattern's capture, when it has one, is always \d+: the declared size
    return [{'resource': kind, 'declared_size': int(match.group(1)) if match.groups() else None,
             'source': 'code', 'line': text.count('\n', 0, match.start()) + 1}
            for kind, regex in _POOL_PATTERNS for match in regex.finditer(text)]
