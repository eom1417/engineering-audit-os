"""How much of what each detector shows is true: judged labels in, eaos/data/detector-verdicts.json out.

The labels stay out of the published tree, in $EAOS_LABELS (default ../eaos-private/labels), one file per detector,
`<detector>.jsonl` (`:` written `__`), one judged output a line: {"project", "place", "true": bool, "why"}, and for what was
planted {"project", "place", "planted": true, "found": bool}. A judge reads the code and the output, blind to the detector's
score: another kind of model than the one that wrote the detector, and the owner samples five of each.

    python tools/judging/precision.py sample <report> <detector>   # the outputs of a check to judge, as label lines without a verdict
    python tools/judging/precision.py score [--write]              # precision, recall and how many were judged, per detector

A detector with labels is shown only above the bar (a detector of the look, `DESIGN`, needs more judged than an older one); one
without labels keeps the verdict it has. A verdict without labels behind it is never written.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
VERDICTS = ROOT / 'eaos' / 'data' / 'detector-verdicts.json'
LABELS = Path(os.environ.get('EAOS_LABELS') or ROOT.parent / 'eaos-private' / 'labels')
DESIGN, DESIGN_JUDGED = ('design:', 'one_source:'), 20


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def measured(rows):
    """{judged, precision, recall}: recall None when nothing was planted."""
    judged = [row for row in rows if 'true' in row]
    planted = [row for row in rows if row.get('planted')]
    return {'judged': len(judged), 'precision': round(sum(row['true'] for row in judged) / len(judged), 3) if judged else None,
            'recall': round(sum(bool(row.get('found')) for row in planted) / len(planted), 3) if planted else None}


def why_hidden(detector, score, bar):
    """Why this score does not pass, or None."""
    needed = DESIGN_JUDGED if detector.startswith(DESIGN) else bar['judged']
    if score['judged'] < needed: return f"only {score['judged']} judged outputs (bar {needed})"
    if score['precision'] < bar['precision']: return f"precision {score['precision']} < {bar['precision']} on {score['judged']} judged outputs"
    if score['recall'] is not None and score['recall'] < bar['recall']: return f"recall {score['recall']} < {bar['recall']}"
    return None


def apply(verdicts, scores):
    """The verdicts with each scored detector moved to where its score puts it; the others as they were."""
    hidden, shown = dict(verdicts['hidden']), set(verdicts['shown'])
    for detector, score in scores.items():
        why = why_hidden(detector, score, verdicts['bar'])
        hidden.pop(detector, None)
        shown.discard(detector)
        if why: hidden[detector] = why
        else: shown.add(detector)
    return {**verdicts, 'source': 'tools/judging/precision.py score --write', 'hidden': hidden, 'shown': sorted(shown)}


def score(folder=LABELS):
    return {path.stem.replace('__', ':'): measured(_rows(path)) for path in sorted(Path(folder).glob('*.jsonl'))}


def sample(report, detector):
    """A check's outputs of one detector, kept aside or shown, as lines for the judge to give a verdict."""
    from eaos.analysis.claims.ledger import detector_of
    dossier = json.loads((Path(report) / 'dossier.json').read_text(encoding='utf-8'))
    claims = [*(dossier.get('claims') or ()), *(dossier.get('withheld') or ())]
    return [{'project': Path(dossier.get('target') or report).name, 'claim': claim.get('id'), 'place': claim.get('statement', '')[:200]}
            for claim in claims if detector_of(claim) == detector]


def main(argv):
    if argv[:1] == ['sample']:
        for row in sample(argv[1], argv[2]): print(json.dumps(row, ensure_ascii=False))
    elif argv[:1] == ['score']:
        scores = score()
        for detector, row in scores.items(): print(detector, row)
        if '--write' in argv and scores:
            VERDICTS.write_text(json.dumps(apply(json.loads(VERDICTS.read_text(encoding='utf-8')), scores), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    else: raise SystemExit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
