"""The output contract: rules a rendered dossier must satisfy before anyone is asked to read it."""
from pathlib import Path
import re

BUDGETS = {'DECISION-BRIEF.md': 120, 'SYSTEM-MAP.md': 260, 'COUPLING-ATLAS.md': 220, 'EVOLUTION.md': 220,
           'PROVENANCE.md': 80, 'FLOWS.md': 300, 'DOMAIN-AND-DATA.md': 240, 'CONTRACTS.md': 200, 'RISK-REGISTER.md': 200, 'VERIFICATION-MAP.md': 160, 'DELTA.md': 160, 'VERIFICATION-MAP.md': 180}
HUMAN_ARTIFACTS = set(BUDGETS)
CLAIM_REFERENCE = re.compile(r'\bCLM-\d{3,}\b')
MARKERS = {'⬤', '◐', '○', '؟'}
COVERAGE_MARKERS = ('التغطية', 'Coverage')
GAP_MARKERS = ('ما لم يُفحص', 'Not examined')


def rendered(out):
    return {path.name: path.read_text(encoding='utf-8') for path in sorted(Path(out).glob('*.md')) if path.name in HUMAN_ARTIFACTS}


def validate(out, dossier):
    """Return a list of rule violations; an empty list means the output may be published."""
    documents = rendered(out)
    known = {claim['id'] for claim in dossier.get('claims', [])}
    problems = []
    for name, text in sorted(documents.items()):
        lines = text.count('\n')
        if lines > BUDGETS[name]:
            problems.append(f'R2 {name}: {lines} lines exceeds the budget of {BUDGETS[name]}')
        if '```json' in text:
            problems.append(f'R8 {name}: raw record dump in a human artifact')
        for reference in sorted(set(CLAIM_REFERENCE.findall(text))):
            if reference not in known:
                problems.append(f'R1 {name}: references {reference}, which is absent from the ledger')
    brief = documents.get('DECISION-BRIEF.md')
    if brief is None:
        problems.append('R6 DECISION-BRIEF.md: the decision artifact is missing')
    else:
        if not any(marker in brief for marker in COVERAGE_MARKERS):
            problems.append('R6 DECISION-BRIEF.md: no coverage header')
        if not any(marker in brief for marker in GAP_MARKERS):
            problems.append('R6 DECISION-BRIEF.md: the unexamined-scope section may not be omitted')
        if not any(marker in brief for marker in MARKERS):
            problems.append('R3 DECISION-BRIEF.md: no confidence markers on stated claims')
    problem_types = {'risk', 'cause', 'business_rule', 'structure', 'capability_gap'}
    for claim in dossier.get('claims', []):
        states_a_problem = claim.get('claim_type') in problem_types or bool((claim.get('impact') or {}).get('scenario'))
        if states_a_problem and claim.get('confidence') != 'REFUTED':
            disposition = (claim.get('disposition') or {}).get('kind')
            if disposition in (None, 'none_yet'):
                problems.append(f"R5 {claim['id']}: a live risk needs a task or a documented acceptance")
    for task in dossier.get('tasks', []):
        if not task.get('verify_command'):
            problems.append(f"R7 {task.get('id', '?')}: the acceptance criterion is not a runnable command")
    seen = {}
    for claim in dossier.get('claims', []):
        artifacts = claim.get('artifacts') or []
        if len(artifacts) > 1:
            problems.append(f"R4 {claim['id']}: presented in full in more than one artifact ({', '.join(artifacts)})")
        seen.setdefault(claim.get('statement'), []).append(claim['id'])
    for statement, identifiers in sorted(seen.items()):
        if len(identifiers) > 1:
            problems.append('R4 duplicate statement across ' + ', '.join(identifiers))
    return sorted(set(problems))
