"""Recheck one observation on a changed copy: collect the facts again and let the claim's own probe decide.

`python -m eaos recheck --spec '<probe json>' [ROOT]` is the acceptance command of a mechanical repair card.
It runs in the candidate copy (ROOT, default the working directory), collects the facts into a private
directory (and the load model, when the probe reads it; the engines the probe names, when it names them, so a
security finding is asked of the same engines again), and applies eaos.probes.decide_probe, the same function the
audit's probe stage uses. Exit 0: REFUTED, the observation is gone. Exit 1: it is still there.
Exit 2: the probe could not decide, which is never a pass.
"""
import json
import tempfile
from pathlib import Path


def recheck(root, spec):
    from .facts.run import collect, read_available
    from .probes import decide_probe
    with tempfile.TemporaryDirectory(prefix='eaos-recheck-') as scratch:
        out = Path(scratch)
        # No engine named (a branch count, EAOS's own) runs none: an empty list would ask for every engine.
        collect(Path(root).resolve(), out, engines=(spec.get('specification') or {}).get('engines') or None)
        sets = read_available(out)
        if (spec.get('specification') or {}).get('query') == 'load_blocker_present':
            from .load_model import compute, project
            sets['load_model'] = project(compute(out))
        return decide_probe(spec, sets)


def main(args):
    spec = json.loads(args.spec)
    status, detail = recheck(args.root, spec)
    print(f'{status}: {detail}')
    return 0 if status == 'REFUTED' else 1 if status in ('CONFIRMED', 'PARTIAL') else 2
