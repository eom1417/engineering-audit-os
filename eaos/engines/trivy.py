"""Trivy: committed secrets and misconfigured infrastructure files, in one pass.

Its secrets are a second witness beside EAOS's own committed-credential detector and Gitleaks: agreement raises
confidence in the debt register (NS18). Its misconfigurations cover Dockerfiles, Terraform and Kubernetes files.
Vulnerable packages are OSV-Scanner's alone (M2.3): on the compatibility corpus Trivy found none OSV-Scanner did not, and
wrote each advisory as a weakness of the lockfile, one card per advisory (119 on one app) beside OSV-Scanner's one per
package.

No secret value is ever recorded. Trivy masks the value it matched; the adapter removes the whole
`Match:` line from every message before a finding is made, so only the rule, the file and the line remain.
"""
import json
import re
from pathlib import Path

from . import sarif, tool
from .contract import OBSERVED, Report
from .process import run, which

NAME = BINARY = 'trivy'
PINNED = tool.pinned(NAME)
EXCLUDED = ('node_modules', '.git', '.venv', 'venv', 'dist', 'build', '__pycache__', 'vendor', '.next')
MATCH = re.compile(r'Match:.*', re.S)


def capabilities():
    from .contract import Capability
    return [Capability('secret', '<secret rule>'), Capability('misconfiguration', 'AVD-*')]


def version():
    return tool.version(BINARY)


def redact(path):
    """Drop everything from `Match:` on in every message, and every secret rule's description, in place: the
    rule, the file and the line are enough to act on, and the raw file kept in the report holds no more."""
    data = json.loads(path.read_text(encoding='utf-8'))
    for run_ in data.get('runs') or []:
        _redact_rules((run_.get('tool') or {}).get('driver', {}).get('rules') or [])
        _redact_messages(run_.get('results') or [])
    path.write_text(json.dumps(data), encoding='utf-8')


def _redact_rules(rules):
    """A secret rule's description repeats the matched line; only its short name is kept."""
    for rule in rules:
        if rule.get('name') != 'Secret': continue
        short = (rule.get('shortDescription') or {}).get('text', 'secret')
        rule['fullDescription'] = {'text': short}
        if 'help' in rule: rule['help'] = {'text': short, 'markdown': short}


def _redact_messages(results):
    for result in results:
        message = result.get('message') or {}
        if 'text' in message: message['text'] = MATCH.sub('Match: [not recorded]', message['text'])


def _command(output, exclude):
    """The scan: what it learns of the project kept in memory only (never in a cache another project's scan reads); the
    tools' cache holds only its misconfiguration checks."""
    from ..core.toolchain import TRIVY_CACHE, home
    command = [which(BINARY), 'fs', '--format', 'sarif', '--scanners', 'secret,misconfig', '--quiet', '--cache-backend', 'memory',
               '--cache-dir', str(home() / TRIVY_CACHE), '--output', str(output)]
    for directory in EXCLUDED + tuple(exclude): command += ['--skip-dirs', directory]
    return command


def analyze(target, workdir, exclude=(), formats=None):
    if declined := tool.declined(NAME, BINARY, target): return declined
    found = version()
    output = Path(workdir) / NAME / 'trivy.sarif'
    output.parent.mkdir(parents=True, exist_ok=True)
    code, _, error, seconds = run(_command(output, exclude) + [str(target)])
    if code or not output.is_file():
        return tool.failed(NAME, found, seconds, code, error)
    redact(output)
    findings, unmapped = sarif.collected(output, target, NAME, found)
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, unmapped=unmapped, raw=str(output),
                  coverage={'status': 'observed', 'scanners': ['secret', 'misconfig'],
                            'by_kind': {kind: sum(f['kind'] == kind for f in findings) for kind in sorted({f['kind'] for f in findings})}},
                  evaluated={'secret': {'status': 'observed', 'granularity': 'file'},
                             'misconfiguration': {'status': 'observed', 'granularity': 'file'}})
