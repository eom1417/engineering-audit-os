"""Record an explicit engineering assessment without rewriting historical records."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
from .decisions import check_errors, decide
from .workspace import read, write


def apply(out, review, language='ar'):
    out = Path(out)
    dossier = read(out / 'dossier.json')
    claim = next((row for row in dossier['claims'] if row['id'] == review.get('claim_id')), None)
    if claim is None: raise ValueError('Unknown claim for review')
    known = set()
    for path in (out / 'facts').glob('*.json'):
        for row in read(path).get('facts', []):
            known.add(row['id'])
            if row.get('kind') in {'source_file', 'source_document'}:
                from .workspace import safe_file, digest
                raw = safe_file(Path(dossier['provenance']['target']), row['location']['path']).read_bytes()
                if digest(raw) != row['input_sha']: raise ValueError('Source changed since evidence capture')
    if (out / 'semantic-context/evidence.json').is_file():
        known.update(row['id'] for row in read(out / 'semantic-context/evidence.json'))
    if review.get('outcome') in {'retain', 'blocked_missing_requirement'}:
        if not review.get('reviewed_by') or not review.get('reason'):
            raise ValueError('A no-change or blocked decision requires a reviewer and reason')
        before = copy.deepcopy(claim)
        claim['disposition'] = {'kind': 'accepted' if review['outcome'] == 'retain' else 'investigate',
                                'owner': review['reviewed_by'], 'reason': review['reason']}
        if review['outcome'] == 'blocked_missing_requirement':
            claim.pop('assessment', None)
            claim.pop('checks', None)
        return persist(out, dossier, before, claim, decide(claim), language)
    assessment = review.get('assessment')
    if not isinstance(assessment, dict): raise ValueError('assessment must be an object')
    for field in ('reviewed_by', 'violated_invariant', 'before', 'after', 'proposed_change'):
        if not isinstance(assessment.get(field), str) or not assessment[field].strip():
            raise ValueError('Review missing ' + field)
    for field in ('requirement_refs', 'evidence_refs'):
        refs = assessment.get(field)
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in known for ref in refs):
            raise ValueError('Review requires known ' + field)
    checks = review.get('checks', [])
    if not isinstance(checks, list): raise ValueError('checks must be an array')
    for check in checks:
        errors = check_errors(check)
        if errors: raise ValueError('; '.join(errors))
    if checks:
        from .acceptance import fingerprint
        current = fingerprint(dossier['provenance']['target'])
        if any(check['source_revision'] != current for check in checks):
            raise ValueError('Check is not bound to the current candidate revision')
    before = copy.deepcopy(claim)
    claim['assessment'], claim['checks'] = assessment, checks
    decision = decide(claim)
    return persist(out, dossier, before, claim, decision, language)


def persist(out, dossier, before, claim, decision, language):
    # Reject invalid plans before publishing the review event or modified ledger.
    from .plan import build_tasks, waves
    from .impact import load
    waves(build_tasks(Path(dossier['provenance']['target']), out, dossier, load(out)))
    event = {'schema_version': 1, 'recorded_at': datetime.now(timezone.utc).isoformat(),
             'source_snapshot': dossier['provenance']['snapshot_fingerprint'],
             'before': before, 'after': copy.deepcopy(claim), 'decision': decision}
    event_id = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
    (out / 'decision-history').mkdir(exist_ok=True)
    write(out / 'decision-history' / (event_id + '.json'), event)
    write(out / 'dossier.json', dossier)
    from .plan import build
    build(dossier['provenance']['target'], out, language)
    return {'event_id': event_id, 'decision': decision, 'note': 'Reviewer assertion recorded; review is not an executed check.'}
