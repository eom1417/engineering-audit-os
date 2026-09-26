"""Semgrep: EAOS's own rules for what vibe-coded projects get wrong, and the security rules of the official library.

EAOS's rules (eaos/rules/semgrep/*.yml) each sit beside an annotated example, and `semgrep --test` proves
them: a Supabase result read without its error, a response body read without its status, text run as
code, SQL built by pasting values, the service-role key in browser code.

The official library (semgrep-rules) may not be redistributed, so it is never in this repository:
`eaos tools install` fetches it at a pinned commit to this machine, and only its security and secrets
rules are read (its style and i18n rules put 1,000 findings on one project and say nothing about risk).
The report records which rule sets ran.

Semgrep prefixes a rule id with the path of its configuration, so the same rule would change its id
with the install location. The rules are assembled under a fixed layout in the work directory and the
prefix is stripped, so a finding keeps its id across machines. The SARIF goes through eaos.engines.sarif;
the kind of each rule is a row in eaos/rules/sarif-rules.json, and what no row maps is counted.
"""
import json
import shutil
from pathlib import Path

from . import sarif, tool
from .contract import ERROR, OBSERVED, Report
from .process import run, which

NAME = BINARY = 'semgrep'
PINNED = tool.pinned(NAME)
OWN = Path(__file__).resolve().parent.parent / 'rules/semgrep'
OFFICIAL = ('javascript', 'typescript', 'python', 'generic/secrets')
PREFIXES = ('rules.eaos.', 'rules.official.')
EXCLUDED = ('node_modules', '.git', '.venv', 'venv', 'dist', 'build', '__pycache__', 'vendor', '.next')


def capabilities():
    from .contract import Capability
    return [Capability('dataflow', 'eaos.dataflow.*'), Capability('vulnerability', '*.security.*'),
            Capability('secret', 'generic.secrets.*')]


def version():
    return tool.version(BINARY)


def official_checkout():
    """The pinned official library on this machine, or None when `eaos tools install` has not fetched it."""
    from ..toolchain import found_version, registry
    entry = next(t for t in registry()['tools'] if t['name'] == 'semgrep-rules')
    found, _ = found_version(entry)
    from ..toolchain import home
    return (home() / entry['install']['dir'], found) if found == entry['version'] else (None, found)


def assemble(workdir):
    """rules/eaos and rules/official/<pack> under workdir; returns the rule sets it holds."""
    rules = workdir / 'rules'
    if rules.exists(): shutil.rmtree(rules)
    shutil.copytree(OWN, rules / 'eaos', ignore=lambda _, names: [n for n in names if not n.endswith(('.yml', '.yaml'))])
    used = ['eaos']
    checkout, commit = official_checkout()
    if checkout is None: return used, None
    for pack in OFFICIAL:
        for path in sorted((checkout / pack).rglob('*.y*ml')):
            relative = path.relative_to(checkout)
            if path.name.endswith(('.test.yaml', '.test.yml')) or not ('security' in relative.parts or pack == 'generic/secrets'):
                continue
            destination = rules / 'official' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
        used.append(f'official:{pack}' + ('' if pack == 'generic/secrets' else '/**/security'))
    return used, commit


def normalise(path, target):
    """Rewrite the SARIF so every rule id is the rule's own id, not the path it was loaded from, and every
    location is relative to the project, before any finding id is derived from them."""
    data = json.loads(path.read_text(encoding='utf-8'))
    def clean(rule_id):
        return next((rule_id[len(prefix):] for prefix in PREFIXES if str(rule_id).startswith(prefix)), rule_id)
    for run_ in data.get('runs') or []:
        for rule in (run_.get('tool') or {}).get('driver', {}).get('rules') or []:
            rule['id'] = clean(rule.get('id'))
        for result in run_.get('results') or []:
            result['ruleId'] = clean(result.get('ruleId'))
    path.write_text(json.dumps(data), encoding='utf-8')
    sarif.relativise(path, target)


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    workdir = Path(workdir) / NAME
    workdir.mkdir(parents=True, exist_ok=True)
    used, commit = assemble(workdir)
    output = workdir / 'semgrep.sarif'
    command = [which(BINARY), 'scan', '--config', 'rules', '--sarif', '--output', str(output), '--metrics', 'off',
               '--disable-version-check', '--quiet']
    for pattern in EXCLUDED + tuple(exclude): command += ['--exclude', pattern]
    code, _, error, seconds = run(command + [str(Path(target).resolve())], cwd=workdir)
    if code not in (0, 1) or not output.is_file():
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    normalise(output, target)
    findings, unmapped = sarif.read(output, NAME, found)
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, unmapped=unmapped, raw=str(output),
                  coverage={'status': 'observed', 'rule_sets': used, 'official_commit': commit,
                            'official_missing': None if commit else 'python -m eaos tools install --only semgrep-rules'},
                  evaluated={'dataflow': {'status': 'observed', 'granularity': 'file'},
                             'vulnerability': {'status': 'observed' if commit else 'partial', 'granularity': 'file'},
                             'secret': {'status': 'observed' if commit else 'partial', 'granularity': 'file'}})

