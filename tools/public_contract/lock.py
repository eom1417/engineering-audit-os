"""The lock on what EAOS promises its outside users: the CLI and MCP tools as declared, how they answer, and saved projects
still read. tests/guards/test_public_contract.py holds every change to it.

    python tools/public_contract/lock.py                 what differs from the lock (tests/fixtures/contract/); 1 on a break
    python tools/public_contract/lock.py --record        writes additions into the lock; refused while anything breaks
    python tools/public_contract/lock.py --save-project  freezes a real check under tests/fixtures/saved-project/<this version>
    python tools/public_contract/lock.py --accept-break "<why>" --approved-by "<who, where>"
                                                         a break the maintainers agreed to: kept with its reason, in CHANGELOG.md too

A break takes something from a caller who relies on it today: a command, tool, argument, choice or answer's key gone, a new
requirement, a narrower kind, another default or exit code, a read-only tool that writes. An addition takes nothing: it is
recorded so that it is held from then on. Words (descriptions, help, messages) and values are not the contract: the golden
trial reads those. Nothing here runs in the product: tools/public_contract/capture.py reads it from outside.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / 'tests' / 'fixtures' / 'contract'
CAPTURE = Path(__file__).with_name('capture.py')
PARTS = ('cli', 'mcp', 'behaviour', 'accounting')
ACCEPTED = 'accepted-breaks.json'
HINTS = ('read_only_hint', 'destructive_hint', 'open_world_hint')


class Refused(Exception):
    """The lock was not written: what it would have hidden is in the message."""


class Found:
    """What a comparison found, in the words a person reads."""

    def __init__(self):
        self.breaks, self.additions = [], []

    def broke(self, text): self.breaks.append(text)

    def added(self, text): self.additions.append(text)


def _kinds(schema):
    if 'anyOf' in schema: return {kind for option in schema['anyOf'] for kind in _kinds(option)}
    kind = schema.get('type', 'any')
    if kind == 'array': return {f"array<{','.join(sorted(_kinds(schema.get('items', {}))))}>"}
    return set(kind) if isinstance(kind, list) else {kind}


def _enum(schema):
    """The only values a parameter takes, or None when it takes any of its kind (null is no value of its own)."""
    if 'enum' in schema: return set(schema['enum'])
    options = [option for option in schema.get('anyOf', ()) if option.get('type') != 'null']
    limits = [_enum(option) for option in options]
    return set().union(*limits) if limits and None not in limits else None


def _values(old, new, where, found):
    before, after = _enum(old), _enum(new)
    if after is None: return
    if before is None or before - after: found.broke(f'{where}: fewer values accepted')
    elif after - before: found.added(f'{where}: more values accepted')


def _parameter(old, new, where, found):
    if 'any' not in _kinds(new) and not _kinds(old) <= _kinds(new):
        found.broke(f'{where}: kind narrowed from {sorted(_kinds(old))} to {sorted(_kinds(new))}')
    elif _kinds(new) - _kinds(old):
        found.added(f'{where}: kind widened')
    if 'default' in old and 'default' in new and old['default'] != new['default']: found.broke(f'{where}: default changed')
    _values(old, new, where, found)


def _tool_input(old, new, where, found):
    before, after = old.get('properties', {}), new.get('properties', {})
    wanted_before, wanted_after = set(old.get('required', [])), set(new.get('required', []))
    for name, schema in before.items():
        if name in after: _parameter(schema, after[name], f'{where}.{name}', found)
        else: found.broke(f'{where}: parameter {name} removed')
    for name in after.keys() - before.keys():
        (found.broke if name in wanted_after else found.added)(f'{where}: new {"required" if name in wanted_after else "optional"} parameter {name}')
    for name in (wanted_after - wanted_before) & before.keys(): found.broke(f'{where}.{name}: optional became required')
    for name in (wanted_before - wanted_after) & after.keys(): found.added(f'{where}.{name}: required became optional')


def _mcp(old, new, found):
    for name, tool in old['tools'].items():
        now = new['tools'].get(name)
        if now is None:
            found.broke(f'MCP tool {name} removed')
            continue
        _tool_input(tool['input'], now['input'], name, found)
        for hint in HINTS:
            if tool['annotations'].get(hint) != now['annotations'].get(hint): found.broke(f'{name}: {hint} changed')
    for name in new['tools'].keys() - old['tools'].keys(): found.added(f'MCP tool {name} added')
    for name in set(old['prompts']) - set(new['prompts']): found.broke(f'MCP prompt {name} removed')
    for name in set(new['prompts']) - set(old['prompts']): found.added(f'MCP prompt {name} added')


def _by_flag(rows):
    return {flag: row for row in rows for flag in (row['flags'] or ['@' + row['dest']])}


def _choices(old, new, where, found):
    before, after = old['choices'], new['choices']
    if after is not None and (before is None or set(before) - set(after)): found.broke(f'{where}: fewer choices accepted')
    elif before is not None and (after is None or set(after) - set(before)): found.added(f'{where}: more choices accepted')


def _argument(old, new, where, found):
    for field in ('nargs', 'kind', 'dest', 'type', 'default'):
        if old[field] != new[field]: found.broke(f'{where}: {field} changed')
    if new['required'] and not old['required']: found.broke(f'{where}: became required')
    if old['required'] and not new['required']: found.added(f'{where}: became optional')
    _choices(old, new, where, found)


def _cli(old, new, found):
    for command, rows in old.items():
        if command not in new:
            found.broke(f'CLI command {command} removed')
            continue
        before, after = _by_flag(rows), _by_flag(new[command])
        for flag, row in before.items():
            if flag in after: _argument(row, after[flag], f'{command} {flag}', found)
            else: found.broke(f'{command}: argument {flag} removed')
        for flag in after.keys() - before.keys():
            required = after[flag]['required']
            (found.broke if required else found.added)(f'{command}: new {"required" if required else "optional"} argument {flag}')
    for command in new.keys() - old.keys(): found.added(f'CLI command {command} added')


def _shape(old, new, where, found):
    if isinstance(old, dict) and isinstance(new, dict):
        for key, value in old.items():
            if key in new: _shape(value, new[key], f'{where}.{key}', found)
            else: found.broke(f'{where}: answer lost {key}')
        for key in new.keys() - old.keys(): found.added(f'{where}: answer gained {key}')
    elif old != new:
        found.broke(f'{where}: {json.dumps(old)[:60]} became {json.dumps(new)[:60]}')


def _behaviour(old, new, found):
    for case, answer in old.items():
        if case in new: _shape(answer, new[case], case, found)
        else: found.broke(f'{case}: no longer answered')
    for case in new.keys() - old.keys(): found.added(f'{case}: new case')


def compare(old, new):
    """(what breaks a caller of `old`, what `new` only adds), each sorted."""
    found = Found()
    _cli(old['cli'], new['cli'], found)
    _mcp(old['mcp'], new['mcp'], found)
    _behaviour(old['behaviour'], new['behaviour'], found)
    return sorted(found.breaks), sorted(found.additions)


def hermetic(scratch, root):
    """The environment of a capture: its own home and output, git alone on its PATH, nothing of this machine's or account's."""
    (scratch / 'bin').mkdir(parents=True)
    (scratch / 'home').mkdir()
    (scratch / 'work').mkdir()
    os.symlink(shutil.which('git'), scratch / 'bin' / 'git')
    return {'PATH': str(scratch / 'bin'), 'HOME': str(scratch / 'home'), 'LANG': 'C.UTF-8', 'PYTHONSAFEPATH': '1', 'PYTHONPATH': str(root),
            'PYTHONDONTWRITEBYTECODE': '1', 'EAOS_HOME': str(scratch / 'eaos'), 'EAOS_OUTPUT': str(scratch / 'output'),
            'EAOS_ENGINE_TOOLS': str(scratch / 'tools'), 'EAOS_ASSISTANT': 'none', 'EAOS_ANSWER_SECONDS': '0',
            'EAOS_CONTRACT_SCRATCH': str(scratch / 'work')}


def capture(root=ROOT):
    """The contract of the code under `root`, read in a process of its own."""
    with tempfile.TemporaryDirectory(prefix='eaos-contract-') as scratch:
        done = subprocess.run([sys.executable, str(CAPTURE)], env=hermetic(Path(scratch).resolve(), root),
                              stdin=subprocess.DEVNULL, capture_output=True, text=True)
    if done.returncode: raise RuntimeError(f'the capture failed: {done.stderr[-800:]}')
    return json.loads(done.stdout)


def load(lock=LOCK):
    return {part: json.loads((lock / f'{part}.json').read_text(encoding='utf-8')) for part in PARTS}


def write(snapshot, lock=LOCK):
    lock.mkdir(parents=True, exist_ok=True)
    for part in PARTS:
        (lock / f'{part}.json').write_text(json.dumps(snapshot[part], ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')


def accepted(lock=LOCK):
    path = lock / ACCEPTED
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []


def record(new, lock=LOCK):
    """The lock made `new`, which may only add to it; a first lock has nothing to break."""
    breaks = compare(load(lock), new)[0] if (lock / 'cli.json').is_file() else []
    if breaks: raise Refused('breaks what callers rely on, so it is not recorded:\n  ' + '\n  '.join(breaks))
    silent = [name for name, how in new['accounting'].items() if how.startswith('UNACCOUNTED')]
    if silent: raise Refused(f'a tool says neither how it is held nor why not: {silent}')
    write(new, lock)


def accept_break(new, why, approved_by, lock=LOCK):
    """A break the maintainers agreed to, kept in the lock with its reason, who agreed and what it takes away."""
    if not (why or '').strip() or not (approved_by or '').strip(): raise Refused('a break needs its reason and who approved it')
    breaks = compare(load(lock), new)[0]
    if not breaks: raise Refused('nothing breaks: use --record')
    rows = [*accepted(lock), {'why': why.strip(), 'approved_by': approved_by.strip(), 'breaks': breaks}]
    write(new, lock)
    (lock / ACCEPTED).write_text(json.dumps(rows, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return breaks


def save_project():
    with tempfile.TemporaryDirectory(prefix='eaos-contract-') as scratch:
        subprocess.run([sys.executable, str(CAPTURE), '--save-project'], env=hermetic(Path(scratch).resolve(), ROOT), stdin=subprocess.DEVNULL, check=True)


def _option(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv[:-1] else None


def main():
    if '--save-project' in sys.argv: return save_project()
    new = capture()
    try:
        if '--accept-break' in sys.argv:
            accept_break(new, _option('--accept-break'), _option('--approved-by'))
            print('recorded with its reason; say it in CHANGELOG.md too')
            return 0
        if '--record' in sys.argv:
            record(new)
            print('recorded')
            return 0
    except Refused as refused:
        print(f'REFUSED: {refused}')
        return 1
    breaks, additions = compare(load(), new)
    for line in breaks: print('BREAK ', line)
    for line in additions: print('ADDED ', line)
    print('OK' if not breaks and not additions else f'{len(breaks)} breaks, {len(additions)} additions')
    return 1 if breaks else 0


if __name__ == '__main__':
    sys.exit(main())
