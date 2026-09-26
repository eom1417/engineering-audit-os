"""The four reports judged by writing tools, the way code is judged by linters: report-quality.json.

Vale runs the EAOS style (eaos/rules/vale: vague wording in Arabic and English is an error), and
markdownlint-cli2 runs the structure every report follows (eaos/rules/.markdownlint-cli2.jsonc). A report
passes when both count zero errors. A tool that is not installed, or did not produce a readable result,
is recorded as null: never 0, because an unrun check is not a pass.
"""
import json
import re
from pathlib import Path

from .engines.process import run, which

NAMES = ('CURRENT-STATE.md', 'TARGET-STATE.md', 'GAP-AND-STRATEGY.md', 'EXECUTION-PLAN.md')
RULES = Path(__file__).resolve().parent / 'rules'
VALE_CONFIG = RULES / 'vale/.vale.ini'
MARKDOWNLINT_CONFIG = RULES / '.markdownlint-cli2.jsonc'
SUMMARY = re.compile(r'Summary: (\d+) (?:issue|error)')


def tools_path():
    from .toolchain import home
    import os
    return str(home() / 'bin') + os.pathsep + os.environ.get('PATH', '')


def vale_errors(out, name):
    """EAOS.* alerts at error level, or None when Vale is absent or its output cannot be read."""
    binary = which('vale')
    if not binary: return None
    code, stdout, _, _ = run([binary, '--config', str(VALE_CONFIG), '--output', 'JSON', name], cwd=out)
    try: alerts = [alert for rows in json.loads(stdout or '{}').values() for alert in rows]
    except ValueError: return None
    if code not in (0, 1) and not alerts: return None
    return sum(alert.get('Severity') == 'error' and str(alert.get('Check', '')).startswith('EAOS.') for alert in alerts)


def markdownlint_errors(out, name):
    """The issue count markdownlint-cli2 reports, or None when it is absent or printed no summary."""
    binary = which('markdownlint-cli2')
    if not binary: return None
    _, stdout, stderr, _ = run([binary, '--config', str(MARKDOWNLINT_CONFIG), name], cwd=out, env={'PATH': tools_path()})
    found = SUMMARY.search(stdout + stderr)
    return int(found.group(1)) if found else None


def check(out):
    """report-quality.json for the four reports present in out; a missing report is not listed."""
    out = Path(out)
    reports = [{'name': name, 'vale_errors': vale_errors(out, name), 'markdownlint_errors': markdownlint_errors(out, name)}
               for name in NAMES if (out / name).is_file()]
    record = {'schema_version': 1, 'reports': reports,
              'passing': sum(r['vale_errors'] == 0 and r['markdownlint_errors'] == 0 for r in reports),
              'tools': {'vale': bool(which('vale')), 'markdownlint-cli2': bool(which('markdownlint-cli2'))}}
    (out / 'report-quality.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return record
