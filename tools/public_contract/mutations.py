"""The proof that the lock of tools/public_contract/lock.py catches real changes: each mutation edits a copy of the product's own
code, the contract is read from that copy and compared with the lock. A break must be called one, an addition must not, and
a change of words or values is outside the contract. Run by hand when the lock's design changes (about a minute);
tests/guards/test_public_contract.py holds the comparison itself on every run. An anchor that no longer matches fails."""
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lock as public_contract  # noqa: E402  (beside this file)

FIX, SERVER, CLI, TOOL = 'interfaces/mcp_server/fix.py', 'interfaces/mcp_server/server.py', 'interfaces/cli.py', 'def fix_skip(card: str, reason: str, project: str | None = None)'
GOALS = "['onboarding','debugging','evolution','architecture']"
OUT = "q.add_argument('target');q.add_argument('--out',required=True)\n    q.add_argument('--lang',choices=['ar','en'],default='ar')"
READING = "@server.tool(annotations=reading, description='Where this project"
STATUS = "    result = status_of(project)\n"
SKIP = "    @server.tool(annotations=working, description='Leave a card of the open batch out"
# name, what the comparison must say (a break's or an addition's own words; None: neither), the file under eaos/, the text,
# what it becomes. A break found for another reason than the one named does not count.
MUTATIONS = (
    ('MCP tool removed', ('break', 'MCP tool fix_skip removed'), FIX, f"{TOOL} -> str:\n        return tools.fix_skip(card, reason, project)\n", 'DELETE-TOOL'),
    ('MCP parameter renamed', ('break', 'fix_skip: parameter card removed'), FIX, 'def fix_skip(card: str, reason: str, project: str | None = None) -> str:\n        return tools.fix_skip(card, reason, project)',
     'def fix_skip(card_id: str, reason: str, project: str | None = None) -> str:\n        return tools.fix_skip(card_id, reason, project)'),
    ('MCP optional became required', ('break', 'choose_branch.person_said: optional became required'), SERVER, "person_said: str = '', project", 'person_said: str, project'),
    ('MCP new required parameter', ('break', 'fix_skip: new required parameter why'), FIX, TOOL, 'def fix_skip(card: str, reason: str, why: str, project: str | None = None)'),
    ('MCP kind narrowed', ('break', 'status.project: kind narrowed'), SERVER, 'def status(project: str | None = None)', "def status(project: str = '.')"),
    ('MCP read-only tool writes', ('break', 'status: read_only_hint changed'), SERVER, READING, READING.replace('reading', 'working')),
    ('MCP answer lost a key', ('break', 'empty:mcp:status: answer lost next'), SERVER, STATUS, STATUS + "    result.pop('next', None)\n"),
    ('MCP error became an exception', ('break', 'empty:mcp:design: answer lost error'), SERVER, "        except LookupError as problem:\n            result = {'error': str(problem)}\n",
     '        except LookupError as problem:\n            raise\n'),
    ('MCP failure answered as success', ('break', 'empty:writing:fix_skip: answer lost error'), FIX, 'return tools.fix_skip(card, reason, project)', "return {'skipped': True}"),
    ('CLI command removed', ('break', 'CLI command facts removed'), CLI, '    deep_checks.commands(s)\n    args=p.parse_args(argv)',
     "    deep_checks.commands(s)\n    del s.choices['facts']\n    args=p.parse_args(argv)"),
    ('CLI flag removed', ('break', 'audit: argument --goal removed'), CLI, f"    q.add_argument('--goal',choices={GOALS},default='evolution')\n", ''),
    ('CLI default changed', ('break', 'audit --lang: default changed'), CLI, OUT, OUT.replace("default='ar'", "default='en'")),
    ('CLI choice removed', ('break', 'audit --goal: fewer choices accepted'), CLI, GOALS, GOALS.replace("'debugging',", '')),
    ('CLI new required argument', ('break', 'audit: new required argument --must'), CLI, OUT, OUT.replace("required=True)", "required=True);q.add_argument('--must',required=True)")),
    ('CLI exit code changed', ('break', '.exit: "2" became "1"'), CLI, "print(f'eaos: {e}',file=sys.stderr);return 2", "print(f'eaos: {e}',file=sys.stderr);return 1"),
    ('saved state written by a read', ('break', 'reading-leaves-the-state.unchanged'), SERVER, STATUS,
     STATUS + "    from ...core.project import state as _state\n    _saved = _state.current(project or '.')\n    _saved and _state.write(_saved)\n"),
    ('MCP new optional parameter', ('addition', 'fix_skip: new optional parameter note'), FIX, TOOL, "def fix_skip(card: str, reason: str, project: str | None = None, note: str = '')"),
    ('MCP new tool', ('addition', 'MCP tool brand_new added'), FIX, SKIP, "    @server.tool(annotations=reading, description='x')\n    @_answer\n    def brand_new(project: str | None = None) -> str:\n        return {}\n\n" + SKIP),
    ('CLI new optional flag', ('addition', 'audit: new optional argument --brand-new'), CLI, "q.add_argument('--goal',choices", "q.add_argument('--brand-new',action='store_true');q.add_argument('--goal',choices"),
    ('CLI new choice', ('addition', 'audit --goal: more choices accepted'), CLI, GOALS, GOALS.replace("'architecture'", "'architecture','extra'")),
    ('MCP answer gained a key', ('addition', 'empty:mcp:status: answer gained extra'), SERVER, STATUS, STATUS + "    result['extra'] = 1\n"),
    ('tool description reworded', None, FIX, 'Leave a card of the open batch out', 'Leave one card of the open batch out'),
    ('a value inside an answer changed (outside the contract)', None, SERVER, STATUS, STATUS + "    result['branch'] = 'another'\n"),
)


def _mutated(text, name, old, new):
    if old not in text: raise ValueError(f'{name}: its anchor is gone: {old[:60]}')
    if new != 'DELETE-TOOL': return text.replace(old, new, 1)
    start = text.rindex('    @server.tool(', 0, text.index(old))
    return text[:start] + text[text.index(old) + len(old):]


def _as_said(expected, breaks, additions):
    """Whether the comparison said what was expected, and only a break where a break was expected."""
    if expected is None: return not breaks and not additions
    kind, words = expected
    if kind == 'addition': return not breaks and any(words in line for line in additions)
    return any(words in line for line in breaks)


def _tried(tree, row):
    name, expected, relative, old, new = row
    path = tree / 'eaos' / relative
    text = path.read_text(encoding='utf-8')
    path.write_text(_mutated(text, name, old, new), encoding='utf-8')
    try: breaks, additions = public_contract.compare(public_contract.load(), public_contract.capture(tree))
    finally: path.write_text(text, encoding='utf-8')
    held = _as_said(expected, breaks, additions)
    print(f"{'ok  ' if held else 'MISS'} {name}: {len(breaks)} breaks, {len(additions)} additions; {(breaks or additions or ['-'])[0][:80]}")
    return held


def main():
    with tempfile.TemporaryDirectory(prefix='eaos-mutations-') as scratch:
        tree = Path(scratch)
        shutil.copytree(public_contract.ROOT / 'eaos', tree / 'eaos', ignore=shutil.ignore_patterns('__pycache__'))
        control = public_contract.compare(public_contract.load(), public_contract.capture(tree))
        print(f'control, no mutation: {len(control[0])} breaks, {len(control[1])} additions')
        held = sum(_tried(tree, row) for row in MUTATIONS) if control == ([], []) else 0
    print(f'{held} of {len(MUTATIONS)} as expected')
    return 0 if held == len(MUTATIONS) else 1


if __name__ == '__main__':
    sys.exit(main())
