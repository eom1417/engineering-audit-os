"""The whole system in layers (M6): a check reads every project as the layers a professional firm reads, by default.

    run(target, out)          the static part: the layer map, the boundaries, what ships to the browser, every endpoint
                              and its guard, the data layer's rules, where the business rules live, operations and tests;
                              writes <out>/layers.json (what people and the Studio read) and the `boundaries` fact set
                              (what the claims make cards of: eaos/analysis/layer_claims.py)
    amend(out, live)          the live part's findings (the data rules tried, the API tried, the built output of the
                              isolated copy: eaos/live/layers_live.py) joined to the same two

Nothing is written into the project; a placement EAOS is unsure of becomes a question, never a finding.
"""
import json
from pathlib import Path

from ...facts import digest, make
from ...facts.store import write_set
from . import boundaries, browser, data, endpoints, operations, rules_split
from .catalog import BOUNDARIES, RULES, fix, sentence
from .placement import layer_map
from .source import Project

NAME = 'boundaries'
VERSION = '1'
RECORD = 'layers.json'
SEVERITIES = ('low', 'medium', 'high')
LIMITATIONS = ['Read from the code, the migrations and the built output; a guard or a rule EAOS cannot read is asked, '
               'never assumed. Live findings (the data rules and the API tried) are measured on an isolated copy.']


def _policy_layers(target):
    path = Path(target) / 'eaos.policy.json'
    try: return json.loads(path.read_text(encoding='utf-8')).get('layers') if path.is_file() else None
    except ValueError: return None


def _said(row, live=False):
    """A finding with its boundary, severity and sentences, as the record keeps it."""
    boundary, severity = RULES[row['rule']][:2]
    params = {**row['params'], **({'path': row['path']} if row.get('path') and 'path' not in row['params'] else {})}
    return {**row, 'boundary': boundary, 'severity': row.get('severity') or severity, 'live': live,
            'en': sentence(row['rule'], params), 'ar': sentence(row['rule'], params, 'ar'),
            'fix_en': fix(row['rule'], params), 'fix_ar': fix(row['rule'], params, 'ar')}


def _layers(drawn):
    reference = drawn['reference'] or {'layers': []}
    counts = {}
    for row in drawn['rows']: counts[row['layer']] = counts.get(row['layer'], 0) + 1
    return [{'name': layer['name'], 'role': layer.get('role'), 'responsibility': layer.get('responsibility'),
             'allowed': layer.get('allowed_dependencies') or [], 'files': counts.get(layer['name'], 0)} for layer in reference['layers']]


def _read(path):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def check(target, out, verification=None):
    """The record of the static part (no file written); `verification`: the project's tests as this check ran them."""
    project = Project(target, out)
    policy = _policy_layers(target)
    drawn = {**layer_map(project, policy), 'declared_policy': bool(policy)}
    breaches, questions = boundaries.check(project, drawn)
    table = endpoints.table(project)
    guarded, asked = endpoints.judged(table)
    sides = {row['path']: row['side'] for row in drawn['rows']}
    shipped, held, infra = browser.check(project, drawn['rows']), data.check(project, sides), operations.infrastructure(project, drawn)
    tested = operations.tests(project, drawn, table, verification)
    found = breaches + shipped['findings'] + guarded + held['findings'] + rules_split.check(project, drawn['rows'], table) \
        + operations.operations_findings(infra) + tested['findings']
    return {'schema_version': 1, 'type': drawn['type'], 'declared_policy': drawn['declared_policy'], 'layers': _layers(drawn),
            'map': [{k: row[k] for k in ('path', 'layer', 'side', 'confidence', 'reason')} for row in drawn['rows']],
            'gaps': drawn['gaps'], 'endpoints': table, 'tables': held['tables'], 'built': shipped['built'],
            'operations': infra, 'tests': {k: v for k, v in tested.items() if k != 'findings'},
            'findings': [_said(row) for row in found], 'questions': questions + asked, 'live': None}


def summary(record):
    """Per boundary, its findings by severity, and the critical ones (high) first."""
    by = {name: {s: sum(1 for f in record['findings'] if f['boundary'] == name and f['severity'] == s) for s in SEVERITIES}
          for name in BOUNDARIES}
    return {'boundaries': by, 'findings': len(record['findings']), 'questions': len(record['questions']),
            'critical': [f['en'] for f in record['findings'] if f['severity'] == 'high'][:10],
            'files': len(record['map']), 'gaps': len(record['gaps']), 'endpoints': len(record['endpoints']),
            'placed': len(record['map']) - len(record['gaps']), 'tables': len(record['tables']),
            'by_boundary': {name: sum(by[name].values()) for name in BOUNDARIES}}


def facts_of(record):
    return _facts(record)[1]


def _facts(record):
    sha = digest(json.dumps([f['rule'] + str(f.get('path')) + str(f.get('line')) for f in record['findings']]).encode('utf-8'))
    return sha, [make('boundary_finding', NAME, VERSION, sha, {'path': f.get('path') or '*', 'start_line': f.get('line')},
                      {key: f[key] for key in ('rule', 'boundary', 'severity', 'params', 'evidence', 'en', 'ar', 'fix_en', 'fix_ar', 'live')},
                      limitations=LIMITATIONS) for f in record['findings']]


def write(out, record):
    out = Path(out)
    record['summary'] = summary(record)
    (out / RECORD).write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    sha, facts = _facts(record)
    asked = [{'question': q['question'], 'question_ar': q['question_ar'], 'path': q['path']} for q in record['questions'][:30]]
    write_set(out, NAME, NAME, VERSION, facts, sha, LIMITATIONS, {**record['summary'], 'asked': asked})
    return record['summary']


def run(target, out, verification=None):
    return write(out, check(target, out, verification))


def depcruise_rules(target, out):
    """Write the layer map's rules where dependency-cruiser's adapter reads them, before the engines run."""
    project = Project(target, out)
    policy = _policy_layers(target)
    rules = boundaries.rules({**layer_map(project, policy), 'declared_policy': bool(policy)})
    (Path(out) / 'engines').mkdir(parents=True, exist_ok=True)
    (Path(out) / 'engines' / boundaries.DEPCRUISE_FILE).write_text(json.dumps(rules), encoding='utf-8')
    return len(rules)


NAMING = ('route', 'method', 'table', 'name', 'field', 'to', 'family', 'area')
# The boundaries a change can break; a missing piece of operations or a test not written yet is not broken by a fix.
GATED = ('browser', 'endpoints', 'data', 'rules', 'layers')


def _key(finding):
    """What names a finding whatever line it moved to: its rule, its file and the values that name it."""
    return (finding['rule'], finding.get('path'), tuple(str(finding['params'].get(k)) for k in NAMING))


def introduced(before, after):
    """The sentences of the static findings `after` has and `before` had not: the boundaries a change broke, the gate a
    fix batch is judged by beside the project's own policy (eaos/journeys/execute.py new_breakage)."""
    had = {_key(f) for f in before.get('findings') or [] if not f.get('live')}
    return [f"the change broke a boundary: {f['en']}" for f in after['findings'] if f['boundary'] in GATED and _key(f) not in had]


def amend(out, live):
    """Join the live part's findings and what it measured to the record and the fact set."""
    record = _read(Path(out) / RECORD)
    if record is None: return None
    record['findings'] = [f for f in record['findings'] if not f.get('live')] + [_said(row, live=True) for row in live['findings']]
    record['live'] = {key: value for key, value in live.items() if key != 'findings'}
    return write(out, record)
