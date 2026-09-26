"""Checkov: GitHub Actions, Dockerfiles, Terraform and Kubernetes files checked against their known pitfalls.

It applies only where such files exist (.github/workflows, a Dockerfile, Terraform); elsewhere it is
not applicable, not absent. A run that finds nothing is still evidence: the coverage records how many
checks passed per framework, so a clean result reads apart from a check that never ran.
"""
import json
import shutil
from pathlib import Path

from . import sarif, tool
from .contract import ERROR, OBSERVED, Report
from .process import run, which

NAME = BINARY = 'checkov'
PINNED = tool.pinned(NAME)


def capabilities():
    from .contract import Capability
    return [Capability('misconfiguration', 'CKV*')]


def version():
    return tool.version(BINARY)


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    workdir = Path(workdir) / NAME
    if workdir.exists(): shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    command = [which(BINARY), '-d', str(target), '-o', 'sarif', '-o', 'json', '--output-file-path', str(workdir),
               '--quiet', '--compact', '--skip-download', '--skip-path', 'node_modules']
    for pattern in exclude: command += ['--skip-path', pattern]
    # Checkov exits 1 when a check fails; that is a result, not an error.
    code, _, error, seconds = run(command, cwd=workdir)
    output, summary = workdir / 'results_sarif.sarif', workdir / 'results_json.json'
    if code not in (0, 1) or not output.is_file():
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    sarif.relativise(output, target)
    findings, unmapped = sarif.read(output, NAME, found)
    frameworks = {}
    if summary.is_file():
        data = json.loads(summary.read_text(encoding='utf-8'))
        for row in data if isinstance(data, list) else [data]:
            if isinstance(row, dict) and row.get('check_type'):
                frameworks[row['check_type']] = {k: (row.get('summary') or {}).get(k) for k in ('passed', 'failed', 'skipped')}
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, unmapped=unmapped, raw=str(output),
                  coverage={'status': 'observed', 'frameworks': frameworks},
                  evaluated={'misconfiguration': {'status': 'observed', 'granularity': 'file'}})
