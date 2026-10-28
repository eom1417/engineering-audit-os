"""Recheck one observation on a changed copy: collect the facts again and let the claim's own probe decide.

`python -m eaos recheck --spec '<probe json>' [ROOT]` is the acceptance command of a mechanical repair card.
It runs in the candidate copy (ROOT, default the working directory), collects the facts into a private
directory (and the load model, when the probe reads it; the engines the probe names, when it names them, so a
security finding is asked of the same engines again), and applies eaos.analysis.claims.probes.decide_probe, the same function the
audit's probe stage uses. Exit 0: REFUTED, the observation is gone. Exit 1: it is still there.
Exit 2: the probe could not decide, which is never a pass.
"""
import json
import tempfile
from pathlib import Path


def _load_model(root, out, specification):
    from ..readiness.load_model import compute
    from ..readiness.load_projection import project
    return {'load_model': project(compute(out))}


def _boundaries(root, out, specification):
    from ..layers import check, facts_of
    return {'boundaries': {'facts': facts_of(check(Path(root).resolve(), out))}}


def _logic_flaws(root, out, specification):
    from .from_logic_flaws import reread
    return {'logic_flaws': reread(root, specification)}            # the code read again, never an old hunt


def _rule(root, out, specification):
    from ..rules import guards
    return {'rule': guards.run(specification['guard'], Path(root).resolve())}     # the person's rule's own guard (M16)


# What a probe reads beside the collected facts, made again on the copy: {query: (root, out, specification) -> sets}.
MORE = {'load_blocker_present': _load_model, 'boundary_finding_present': _boundaries, 'logic_flaw_present': _logic_flaws,
        'rule_broken': _rule}


def recheck(root, spec):
    from ...facts.run import collect, read_available
    from .probes import decide_probe
    specification = spec.get('specification') or {}
    with tempfile.TemporaryDirectory(prefix='eaos-recheck-') as scratch:
        out = Path(scratch)
        # No engine named (a branch count, EAOS's own) runs none: an empty list would ask for every engine.
        collect(Path(root).resolve(), out, engines=specification.get('engines') or None)
        sets = read_available(out)
        for name, made in (MORE[specification['query']](root, out, specification) if specification.get('query') in MORE else {}).items():
            sets[name] = made
        return decide_probe(spec, sets)


def main(args):
    spec = json.loads(args.spec)
    status, detail = recheck(args.root, spec)
    print(f'{status}: {detail}')
    return 0 if status == 'REFUTED' else 1 if status in ('CONFIRMED', 'PARTIAL') else 2
