"""Measure how much of the intended product exists, from real reports.

Usage:  python tools/capability_score.py <report-dir> [<report-dir> ...] [--write]

Every number comes from the reports given. A domain whose evidence is missing is reported as
unmeasured, and an unmeasured domain never meets its target.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))


def environment():
    """The facts about this repository that no single report carries."""
    from invariants import check, extract, load_register, merge
    register = merge(extract(), load_register())
    unenforced = check(register)
    tests = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-q'],
                           cwd=ROOT, capture_output=True, text=True)
    owners = subprocess.run([sys.executable, '-m', 'unittest',
                             'tests.test_artifact_contract.SingleWriterTests', '-q'],
                            cwd=ROOT, capture_output=True, text=True)
    evidence = ROOT / 'evaluations/release-evidence.json'
    return {
        'invariants_enforced': round(1 - len(unenforced) / max(1, len(register['invariants'])), 4),
        'tests_pass': float(tests.returncode == 0),
        'one_artifact_one_owner': float(owners.returncode == 0),
        'release_evidence': json.loads(evidence.read_text(encoding='utf-8')) if evidence.is_file() else None,
    }


def render(card):
    lines = ['# Capability scorecard', '',
             f"> Measured from {len(card['reports'])} report(s). An unmeasured indicator is not a pass. "
             f"Target for every domain: {card['target']}.", '',
             f"**Overall {card['overall']}** · {card['domains_meeting_target']} of "
             f"{card['domains_total']} domains at target.", '',
             '| Domain | Score | Target | Met | Unmeasured |', '| --- | --- | --- | --- | --- |']
    for name, row in card['domains'].items():
        lines.append(f"| {name} | {row['score']} | {row['target']} | "
                     f"{'yes' if row['meets_target'] else 'no'} | {row['unmeasured_indicators']} |")
    for name, row in card['domains'].items():
        lines += ['', f'## {name}', '', '| Indicator | Value |', '| --- | --- |']
        for key, value in row['indicators'].items():
            lines.append(f"| {key} | {'unmeasured' if value is None else value} |")
    lines += ['', '## Limits', ''] + [f'- {line}' for line in card['limitations']]
    return '\n'.join(lines) + '\n'


def main(argv):
    from eaos.capability import score
    reports = [Path(item) for item in argv if not item.startswith('--')]
    if not reports:
        print(__doc__, file=sys.stderr)
        return 2
    missing = [report for report in reports if not (report / 'dossier.json').is_file()]
    if missing:
        print(f'not a report directory: {missing}', file=sys.stderr)
        return 2
    card = score(reports, environment())
    if '--write' in argv:
        (ROOT / 'docs/capability-score.json').write_text(
            json.dumps(card, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (ROOT / 'docs/CAPABILITY-SCORE.md').write_text(render(card), encoding='utf-8')
    print(json.dumps({'overall': card['overall'],
                      'domains': {name: row['score'] for name, row in card['domains'].items()},
                      'at_target': card['domains_meeting_target'], 'of': card['domains_total']},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
