"""The claims the ledger sets aside: one breaking an epistemic rule (no evidence, an unknown fact) is kept out with its
reason and named in the report, and the others go on; one builder's slip does not stop the whole check."""
from .ledger import _claim_errors, detector_of


def set_aside(claims, evidence_ids=(), fact_ids=()):
    """(kept, set aside), each set-aside claim with its detector and the rules it breaks."""
    known, kept, aside = (set(evidence_ids), set(fact_ids)), [], []
    for claim in claims:
        problems = _claim_errors(claim, known)
        if not problems: kept.append(claim); continue
        aside.append({**claim, 'withheld': {'detector': detector_of(claim) or 'unknown', 'why': '; '.join(problems), 'rejected': True}})
    return kept, aside


def screen(rows, withheld, records, sets):
    """(rows, withheld): a dossier's claims with the unsound ones moved to its withheld list, numbered after it."""
    evidence = {e['id'] for e in records['evidence']} if records['evidence'] else ()
    rows, aside = set_aside(rows, evidence, {f['id'] for data in sets.values() for f in data['facts']})
    for number, row in enumerate(aside, start=len(withheld) + 1): row['id'] = 'WHD-%03d' % number
    return rows, withheld + aside
