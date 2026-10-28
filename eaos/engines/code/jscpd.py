"""jscpd: near copies of code over 224 formats, in a fifth of a second.

With its near modes (M15.2) it finds four kinds of copy, each a pair of places: exact, renamed (the same tokens, names
aside), gap (one or two lines changed between two matching runs) and similar (two functions whose syntax trees share
most subtrees, for JavaScript, TypeScript, Python, Go, Java and others; test files left out). The thresholds are the
law's (eaos/core/contracts/code_laws.py NEAR_COPY). Each pair is a record (`near_copy`), never a finding:
eaos/analysis/assessments/one_source.py joins the pairs into one cluster per pattern. A pair that copies only a block of
imports (three or more, with at most three other lines around them) is left out: modules of one kind start alike, and
there is no logic to give one home.

It scans exactly what it is given. Without the declared analysis exclusions it counted our own
report artifacts and reported 23.1% duplication where the source holds 1.85%; scope is our duty.
"""
import json
import re
from pathlib import Path

from ..contract import Report, OBSERVED, UNAVAILABLE
from ...core.contracts.code_laws import NEAR_COPY
from .. import tool
from ..process import run, which

NAME, BINARY, PINNED = 'jscpd', 'jscpd', '5.4.2'
ALWAYS_IGNORED = ('**/.git/**', '**/node_modules/**', '**/.venv/**', '**/dist/**', '**/build/**',
                  '**/__pycache__/**', '**/.enola/**', '**/*.d.ts')     # a declaration file: types written (or generated) for code elsewhere
IMPORT = re.compile(r'^\s*(from\s+\S+\s+import\b|import\s|export\s.*\bfrom\s|\}\s*from\s)')
ASIDE = re.compile(r'^\s*("""|\'\'\'|#|//|\*|/\*)?\s*$|^\s*(#|//)')        # blank, a comment, a docstring's quotes alone
NEAR_MODES = ('--similarity', str(NEAR_COPY['similarity']), '--max-gap-lines', str(NEAR_COPY['max_gap_lines']),
              '--ignore-identifiers', '--min-tokens', str(NEAR_COPY['min_tokens']))


def capabilities(): return []


def analyze(target, workdir, exclude=(), formats=None):
    found = tool.version(BINARY)
    if found is None:
        return Report(NAME, None, PINNED, UNAVAILABLE, reason='jscpd is not installed')
    workdir = Path(workdir) / 'jscpd'
    workdir.mkdir(parents=True, exist_ok=True)
    ignored = ','.join(ALWAYS_IGNORED + tuple(f'**/{pattern}/**' for pattern in exclude))
    # Read from inside the target: the patterns to skip then match its own folders, never the ones it sits in (a project
    # under a folder named fixtures was skipped whole).
    command = [which(BINARY), '.', *NEAR_MODES, '--reporters', 'json', '--output', str(workdir.resolve()), '--ignore', ignored, '--silent']
    # Without a format list jscpd counts markdown and JSON as duplication: 28.98% here against 1.88%
    # over source. The caller owns the source vocabulary, so it passes it in.
    if formats:
        command += ['--format', ','.join(sorted(_formats(formats)))]
    code, _, error, seconds = run(command, cwd=target)
    report_path = workdir / 'jscpd-report.json'
    if not report_path.is_file():
        return tool.failed(NAME, found, seconds, code, error)
    report = json.loads(report_path.read_text(encoding='utf-8'))
    pairs = [clone for clone in report.get('duplicates', []) if not imports_only(clone.get('fragment') or '')]
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, metrics=[_record(clone) for clone in pairs],
                  coverage=_coverage(report, ignored, formats), provenance={'near_copy': NEAR_COPY}, raw=str(report_path))


def _formats(formats):
    """jscpd's names of the languages asked: JSX is its own format there (a .jsx file is javascript to EAOS)."""
    return set(formats) | ({'jsx'} if 'javascript' in formats else set())


def imports_only(fragment):
    """Whether a pair copies only a block of imports: three import lines or more, at most three other lines of code."""
    lines = [line for line in fragment.splitlines() if not ASIDE.match(line)]
    imports = sum(1 for line in lines if IMPORT.match(line))
    return imports >= 3 and len(lines) - imports <= 3


def _place(side):
    return {'path': side['name'], 'line': side.get('start'), 'end_line': side.get('end')}


def _record(clone):
    """One pair of copies: where each is, its kind (exact, renamed, gap, similar), and how alike."""
    first, second = _place(clone['firstFile']), _place(clone['secondFile'])
    return {'path': first['path'], 'line': first['line'], 'symbol': None, 'granularity': 'file',
            'measurements': {'record': 'near_copy', 'kind': clone.get('kind') or 'exact', 'similarity': clone.get('similarity'),
                             'lines': clone.get('lines'), 'tokens': clone.get('tokens'), 'end_line': first['end_line'],
                             'format': clone.get('format'), 'other': second}}


def _coverage(report, ignored, formats):
    """What jscpd read: its files, lines and formats, the share of lines duplicated, and what it was told to skip."""
    total = (report.get('statistics') or {}).get('total') or {}
    return {'status': 'observed', 'files': total.get('sources'), 'lines': total.get('lines'),
            'formats': sorted((report.get('statistics') or {}).get('formats', {})),
            'duplicated_line_percentage': total.get('percentage'), 'ignored': ignored,
            'formats_requested': sorted(formats) if formats else 'every format jscpd detects'}
