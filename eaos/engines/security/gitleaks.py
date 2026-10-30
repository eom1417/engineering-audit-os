"""Gitleaks: secrets written into the project's files (keys, tokens, private keys), by its own rules and entropy.

A second secret scanner beside Semgrep's and EAOS's own, with its own rule set: where two of them name the same line
(eaos/analysis/assessments/weaknesses.py) the secret is corroborated. It reads the files as they are today (`gitleaks dir`), the same
snapshot as every other engine, and never prints a secret: `--redact` keeps only where it is.

The directories outside the project's own code are an allowlist in a configuration written beside its output,
which extends Gitleaks' default rules rather than replacing them.
"""
import re
from pathlib import Path

from .. import sarif, tool
from ..contract import OBSERVED, Capability, Report
from ..process import run, which

NAME = BINARY = 'gitleaks'
PINNED = tool.pinned(NAME)
EXCLUDED = ('.git', 'node_modules', '.venv', 'venv', 'dist', 'build', 'vendor')
CONFIG = """[extend]
useDefault = true

[allowlist]
description = "EAOS: what is not the project's own code"
paths = ['''(^|/)({names})/''']
"""


def capabilities():
    return [Capability('secret', '*')]


@tool.engine(NAME, BINARY, fresh=True)
def analyze(target, workdir, exclude, formats, found):
    config, output = workdir / 'gitleaks.toml', workdir / 'gitleaks.sarif'
    names = [re.escape(name.strip('/')) for name in EXCLUDED + tuple(exclude) if name.strip('/')]
    config.write_text(CONFIG.replace('{names}', '|'.join(names)), encoding='utf-8')
    code, _, error, seconds = run([which(BINARY), 'dir', str(Path(target).resolve()), '-c', str(config), '-f', 'sarif',
                                   '-r', str(output), '--redact', '--no-banner', '--exit-code', '0', '-l', 'error'], cwd=workdir)
    if code != 0 or not output.is_file():
        return tool.failed(NAME, found, seconds, code, error)
    findings, unmapped = sarif.collected(output, target, NAME, found)
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, unmapped=unmapped, raw=str(output),
                  coverage={'status': 'observed', 'snapshot': 'the files as they are, not the history'},
                  evaluated={'secret': {'status': 'observed', 'granularity': 'file'}})
