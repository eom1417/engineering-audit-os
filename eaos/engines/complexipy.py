"""complexipy: cognitive complexity of every Python function (how hard it is to read, not how many paths it has).

Every function becomes a measurement row (granularity `symbol`, its name `Class::method` as complexipy
writes it); one above complexipy's default limit (15) is also a `complexity` finding, a witness beside
Lizard's cyclomatic count. A file complexipy cannot parse is named in the coverage, not hidden: its exit
code is 1 then, and every other file is still measured. It names that file on stdout, not stderr. Its cache goes to the work directory.
"""
import json
import re
from pathlib import Path

from . import tool
from .contract import ERROR, OBSERVED, SYMBOL, Capability, Report, finding, measurement, subject
from .process import run, which

NAME = BINARY = 'complexipy'
PINNED = tool.pinned(NAME)
THRESHOLD = 15
EXCLUDED = ('.git', 'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', 'vendor')
FAILED = re.compile(r'Failed to process\s+(\S+)')
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def capabilities():
    return [Capability('complexity', 'complexipy.cognitive', granularity=SYMBOL)]


def version():
    return tool.version(BINARY)


def normalise(rows, found):
    metrics, findings = [], []
    for row in rows:
        path, symbol, value = tool.relative(row['path']), row['function_name'], int(row['complexity'])
        metrics.append({'path': path, 'line': None, 'symbol': symbol, 'granularity': 'symbol',
                        'measurements': {'cognitive_complexity': value}})
        if value > THRESHOLD:
            findings.append(finding(NAME, found, 'cognitive', 'complexity', subject('symbol', f'{path}::{symbol}', path),
                                    f'function {symbol} has cognitive complexity {value} (threshold {THRESHOLD})',
                                    measurements=[measurement('cognitive_complexity', value, THRESHOLD)],
                                    raw_ref=f'{NAME}/complexipy.json'))
    return sorted(metrics, key=lambda m: (m['path'], m['symbol'])), findings


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    target = Path(target).resolve()
    folder = Path(workdir) / NAME
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / 'complexipy.json'
    output.unlink(missing_ok=True)
    # complexipy reads each exclusion as a glob over project-relative paths: a bare `fixtures` or `tests/fixtures`
    # matches nothing, `**/<entry>/**` matches the entry at any depth, the top level included.
    excluded = [argument for name in EXCLUDED + tuple(exclude) if name.strip('/')
                for argument in ('-e', f"**/{name.strip('/')}/**")]
    command = [which(BINARY), '.', '--output-format', 'json', '--output', str(output), '--cache-dir', str(folder / 'cache'),
               '--quiet', '--ignore-complexity', '--color', 'no', *excluded]
    code, out, error, seconds = run(command, cwd=target)
    if not output.is_file():
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    unparsed = sorted({tool.relative(path, target) for path in FAILED.findall(ANSI.sub('', out + '\n' + error))})
    metrics, findings = normalise(json.loads(output.read_text(encoding='utf-8')), found)
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, raw=str(output), metrics=metrics, findings=findings,
                  coverage={'status': 'observed', 'functions': len(metrics), 'files': len({m['path'] for m in metrics}),
                            'over_threshold': len(findings), 'threshold': THRESHOLD, 'unparsed_files': unparsed},
                  provenance={'threshold': THRESHOLD},
                  evaluated={'complexity': {'status': 'observed', 'granularity': SYMBOL}})
