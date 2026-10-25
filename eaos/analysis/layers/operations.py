"""The operations layer and the tests layer, read from the facts (M6.9, M6.10).

Operations: every item of the reference type's infrastructure baseline (the pipeline and what it checks, configuration
kept apart from the code, where secrets live, error tracking and logs, health checks, migrations and backups, hosting),
found present or absent by eaos/analysis/target_projection.py's reading of the facts; each missing one is a finding that
names the item it fails (the infrastructure files' own findings are Checkov's, among the engines').

Tests: the project's own tests for every stack (Vitest, Jest, Mocha, Node's runner, Playwright, Cypress, pytest, Go), the
pass rate when the check ran them in the isolated copy (verification.json), which layers no test reaches, and every
endpoint that writes which no test reaches: no test names its route or its handler.
"""
import json
import re

from .endpoints import PARAM

from .. import target_projection

RUNNERS = (('vitest', 'Vitest'), ('jest', 'Jest'), ('mocha', 'Mocha'), ('@playwright/test', 'Playwright'), ('cypress', 'Cypress'),
           ('ava', 'AVA'), ('node --test', "Node's test runner"))
PYTHON_TESTS = ('pytest.ini', 'conftest.py', 'tox.ini')


def infrastructure(project, layer_map):
    """[{area, item, present, evidence, success}] of the reference type's baseline; [] when no type fits."""
    reference = layer_map.get('reference')
    if not reference: return []
    facts = target_projection.facts_by_kind(project.out)
    files = sorted(f['location']['path'] for f in facts['graph_node'])
    rows = target_projection.infrastructure(reference, facts, project.root, files, reference.get('root', ''))
    items = {item['area']: item for item in target_projection.baseline_items(reference)}
    return [{'area': row['area'], 'item': items[row['area']]['item'], 'present': row['present'], 'evidence': row['evidence'],
             'success': items[row['area']]['success_measure'], 'tool': row['tool']} for row in rows]


def operations_findings(rows):
    return [{'rule': 'operations-missing', 'path': '*', 'line': None, 'evidence': row['evidence'],
             'params': {'area': row['area'], 'item': row['item'], 'evidence': row['evidence'], 'success': row['success']}}
            for row in rows if not row['present']]


def _node_runners(manifest):
    try: data = json.loads(manifest.read_text(encoding='utf-8'))
    except (OSError, ValueError): return []
    names = set(data.get('dependencies') or {}) | set(data.get('devDependencies') or {})
    scripts = ' '.join((data.get('scripts') or {}).values())
    return [label for key, label in RUNNERS if key in names or key in scripts]


def runners(project):
    """The test runners the project declares."""
    found = [label for manifest in [project.root / 'package.json', *project.root.glob('*/package.json')] for label in _node_runners(manifest)]
    python = any((project.root / name).is_file() for name in PYTHON_TESTS) or any(p.endswith('.py') for p in project.tests)
    go = any(p.endswith('_test.go') for p in project.tests)
    return sorted(set(found + (['pytest'] if python else []) + (['go test'] if go else [])))


def _named(row, texts):
    """Whether a test names the endpoint: its route (parameters as any value) or its handler."""
    route = str(row['route'])
    if route.startswith('action:'): return bool(re.search(r'\b' + re.escape(route[7:]) + r'\b', texts))
    pieces = PARAM.split(route.rstrip('/') or '/')
    pattern = '[^/\'"`?]+'.join(re.escape(piece) for piece in pieces)
    if re.search(r'[\'"`]' + pattern + r'(?:[/?\'"`])', texts): return True
    handler = row.get('handler') or ''
    return bool(handler) and len(handler) > 3 and bool(re.search(r'\b' + re.escape(handler) + r'\b', texts))


def _untested_layers(project, layer_map):
    """The layers whose files no test imports."""
    reached = {target for path in project.tests for target in project.edges.get(path, ())}
    placed = {row['layer'] for row in layer_map['rows'] if row['layer'] and row['layer'] != 'database'}
    return sorted(placed - {row['layer'] for row in layer_map['rows'] if row['path'] in reached})


def _failing(run):
    if not (run and run['failed']): return []
    return [{'rule': 'tests-failing', 'path': '*', 'line': None, 'evidence': run['command'],
             'params': {'failed': run['failed'], 'total': run['total'], 'command': run['command']}}]


def tests(project, layer_map, endpoints, verification=None):
    """{'runners', 'files', 'run', 'layers_untested', 'endpoints_untested', 'findings'}."""
    texts = '\n'.join(project.text(path) for path in project.tests)
    untested = [row for row in endpoints if row['writes'] and not row['empty'] and not _named(row, texts)]
    run = _run(verification)
    findings = [{'rule': 'untested-write', 'path': row['path'], 'line': row['line'], 'evidence': f"{row['method']} {row['route']}",
                 'params': {'method': row['method'], 'route': row['route'], 'path': row['path']}} for row in untested] + _failing(run)
    return {'runners': runners(project), 'files': len(project.tests), 'run': run, 'layers_untested': _untested_layers(project, layer_map),
            'endpoints_untested': [f"{row['method']} {row['route']}" for row in untested], 'findings': findings}


def _command(verification):
    attempts = verification.get('attempts') or []
    return ' '.join(map(str, verification.get('command') or (attempts[0].get('argv') if attempts else []) or []))


def _run(verification):
    """{'command', 'total', 'failed', 'passed'} of the project's tests the check ran, or None."""
    if not (verification and verification.get('executed')): return None
    attempts = verification.get('attempts') or []
    failed = sum(1 for attempt in attempts if attempt.get('exit_code') not in (0, None))
    return {'command': _command(verification), 'total': (verification.get('suite') or {}).get('tests') or len(attempts),
            'failed': failed, 'passed': not failed}
