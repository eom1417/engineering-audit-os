"""dependency-cruiser: the JavaScript and TypeScript import graph, its cycles, and the owner's boundaries as rules.

The rules are written into the work directory, never into the project: `no-circular` always, one `forbidden` rule per
`deny` in the project's own eaos.policy.json when it declares layers, and the rules of the layer map EAOS drew (M6.2:
each layer of the reference type barred from the layers it may not use, and browser code from reaching server code
through any chain of files). Cycles and
boundary breaches are findings, one per distinct cycle, on the runtime graph (a cycle through an
`import type` is erased by the compiler, so it is not reported); they are a witness beside EAOS's own graph and
enola, so agreement between them is what raises a claim.

Without a TypeScript compiler beside it, dependency-cruiser reads no .ts file and reports an empty,
clean graph. `eaos tools install` puts one there; a run that examined no module in a project that has
JavaScript or TypeScript is an error with the tool's own warning, never a clean result.
"""
import json
from pathlib import Path

from .. import tool
from ..contract import ERROR, FILE, OBSERVED, Report, finding, subject
from ..process import run, which

NAME = 'dependency-cruiser'
BINARY = 'depcruise'
PINNED = tool.pinned(NAME)
SKIPPED = 'node_modules|dist|build|coverage|\\.next|vendor'
LAYERS = 'layers-depcruise.json'


def capabilities():
    from ..contract import Capability
    return [Capability('cycle', 'no-circular', granularity=FILE), Capability('boundary', 'policy.deny', granularity=FILE)]


def version(): return tool.version(BINARY)


def glob_regex(pattern):
    """A path glob of eaos.policy.json (`src/ui/**`) as the regular expression dependency-cruiser matches."""
    out, index = '', 0
    while index < len(pattern):
        if pattern.startswith('**', index): out, index = out + '.*', index + 2
        elif pattern[index] == '*': out, index = out + '[^/]*', index + 1
        elif pattern[index] == '?': out, index = out + '[^/]', index + 1
        else: out, index = out + ('\\' + pattern[index] if pattern[index] in '.+()[]{}^$|\\' else pattern[index]), index + 1
    return '^' + out + ('$' if not pattern.endswith('**') else '')


def configuration(target, workdir=None):
    """The rule set: no-circular, one forbidden rule per deny in the project's eaos.policy.json, and the layer map's rules
    (LAYERS, written by the layers stage beside the engines' folder: eaos/analysis/layers/boundaries.py)."""
    denied = _policy_rules(Path(target) / 'eaos.policy.json') + _layer_rules(workdir)
    rules = [{'name': 'no-circular', 'severity': 'error', 'from': {}, 'to': {'circular': True}}] + denied
    declared = len(denied)
    return {'forbidden': rules, 'options': {'doNotFollow': {'path': 'node_modules'}, 'exclude': {'path': SKIPPED},
                                            # The runtime graph: a type-only import is erased by the compiler,
                                            # so a cycle through one does not exist when the code runs.
                                            'tsPreCompilationDeps': False}}, declared


def _policy_rules(policy):
    """A forbidden rule per `deny` of eaos.policy.json whose two layers are declared."""
    data = _policy(policy)
    layers, rules = data.get('layers') or {}, []
    for index, rule in enumerate(data.get('rules') or []):
        deny = rule.get('deny') or {}
        source, sink = layers.get(deny.get('from')), layers.get(deny.get('to'))
        if not source or not sink: continue
        rules.append({'name': f"policy-{index + 1}-{deny['from']}-to-{deny['to']}", 'severity': 'error',
                      'comment': rule.get('reason', ''),
                      'from': {'path': '|'.join(glob_regex(p) for p in source)},
                      'to': {'path': '|'.join(glob_regex(p) for p in sink)}})
    return rules


def _layer_rules(workdir):
    """The rules the layer map wrote for this check, or none."""
    path = Path(workdir) / LAYERS if workdir else None
    if not (path and path.is_file()): return []
    try: return json.loads(path.read_text(encoding='utf-8'))
    except ValueError: return []


def _policy(policy):
    """What eaos.policy.json declares; {} when there is none or it is not JSON."""
    if not policy.is_file(): return {}
    try: return json.loads(policy.read_text(encoding='utf-8'))
    except ValueError: return {}


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


def _cruise(target, workdir, rules, graph, keep_types):
    """(summary, seconds, failure) of one run on the runtime or the source graph; failure is '' when it wrote its output."""
    rules['options']['tsPreCompilationDeps'] = keep_types
    config = workdir / f'rules-{graph}.json'
    config.write_text(json.dumps(rules, indent=1), encoding='utf-8')
    output = workdir / f'depcruise-{graph}.json'
    command = [which(BINARY), '.', '--config', str(config), '--output-type', 'json', '--output-to', str(output)]
    if (target / 'tsconfig.json').is_file(): command += ['--ts-config', 'tsconfig.json']
    # It exits with the number of error-level violations; a violation is a result, not a failure.
    code, _, error, spent = run(command, cwd=target)
    if not output.is_file(): return None, spent, error.strip()[-300:] or f'exit {code}'
    return json.loads(output.read_text(encoding='utf-8')).get('summary') or {}, spent, ''


def _violation(found, violation):
    """(key, finding) of one violation: an import cycle keyed by its members, or a forbidden import by its rule."""
    rule = (violation.get('rule') or {}).get('name', '')
    if violation.get('type') == 'cycle' or rule == 'no-circular':
        members = [violation['from']] + [step['name'] for step in violation.get('cycle') or []]
        key = tuple(sorted(set(members)))
        return key, finding(NAME, found, 'no-circular', 'cycle', subject('module', ' -> '.join(key), key[0]),
                            'import cycle: ' + ' -> '.join(members), raw_ref=f'{NAME}/depcruise-runtime.json',
                            sites=[{'path': member, 'line': None} for member in key])
    return (rule, violation['from'], violation['to']), finding(
        NAME, found, rule, 'boundary', subject('module', violation['from'], violation['from']),
        f"{violation['from']} imports {violation['to']}, which {rule} forbids", raw_ref=f'{NAME}/depcruise-runtime.json',
        sites=[{'path': violation['from'], 'line': None}, {'path': violation['to'], 'line': None}])


def _findings(found, summary):
    """(findings, keys seen): one finding per distinct cycle or forbidden import of the runtime graph."""
    findings, seen = [], set()
    for violation in summary.get('violations') or []:
        key, made = _violation(found, violation)
        if key in seen: continue
        seen.add(key)
        findings.append(made)
    return findings, seen


def analyze(target, workdir, exclude=(), formats=None):
    declined, found = tool.started(NAME, BINARY, target)
    if declined: return declined
    target = Path(target).resolve()
    rules, declared = configuration(target, workdir)
    workdir = tool.folder(workdir, NAME)
    if exclude: rules['options']['exclude']['path'] += '|' + '|'.join(glob_regex(p).lstrip('^') for p in exclude)
    runs, seconds = {}, 0.0
    # Twice: the runtime graph gives the findings; the source graph (type imports kept) shows which cycles
    # exist only through `import type`: coupling a design should remove, but not a cycle when the code runs.
    for graph, keep_types in (('runtime', False), ('source', True)):
        runs[graph], spent, failure = _cruise(target, workdir, rules, graph, keep_types)
        seconds += spent
        if failure: return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=failure)
    summary = runs['runtime']
    issues = _issues(summary)
    if not summary.get('totalCruised'):
        return Report(NAME, found, PINNED, ERROR, seconds=seconds,
                      reason='no module was examined' + (f" ({', '.join(issues)})" if issues else ''))
    output = workdir / 'depcruise-runtime.json'
    findings, seen = _findings(found, summary)
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, findings=findings, raw=str(output),
                  coverage={'status': 'observed', 'modules': summary.get('totalCruised'),
                            'dependencies': summary.get('totalDependenciesCruised'),
                            'policy_rules': declared, 'environment_issues': issues,
                            'graph': 'runtime imports; type-only imports are erased, as the compiler erases them',
                            'type_only_cycles': type_only_cycles(runs['source'], seen)},
                  evaluated={'cycle': {'status': 'observed', 'granularity': FILE},
                             'boundary': {'status': 'observed' if declared else 'not_declared', 'granularity': FILE}})


def _issues(summary):
    """The names of the problems dependency-cruiser met in the project's environment."""
    return [issue['name'] for issue in (summary.get('environment') or {}).get('issues') or []]
