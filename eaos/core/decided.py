"""Whether an investigation is finished: its observation carries a recorded decision in the report.

An investigation card changes no code; it ends when someone records what the evidence means (eaos
decision-review): a repair with its assessment and check, a retain with an owner and a reason, or the claim
refuted. `python -m eaos decided REPORT OBSERVATION_UID` exits 0 once the dossier holds such a decision for
that observation, and 1 while it is still open. It is the runnable acceptance of an investigation card.
"""
import json
from pathlib import Path


def status(report, uid):
    from .decisions import decide, identity
    dossier = json.loads((Path(report) / 'dossier.json').read_text(encoding='utf-8'))
    claim = next((c for c in dossier.get('claims') or [] if (c.get('uid') or identity(c)) == uid), None)
    if claim is None: return 'gone', 'the observation is no longer in the report'
    decision = decide(claim)
    if decision['kind'] == 'investigate': return 'open', decision['reason']
    return decision['kind'], decision['reason']


def main(args):
    state, reason = status(args.report, args.uid)
    print(f'{state}: {reason}')
    return 1 if state == 'open' else 0
