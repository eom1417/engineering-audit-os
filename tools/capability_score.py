"""Measure how much of the intended product exists, from real reports.

Usage:  python tools/capability_score.py <report-dir> [<report-dir> ...] [--write]

Every number comes from the reports given. A domain whose evidence is missing is reported as
unmeasured, and an unmeasured domain never meets its target.

`--write` also raises the high-water mark in docs/capability-high-water.json, and never lowers
it. The no-regression gate compares against that file rather than against the scorecard, because
the scorecard is overwritten by every remeasurement: comparing a run to a record it just wrote is
not a comparison, and a real fall from 0.9788 to 0.6667 passed through it unremarked.
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


HIGH_WATER = 'docs/capability-high-water.json'


def raise_high_water(card, path=None):
    """Record the best each domain has ever measured. A mark goes up or stays; it never comes down.

    The commit that reached a level is stored beside it, so a regression can be read back to the
    run that set the bar rather than to an anonymous number.
    """
    path = Path(path) if path else ROOT / HIGH_WATER
    previous = {}
    if path.is_file():
        try: previous = json.loads(path.read_text(encoding='utf-8'))
        except ValueError: previous = {}
    domains = dict(previous.get('domains') or {})
    commits = dict(previous.get('reached_at') or {})
    head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip() or 'unknown'
    raised = []
    for name, row in card['domains'].items():
        value = row['score']
        if value is None: continue
        if name not in domains or value > domains[name]:
            if name in domains: raised.append(f"{name}: {domains[name]} -> {value}")
            domains[name], commits[name] = value, head
    record = {'schema_version': 1, 'note': 'The best each domain has measured. Written only upward.',
              'domains': dict(sorted(domains.items())), 'reached_at': dict(sorted(commits.items()))}
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return raised


def engines_were_off(reports):
    """Report directories whose engines stage says nobody asked for the engines.

    The whole product is an argument for using these four engines. Judging it with them switched
    off measures a different tool, so a scorecard built on such a report is refused rather than
    quietly printed.
    """
    off = []
    for report in reports:
        manifest = Path(report) / 'run-manifest.json'
        if not manifest.is_file(): continue
        try: stages = json.loads(manifest.read_text(encoding='utf-8')).get('stages') or {}
        except ValueError: continue
        stage = stages.get('engines')
        if isinstance(stage, dict) and stage.get('status') == 'unavailable' \
           and 'not requested' in (stage.get('reason') or ''):
            off.append(str(report))
    return off


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
    off = engines_were_off(reports)
    if off and '--allow-engines-off' not in argv:
        print(f'refusing to score reports produced without the engines: {off}\n'
              f'rerun the audit with --engines codegraph enola jscpd reforge, '
              f'or pass --allow-engines-off to record a partial measurement deliberately',
              file=sys.stderr)
        return 2
    card = score(reports, environment())
    if '--write' in argv:
        for line in raise_high_water(card):
            print('  high-water raised ' + line, file=sys.stderr)
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
