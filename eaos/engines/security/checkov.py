"""Checkov: GitHub Actions, Dockerfiles, Terraform and Kubernetes files checked against their known pitfalls.

It applies only where such files exist (.github/workflows, a Dockerfile, Terraform); elsewhere it is
not applicable, not absent. A run that finds nothing is still evidence: the coverage records how many
checks passed per framework, so a clean result reads apart from a check that never ran.
"""
import re
import json

from .. import sarif, tool
from ..contract import OBSERVED, Report
from ..process import run, which

NAME = BINARY = 'checkov'
PINNED = tool.pinned(NAME)


def capabilities():
    from ..contract import Capability
    return [Capability('misconfiguration', 'CKV*')]


def version(): return tool.version(BINARY)


def _command(target, workdir, exclude):
    command = [which(BINARY), '-d', str(target), '-o', 'sarif', '-o', 'json', '--output-file-path', str(workdir),
               '--quiet', '--compact', '--skip-download', '--skip-path', 'node_modules']
    for pattern in exclude: command += ['--skip-path', re.escape(pattern)]     # Checkov reads it as a regular expression
    return command


def _frameworks(summary):
    """{framework: {passed, failed, skipped}} from Checkov's JSON summary: a clean run still says what it checked."""
    if not summary.is_file(): return {}
    data = json.loads(summary.read_text(encoding='utf-8'))
    return {row['check_type']: {k: (row.get('summary') or {}).get(k) for k in ('passed', 'failed', 'skipped')}
            for row in (data if isinstance(data, list) else [data]) if isinstance(row, dict) and row.get('check_type')}


@tool.engine(NAME, BINARY, fresh=True)
def analyze(target, workdir, exclude, formats, found):
    # Checkov exits 1 when a check fails; that is a result, not an error.
    code, _, error, seconds = run(_command(target, workdir, exclude), cwd=workdir)
    output, summary = workdir / 'results_sarif.sarif', workdir / 'results_json.json'
    if code not in (0, 1) or not output.is_file():
        return tool.failed(NAME, found, seconds, code, error)
    findings, unmapped = sarif.collected(output, target, NAME, found)
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, unmapped=unmapped, raw=str(output),
                  coverage={'status': 'observed', 'frameworks': _frameworks(summary)},
                  evaluated={'misconfiguration': {'status': 'observed', 'granularity': 'file'}})
