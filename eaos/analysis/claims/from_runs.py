"""The claims that read what the runs of the copy left beside the code (made after the facts' claims, numbered after
them, eaos/analysis/understanding/dossier.py): old engines and code never run (M13), how the data is saved and kept
(M14)."""
from .from_keeping import keeping_claims
from .from_old_engines import old_engine_claims


def run_claims(out, sets, target, offset):
    rows = old_engine_claims(out, sets, target, offset)
    return rows + keeping_claims(out, sets, target, offset + len(rows))
