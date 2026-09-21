"""Does the recorded evidence support a release, and which claims does it not support?

A release decision made from a record nobody checked is a decision made from a feeling. This
reads the evidence file, re-applies the protocol that was declared before the run, and prints
what the evidence does and does not establish. It never upgrades a blocked verdict.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DECISIONS = ('release', 'limited_release', 'pilot', 'no_release')


def check(path):
    from eaos.evaluation_protocol import ARMS, verdict
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    problems = []
    for field in ('protocol', 'results', 'decision', 'supported_scope', 'unsupported_scope'):
        if field not in payload:
            problems.append(f'the record has no {field}')
    if problems:
        return {'ok': False, 'problems': problems, 'decision': None}
    record = payload['protocol']
    results = payload['results']
    outcome = verdict(record, results.get('measured', {}))
    decision = payload['decision']
    if decision not in DECISIONS:
        problems.append(f'decision must be one of {list(DECISIONS)}')
    if outcome['verdict'] != 'supported' and decision == 'release':
        problems.append(f"the evidence is {outcome['verdict']}, which does not support a full release")
    ran = set(results.get('arms_run') or [])
    unknown = sorted(ran - set(ARMS))
    if unknown:
        problems.append(f'unknown arm in the results: {unknown}')
    for arm in ARMS:
        if arm not in ran and arm not in (results.get('arms_blocked') or {}):
            problems.append(f'arm {arm} was neither run nor recorded as blocked')
    if not payload['unsupported_scope']:
        problems.append('no unsupported scope is recorded; every evaluation has a boundary')
    for row in payload.get('human_judgement') or []:
        if row.get('independent') is not True and row.get('status') != 'blocked':
            problems.append(f"human judgement {row.get('id')} is neither independent nor marked blocked")
    return {'ok': not problems, 'problems': sorted(problems), 'verdict': outcome,
            'decision': decision, 'supported_scope': payload['supported_scope'],
            'unsupported_scope': payload['unsupported_scope']}


def main(argv):
    if not argv:
        print('usage: check_release_evidence.py <evidence.json>', file=sys.stderr)
        return 2
    result = check(argv[0])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
