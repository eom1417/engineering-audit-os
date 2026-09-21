"""The output contract: rules a rendered dossier must satisfy before anyone is asked to read it."""
from pathlib import Path
import re

from .artifacts import BY_NAME, BUDGETS, DOCUMENT

# One source for what may be produced and how long it may be; rules.py used to keep its own list,
# and sixteen documents were outside it and therefore never checked at all.
HUMAN_ARTIFACTS = set(BUDGETS)
CLAIM_REFERENCE = re.compile(r'\bCLM-\d{3,}\b')
MARKERS = {'⬤', '◐', '○', '؟'}
COVERAGE_MARKERS = ('التغطية', 'Coverage')
GAP_MARKERS = ('ما لم يُفحص', 'Not examined')


def rendered(out):
    """Every markdown document in the report, declared or not. An undeclared one is R13's business."""
    paths = list(Path(out).glob('*.md')) + list((Path(out) / 'PLAN').glob('*.md'))
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
        if name not in BY_NAME and not name.startswith('PLAN/'):
            problems.append(f'R13 {name}: produced but not declared in the artifact contract, '
                            f'so no stage owns it and no budget applies')
        if '```json' in text:
            problems.append(f'R8 {name}: raw record dump in a human artifact')
        for reference in sorted(set(CLAIM_REFERENCE.findall(text))):
            if reference not in known:
                problems.append(f'R1 {name}: references {reference}, which is absent from the ledger')
    if 'README.md' not in documents:
        problems.append('R12 README.md: the dossier has no index or reading order')
    problems += missing_required(out, documents)
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


def missing_required(out, documents):
    """R13: a required artifact that is absent must be explained by the run manifest, not by silence.

    With no manifest there was no pipeline run — a single command wrote part of a report — and we
    cannot call an artifact missing when nothing claimed it would be produced.
    """
    import json
    manifest_path = Path(out) / 'run-manifest.json'
    if not manifest_path.is_file():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8')).get('stages', {})
    except ValueError:
        return []
    found = []
    for artifact in BY_NAME.values():
        if not artifact.required or not artifact.checked or (Path(out) / artifact.name).exists():
            continue
        if artifact.kind == DOCUMENT and artifact.name in documents:
            continue
        status = (manifest.get(artifact.owner) or {}).get('status')
        if status in ('skipped', 'unavailable', 'failed', 'not_reached'):
            continue
        found.append(f"R13 {artifact.name}: required, absent, and stage '{artifact.owner}' "
                     f"does not explain it (status {status or 'unknown'})")
    return sorted(found)
