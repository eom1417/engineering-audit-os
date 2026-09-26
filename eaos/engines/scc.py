"""scc: lines, code, comments and complexity for every file, in every language it knows.

A second, independent witness on size beside EAOS's own metrics: the per-file table (NS18) reads both,
and a file the two disagree about is worth a look. These are measurements, not findings.
"""
import json
from pathlib import Path

from . import tool
from .contract import ERROR, OBSERVED, Report
from .process import run, which

NAME = BINARY = 'scc'
PINNED = tool.pinned(NAME)
EXCLUDED = ('.git', 'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', '.next', 'vendor')


def capabilities():
    return []


def version():
    return tool.version(BINARY)


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    target = Path(target)
    output = Path(workdir) / NAME / 'scc.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [which(BINARY), '--by-file', '--format', 'json', '--no-cocomo', '--output', str(output),
               '--exclude-dir', ','.join(EXCLUDED + tuple(exclude)), str(target)]
    code, _, error, seconds = run(command)
    if code or not output.is_file():
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    languages = json.loads(output.read_text(encoding='utf-8')) or []
    metrics, totals = [], {}
    for language in languages:
        totals[language['Name']] = {'files': language['Count'], 'code': language['Code'], 'complexity': language['Complexity']}
        for row in language.get('Files') or []:
            location = Path(row['Location'])
            path = location.relative_to(target).as_posix() if location.is_absolute() and target in location.parents else row['Location']
            metrics.append({'path': path, 'granularity': 'file',
                            'measurements': {'language': row['Language'], 'lines': row['Lines'], 'code': row['Code'],
                                             'comment': row['Comment'], 'blank': row['Blank'], 'complexity': row['Complexity'],
                                             'generated': row.get('Generated', False), 'minified': row.get('Minified', False)}})
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, raw=str(output), metrics=sorted(metrics, key=lambda m: m['path']),
                  coverage={'status': 'observed', 'files': len(metrics), 'languages': dict(sorted(totals.items()))})
