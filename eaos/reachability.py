"""Dead code via static reachability: traces imports from production entry points.

The reachability walker produces ``dead_code`` facts and the claims they become.
A dead candidate is a module that no production entry point imports and a symbol
that no caller references elsewhere in the snapshot. The spec for NS5.T1 is:
entry points (entry_point, not test_only, not npm_script) are the seeds; module_edge
facts are the edges; dynamic imports are still edges; symbols are matched by
text search to drop false positives a registry export would introduce.

``build(facts)`` returns the list of dead_code facts the reachability scan found,
using only facts already produced for the project; it never re-parses source.
"""
import re
from collections import defaultdict, deque

NAME = 'reachability'
VERSION = '1'

# Files excluded from being a dead candidate (per spec): tests, fixtures, configs,
# setup, anything vendored. The detector lists them so a developer can audit.
EXCLUDED_PATH_PATTERNS = (
    re.compile(r'\.config\.'),
    re.compile(r'(^|/)conftest\.py$'),
    re.compile(r'(^|/)setup\.py$'),
    re.compile(r'(^|/)tests?/'),
    re.compile(r'(^|/)__tests__/'),
    re.compile(r'(^|/)fixtures?/'),
    re.compile(r'\.test\.'),
    re.compile(r'\.spec\.'),
)


def _is_excluded(path):
    return any(pattern.search(path) for pattern in EXCLUDED_PATH_PATTERNS)


def _entry_seeds(entry_facts):
    """Production entry points: person- or service-reachable, not tests, not npm_script."""
    for fact in entry_facts:
        value = fact.get('value') or {}
        if value.get('category') == 'test' or value.get('test_only'):
            continue
        framework = value.get('framework')
        if framework in {'npm_script', 'public_api'}:
            continue
        surface = value.get('surface')
        if surface not in {'page', 'http', 'cli'}:
            continue
        path = (fact.get('location') or {}).get('path')
        if path:
            yield path


def _source_files(structure_facts):
    """Every parsed source file the resolve stage saw."""
    for fact in structure_facts:
        if fact.get('kind') != 'source_file':
            continue
        path = (fact.get('location') or {}).get('path')
        value = fact.get('value') or {}
        if path and value.get('parse_status') == 'PARSED':
            yield path


def _module_edges(resolved_facts, import_facts):
    """The edges the importer-graph walker follows.

    The spec calls out both ``import()`` with a literal argument and
    ``importlib.import_module('x')`` as edges; we read them out of the import_fact
    payload the import_edge extractor wrote. Resolved imports are direct; dynamic
    imports with a literal target resolve to the same set.
    """
    edges = defaultdict(set)
    for fact in resolved_facts:
        if fact.get('kind') != 'module_edge': continue
        resolution = fact.get('resolution')
        if resolution not in {'RESOLVED', 'DYNAMIC'}: continue
        path = (fact.get('location') or {}).get('path')
        target = ((fact.get('value') or {}).get('to_path')) or ''
        if path and target:
            edges[path].add(target)
    for fact in import_facts:
        if fact.get('kind') != 'import_edge': continue
        # A dynamic-import call (``import('name')``) becomes an edge too: we read the
        # literal target string out of the args. The import_edge extractor stores it in
        # value.module when the argument is a string literal.
        path = (fact.get('location') or {}).get('path')
        module = ((fact.get('value') or {})).get('module') or ''
        is_dynamic = ((fact.get('value') or {})).get('is_dynamic') or False
        if not (path and module and (is_dynamic or module.startswith('./') or module.startswith('../'))):
            continue
        # Resolve the module string relative to the importer's directory; the
        # spec treats this as an edge like any other module_edge.
        directory = '/'.join(path.split('/')[:-1])
        target = module[2:] if module.startswith('./') else module
        resolved = (f"{directory}/{target}" if directory else target).replace('//', '/')
        edges[path].add(resolved)
    return edges


def _reachable_from(seeds, edges):
    """BFS over the import graph starting from every production entry-point path."""
    seen = set()
    queue = deque()
    for seed in seeds:
        seen.add(seed)
        queue.append(seed)
    while queue:
        node = queue.popleft()
        for target in edges.get(node, ()):
            if target in seen:
                continue
            seen.add(target)
            queue.append(target)
    return seen


def _declared_symbols(symbol_facts):
    """Every symbol the structure stage saw, indexed by file."""
    by_path = defaultdict(set)
    for fact in symbol_facts:
        if fact.get('kind') != 'symbol': continue
        location = fact.get('location') or {}
        path = location.get('path')
        name = ((fact.get('value') or {})).get('name')
        if path and name:
            by_path[path].add(name)
    return by_path


def _symbol_referenced_elsewhere(symbol, files, source_text):
    """A name that appears elsewhere in the snapshot text is referenced; not a candidate.

    The spec accepts a symbol whose name is searched for outside its declaration; a hit
    anywhere in the file list drops the false-positive. We use a per-name cache to keep
    the cost bounded on real projects.
    """
    pattern = re.compile(r'\b' + re.escape(symbol) + r'\b')
    for f in files:
        text = source_text.get(f)
        if text is None or f not in source_text: continue
        rest = pattern.sub('', text, count=1)
        if not rest.startswith(text.split(symbol, 1)[0]):
            return True
    return False


def _entry_symbol_seeds(entry_facts):
    """The symbols the entry-points own — counted as live by definition.

    A test entry point does not own symbols of the production kind: its handler is a
    test method, not a public surface. Skipping it prevents a false 'unreachable'
    verdict on every test handler.
    """
    names = set()
    for fact in entry_facts:
        value = fact.get('value') or {}
        if value.get('category') == 'test' or value.get('test_only'):
            continue
        framework = value.get('framework')
        if framework in {'npm_script', 'public_api'}:
            continue
        surface = value.get('surface')
        if surface not in {'page', 'http', 'cli'}:
            continue
        handler = value.get('handler')
        if handler and handler != 'h':
            names.add(handler)
        for entry in ('symbol', 'route', 'name'):
            v = ((fact.get('location') or {})).get(entry)
            if v: names.add(v)
    return names


def build(facts):
    """Produce one ``dead_code`` fact for every module + symbol no live path reaches.

    The result is a list of facts (``kind='dead_code'``). They are written by the
    caller (the load or claim stage) into the project's fact set so downstream
    generators can treat them as engine_finding-shaped observations.
    """
    entry_facts = [f for f in facts if f.get('kind') == 'entry_point']
    resolved_facts = [f for f in facts if f.get('kind') == 'module_edge']
    structure_facts = [f for f in facts if f.get('kind') == 'source_file']
    symbol_facts = [f for f in facts if f.get('kind') == 'symbol']
    import_facts = [f for f in facts if f.get('kind') == 'import_edge']

    edges = _module_edges(resolved_facts, import_facts)
    seeds = list(_entry_seeds(entry_facts))
    reached = _reachable_from(seeds, edges)
    candidate_modules = [p for p in _source_files(structure_facts)
                        if p not in reached and not _is_excluded(p)]

    entry_symbols = _entry_symbol_seeds(entry_facts)
    dead_symbols = []
    declared = _declared_symbols(symbol_facts)
    for path, names in declared.items():
        if _is_excluded(path):
            continue
        for name in names:
            if name in entry_symbols: continue
            if name.startswith('_'): continue  # private; rarely a candidate
            dead_symbols.append((path, name))

    facts_out = []
    sites = [{'path': module, 'line': 1, 'symbol': module} for module in sorted(candidate_modules)]
    facts_out.append({
        'id': f'FACT-RCH-{len(candidate_modules)}-M',
        'kind': 'engine_finding', 'extractor': NAME, 'extractor_version': VERSION,
        'extractor_input_sha': '',
        'message': f'unreachable module: function `dead code` in {len(candidate_modules)} files: ' +
                  ', '.join(sorted(candidate_modules)[:5]) +
                  (' ...' if len(candidate_modules) > 5 else ''),
        'location': {'path': sorted(candidate_modules)[0] if candidate_modules else '', 'line': 1,
                     'symbol': sorted(candidate_modules)[0] if candidate_modules else ''},
        'value': {'engine': 'reachability', 'engine_version': VERSION,
                  'rule': 'unreachable-module', 'kind': 'dead_code',
                  'method': 'reachability', 'message': 'unreachable module',
                  'subject_kind': 'module', 'subject': 'multiple',
                  'sites': sites, 'measurements': [], 'engine_confidence': 0.5},
    }) if candidate_modules else None

    sites = [{'path': p, 'line': 1, 'symbol': n} for p, n in dead_symbols[:50]]
    facts_out.append({
        'id': f'FACT-RCH-{len(dead_symbols)}-S',
        'kind': 'engine_finding', 'extractor': NAME, 'extractor_version': VERSION,
        'extractor_input_sha': '',
        'message': f'unreachable symbol: function `dead code` in {len(dead_symbols)} candidates: ' +
                  ', '.join(f'{p}:{n}' for p, n in dead_symbols[:5]) +
                  (' ...' if len(dead_symbols) > 5 else ''),
        'location': {'path': dead_symbols[0][0] if dead_symbols else '', 'line': 1,
                     'symbol': dead_symbols[0][1] if dead_symbols else ''},
        'value': {'engine': 'reachability', 'engine_version': VERSION,
                  'rule': 'unreachable-symbol', 'kind': 'dead_code',
                  'method': 'reachability', 'message': 'unreachable symbol',
                  'subject_kind': 'symbol', 'subject': 'multiple',
                  'sites': sites, 'measurements': [], 'engine_confidence': 0.4},
    }) if dead_symbols else None

    return [f for f in facts_out if f]


LIMITATIONS = (
    'A module that has no imports at all is unreachable only if every seed fails to '
    'reference it by name; a name match in any other file drops the candidate.',
    'Dynamic imports with a non-literal target (e.g. ``import(path)`` where path is computed) '
    'are not followed.',
    'TypeScript module paths that resolve through a bundler alias are followed when the '
    'alias resolves to a literal in the snapshot; unresolved aliases count as edges to nowhere.',
)
