"""Gitleaks: secrets written into the project's files (keys, tokens, private keys), by its own rules and entropy.

A second secret scanner beside Trivy's and Semgrep's, with its own rule set: where two of them name the same line
(eaos/analysis/weaknesses.py) the secret is corroborated. It reads the files as they are today (`gitleaks dir`), the same
snapshot as every other engine, and never prints a secret: `--redact` keeps only where it is.

The directories outside the project's own code are an allowlist in a configuration written beside its output,
which extends Gitleaks' default rules rather than replacing them.
"""
import re
import shutil
from pathlib import Path

from . import sarif, tool
from .contract import ERROR, OBSERVED, Capability, Report
from .process import run, which

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


def version():
    return tool.version(BINARY)


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    workdir = Path(workdir) / NAME
    if workdir.exists(): shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    config, output = workdir / 'gitleaks.toml', workdir / 'gitleaks.sarif'
    names = [re.escape(name.strip('/')) for name in EXCLUDED + tuple(exclude) if name.strip('/')]
    config.write_text(CONFIG.replace('{names}', '|'.join(names)), encoding='utf-8')
    code, _, error, seconds = run([which(BINARY), 'dir', str(Path(target).resolve()), '-c', str(config), '-f', 'sarif',
                                   '-r', str(output), '--redact', '--no-banner', '--exit-code', '0', '-l', 'error'], cwd=workdir)
    if code != 0 or not output.is_file():
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    sarif.relativise(output, target)
    findings, unmapped = sarif.read(output, NAME, found)
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, unmapped=unmapped, raw=str(output),
                  coverage={'status': 'observed', 'snapshot': 'the files as they are, not the history'},
                  evaluated={'secret': {'status': 'observed', 'granularity': 'file'}})
