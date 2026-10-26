"""Bandit: security weaknesses in Python, found by walking each file's syntax tree.

A second reader of Python security beside Semgrep, working another way: Semgrep matches patterns of text, Bandit
visits the parsed tree, so where both report a weakness at the same line (eaos/analysis/assessments/weaknesses.py) it is corroborated.
Only medium and high severity are reported: Bandit's low ones (importing subprocess, an `except: pass`) name a
module or an idiom, not a weakness, and put hundreds of lines on a project that runs commands at all.

Bandit matches an excluded entry anywhere in a path, so each one is passed as `/name/`: a bare `build` would also drop
`journeys/build_from_plan/steps.py`. Its SARIF goes through eaos.engines.sarif, which reads the CWE each rule names.
"""
from pathlib import Path

from .. import sarif, tool
from ..contract import OBSERVED, Capability, Report
from ..process import run, which

NAME = BINARY = 'bandit'
PINNED = tool.pinned(NAME)
EXCLUDED = ('.git', 'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', 'vendor')


def capabilities():
    return [Capability('vulnerability', 'B*'), Capability('secret', 'B10[5-7]')]


def version(): return tool.version(BINARY)


@tool.engine(NAME, BINARY, fresh=True)
def analyze(target, workdir, exclude, formats, found):
    output = workdir / 'bandit.sarif'
    skipped = ','.join(f"/{name.strip('/')}/" for name in EXCLUDED + tuple(exclude) if name.strip('/'))
    # Bandit exits 1 when it found something; that is a result, not an error.
    code, _, error, seconds = run([which(BINARY), '-r', '.', '-f', 'sarif', '-o', str(output), '-q',
                                   '--severity-level', 'medium', '-x', skipped], cwd=Path(target).resolve())
    if code not in (0, 1) or not output.is_file():
        return tool.failed(NAME, found, seconds, code, error)
    findings, unmapped = sarif.collected(output, target, NAME, found)
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, unmapped=unmapped, raw=str(output),
                  coverage={'status': 'observed', 'severity_reported': 'medium and high'},
                  evaluated={'vulnerability': {'status': 'observed', 'granularity': 'file'}})
