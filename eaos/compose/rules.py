"""The output contract: rules a rendered dossier must satisfy before anyone is asked to read it."""
from pathlib import Path
import re

BUDGETS = {'DECISION-BRIEF.md': 120, 'SYSTEM-MAP.md': 260, 'COUPLING-ATLAS.md': 220, 'EVOLUTION.md': 220,
           'PROVENANCE.md': 80, 'FLOWS.md': 300, 'DOMAIN-AND-DATA.md': 240, 'CONTRACTS.md': 200,
           'RISK-REGISTER.md': 200, 'VERIFICATION-MAP.md': 180, 'DELTA.md': 160, 'README.md': 120,
           'ONBOARDING.md': 200, 'POLICY.md': 160}
HUMAN_ARTIFACTS = set(BUDGETS)
CLAIM_REFERENCE = re.compile(r'\bCLM-\d{3,}\b')
MARKERS = {'⬤', '◐', '○', '؟'}
COVERAGE_MARKERS = ('التغطية', 'Coverage')
GAP_MARKERS = ('ما لم يُفحص', 'Not examined')


def rendered(out):
    paths = [p for p in Path(out).glob('*.md') if p.name in HUMAN_ARTIFACTS or p.name == 'SEMANTIC.md']
    paths += list((Path(out) / 'PLAN').glob('*.md'))
    return {p.relative_to(out).as_posix(): p.read_text(encoding='utf-8') for p in sorted(paths)}


def validate(out, dossier):
    """Return a list of rule violations; an empty list means the output may be published."""
    documents = rendered(out)
    known = {claim['id'] for claim in dossier.get('claims', [])}
    problems = []
    for name, text in sorted(documents.items()):
        lines = text.count('\n')
        if lines > BUDGETS.get(name, 200):
            problems.append(f'R2 {name}: {lines} lines exceeds the budget of {BUDGETS.get(name, 200)}')
        if '```json' in text:
            problems.append(f'R8 {name}: raw record dump in a human artifact')
        for reference in sorted(set(CLAIM_REFERENCE.findall(text))):
            if reference not in known:
                problems.append(f'R1 {name}: references {reference}, which is absent from the ledger')
    if 'README.md' not in documents:
        problems.append('R12 README.md: the dossier has no index or reading order')
    for name, text in sorted(documents.items()):
        if name in {'README.md', 'PROVENANCE.md'}: continue
        # A brief with nothing to report has nothing to link to; the rule applies when claims exist.
        if name == 'DECISION-BRIEF.md' and dossier.get('claims') and '](' not in text:
            problems.append('R12 DECISION-BRIEF.md: no cross-reference to the artifact holding the detail')
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
        states_a_problem = (claim.get('claim_type') in problem_types
                            or bool((claim.get('impact') or {}).get('scenario'))
                            or claim.get('confidence') in {'HYPOTHESIS', 'LIKELY'})
        if states_a_problem and claim.get('confidence') != 'REFUTED':
            disposition = (claim.get('disposition') or {}).get('kind')
            if disposition in (None, 'none_yet'):
                problems.append(f"R5 {claim['id']}: a live risk needs a task or a documented acceptance")
    for task in dossier.get('tasks', []):
        if task.get('contract_version') == 1:
            decision = task.get('decision') or {}
            if decision.get('kind') not in {'repair', 'investigate', 'retain'}:
                problems.append(f"R7 {task.get('id', '?')}: missing typed decision")
            if decision.get('readiness') == 'ready' and (not decision.get('checks') or decision.get('blockers')):
                problems.append(f"R7 {task.get('id', '?')}: ready task lacks checks or has blockers")
        elif not task.get('verify_command'):
            problems.append(f"R7 {task.get('id', '?')}: the acceptance criterion is not a runnable command")
    for claim in dossier.get('claims', []):
        if 'priority' in claim and not claim.get('priority_factors'):
            problems.append(f"R11 {claim['id']}: priority without the inputs it was computed from")
    seen = {}
    for claim in dossier.get('claims', []):
        artifacts = claim.get('artifacts') or []
        if len(artifacts) > 1:
            problems.append(f"R4 {claim['id']}: presented in full in more than one artifact ({', '.join(artifacts)})")
        import json
        seen.setdefault((claim.get('statement'), json.dumps(claim.get('probe_spec') or {}, sort_keys=True)), []).append(claim['id'])
    for statement, identifiers in sorted(seen.items()):
        if len(identifiers) > 1:
            problems.append('R4 duplicate statement across ' + ', '.join(identifiers))
    return sorted(set(problems))
