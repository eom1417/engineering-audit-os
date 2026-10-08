"""knip: unused files, exports and dependencies of a JavaScript or TypeScript project.

knip's plugins load the project's own configuration files (vite.config.ts, eslint.config.js) as code, and
EAOS runs no code of the project it reads. So knip runs with every plugin switched off, from a configuration
written to the work directory, and the configuration files join the entry files instead: knip then parses
them like any other source and sees what they import without running them. Without its plugins and without
node_modules, knip cannot tell which devDependency a tool or a script uses, so devDependencies, binaries and
unlisted names are counted, not reported; unused files and exports become `dead_code` findings, unused
production dependencies `unused_dependency` findings.
"""
import json
import os
from pathlib import Path

from . import tool
from .contract import ERROR, FILE, OBSERVED, SYMBOL, Capability, Report, finding, subject
from .process import run, which

NAME = BINARY = 'knip'
PINNED = tool.pinned(NAME)
EXCLUDED = ('node_modules', 'dist', 'build', 'coverage', '.next', 'vendor')
# knip's own default entry files, plus the configuration files its plugins would have loaded.
ENTRY = ('{index,cli,main}.{js,cjs,mjs,jsx,ts,cts,mts,tsx}', 'src/{index,cli,main}.{js,cjs,mjs,jsx,ts,cts,mts,tsx}',
         '*.config.{js,cjs,mjs,ts,cts,mts}')
EXPORTS = {'exports': 'export', 'nsExports': 'namespace export', 'types': 'exported type', 'nsTypes': 'namespace type',
           'enumMembers': 'enum member', 'namespaceMembers': 'namespace member'}
COUNTED = ('devDependencies', 'optionalPeerDependencies', 'binaries', 'unlisted', 'unresolved', 'duplicates',
           'catalog', 'catalogReferences')


def capabilities():
    return [Capability('dead_code', 'knip.files', granularity=FILE), Capability('dead_code', 'knip.exports', granularity=SYMBOL),
            Capability('unused_dependency', 'knip.dependencies', granularity=FILE)]


def version():
    return tool.version(BINARY)


def plugins(binary):
    """Every plugin the installed knip knows, read from its own package (bin/knip.js -> dist/plugins/<name>)."""
    folder = Path(os.path.realpath(binary)).parent.parent / 'dist' / 'plugins'
    return sorted(p.name for p in folder.iterdir() if p.is_dir() and not p.name.startswith('_')) if folder.is_dir() else []


def configuration(names, exclude=()):
    return {**{name: False for name in names}, 'entry': list(ENTRY),
            'ignore': [f'**/{name}/**' for name in EXCLUDED + tuple(exclude)]}


def normalise(report, found):
    findings, counted = [], {}
    for issue in report.get('issues') or []:
        path = tool.relative(issue['file'])
        for item in issue.get('files') or []:
            name = tool.relative(item.get('name') or path)
            findings.append(finding(NAME, found, 'files', 'dead_code', subject('file', name, name),
                                    f'unused file `{name}`: no entry file reaches it', raw_ref=f'{NAME}/knip.json'))
        for field, label in EXPORTS.items():
            for item in issue.get(field) or []:
                findings.append(finding(NAME, found, field, 'dead_code', subject('symbol', f"{path}:{item['name']}", path, item.get('line')),
                                        f"unused {label} `{item['name']}` in {path}", raw_ref=f'{NAME}/knip.json'))
        for item in issue.get('dependencies') or []:
            findings.append(finding(NAME, found, 'dependencies', 'unused_dependency',
                                    subject('dependency', item['name'], path, item.get('line')),
                                    f"dependency `{item['name']}` is declared in {path} but no file imports it",
                                    raw_ref=f'{NAME}/knip.json'))
        for field in COUNTED:
            if issue.get(field): counted[field] = counted.get(field, 0) + len(issue[field])
    return findings, dict(sorted(counted.items()))


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    target = Path(target).resolve()
    folder = Path(workdir) / NAME
    folder.mkdir(parents=True, exist_ok=True)
    names = plugins(which(BINARY))
    if not names:
        return Report(NAME, found, PINNED, ERROR, reason='the plugin list of the installed knip was not found; '
                      'run without switching plugins off, it would load the project\'s configuration files as code')
    config = folder / 'knip-config.json'
    config.write_text(json.dumps(configuration(names, exclude), indent=1), encoding='utf-8')
    command = [which(BINARY), '--config', str(config), '--reporter', 'json', '--no-progress', '--no-exit-code',
               '--no-config-hints', '--no-tag-hints']
    code, out, error, seconds = run(command, cwd=target)
    try: report = json.loads(out)
    except ValueError:
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    output = folder / 'knip.json'
    output.write_text(out, encoding='utf-8')
    findings, counted = normalise(report, found)
    by_rule = {}
    for item in findings: by_rule[item['rule']] = by_rule.get(item['rule'], 0) + 1
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, raw=str(output), findings=findings,
                  coverage={'status': 'observed', 'findings_by_rule': dict(sorted(by_rule.items())),
                            'counted_not_reported': counted, 'plugins': f'all {len(names)} switched off',
                            'entry': list(ENTRY), 'tool_errors': [line for line in error.splitlines() if line.startswith('ERROR')][:5]},
                  evaluated={'dead_code': {'status': 'observed', 'granularity': SYMBOL},
                             'unused_dependency': {'status': 'observed', 'granularity': FILE}})
