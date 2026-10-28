"""The claims that read what the runs of the copy left beside the code (made after the facts' claims, numbered after
them, eaos/analysis/understanding/dossier.py): old engines and code never run (M13), how the data is saved and kept
(M14), one source per pattern (M15: the look the pages showed beside the code's patterns)."""
from .from_keeping import keeping_claims
from .from_old_engines import old_engine_claims
from .from_one_source import one_source_claims


def run_claims(out, sets, target, offset):
    rows = old_engine_claims(out, sets, target, offset)
    rows += keeping_claims(out, sets, target, offset + len(rows))
    return rows + one_source_claims(out, sets, target, offset + len(rows))
