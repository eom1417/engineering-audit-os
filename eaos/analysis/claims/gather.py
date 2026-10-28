"""The dossier's claims (eaos/analysis/understanding/dossier.py assembles the dossier around them): gathered from the facts, the load
model and the legacy records, merged, withheld under a detector's measured bar, numbered, each with its origin
(product, test or archived code) and a disposition when it asserts a problem; and the claims execution evidence makes.
"""
from pathlib import Path

from . import ledger
from .from_records import from_legacy, from_load_model

# Every live claim is an item of the debt register, the one record that shows it in full (rule R4).
REGISTER = 'debt-register.json'


def runtime_claims(verification, offset, coverage_facts=None, excluded=None):
    """Execution evidence produces claims that are CONFIRMED because something actually ran."""
    if not verification or not verification.get('executed'): return []
    rows = []
    by_path = {fact['location']['path']: fact['id'] for fact in coverage_facts or []}
    uncovered = [path for path in verification.get('uncovered_entry_reachable_files', [])
                 if not (excluded and excluded(path))]
    if uncovered: rows.append(_untested(offset + 1, uncovered, by_path))
    return rows


def _untested(index, uncovered, by_path):
    """The claim that files an entry point reaches were never executed by the test command."""
    return ledger.make(index,
                       f"{len(uncovered)} files reachable from an entry point were never executed by the test command "
                       f"({', '.join(uncovered[:3])}{'…' if len(uncovered) > 3 else ''})",
                       'risk', 'CONFIRMED', ['test_evidence'], [],
                       'A test run that executes those files, or evidence that they are not reachable in production either.',
                       fact_ids=sorted({by_path[path] for path in uncovered if path in by_path}),
                       render={'key': 'untested', 'params': {'count': len(uncovered)}},
                       impact={'scenario': 'A change in these files can ship without any test exercising it.'},
                       disposition={'kind': 'investigate', 'reason': 'Decide whether each path needs a test or is genuinely dead.'})


PROBLEM_TYPES = {'risk', 'cause', 'business_rule', 'structure', 'capability_gap'}


def needs_a_disposition(claim):
    """Anything that states a consequence, and anything not yet established, has to end somewhere:
    a task, a documented acceptance, or an open investigation."""
    return (claim['claim_type'] in PROBLEM_TYPES
            or bool((claim.get('impact') or {}).get('scenario'))
            or claim.get('confidence') in {'HYPOTHESIS', 'LIKELY'})


def asserts_a_problem(claim):
    return needs_a_disposition(claim)


ARCHIVE_PARTS = {'archive', 'archived', 'attic', '_archive'}


def archived(path):
    """Code the project set aside in an archive folder: kept for reference, not part of the running product."""
    return bool({part.lower() for part in Path(path).parts[:-1]} & ARCHIVE_PARTS)


def _located(claim, fact_index):
    """The paths of a claim's facts: each fact's own, then the several a fact covers."""
    paths = [fact_index[fact_id] for fact_id in claim.get('fact_ids', []) if fact_id in fact_index]
    extra = []
    for fact_id in claim.get('fact_ids', []):
        extra += fact_index.get(fact_id + ':paths', [])
    return [path for path in paths + extra if path]


def origin_of(claim, fact_index):
    """Whether a claim is about product code, test and fixture code, or archived code; a reader must not confuse them."""
    from ...core.contracts.vocabulary import classify
    located = _located(claim, fact_index)
    if located and all(archived(path) for path in located): return 'archive'
    categories = {classify(path) for path in located if not archived(path)}
    if not categories: return 'unknown'
    if categories == {'test'}: return 'test'
    return 'test_and_source' if 'test' in categories else 'source'


def fact_index_of(sets):
    """Where each fact lives, including the several paths a single fact can cover."""
    index = {}
    for data in sets.values():
        for fact in data['facts']:
            index[fact['id']] = fact['location'].get('path')
            paths = _covered(fact.get('value') if isinstance(fact.get('value'), dict) else {})
            if paths: index[fact['id'] + ':paths'] = paths
    return index


def _covered(value):
    """The several paths one fact covers (a rule's definitions, a cycle's or a UI pattern's members, a cluster's occurrences,
    a near copy's other side), else None."""
    paths = None
    definitions = value.get('definitions')
    if definitions: paths = [row['path'] for row in definitions]
    members = value.get('members')
    if members: paths = [row['path'] if isinstance(row, dict) else row for row in members]       # a cycle's, a UI pattern's
    other = value.get('other')
    if isinstance(other, dict) and other.get('path'): paths = [other['path']]                       # a near copy's other side
    # A cluster spans several files; without them the claim looks like it names none.
    occurrences = value.get('occurrences')
    if isinstance(occurrences, list) and occurrences and isinstance(occurrences[0], dict):
        paths = sorted({row['path'] for row in occurrences if row.get('path')}) or paths
    return paths


def _gathered_claims(sets, records, load_record, target):
    """Every claim before merging: from the facts, the load model and the legacy records."""
    rows = ledger.from_facts(sets, target=target)
    if load_record:
        rows += from_load_model({'load_model': load_record}, len(rows))
    if records['findings'] or records['architecture']:
        rows += from_legacy(records['findings'], records['architecture'] or {}, records['flows'],
                                   records['coverage'], (records['state'] or {}).get('revision'))
    return rows


def _settle_claim(row, fact_index):
    """A numbered claim's origin, the artifact that shows it, and a disposition when it asserts a problem."""
    row['origin'] = origin_of(row, fact_index)
    row.setdefault('artifacts', [REGISTER])
    if asserts_a_problem(row) and (row.get('disposition') or {}).get('kind') in (None, 'none_yet'):
        row['disposition'] = {'kind': 'investigate', 'reason': 'Ranked for review; no owner assigned yet in this run.'}


def _assess_mechanically(rows, sets, target):
    from ..assessments.mechanical import build_assessment as mechanical
    for row in rows:
        built = mechanical(row, sets, target)
        if built: row['assessment'], row['checks'] = built['assessment'], built['checks']


def build_claims(sets, records, load_record=None, target=None):
    rows = _gathered_claims(sets, records, load_record, target)
    fact_index = fact_index_of(sets)
    # A claim from a detector under its measured precision bar is set aside before numbering: it is never
    # shown, planned or counted, and the precision set (tools/precision.py) still reads it.
    rows, withheld = ledger.withhold(ledger.merge(rows))
    rows = ledger.renumber(rows)
    for number, row in enumerate(withheld, start=1): row['id'] = 'WHD-%03d' % number
    for row in rows: _settle_claim(row, fact_index)
    # After numbering and origin are settled: a confirmed product observation whose evidence is mechanical
    # carries a ready repair under its family's engagement rule (eaos/analysis/assessments/mechanical.py).
    if target is not None: _assess_mechanically(rows, sets, target)
    return rows, fact_index, withheld
