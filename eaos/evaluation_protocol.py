"""The comparison protocol, fixed before anything is run.

A hypothesis chosen after seeing the results is not a hypothesis. This declares what is being
compared, on which cases, by whom, and what would count as failure — and refuses a record that
was written after the fact or judged by the person who wrote the answers.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

VERSION = 1
SPLITS = ('train', 'development', 'holdout')
ARMS = ('facts_only', 'eaos_with_model', 'plain_agent')
# A case is one of these. A corpus of only healthy projects proves nothing about detection.
CASE_KINDS = ('healthy', 'defective', 'ambiguous', 'planted_fixture', 'non_python', 'large')
LIMITATIONS = [
    'A protocol fixes the question; it does not make the answer generalise beyond the corpus.',
    'Scripted fixtures measure detection, never usefulness to a reader.',
    'A case judged by whoever wrote its ground truth is not independent and is recorded as blocked.',
]


def protocol(hypothesis, thresholds, cases, arms=ARMS, adjudicator=None, authored_by=None,
             declared_at=None):
    """A protocol record. Every field is required because every missing one is a way to move the goalposts."""
    problems = []
    if not hypothesis or len(hypothesis.strip()) < 20:
        problems.append('state the hypothesis as a sentence that could turn out false')
    if not thresholds:
        problems.append('declare the thresholds before the run, not after')
    for name, value in (thresholds or {}).items():
        if not isinstance(value, (int, float)):
            problems.append(f'threshold {name} must be a number decided in advance')
    seen_kinds = {case.get('kind') for case in cases}
    for required in ('healthy', 'defective'):
        if required not in seen_kinds:
            problems.append(f'the corpus has no {required} case, so a result would not mean anything')
    for case in cases:
        if case.get('split') not in SPLITS:
            problems.append(f"case {case.get('id')}: split must be one of {list(SPLITS)}")
        if case.get('kind') not in CASE_KINDS:
            problems.append(f"case {case.get('id')}: kind must be one of {list(CASE_KINDS)}")
        if case.get('split') == 'holdout' and case.get('answers_visible_to_analyser'):
            problems.append(f"case {case.get('id')}: a holdout case whose answers are visible is not holdout")
    for arm in arms:
        if arm not in ARMS:
            problems.append(f'unknown arm {arm}')
    if adjudicator and authored_by and adjudicator == authored_by:
        problems.append('the adjudicator wrote the answers; that judgement is not independent')
    return {'contract_version': VERSION,
            'declared_at': declared_at or datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'hypothesis': hypothesis, 'thresholds': dict(sorted((thresholds or {}).items())),
            'arms': list(arms), 'cases': cases, 'adjudicator': adjudicator, 'authored_by': authored_by,
            'independent': bool(adjudicator) and adjudicator != authored_by,
            'problems': sorted(set(problems)), 'valid': not problems,
            'limitations': LIMITATIONS}


def verdict(record, results):
    """Compare measured results against the thresholds that were declared beforehand."""
    if not record.get('valid'):
        return {'verdict': 'blocked', 'reason': 'the protocol itself is invalid', 'failed': record['problems']}
    if not record.get('independent'):
        return {'verdict': 'blocked',
                'reason': 'no independent adjudicator, so the result is recorded rather than believed',
                'failed': []}
    failed = [name for name, threshold in record['thresholds'].items()
              if name not in results or results[name] < threshold]
    missing = [name for name in record['thresholds'] if name not in results]
    return {'verdict': 'not_supported' if failed else 'supported',
            'failed': sorted(failed), 'unmeasured': sorted(missing),
            'measured': {name: results.get(name) for name in sorted(record['thresholds'])},
            'limits': ' '.join(LIMITATIONS)}


def write(path, record):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return str(path)
