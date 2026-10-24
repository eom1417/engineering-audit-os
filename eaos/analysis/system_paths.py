"""How the system map reads a path (eaos/analysis/system_map.py): a test file, a call's URL, two routes that are one, an
API's resource, the route a file-routed handler answers, and the files a file reaches by imports.
"""
import json
import re
from pathlib import Path

METHODS = ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS')
ROUTE_ROOTS = ('routes', 'api', 'pages', 'handlers', 'endpoints', 'functions')
TEST = re.compile(r'(^|/)(tests?|__tests__|e2e|spec|fixtures?)/|\.(test|spec)\.[a-z]+$|(^|/)test_[^/]*\.py$')


def _load(path, default):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default


def _facts(report, name, *kinds):
    record = _load(Path(report) / 'facts' / f'{name}.json', {})
    rows = record.get('facts') if isinstance(record, dict) else None
    return [f for f in rows or [] if isinstance(f, dict) and f.get('kind') in kinds]


def _path(fact):
    return str((fact.get('location') or {}).get('path') or '')


def is_test(path):
    return bool(TEST.search(str(path)))


def clean_path(target):
    """The URL path of a call as the code wrote it: a template or query cut off ('/api/audit${before' -> '/api/audit')."""
    text = str(target or '').strip()
    for stop in ('${', '?', '#', '`', ' ', "'", '"', '{'):
        if stop in text: text = text[:text.index(stop)]
    return text.rstrip('/') or ('/' if text.startswith('/') else text)


def _segments(path):
    return ['*' if s[:1] in (':', '$', '[', '{', '*', '<') else s for s in str(path).strip('/').split('/') if s]


def same_route(a, b):
    """Two paths are one route when each segment is equal, or one of them is a parameter (:id, [id], {id}, $id)."""
    x, y = _segments(a), _segments(b)
    return len(x) == len(y) and all(p == q or '*' in (p, q) for p, q in zip(x, y))


def _words(text):
    return [w for w in re.split(r'[/\-_.]+', str(text).lower()) if w]


def api_group(path):
    """The resource an API belongs to: /api/users and /api/users/:id are both /api/users*."""
    parts = [s for s in str(path).split('/') if s]
    if not parts: return '/'
    if '://' in str(path): return '/'.join(str(path).split('/')[:3])
    head = 2 if parts[0] in ('api', 'v1', 'v2', 'rest') and len(parts) > 1 else 1
    if head == 2 and parts[1] in ('v1', 'v2', 'v3') and len(parts) > 2: head = 3
    return '/' + '/'.join(parts[:head])


def route_of_file(path):
    """(the URL words a file-routed handler answers, spelled as its path after routes/ or api/), or None."""
    parts = str(path).split('/')
    stem = re.sub(r'\.(ts|tsx|js|jsx|mjs|cjs|py)$', '', parts[-1])
    parts = parts[:-1] + [stem]
    roots = [i for i, p in enumerate(parts[:-1]) if p in ROUTE_ROOTS]
    rel = parts[roots[-1] + 1:] if roots else parts[-1:]
    while rel and rel[-1] in ('index', 'route', '+server', 'handler', '__init__'): rel = rel[:-1]
    return '/'.join(rel)


def _reach(start, imports, depth, stop=()):
    seen, front = {start}, [start]
    for _ in range(depth):
        front = [d for f in front if f not in stop or f == start for d in imports.get(f, ()) if d not in seen and not is_test(d)]
        seen.update(front)
    return seen
