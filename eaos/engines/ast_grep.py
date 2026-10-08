"""ast-grep: EAOS's own structural rules over the project's syntax trees (eaos/rules/ast-grep).

The first rules record facts rather than judge: every React component with the name it is bound to
(`const VehicleCard = (...) => <jsx/>`, `function Dashboard() { return <jsx/> }`), and every `useEffect`
whose whole body is one state setter (derived state). A record becomes a measurement row (granularity
`symbol`) that later stages read; a rule whose metadata names a kind of the shared vocabulary becomes a
finding instead. Each rule sits beside its examples in rule-tests/, proved by `ast-grep test`.
"""
import json
import re
from pathlib import Path

from . import tool
from .contract import ERROR, KINDS, OBSERVED, SYMBOL, Capability, Report, finding, subject
from .process import run, which

NAME = 'ast-grep'
BINARY = 'ast-grep'
PINNED = tool.pinned(NAME)
RULES = Path(__file__).resolve().parent.parent / 'rules/ast-grep'
EXCLUDED = ('.git', 'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', '.next', 'vendor', 'coverage')
# A rule's metadata is written on one line (`metadata: {record: ..., kind: ...}`), so it is read without YAML.
METADATA_KIND = re.compile(r'^metadata:.*\bkind: (\w+)', re.M)
RULE_ID = re.compile(r'^id: (\S+)', re.M)


def rules():
    """(rule id, finding kind or None) for every rule in the pack."""
    out = []
    for path in sorted((RULES / 'rules').glob('*.yml')):
        for block in re.split(r'^---$', path.read_text(encoding='utf-8'), flags=re.M):
            found = RULE_ID.search(block)
            if not found: continue
            kind = METADATA_KIND.search(block)
            out.append((found.group(1), kind.group(1) if kind else None))
    return out


def capabilities():
    return [Capability(kind, rule, granularity=SYMBOL) for rule, kind in rules() if kind in KINDS]


def version():
    return tool.version(BINARY)


def records(lines):
    """The parsed matches of a `--json=stream` run, one JSON object per line."""
    return [json.loads(line) for line in lines.splitlines() if line.strip()]


def normalise(rows, found):
    """(metrics, findings, matches by rule) from ast-grep's matches."""
    metrics, findings, by_rule = [], [], {}
    for row in rows:
        rule, meta = row['ruleId'], row.get('metadata') or {}
        by_rule[rule] = by_rule.get(rule, 0) + 1
        captures = {name: value['text'] for name, value in ((row.get('metaVariables') or {}).get('single') or {}).items()}
        path, line = tool.relative(row['file']), row['range']['start']['line'] + 1
        symbol = captures.get('NAME') or captures.get('SETTER')
        if meta.get('kind') in KINDS:
            findings.append(finding(NAME, found, rule, meta['kind'], subject('symbol', f'{path}:{line}:{symbol}', path, line),
                                    row.get('message') or rule, raw_ref=f'{NAME}/ast-grep.jsonl'))
            continue
        metrics.append({'path': path, 'line': line, 'symbol': symbol, 'granularity': 'symbol',
                        'measurements': {'record': meta.get('record') or rule, 'rule': rule, 'form': meta.get('form'),
                                         'captures': dict(sorted(captures.items())),
                                         'end_line': row['range']['end']['line'] + 1}})
    return (sorted(metrics, key=lambda m: (m['path'], m['line'])), findings, dict(sorted(by_rule.items())))


def analyze(target, workdir, exclude=(), formats=None):
    declined = tool.declined(NAME, BINARY, target)
    if declined: return declined
    found = version()
    target = Path(target).resolve()
    output = Path(workdir) / NAME / 'ast-grep.jsonl'
    output.parent.mkdir(parents=True, exist_ok=True)
    globs = [argument for name in EXCLUDED + tuple(exclude) for argument in ('--globs', f'!**/{name}/**')]
    command = [which(BINARY), 'scan', '--config', str(RULES / 'sgconfig.yml'), '--json=stream', '--include-metadata',
               '--color', 'never', *globs, '.']
    code, out, error, seconds = run(command, cwd=target)
    if code and not out.strip():
        return Report(NAME, found, PINNED, ERROR, seconds=seconds, reason=error.strip()[-300:] or f'exit {code}')
    output.write_text(out, encoding='utf-8')
    metrics, findings, by_rule = normalise(records(out), found)
    by_record = {}
    for row in metrics:
        by_record[row['measurements']['record']] = by_record.get(row['measurements']['record'], 0) + 1
    return Report(NAME, found, PINNED, OBSERVED, seconds=seconds, raw=str(output), metrics=metrics, findings=findings,
                  coverage={'status': 'observed', 'rule_pack': 'eaos/rules/ast-grep', 'rules': len(rules()),
                            'matches_by_rule': by_rule, 'records': dict(sorted(by_record.items())),
                            'files_with_matches': len({row['path'] for row in metrics})},
                  evaluated={capability.kind: {'status': 'observed', 'granularity': SYMBOL} for capability in capabilities()})
