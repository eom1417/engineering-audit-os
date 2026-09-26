"""dependency-cruiser: the JavaScript and TypeScript import graph, its cycles, and the owner's boundaries as rules.

The rules are written into the work directory, never into the project: `no-circular` always, and one
`forbidden` rule per `deny` in the project's own eaos.policy.json when it declares layers. Cycles and
boundary breaches are findings, one per distinct cycle, on the runtime graph (a cycle through an
`import type` is erased by the compiler, so it is not reported); they are a witness beside EAOS's own graph and
enola, so agreement between them is what raises a claim.

Without a TypeScript compiler beside it, dependency-cruiser reads no .ts file and reports an empty,
clean graph. `eaos tools install` puts one there; a run that examined no module in a project that has
JavaScript or TypeScript is an error with the tool's own warning, never a clean result.
"""
import json
from pathlib import Path

from . import tool
from .contract import ERROR, FILE, OBSERVED, Report, finding, subject
from .process import run, which

NAME = 'dependency-cruiser'
BINARY = 'depcruise'
PINNED = tool.pinned(NAME)
SKIPPED = 'node_modules|dist|build|coverage|\\.next|vendor'


def capabilities():
    from .contract import Capability
    return [Capability('cycle', 'no-circular', granularity=FILE), Capability('boundary', 'policy.deny', granularity=FILE)]


def version():
    return tool.version(BINARY)


def glob_regex(pattern):
    """A path glob of eaos.policy.json (`src/ui/**`) as the regular expression dependency-cruiser matches."""
    out, index = '', 0
    while index < len(pattern):
        if pattern.startswith('**', index): out, index = out + '.*', index + 2
        elif pattern[index] == '*': out, index = out + '[^/]*', index + 1
        elif pattern[index] == '?': out, index = out + '[^/]', index + 1
        else: out, index = out + ('\\' + pattern[index] if pattern[index] in '.+()[]{}^$|\\' else pattern[index]), index + 1
    return '^' + out + ('$' if not pattern.endswith('**') else '')


def configuration(target):
    """The rule set: no-circular, plus one forbidden rule per deny in the project's eaos.policy.json."""
    rules = [{'name': 'no-circular', 'severity': 'error', 'from': {}, 'to': {'circular': True}}]
    policy = Path(target) / 'eaos.policy.json'
    declared = 0
    if policy.is_file():
        try: data = json.loads(policy.read_text(encoding='utf-8'))
        except ValueError: data = {}
        layers = data.get('layers') or {}
        for index, rule in enumerate(data.get('rules') or []):
            deny = rule.get('deny') or {}
            source, sink = layers.get(deny.get('from')), layers.get(deny.get('to'))
            if not source or not sink: continue
            rules.append({'name': f"policy-{index + 1}-{deny['from']}-to-{deny['to']}", 'severity': 'error',
                          'comment': rule.get('reason', ''),
                          'from': {'path': '|'.join(glob_regex(p) for p in source)},
                          'to': {'path': '|'.join(glob_regex(p) for p in sink)}})
            declared += 1
    return {'forbidden': rules, 'options': {'doNotFollow': {'path': 'node_modules'}, 'exclude': {'path': SKIPPED},
                                            # The runtime graph: a type-only import is erased by the compiler,
                                            # so a cycle through one does not exist when the code runs.
                                            'tsPreCompilationDeps': False}}, declared


def cycles(summary):
    """Every distinct cycle in a run, as (members in order, sorted key)."""
    out = {}
    for violation in summary.get('violations') or []:
        if violation.get('type') == 'cycle' or (violation.get('rule') or {}).get('name') == 'no-circular':
            members = [violation['from']] + [step['name'] for step in violation.get('cycle') or []]
            out.setdefault(tuple(sorted(set(members))), members)
    return out


def type_only_cycles(source, runtime_keys):
    """Cycles of the source graph the runtime graph does not have: they close only through `import type`."""
    return [' -> '.join(members) for key, members in sorted(cycles(source).items()) if key not in runtime_keys]


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    target = Path(target).resolve()
    workdir = Path(workdir) / NAME
    workdir.mkdir(parents=True, exist_ok=True)
    rules, declared = configuration(target)
    if exclude: rules['options']['exclude']['path'] += '|' + '|'.join(glob_regex(p).lstrip('^') for p in exclude)
    runs, seconds = {}, 0.0
    # Twice: the runtime graph gives the findings; the source graph (type imports kept) shows which cycles
    # exist only through `import type`: coupling a design should remove, but not a cycle when the code runs.
    for graph, keep_types in (('runtime', False), ('source', True)):
        rules['options']['tsPreCompilationDeps'] = keep_types
        config = workdir / f'rules-{graph}.json'
        config.write_text(json.dumps(rules, indent=1), encoding='utf-8')
        output = workdir / f'depcruise-{graph}.json'
        command = [which(BINARY), '.', '--config', str(config), '--output-type', 'json', '--output-to', str(output)]
        if (target / 'tsconfig.json').is_file(): command += ['--ts-config', 'tsconfig.json']
        # It exits with the number of error-level violations; a violation is a result, not a failure.
        code, _, error, spent = run(command, cwd=target)
        seconds += spent
        if not output.is_file():
            return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
        runs[graph] = json.loads(output.read_text(encoding='utf-8')).get('summary') or {}
    summary = runs['runtime']
    issues = [issue['name'] for issue in (summary.get('environment') or {}).get('issues') or []]
    if not summary.get('totalCruised'):
        return Report(NAME, found, PINNED, ERROR, seconds=seconds,
                      reason='no module was examined' + (f" ({', '.join(issues)})" if issues else ''))
    output = workdir / 'depcruise-runtime.json'
    findings, seen = [], set()
    for violation in summary.get('violations') or []:
        rule = (violation.get('rule') or {}).get('name', '')
        if violation.get('type') == 'cycle' or rule == 'no-circular':
            members = [violation['from']] + [step['name'] for step in violation.get('cycle') or []]
            key = tuple(sorted(set(members)))
            if key in seen: continue
            seen.add(key)
            findings.append(finding(NAME, found, 'no-circular', 'cycle', subject('module', ' -> '.join(key), key[0]),
                                    'import cycle: ' + ' -> '.join(members), raw_ref=f'{NAME}/depcruise-runtime.json',
                                    sites=[{'path': member, 'line': None} for member in key]))
        else:
            key = (rule, violation['from'], violation['to'])
            if key in seen: continue
            seen.add(key)
            findings.append(finding(NAME, found, rule, 'boundary', subject('module', violation['from'], violation['from']),
                                    f"{violation['from']} imports {violation['to']}, which {rule} forbids",
                                    raw_ref=f'{NAME}/depcruise-runtime.json',
                                    sites=[{'path': violation['from'], 'line': None}, {'path': violation['to'], 'line': None}]))
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, raw=str(output),
                  coverage={'status': 'observed', 'modules': summary.get('totalCruised'),
                            'dependencies': summary.get('totalDependenciesCruised'),
                            'policy_rules': declared, 'environment_issues': issues,
                            'graph': 'runtime imports; type-only imports are erased, as the compiler erases them',
                            'type_only_cycles': type_only_cycles(runs['source'], seen)},
                  evaluated={'cycle': {'status': 'observed', 'granularity': FILE},
                             'boundary': {'status': 'observed' if declared else 'not_declared', 'granularity': FILE}})
