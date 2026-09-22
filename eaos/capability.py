"""How much of the intended product exists, measured from a report rather than asserted.

A plan whose targets cannot be measured is a wish. Every indicator here is computed from an
actual report directory: if the evidence for it is absent, the indicator is unmeasured and says
so, and an unmeasured indicator never counts as a pass.
"""
import json
from pathlib import Path

VERSION = 1
TARGET = 0.80
LIMITATIONS = [
    'A score measures what the tool produced on the reports it was given, never how useful a '
    'reader found it. The independent_proof domain is the only one that asks that question.',
    'An indicator with no evidence is unmeasured, not zero and not one.',
    'Scores over a corpus of one project describe that project.',
]


def _read(path):
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None
    except ValueError:
        return None


def _ratio(numerator, denominator):
    if not denominator:
        return None
    return round(min(1.0, numerator / denominator), 4)


def _facts(report, name, kind=None):
    payload = _read(Path(report) / 'facts' / f'{name}.json')
    rows = (payload or {}).get('facts', [])
    return [row for row in rows if kind is None or row['kind'] == kind]


def _summary(report, name):
    return ((_read(Path(report) / 'facts' / f'{name}.json') or {}).get('summary')) or {}


# ---------------------------------------------------------------- domains

def layered_engineering(report, extra=None):
    extra = extra or {}
    policy = _summary(report, 'policy')
    violations = policy.get('violations')
    unclassified = policy.get('unclassified_count')
    return {
        'policy_has_no_violations': None if violations is None else float(violations == 0),
        'policy_covers_every_file': None if unclassified is None else float(unclassified == 0),
        'invariants_enforced': extra.get('invariants_enforced'),
        'tests_pass': extra.get('tests_pass'),
        'one_artifact_one_owner': extra.get('one_artifact_one_owner'),
    }


def _language_rows(report):
    """Per language: files parsed, imports resolved, entry points, flows."""
    files = {}
    for fact in _facts(report, 'syntax', 'source_file'):
        language = fact['value'].get('language')
        if not language:
            continue
        files.setdefault(language, {'files': 0, 'parsed': 0, 'imports': 0, 'resolved': 0})
        files[language]['files'] += 1
        if fact['value'].get('parse_status') in ('OBSERVED', 'PARSED'):
            files[language]['parsed'] += 1
    by_path = {fact['location']['path']: fact['value'].get('language')
               for fact in _facts(report, 'syntax', 'source_file')}
    for edge in _facts(report, 'resolve'):
        language = by_path.get(edge['location']['path'])
        if language not in files:
            continue
        if edge.get('resolution') not in ('RESOLVED', 'UNRESOLVED', 'AMBIGUOUS'):
            continue        # EXTERNAL and stdlib have no file to resolve to
        files[language]['imports'] += 1
        if edge.get('resolution') == 'RESOLVED':
            files[language]['resolved'] += 1
    return files


def _depth(row):
    parse = _ratio(row['parsed'], row['files'])
    resolve = _ratio(row['resolved'], row['imports'])
    parts = [value for value in (parse, resolve) if value is not None]
    return round(sum(parts) / len(parts), 4) if parts else None


def structure_python(report, extra=None, minimum_share=0.4):
    rows = _language_rows(report)
    total = sum(item['files'] for item in rows.values())
    row = rows.get('python')
    if not row or not total or row['files'] / total < minimum_share:
        return {'python_files_parsed': None, 'python_imports_resolved': None,
                'entry_points_traced': None, 'symbols_extracted': None}
    entry = [f for f in _facts(report, 'entrypoints', 'entry_point')
             if f['value'].get('category') != 'test']
    flows = _facts(report, 'flows', 'flow')
    return {
        'python_files_parsed': None if not row else _ratio(row['parsed'], row['files']),
        'python_imports_resolved': None if not row else _ratio(row['resolved'], row['imports']),
        'entry_points_traced': _ratio(len(flows), len(entry)),
        'symbols_extracted': None if not _facts(report, 'syntax', 'symbol') else 1.0,
    }


def structure_polyglot(report, extra=None, minimum_files=5):
    rows = {name: row for name, row in _language_rows(report).items()
            if name != 'python' and row['files'] >= minimum_files}
    if not rows:
        return {'languages_with_depth': None, 'imports_resolved_outside_python': None}
    depths = {name: _depth(row) for name, row in rows.items()}
    measured = [value for value in depths.values() if value is not None]
    resolved = _ratio(sum(row['resolved'] for row in rows.values()),
                      sum(row['imports'] for row in rows.values()))
    return {
        'languages_with_depth': _ratio(sum(1 for value in measured if value >= TARGET), len(rows)),
        'imports_resolved_outside_python': resolved,
        'languages_seen': len(rows),
    }


# The operational questions a reader asks about a system that must carry load. Each needs a
# detector; a detector that does not exist yet is an unanswered question, not a clean result.
RUNTIME_DETECTORS = ('deployment_target', 'ci_step', 'security_surface', 'observability_signal',
                     'integration_target', 'data_model', 'migration_step',
                     'query_bound', 'resilience_policy', 'cache_policy', 'rate_limit',
                     'connection_pool')


def runtime_surface(report, extra=None):
    present = {kind for kind in RUNTIME_DETECTORS if _facts(report, 'runtime', kind)}
    declared = {kind for kind in RUNTIME_DETECTORS}
    known = set((_read(Path(report) / 'facts/runtime.json') or {}).get('summary', {})
                .get('by_kind', {}))
    return {
        'detectors_implemented': _ratio(len(known & declared), len(declared)),
        'detectors_finding_evidence': _ratio(len(present), len(declared)),
    }


# The eight questions a load model must answer for every entry point.
LOAD_QUESTIONS = ('data_access_calls', 'repeats_per_iteration', 'result_is_bounded',
                  'complexity_class', 'shared_mutable_state', 'outbound_calls_protected',
                  'cached', 'rate_limited')


def load_model(report, extra=None):
    record = _read(Path(report) / 'load-model.json')
    entry = [f for f in _facts(report, 'entrypoints', 'entry_point')
             if f['value'].get('category') != 'test']
    if not record:
        return {'entry_points_with_a_cost_record': _ratio(0, len(entry)) if entry else None,
                'questions_answered': 0.0 if entry else None,
                'projection_recorded': 0.0}
    rows = record.get('entry_points', [])
    answered = sum(1 for row in rows for question in LOAD_QUESTIONS
                   if (row.get('answers') or {}).get(question, {}).get('status') in ('answered', 'not_applicable'))
    return {
        'entry_points_with_a_cost_record': _ratio(len(rows), len(entry) or len(rows)),
        'questions_answered': _ratio(answered, len(rows) * len(LOAD_QUESTIONS)),
        'projection_recorded': float(bool(record.get('projection'))),
    }


def target_architecture(report, extra=None):
    record = _read(Path(report) / 'target-architecture.json')
    if not record:
        return {'components_assessed': None, 'decisions_with_alternatives': None,
                'gap_matrix_resolved': None}
    components = record.get('components', [])
    assessed = [row for row in components if row.get('relation') != 'unassessed']
    decisions = record.get('decisions', [])
    with_alternatives = [row for row in decisions if len(row.get('options') or []) >= 2
                         and row.get('chosen') and row.get('tradeoffs')]
    matrix = record.get('gap_matrix', [])
    resolved = [row for row in matrix if row.get('gap') != 'unassessed']
    return {
        'components_assessed': _ratio(len(assessed), len(components)),
        'decisions_with_alternatives': _ratio(len(with_alternatives), len(decisions)) if decisions else None,
        'gap_matrix_resolved': _ratio(len(resolved), len(matrix)),
    }


def transformation_plan(report, extra=None):
    record = _read(Path(report) / 'transform-plan.json')
    stages = (record or {}).get('stages', [])
    if not stages:
        return {'stages_with_runnable_acceptance': None, 'stages_with_rollback': None,
                'stages_with_predicted_effect': None, 'predictions_verified': None}
    runnable = [row for row in stages if (row.get('acceptance') or {}).get('command')
                or (row.get('acceptance') or {}).get('kind') == 'equivalence']
    guarantee = _read(Path(report) / 'guarantee.json')
    verified = (guarantee or {}).get('rows') or []
    return {
        'stages_with_runnable_acceptance': _ratio(len(runnable), len(stages)),
        'stages_with_rollback': _ratio(sum(1 for row in stages if row.get('rollback')), len(stages)),
        'stages_with_predicted_effect': _ratio(sum(1 for row in stages if row.get('predicted')), len(stages)),
        'predictions_verified': _ratio(len(verified), len(stages)) if guarantee else None,
    }


# Directories whose contents are a project's own fixtures or vendored copies. A finding about
# them is a finding about somebody else's code, and it must not lead the report.
NOT_THE_READER_S_CODE = ('testdata/', '/testdata/', 'fixtures/', '/fixtures/', 'vendor/', '/vendor/',
                         'node_modules/', 'third_party/', '/examples/', 'generated/')


def _about_the_reader_s_code(claim):
    paths = (claim.get('priority_factors') or {}).get('paths') or []
    if not paths:
        return True
    return not all(any(marker in path for marker in NOT_THE_READER_S_CODE) for path in paths)


def report_clarity(report, extra=None, top=10):
    verdict = _read(Path(report) / 'report-result.json') or {}
    dossier = _read(Path(report) / 'dossier.json') or {}
    claims = dossier.get('claims', [])
    from .compose.artifacts import BY_NAME
    documents = [path.name for path in Path(report).glob('*.md')]
    declared = [name for name in documents if name in BY_NAME]
    located = [claim for claim in claims
               if claim.get('falsifier') and (claim.get('fact_ids') or claim.get('evidence_ids'))]
    attributed = [claim for claim in claims
                  if 'model_inference' not in claim.get('method', []) or claim.get('basis')]
    ranked = sorted(claims, key=lambda claim: -(claim.get('priority') or 0))[:top]
    return {
        'output_contract_clean': float(not verdict.get('output_spec_violations', ['unknown'])),
        'documents_declared': _ratio(len(declared), len(documents)),
        'claims_with_evidence_and_falsifier': _ratio(len(located), len(claims)),
        'interpretation_declares_its_basis': _ratio(len(attributed), len(claims)),
        'top_findings_are_about_the_reader_s_code':
            _ratio(sum(1 for claim in ranked if _about_the_reader_s_code(claim)), len(ranked)),
    }


def independent_proof(report, extra=None):
    record = (extra or {}).get('release_evidence')
    if not record:
        return {'independent_reviews': None}
    rows = record.get('human_judgement') or []
    done = [row for row in rows if row.get('independent') and row.get('status') != 'blocked']
    return {'independent_reviews': _ratio(len(done), len(rows)) if rows else None}


DOMAINS = {
    'layered_engineering': layered_engineering,
    'structure_python': structure_python,
    'structure_polyglot': structure_polyglot,
    'runtime_surface': runtime_surface,
    'load_model': load_model,
    'target_architecture': target_architecture,
    'transformation_plan': transformation_plan,
    'report_clarity': report_clarity,
    'independent_proof': independent_proof,
}


def score(reports, extra=None):
    """One scorecard over one or more report directories. The weakest report decides a domain."""
    extra = extra or {}
    domains = {}
    for name, compute in DOMAINS.items():
        per_report = {}
        for report in reports:
            per_report[str(report)] = compute(report, extra)
        indicators = {}
        for key in sorted({key for row in per_report.values() for key in row}):
            values = [row.get(key) for row in per_report.values()]
            numbers = [value for value in values if isinstance(value, (int, float))]
            indicators[key] = round(min(numbers), 4) if numbers else None
        measured = [value for key, value in indicators.items()
                    if isinstance(value, (int, float)) and key != 'languages_seen']
        domains[name] = {
            'indicators': indicators,
            'measured_indicators': len(measured),
            'unmeasured_indicators': sum(1 for key, value in indicators.items()
                                         if value is None and key != 'languages_seen'),
            'score': round(sum(measured) / len(measured), 4) if measured else None,
            'target': TARGET,
        }
        detail = domains[name]
        detail['meets_target'] = bool(detail['score'] is not None and detail['score'] >= TARGET
                                      and detail['unmeasured_indicators'] == 0)
    scored = [row['score'] for row in domains.values() if row['score'] is not None]
    return {
        'contract_version': VERSION,
        'reports': [str(report) for report in reports],
        'domains': domains,
        'overall': round(sum(scored) / len(scored), 4) if scored else None,
        'domains_meeting_target': sum(1 for row in domains.values() if row['meets_target']),
        'domains_total': len(domains),
        'target': TARGET,
        'limitations': LIMITATIONS,
    }
