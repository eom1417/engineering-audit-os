"""The output contract: rules a rendered dossier must satisfy before anyone is asked to read it."""
from pathlib import Path
import re

from .artifacts import BY_NAME, BUDGETS, DOCUMENT
from ...core.system.files import read_json

# One source for what may be produced and how long it may be; rules.py used to keep its own list,
# and sixteen documents were outside it and therefore never checked at all.
CLAIM_REFERENCE = re.compile(r'\bCLM-\d{3,}\b')


def rendered(out):
    """Every markdown document in the report, declared or not. An undeclared one is R13's business."""
    paths = list(Path(out).glob('*.md')) + list((Path(out) / 'PLAN').glob('*.md'))
    return {p.relative_to(out).as_posix(): p.read_text(encoding='utf-8') for p in sorted(paths)}


def validate(out, dossier):
    """Return a list of rule violations; an empty list means the output may be published."""
    documents = rendered(out)
    known = {claim['id'] for claim in dossier.get('claims', [])}
    claims = dossier.get('claims', [])
    problems = []
    for name, text in sorted(documents.items()): problems += _document_rules(name, text, known)
    if 'README.md' not in documents:
        problems.append('R12 README.md: the dossier has no index or reading order')
    problems += missing_required(out, documents)
    problems += documents_without_a_record_twin()
    problems += [f"R5 {claim['id']}: a live risk needs a task or a documented acceptance" for claim in claims if _undecided_risk(claim)]
    for task in dossier.get('tasks', []): problems += _task_rules(task)
    problems += [f"R11 {claim['id']}: priority without the inputs it was computed from"
                 for claim in claims if 'priority' in claim and not claim.get('priority_factors')]
    problems += _duplicate_rules(claims)
    return sorted(set(problems))


def _document_rules(name, text, known):
    """R2, R13, R8 and R1 on one rendered document."""
    problems = []
    lines = text.count('\n')
    if lines > BUDGETS.get(name, 200):
        problems.append(f'R2 {name}: {lines} lines exceeds the budget of {BUDGETS.get(name, 200)}')
    if name not in BY_NAME and not name.startswith('PLAN/'):
        problems.append(f'R13 {name}: produced but not declared in the artifact contract, '
                        f'so no stage owns it and no budget applies')
    if '```json' in text:
        problems.append(f'R8 {name}: raw record dump in a human artifact')
    problems += [f'R1 {name}: references {reference}, which is absent from the ledger'
                 for reference in sorted(set(CLAIM_REFERENCE.findall(text))) if reference not in known]
    return problems


PROBLEM_TYPES = {'risk', 'cause', 'business_rule', 'structure', 'capability_gap'}


def _undecided_risk(claim):
    """R5: a live claim that states a problem and has no disposition yet."""
    states_a_problem = (claim.get('claim_type') in PROBLEM_TYPES
                        or bool((claim.get('impact') or {}).get('scenario'))
                        or claim.get('confidence') in {'HYPOTHESIS', 'LIKELY'})
    return (states_a_problem and claim.get('confidence') != 'REFUTED'
            and (claim.get('disposition') or {}).get('kind') in (None, 'none_yet'))


def _task_rules(task):
    """R7 on one task: a typed, checkable decision, or a runnable acceptance command for an older task."""
    if task.get('contract_version') != 1:
        return [] if task.get('verify_command') else [f"R7 {task.get('id', '?')}: the acceptance criterion is not a runnable command"]
    problems = []
    decision = task.get('decision') or {}
    if decision.get('kind') not in {'repair', 'investigate', 'retain'}:
        problems.append(f"R7 {task.get('id', '?')}: missing typed decision")
    if decision.get('readiness') == 'ready' and (not decision.get('checks') or decision.get('blockers')):
        problems.append(f"R7 {task.get('id', '?')}: ready task lacks checks or has blockers")
    return problems


def _duplicate_rules(claims):
    """R4: a claim shown in full in one artifact only, and no statement made twice."""
    import json
    problems, seen = [], {}
    for claim in claims:
        artifacts = claim.get('artifacts') or []
        if len(artifacts) > 1:
            problems.append(f"R4 {claim['id']}: presented in full in more than one artifact ({', '.join(artifacts)})")
        seen.setdefault((claim.get('statement'), json.dumps(claim.get('probe_spec') or {}, sort_keys=True)), []).append(claim['id'])
    problems += ['R4 duplicate statement across ' + ', '.join(identifiers)
                 for _, identifiers in sorted(seen.items()) if len(identifiers) > 1]
    return problems


def missing_required(out, documents):
    """R13: a required artifact that is absent must be explained by the run manifest, not by silence.

    With no manifest there was no pipeline run — a single command wrote part of a report — and we
    cannot call an artifact missing when nothing claimed it would be produced.
    """
    manifest_path = Path(out) / 'run-manifest.json'
    if not manifest_path.is_file():
        return []
    manifest = read_json(manifest_path)
    if manifest is None: return []
    manifest = manifest.get('stages', {})
    found = [f"R13 {artifact.name}: required, absent, and stage '{artifact.owner}' "
             f"does not explain it (status {(manifest.get(artifact.owner) or {}).get('status') or 'unknown'})"
             for artifact in BY_NAME.values() if not _explained(artifact, out, documents, manifest)]
    return sorted(found)


def _explained(artifact, out, documents, manifest):
    """True when the artifact is not required, is there, or its stage's status says why it is not."""
    if not artifact.required or not artifact.checked or (Path(out) / artifact.name).exists(): return True
    if artifact.kind == DOCUMENT and artifact.name in documents: return True
    return (manifest.get(artifact.owner) or {}).get('status') in ('skipped', 'unavailable', 'failed', 'not_reached')


def documents_without_a_record_twin():
    """R14: a model reads the record, a person reads the document, and both come from one source.

    A document with no machine-readable twin is a dead end for anything that has to act on what it
    says: the reader can see the conclusion and cannot reach the detail behind it. Some documents
    genuinely have no separate twin because they render the fact store directly, and those say so.
    Silence is the only answer this rule refuses.
    """
    found = []
    for artifact in BY_NAME.values():
        if artifact.kind != DOCUMENT:
            continue
        if artifact.record or artifact.record_absent_because:
            continue
        found.append(f'R14 {artifact.name}: a document with no record twin and no reason given; '
                     f'set `record=` to its machine-readable source or `record_absent_because=`')
    return sorted(found)
