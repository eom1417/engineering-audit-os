"""jscpd: token-level clone detection over 224 formats, in a fifth of a second.

It scans exactly what it is given. Without the declared analysis exclusions it counted our own
report artifacts and reported 23.1% duplication where the source holds 1.85%; scope is our duty.
"""
import json
from pathlib import Path

from .contract import Capability, Report, OBSERVED, UNAVAILABLE, ERROR, finding, measurement, subject
from .process import run, which

NAME, BINARY, PINNED = 'jscpd', 'jscpd', '5.3.0'
ALWAYS_IGNORED = ('**/.git/**', '**/node_modules/**', '**/.venv/**', '**/dist/**', '**/build/**',
                  '**/__pycache__/**', '**/.enola/**')


def capabilities():
    return [Capability('literal_duplication', 'jscpd.exact_clone')]


def version():
    binary = which(BINARY)
    if not binary:
        return None
    code, out, _, _ = run([binary, '--version'], timeout=30)
    return out.strip().split()[-1] if code == 0 and out.strip() else None


def analyze(target, workdir, exclude=(), formats=None):
    found = version()
    if found is None:
        return Report(NAME, None, PINNED, UNAVAILABLE, reason='jscpd is not installed')
    workdir = Path(workdir) / 'jscpd'
    workdir.mkdir(parents=True, exist_ok=True)
    ignored = ','.join(ALWAYS_IGNORED + tuple(f'**/{pattern}/**' for pattern in exclude))
    command = [which(BINARY), str(target), '--reporters', 'json',
               '--output', str(workdir), '--ignore', ignored, '--silent']
    # Without a format list jscpd counts markdown and JSON as duplication: 28.98% here against 1.88%
    # over source. The caller owns the source vocabulary, so it passes it in.
    if formats:
        command += ['--format', ','.join(sorted(formats))]
    code, _, error, seconds = run(command)
    report_path = workdir / 'jscpd-report.json'
    if not report_path.is_file():
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    total = (report.get('statistics') or {}).get('total') or {}
    findings = []
    for clone in report.get('duplicates', []):
        first, second = clone['firstFile'], clone['secondFile']
        findings.append(finding(
            NAME, found, 'exact_clone', 'literal_duplication',
            subject('file', first['name'], first['name'], first.get('start')),
            f"{clone.get('lines', 0)} identical lines: {first['name']}:{first.get('start')} "
            f"and {second['name']}:{second.get('start')}",
            measurements=[measurement('duplicated_lines', clone.get('lines')),
                          measurement('duplicated_tokens', clone.get('tokens'))],
            raw_ref='jscpd/jscpd-report.json',
            sites=[{'path': first['name'], 'line': first.get('start')},
                   {'path': second['name'], 'line': second.get('start')}]))
    coverage = {'status': 'observed', 'files': total.get('sources'), 'lines': total.get('lines'),
                'formats': sorted((report.get('statistics') or {}).get('formats', {})),
                'duplicated_line_percentage': total.get('percentage'), 'ignored': ignored,
                'formats_requested': sorted(formats) if formats else 'every format jscpd detects'}
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, coverage=coverage,
                  provenance={'threshold_tokens': 50}, raw=str(report_path), evaluated={'literal_duplication': 'observed'})
