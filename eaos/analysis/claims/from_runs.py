"""The claims that read what the runs of the copy left beside the code (made after the facts' claims, numbered after
them, eaos/analysis/understanding/dossier.py): old engines and code never run (M13) and one source per pattern (M15)."""
from .from_old_engines import old_engine_claims
from .from_one_source import one_source_claims


def run_claims(out, sets, target, offset):
    rows = old_engine_claims(out, sets, target, offset)
    return rows + one_source_claims(out, sets, target, offset + len(rows))
