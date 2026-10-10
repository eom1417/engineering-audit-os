"""Trivy: vulnerable packages, committed secrets and misconfigured infrastructure files, in one pass.

Its vulnerabilities are a second witness beside OSV-Scanner, and its secrets beside EAOS's own
committed-credential detector: agreement raises confidence in the debt register (NS18), and neither
becomes a second claim about the same place. Its misconfigurations cover Dockerfiles, Terraform and
Kubernetes files.

No secret value is ever recorded. Trivy masks the value it matched; the adapter removes the whole
`Match:` line from every message before a finding is made, so only the rule, the file and the line remain.
"""
import json
import re
from pathlib import Path

from . import sarif, tool
from .contract import ERROR, OBSERVED, Report
from .process import run, which

NAME = BINARY = 'trivy'
PINNED = tool.pinned(NAME)
EXCLUDED = ('node_modules', '.git', '.venv', 'venv', 'dist', 'build', '__pycache__', 'vendor', '.next')
MATCH = re.compile(r'Match:.*', re.S)


def capabilities():
    from .contract import Capability
    return [Capability('vulnerability', 'CVE-*'), Capability('secret', '<secret rule>'),
            Capability('misconfiguration', 'AVD-*')]


def version():
    return tool.version(BINARY)


def redact(path):
    """Drop everything from `Match:` on in every message, and every secret rule's description, in place: the
    rule, the file and the line are enough to act on, and the raw file kept in the report holds no more."""
    data = json.loads(path.read_text(encoding='utf-8'))
    for run_ in data.get('runs') or []:
        # A secret rule's description repeats the matched line; only its short name is kept.
        for rule in (run_.get('tool') or {}).get('driver', {}).get('rules') or []:
            if rule.get('name') == 'Secret':
                short = (rule.get('shortDescription') or {}).get('text', 'secret')
                rule['fullDescription'] = {'text': short}
                if 'help' in rule: rule['help'] = {'text': short, 'markdown': short}
        for result in run_.get('results') or []:
            message = result.get('message') or {}
            if 'text' in message: message['text'] = MATCH.sub('Match: [not recorded]', message['text'])
    path.write_text(json.dumps(data), encoding='utf-8')


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    from ..toolchain import TRIVY_CACHE, home, trivy_db
    output = Path(workdir) / NAME / 'trivy.sarif'
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [which(BINARY), 'fs', '--format', 'sarif', '--scanners', 'vuln,secret,misconfig', '--quiet',
               '--cache-dir', str(home() / TRIVY_CACHE), '--output', str(output)]
    # A database already here is used as it is: the install refreshes it daily in the background, never in a check
    if trivy_db(): command.append('--skip-db-update')
    for directory in EXCLUDED + tuple(exclude): command += ['--skip-dirs', directory]
    code, _, error, seconds = run(command + [str(target)])
    if code or not output.is_file():
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    redact(output)
    sarif.relativise(output, target)
    findings, unmapped = sarif.read(output, NAME, found)
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, unmapped=unmapped, raw=str(output),
                  coverage={'status': 'observed', 'scanners': ['vuln', 'secret', 'misconfig'],
                            'by_kind': {kind: sum(f['kind'] == kind for f in findings) for kind in sorted({f['kind'] for f in findings})}},
                  evaluated={'vulnerability': {'status': 'observed', 'granularity': 'package'},
                             'secret': {'status': 'observed', 'granularity': 'file'},
                             'misconfiguration': {'status': 'observed', 'granularity': 'file'}})
