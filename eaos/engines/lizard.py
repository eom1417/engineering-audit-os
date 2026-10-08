"""Lizard: cyclomatic complexity, length and parameters of every function, in some twenty-five languages.

Every function becomes a measurement row (granularity `symbol`); a function above Lizard's own warning
threshold (cyclomatic complexity over 15) is also a `complexity` finding, a witness beside reforge, enola
and complexipy, so two of them agreeing on one file is what raises a claim. Its CSV has no header: the
column order is pinned by the contract sample in tests/contracts/lizard.json.
"""
import csv
import io
from pathlib import Path

from . import tool
from .contract import ERROR, OBSERVED, SYMBOL, Capability, Report, finding, measurement, subject
from .process import run, which

NAME = BINARY = 'lizard'
PINNED = tool.pinned(NAME)
THRESHOLD = 15
EXCLUDED = ('.git', 'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', '.next', 'vendor', 'coverage')
COLUMNS = ('nloc', 'ccn', 'tokens', 'parameters', 'length', 'location', 'file', 'function', 'long_name', 'start', 'end')


def capabilities():
    return [Capability('complexity', 'lizard.ccn', granularity=SYMBOL)]


def version():
    return tool.version(BINARY)


def rows(text):
    """Lizard's CSV as dictionaries keyed by COLUMNS; a row of another width is skipped and counted."""
    out, skipped = [], 0
    for row in csv.reader(io.StringIO(text)):
        if len(row) < len(COLUMNS): skipped += 1; continue
        out.append(dict(zip(COLUMNS, row)))
    return out, skipped


def normalise(parsed, found):
    metrics, findings = [], []
    for row in parsed:
        path, start, ccn, nloc = tool.relative(row['file']), int(row['start']), int(row['ccn']), int(row['nloc'])
        metrics.append({'path': path, 'line': start, 'symbol': row['function'], 'granularity': 'symbol',
                        'measurements': {'cyclomatic_complexity': ccn, 'nloc': nloc, 'tokens': int(row['tokens']),
                                         'parameters': int(row['parameters']), 'length': int(row['length']),
                                         'end_line': int(row['end'])}})
        if ccn > THRESHOLD:
            findings.append(finding(NAME, found, 'ccn', 'complexity', subject('symbol', f"{path}::{row['function']}", path, start),
                                    f"function {row['function']} has cyclomatic complexity {ccn} (threshold {THRESHOLD})",
                                    measurements=[measurement('cyclomatic_complexity', ccn, THRESHOLD),
                                                  measurement('nloc', nloc)],
                                    raw_ref=f'{NAME}/lizard.csv'))
    return sorted(metrics, key=lambda m: (m['path'], m['line'])), findings


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    target = Path(target).resolve()
    output = Path(workdir) / NAME / 'lizard.csv'
    output.parent.mkdir(parents=True, exist_ok=True)
    patterns = [argument for name in EXCLUDED + tuple(exclude) for argument in ('-x', f'*/{name}/*')]
    # -i -1: the exit code stays 0 however many functions pass the threshold; a warning is a result.
    code, out, error, seconds = run([which(BINARY), '--csv', '-i', '-1', '-t', '4', *patterns, '.'], cwd=target)
    if code:
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    output.write_text(out, encoding='utf-8')
    parsed, skipped = rows(out)
    metrics, findings = normalise(parsed, found)
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, raw=str(output), metrics=metrics, findings=findings,
                  coverage={'status': 'observed', 'functions': len(metrics), 'files': len({m['path'] for m in metrics}),
                            'over_threshold': len(findings), 'threshold_ccn': THRESHOLD, 'rows_skipped': skipped},
                  provenance={'threshold_ccn': THRESHOLD},
                  evaluated={'complexity': {'status': 'observed', 'granularity': SYMBOL}})
