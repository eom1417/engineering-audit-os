"""The governance kit: CI, pre-commit, Renovate and the target's boundary rules, in each tool's own format.

  handover/.github/workflows/eaos.yml     three jobs, each step only when it applies to this project:
                                          build and test (and the behaviour lock when present); security
                                          (Trivy, OSV-Scanner, Semgrep with EAOS's rules, Checkov when there
                                          is CI or IaC, Spectral when there is OpenAPI); architecture
                                          (dependency-cruiser on the target's layers, and the EAOS gate on
                                          what is new against a pinned baseline). Every action is pinned to a
                                          full commit (eaos/rules/actions.json); every tool to the version in
                                          upstreams/toolchain.json, downloaded releases checked by sha256.
  handover/.pre-commit-config.yaml        fast checks only: file hygiene, secrets (Trivy), Semgrep on the
                                          changed files, markdownlint.
  handover/renovate.json                  minor and patch updates grouped weekly; security updates at once.
  handover/.dependency-cruiser.cjs        JS/TS: one rule per pair of target layers that may not depend on
                                          each other (the reference type's allowed_dependencies).
  handover/semgrep/                       EAOS's own Semgrep rules, and for Python the same boundary rules
                                          as imports (boundaries.yml).

The code today breaks the target's boundaries; that is the plan's work. So the workflow fails only on what
is new: dependency-cruiser with its known-violations file once the owner records it, Semgrep with the pull
request's base commit as its baseline, and the EAOS gate against its pinned baseline.
"""
import json
import re
import shutil
from pathlib import Path

from .base import Emitted
from .project import pin, profile, reference
from .yamltext import dump

RULES = Path(__file__).resolve().parent.parent / 'rules'


def _pins():
    return json.loads((RULES / 'actions.json').read_text(encoding='utf-8'))


def uses(name):
    action = _pins()['actions'][name]
    return f"{name}@{action['sha']}"


def literal(glob):
    return re.split(r'[*?]', glob, maxsplit=1)[0]


def glob_regex(glob):
    """A path glob as an anchored regular expression: ** any depth, * within one segment."""
    out = ''
    for token in re.split(r'(\*\*/?|\*|\?)', glob):
        if token in ('**', '**/'): out += '.*'
        elif token == '*': out += '[^/]*'
        elif token == '?': out += '[^/]'
        else: out += re.escape(token)
    return '^' + out + ('' if glob.endswith(('*', '/')) else '$')


def weight(glob):
    """Specificity as placement measures it (reference_architecture.layer_of): the pattern without its stars."""
    return len(glob.replace('*', ''))


def narrower(layer, ref):
    """Globs of other layers inside this layer's globs that win placement over them: the most specific wins."""
    return [g for other in ref['layers'] if other['name'] != layer['name'] for g in other['paths']
            if any(literal(g).startswith(literal(mine)) and weight(g) > weight(mine) for mine in layer['paths'])]


def forbidden_pairs(ref):
    return [(a, b) for a in ref['layers'] for b in ref['layers']
            if a['name'] != b['name'] and b['name'] not in a['allowed_dependencies']]


def depcruise_config(ref):
    rules = []
    for a, b in forbidden_pairs(ref):
        rule = {'name': f"eaos-{a['name']}-not-{b['name']}", 'severity': 'error',
                'comment': f"{a['name']} ({a['responsibility']}) may not depend on {b['name']}: "
                           f"the {ref['id']} reference allows {', '.join(a['allowed_dependencies']) or 'nothing'}.",
                'from': {'path': '|'.join(glob_regex(g) for g in a['paths'])},
                'to': {'path': '|'.join(glob_regex(g) for g in b['paths'])}}
        if narrower(a, ref): rule['from']['pathNot'] = '|'.join(glob_regex(g) for g in narrower(a, ref))
        if narrower(b, ref): rule['to']['pathNot'] = '|'.join(glob_regex(g) for g in narrower(b, ref))
        rules.append(rule)
    rules.append({'name': 'no-circular', 'severity': 'warn', 'comment': 'An import cycle ties modules that should change apart.',
                  'from': {}, 'to': {'circular': True}})
    config = {'forbidden': rules, 'options': {'doNotFollow': {'path': 'node_modules'}, 'exclude': {'path': 'node_modules|dist|build'},
                                              'tsPreCompilationDeps': True}}
    return ('// Boundary rules of the target architecture (' + ref['id'] + '), written by EAOS from target-architecture.json.\n'
            '// Record what the code breaks today once, so CI fails only on new violations:\n'
            '//   npx dependency-cruiser --config .dependency-cruiser.cjs --ts-config tsconfig.json --output-type baseline src'
            ' > .dependency-cruiser-known-violations.json\n'
            'module.exports = ' + json.dumps(config, indent=2) + ';\n')


def module_regex(globs):
    """Python module names a set of path globs covers (core/** -> core, core/database.py -> core.database)."""
    parts = []
    for glob in globs:
        if glob.startswith('*') or not (glob.endswith(('/**', '.py')) or '*' in glob.split('/')[-1] and '.' not in glob.split('/')[-1]):
            continue
        name = glob[:-3] if glob.endswith('/**') else glob[:-3] if glob.endswith('.py') else glob
        name = re.escape(name.replace('/', '.')).replace(r'\*', '[^.]*')
        parts.append(name + (r'(\.|$)' if glob.endswith('/**') else '$'))
    return parts


def semgrep_boundaries(ref):
    rules = []
    for a, b in forbidden_pairs(ref):
        targets, exceptions = module_regex(b['paths']), module_regex(narrower(b, ref))
        sources = [g for g in a['paths'] if g.endswith(('/**', '.py'))]
        if not targets or not sources: continue
        regex = '^' + (f"(?!{'|'.join(exceptions)})" if exceptions else '') + f"({'|'.join(targets)})"
        rule = {'id': f"eaos.boundary.{a['name']}-not-{b['name']}", 'languages': ['python'], 'severity': 'ERROR',
                'message': f"{a['name']} may not import {b['name']}: the {ref['id']} reference allows "
                           f"{', '.join(a['allowed_dependencies']) or 'nothing'} (target-architecture.json).",
                'metadata': {'category': 'maintainability', 'source': 'EAOS target architecture'},
                'paths': {'include': [g.replace('/**', '/') if g.endswith('/**') else g for g in sources]},
                'patterns': [{'pattern-either': [{'pattern': 'import $M'}, {'pattern': 'from $M import $X'}]},
                             {'metavariable-regex': {'metavariable': '$M', 'regex': regex}}]}
        excluded = [g.replace('/**', '/') if g.endswith('/**') else g for g in narrower(a, ref)]
        if excluded: rule['paths']['exclude'] = excluded
        rules.append(rule)
    return rules


def _download(tool, binary):
    """Shell that fetches a pinned release and refuses it unless its sha256 matches the toolchain's."""
    spec = pin(tool)['install']
    name = spec['url'].rsplit('/', 1)[-1]
    fetch = f"curl -fsSL -o {name} {spec['url']}\necho \"{spec['sha256']}  {name}\" | sha256sum -c -\n"
    if spec['archive'] == 'binary': return fetch + f"sudo install -m 0755 {name} /usr/local/bin/{binary}\n"
    return fetch + f"tar -xzf {name} {spec.get('member', binary)}\nsudo install -m 0755 {spec.get('member', binary)} /usr/local/bin/{binary}\n"


def _node_setup(p):
    manager, steps = p['package_manager'], []
    if manager == 'bun':
        steps.append({'uses': uses('oven-sh/setup-bun')})
        install = 'bun install --frozen-lockfile'
    else:
        if manager == 'pnpm': steps.append({'uses': uses('pnpm/action-setup')})
        steps.append({'uses': uses('actions/setup-node'), 'with': {'node-version': 22}})
        install = {'pnpm': 'pnpm install --frozen-lockfile', 'yarn': 'yarn install --frozen-lockfile'}.get(
            manager, 'npm ci' if p['lockfile'] == 'package-lock.json' else 'npm install')
    steps.append({'name': 'Install dependencies', 'run': install})
    run = 'bun run' if manager == 'bun' else f'{manager} run' if manager in ('pnpm', 'yarn') else 'npm run'
    for script in ('build', 'test'):
        if script in p['scripts']: steps.append({'name': script.capitalize(), 'run': f'{run} {script}'})
    return steps


def _python_setup(p):
    steps = [{'uses': uses('actions/setup-python'), 'with': {'python-version': '3.12'}}]
    install = 'pip install -e .' if p['pyproject'] else 'pip install -r requirements.txt' if p['requirements'] else None
    if install: steps.append({'name': 'Install the project', 'run': install})
    if p['pytest']: steps.append({'name': 'Test', 'run': 'pip install pytest\npytest -q\n'})
    return steps


def workflow(p, ref):
    checkout = {'uses': uses('actions/checkout'), 'with': {'fetch-depth': 0}}
    test = [checkout] + (_node_setup(p) if p['js'] else _python_setup(p) if p['python'] else [])
    test.append({'name': 'Behaviour lock (the safety net EAOS wrote before any change)',
                 'if': "hashFiles('behavior-lock/playwright.config.ts') != ''",
                 'run': 'npx --yes playwright@%s install --with-deps chromium\nnpx --yes playwright@%s test --config behavior-lock/playwright.config.ts\n'
                        % (pin('playwright')['version'], pin('playwright')['version'])})
    semgrep_version = pin('semgrep')['version']
    security = [checkout,
                {'name': f"Trivy {pin('trivy')['version']}: vulnerabilities, secrets and misconfiguration",
                 'run': _download('trivy', 'trivy') + 'trivy fs --scanners vuln,secret,misconfig --severity HIGH,CRITICAL --exit-code 1 .\n'},
                {'name': f"OSV-Scanner {pin('osv-scanner')['version']}: known-vulnerable dependencies",
                 'run': _download('osv-scanner', 'osv-scanner') + 'osv-scanner scan source -r .\n'},
                {'uses': uses('actions/setup-python'), 'with': {'python-version': '3.12'}},
                {'name': f'Semgrep {semgrep_version} with the EAOS rules: new findings only on a pull request',
                 'env': {'BASE': '${{ github.event.pull_request.base.sha }}'},
                 'run': f'pip install semgrep=={semgrep_version}\n'
                        'semgrep scan --config semgrep/ --error --metrics=off ${BASE:+--baseline-commit "$BASE"}\n'}]
    if p['ci_or_iac']:
        security.append({'name': f"Checkov {pin('checkov')['version']}: CI and infrastructure as code",
                         'run': f"pip install checkov=={pin('checkov')['version']}\ncheckov -d . --quiet --compact\n"})
    for spec in p['openapi']:
        security.append({'name': f'Spectral: {spec}',
                         'run': "echo 'extends: [\"spectral:oas\"]' > .spectral.yaml\n"
                                f"npx --yes @stoplight/spectral-cli@{pin('spectral')['version']} lint {spec}\n"})
    architecture = [checkout]
    if p['js'] and ref:
        depcruise = f"npx --yes dependency-cruiser@{pin('dependency-cruiser')['version']} --config .dependency-cruiser.cjs" + \
                    (' --ts-config tsconfig.json' if p['tsconfig'] else '')
        architecture += [{'uses': uses('actions/setup-node'), 'with': {'node-version': 22}},
                         {'name': 'Install TypeScript for dependency-cruiser', 'run': 'npm install --no-save typescript@6.0.3'},
                         {'name': 'Target boundaries: new violations only',
                          'if': "hashFiles('.dependency-cruiser-known-violations.json') != ''",
                          'run': depcruise + ' --ignore-known .dependency-cruiser-known-violations.json src\n'},
                         {'name': 'Target boundaries: record the known violations first (see .dependency-cruiser.cjs)',
                          'if': "hashFiles('.dependency-cruiser-known-violations.json') == ''",
                          'run': depcruise + ' --output-type err-long src || echo "::warning::record .dependency-cruiser-known-violations.json to make this step a gate"\n'}]
    architecture += [{'uses': uses('actions/setup-python'), 'with': {'python-version': '3.12'}},
                     {'name': 'EAOS gate: fail only on findings the pinned baseline does not hold',
                      'if': "vars.EAOS_PACKAGE != '' && hashFiles('.eaos/baseline/baseline.json') != ''",
                      'env': {'EAOS_PACKAGE': '${{ vars.EAOS_PACKAGE }}'},
                      'run': 'pip install "$EAOS_PACKAGE"\nmkdir -p .eaos-report\ncp -r .eaos/baseline .eaos-report/\n'
                             'eaos audit . --out .eaos-report --gate new --no-site --exclude .eaos-report --exclude .eaos\n'}]
    return {'name': 'EAOS checks',
            'on': {'pull_request': {}, 'push': {'branches': ['main']}},
            'permissions': {'contents': 'read'},
            'concurrency': {'group': '${{ github.workflow }}-${{ github.ref }}', 'cancel-in-progress': True},
            'jobs': {'test': {'name': 'Build and test', 'runs-on': 'ubuntu-24.04', 'timeout-minutes': 30, 'steps': test},
                     'security': {'name': 'Security', 'runs-on': 'ubuntu-24.04', 'timeout-minutes': 30, 'steps': security},
                     'architecture': {'name': 'Architecture', 'runs-on': 'ubuntu-24.04', 'timeout-minutes': 30, 'steps': architecture}}}


def pre_commit(p):
    hooks = _pins()['hooks']
    repos = [{'repo': 'https://github.com/pre-commit/pre-commit-hooks', 'rev': hooks['https://github.com/pre-commit/pre-commit-hooks'],
              'hooks': [{'id': 'check-merge-conflict'}, {'id': 'check-added-large-files', 'args': ['--maxkb=1024']},
                        {'id': 'detect-private-key'}, {'id': 'check-json'}, {'id': 'check-yaml'}]},
             {'repo': 'https://github.com/semgrep/pre-commit', 'rev': hooks['https://github.com/semgrep/pre-commit'],
              'hooks': [{'id': 'semgrep', 'args': ['--config', 'semgrep/', '--error', '--metrics=off', '--skip-unknown-extensions']}]},
             {'repo': 'https://github.com/DavidAnson/markdownlint-cli2', 'rev': hooks['https://github.com/DavidAnson/markdownlint-cli2'],
              'hooks': [{'id': 'markdownlint-cli2'}]},
             {'repo': 'local', 'hooks': [{'id': 'trivy-secrets', 'name': 'Trivy: committed secrets', 'language': 'system',
                                          'entry': 'trivy fs --scanners secret --exit-code 1 --quiet .', 'pass_filenames': False}]}]
    return dump({'repos': repos}, 'Fast checks before every commit, written by EAOS. Install: pip install pre-commit && pre-commit install\n'
                                  'The trivy-secrets hook needs Trivy on PATH (https://trivy.dev).')


def renovate(p):
    return json.dumps({
        '$schema': 'https://docs.renovatebot.com/renovate-schema.json',
        'extends': ['config:recommended'],
        'timezone': 'UTC',
        'schedule': ['before 6am on monday'],
        'prConcurrentLimit': 5,
        'packageRules': [
            {'description': 'Minor and patch updates of stable packages, together, once a week',
             'matchUpdateTypes': ['minor', 'patch'], 'matchCurrentVersion': '!/^0/', 'groupName': 'minor and patch updates'},
            {'description': 'Actions stay pinned to a full commit', 'matchManagers': ['github-actions'], 'pinDigests': True}],
        'vulnerabilityAlerts': {'schedule': ['at any time'], 'labels': ['security']},
        'osvVulnerabilityAlerts': True,
        'lockFileMaintenance': {'enabled': True, 'schedule': ['before 6am on monday']},
    }, indent=2) + '\n'


def write(report):
    report = Path(report)
    p = profile(report)
    if p['root'] is None: return []
    ref = reference(p)
    folder = report / 'handover'
    (folder / '.github/workflows').mkdir(parents=True, exist_ok=True)
    (folder / 'semgrep').mkdir(parents=True, exist_ok=True)
    items = []
    workflow_path = folder / '.github/workflows/eaos.yml'
    workflow_path.write_text(dump(workflow(p, ref), 'Written by EAOS from the audit of this project. Copy handover/ into the repository root.\n'
                                                   'Set the repository variable EAOS_PACKAGE (a pip requirement for EAOS) to enable the EAOS gate.'),
                             encoding='utf-8')
    items.append(Emitted('handover/.github/workflows/eaos.yml', 'actionlint', ('actionlint', '-shellcheck=', '-pyflakes=', '{path}')))
    (folder / '.pre-commit-config.yaml').write_text(pre_commit(p), encoding='utf-8')
    items.append(Emitted('handover/.pre-commit-config.yaml', 'pre-commit', ('pre-commit', 'validate-config', '{path}')))
    (folder / 'renovate.json').write_text(renovate(p), encoding='utf-8')
    items.append(Emitted('handover/renovate.json', 'renovate', ('renovate-config-validator', '--strict', '{path}')))
    if p['js'] and ref:
        (folder / '.dependency-cruiser.cjs').write_text(depcruise_config(ref), encoding='utf-8')
        items.append(Emitted('handover/.dependency-cruiser.cjs', 'dependency-cruiser',
                             ('depcruise', '--config', '{path}', '--output-type', 'err', '{path}')))
    for rules in sorted((RULES / 'semgrep').glob('*.yml')):
        shutil.copy(rules, folder / 'semgrep' / rules.name)
    boundaries = semgrep_boundaries(ref) if (p['python'] and ref) else []
    if boundaries:
        (folder / 'semgrep/boundaries.yml').write_text(dump({'rules': boundaries}, f"Boundary rules of the target architecture ({ref['id']}), written by EAOS."),
                                                       encoding='utf-8')
    # One Semgrep run judges the whole folder, as CI and pre-commit load it: a start-up of seconds per file adds up.
    items.append(Emitted('handover/semgrep/', 'semgrep', ('semgrep', '--validate', '--metrics=off', '--config', '{path}')))
    return items
