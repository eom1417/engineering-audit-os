"""What EAOS promises its outside users, read from the running code: every CLI command and MCP tool as declared, how they
answer on an empty project and on a saved one, and that reading a saved project leaves its state as it was.

tools/public_contract/lock.py runs this in a process of its own, with a home, a PATH and an environment of its own, so a
machine's tools and accounts never change the answer; alone it means nothing. No product code is changed or called
for its private parts: the parser is taken where `eaos.interfaces.cli.main` parses, the tools from `list_tools`.
`--save-project` freezes a real check of tests/fixtures/saved-project/project under the running version's folder.
"""
import argparse
import asyncio
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest import mock

SAVED = Path(__file__).resolve().parents[2] / 'tests' / 'fixtures' / 'saved-project'
DATE = '2026-01-01T00:00:00Z'    # the saved project's one commit keeps its id, so the frozen state still names it
TOKENS = ('{{PROJECT}}', '{{WORKSPACE}}', '{{OUTPUT}}', '{{PYTHON}}')   # a report names its places and the Python that ran it
# What a frozen report does not need to be read, and only makes the fixture heavy.
UNSAVED = ('technical/human', 'technical/progress', 'technical/behavior-lock', 'technical/run-progress.jsonl', 'REPORT.html')

# Tools no contract run may call, with why; a new tool that reads or writes must be named here or called below.
NOT_CALLED = {
    'open_studio': 'starts a server',
    'open_report': 'rewrites the report and opens a browser, though declared read-only',
    'ask': 'asks the assistant',
    'tools_find': 'searches the web',
    'build_read': 'writes mode=build into the state, though declared read-only',
}
EMPTY_WRITING = (
    'accept', 'act', 'build_edit', 'build_finish', 'build_skip', 'build_start', 'context_make', 'design_choose', 'design_make',
    'extend_plan', 'fix_abandon', 'fix_edit', 'fix_finish', 'fix_skip', 'fix_start', 'reorder', 'safety_net', 'undo')
# A writing tool that succeeds on a real batch or job: the existing test that drives it, or why nothing locks it yet.
WRITING_ELSEWHERE = {
    'audit': 'tests/guards/test_journey.py', 'blueprint_start': 'tests/journeys/test_blueprint.py',
    'blueprint_spec': 'tests/journeys/test_blueprint.py', 'blueprint_design': 'tests/journeys/test_blueprint.py',
    'choose_branch': 'tests/interfaces/test_mcp.py', 'note': 'tests/interfaces/test_mcp.py',
    'rule': 'tests/analysis/test_person_rules.py', 'runs': 'tests/interfaces/test_parity.py',
    'waiting': 'tests/interfaces/test_parity.py', 'branch_change': 'tests/interfaces/test_mcp.py',
    'check_changed': 'not locked: it reads a change the fixture does not have',
    'extend_start': 'not locked: it starts a job', 'logic_flaws': 'not locked: it asks the assistant',
    'project_map': 'not locked: it builds the map with a pinned tool', 'replan_ideal': 'not locked: it asks the assistant',
    'run_nodes': 'not locked: it asks the assistant', 'run_setup': 'not locked: it runs the app',
    'run_try': 'not locked: it runs the app', 'sign_in_forget': 'not locked: it needs a saved sign-in',
    'tools_add': 'not locked: it installs a tool', 'tools_check': 'not locked: it reads the installed tools',
}
UNACCOUNTED = 'UNACCOUNTED: name it in NOT_CALLED, EMPTY_WRITING or WRITING_ELSEWHERE of tools/public_contract/capture.py'
EMPTY_OF = {'array': [], 'object': {}, 'integer': 0, 'boolean': False}
SAVED_ARGUMENTS = {'finding': {'id': 'TASK-001'}, 'report_file': {'name': 'START-HERE.md'}, 'impact': {'target': 'app/prices.py'}}
EMPTY_CLI = ([], ['--version'], ['--help'], ['nosuch'], ['status'], ['status', '--lang', 'xx'], ['status', '{missing}'], ['problem'],
             ['facts'], ['facts', '{missing}', '--out', '{missing}'], ['decided'], ['policy'], ['show', 'NOPE'])
SAVED_CLI = (['status'], ['problems', '--project', '.'], ['history', '--project', '.'], ['runs', '--project', '.'],
             ['plan', '--project', '.'], ['usage', '--project', '.'], ['rules', 'list', '--project', '.'],
             ['waiting', '--project', '.'])


def _plain(value):
    if callable(value): return '<callable>'
    if isinstance(value, (str, int, float, bool, type(None))): return value
    return [_plain(item) for item in value] if isinstance(value, (list, tuple)) else type(value).__name__


def _argument(action):
    return {'dest': action.dest, 'flags': sorted(action.option_strings), 'nargs': action.nargs, 'default': _plain(action.default),
            'choices': None if action.choices is None else sorted(map(str, action.choices)), 'required': bool(action.required),
            'kind': type(action).__name__.lstrip('_'), 'type': getattr(action.type, '__name__', None)}


def _walk(parser, path, out):
    subparsers = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    own = [a for a in parser._actions if not isinstance(a, (argparse._SubParsersAction, argparse._HelpAction))]
    out[' '.join(path) or '<root>'] = sorted((_argument(a) for a in own), key=lambda row: (row['dest'], row['flags']))
    for sub in subparsers:
        for name, child in sub.choices.items(): _walk(child, [*path, name], out)
    return out


class _Parsed(Exception):
    def __init__(self, parser): self.parser = parser


def cli_declared():
    """Every command with its arguments, taken where main() parses, so nothing runs and nothing in the CLI had to change."""
    from eaos.interfaces import cli

    def taken(parser, *_, **__): raise _Parsed(parser)
    with mock.patch.object(argparse.ArgumentParser, 'parse_args', taken):
        try: cli.main([])
        except _Parsed as parsed: return _walk(parsed.parser, [], {})
    raise RuntimeError('eaos.interfaces.cli.main never parsed')


def server():
    from eaos.interfaces.mcp_server.govern import every
    from eaos.interfaces.mcp_server.server import build
    return build(every)


def mcp_declared(mcp):
    tools = {}
    for tool in asyncio.run(mcp.list_tools()):
        hints = tool.annotations.model_dump(exclude_none=True) if tool.annotations else {}
        tools[tool.name] = {'input': tool.input_schema, 'annotations': hints}
    return {'tools': tools, 'prompts': sorted(prompt.name for prompt in asyncio.run(mcp.list_prompts()))}


def shape(value, depth=3):
    """A value's form: keys and kinds to three levels, an array by its first item. The values themselves are not the contract."""
    if isinstance(value, dict) and depth: return {key: shape(item, depth - 1) for key, item in sorted(value.items())}
    if isinstance(value, list) and value and depth: return {'[]': shape(value[0], depth - 1)}
    if isinstance(value, list): return 'array'
    return 'null' if value is None else type(value).__name__


def answer(mcp, name, arguments):
    """A tool's answer as its caller reads it: the JSON inside the text every tool returns, or the refusal raised."""
    try: return shape(json.loads(asyncio.run(mcp.call_tool(name, arguments)).content[0].text))
    except Exception as problem: return {'raised': type(problem).__name__}


def command(argv, missing):
    """A CLI line's exit code and whether it said anything; the words are not the contract."""
    from eaos.interfaces import cli
    out, err = io.StringIO(), io.StringIO()
    words = [str(missing) if word == '{missing}' else word for word in argv]
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try: code = cli.main(words)
        except SystemExit as stopped: code = stopped.code
    return {'exit': str(code or 0), 'says': 'yes' if out.getvalue() or err.getvalue() else 'no'}


def _git(project, *argv):
    env = {**os.environ, 'GIT_AUTHOR_DATE': DATE, 'GIT_COMMITTER_DATE': DATE}
    subprocess.run(['git', '-C', str(project), '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', *argv],
                   check=True, capture_output=True, env=env)


def new_project(where):
    """The frozen project as a repository of one commit, the same commit on every computer."""
    shutil.copytree(SAVED / 'project', where)
    _git(where, 'init', '-q', '-b', 'main')
    _git(where, 'add', '-A')
    _git(where, 'commit', '-qm', 'the saved project')
    return where


def reading_tools(mcp):
    declared = mcp_declared(mcp)['tools']
    return {name: tool for name, tool in declared.items() if tool['annotations'].get('read_only_hint') and name not in NOT_CALLED}


def _required(tool, known=None):
    """The arguments a tool cannot go without, of the kinds it declares and naming nothing, so it answers rather than the schema."""
    kinds = tool['input'].get('properties', {})
    made = {name: EMPTY_OF.get(kinds.get(name, {}).get('type'), 'nothing-such') for name in tool['input'].get('required', [])}
    return made | (known or {})


def empty_behaviour(mcp, scratch):
    """Every reading tool, and every writing tool that must refuse, on a project EAOS has never checked; the CLI's failures."""
    project = new_project(scratch / 'empty' / 'shop')
    os.chdir(project)
    declared = mcp_declared(mcp)['tools']
    rows = {f'empty:mcp:{name}': answer(mcp, name, _required(tool)) for name, tool in reading_tools(mcp).items()}
    rows |= {f'empty:writing:{name}': answer(mcp, name, _required(declared[name])) for name in EMPTY_WRITING if name in declared}
    rows['empty:missing-argument:fix_skip'] = answer(mcp, 'fix_skip', {})
    rows['empty:unknown-tool'] = answer(mcp, 'nothing_such', {})
    rows |= {'empty:cli:' + ' '.join(argv): command(argv, scratch / 'none') for argv in EMPTY_CLI}
    return rows


def _copy_filled(source, target, values):
    for path in source.rglob('*'):
        if path.is_dir(): continue
        data = path.read_bytes()
        for token, value in zip(TOKENS, values): data = data.replace(token.encode(), str(value).encode())
        (target / path.relative_to(source)).parent.mkdir(parents=True, exist_ok=True)
        (target / path.relative_to(source)).write_bytes(data)


def saved_behaviour(mcp, frozen, scratch):
    """A project a past version saved, read by this one: every reading tool and CLI line, and its state left as it was."""
    from eaos.core.project.places import workspace
    project = new_project(scratch / frozen.name / 'shop')
    os.chdir(project)
    room, output = workspace(project), Path(os.environ['EAOS_OUTPUT']) / frozen.name
    _copy_filled(frozen / 'workspace', room, (project, room, output, sys.executable))
    _copy_filled(frozen / 'output', output, (project, room, output, sys.executable))
    before = hashlib.sha256((room / 'state.json').read_bytes()).hexdigest()
    name = f'saved-{frozen.name}'
    rows = {f'{name}:mcp:{tool}': answer(mcp, tool, _required(row, SAVED_ARGUMENTS.get(tool)))
            for tool, row in reading_tools(mcp).items()}
    rows |= {f'{name}:cli:' + ' '.join(argv): command(argv, scratch / 'none') for argv in SAVED_CLI}
    kept = before == hashlib.sha256((room / 'state.json').read_bytes()).hexdigest()
    rows[f'{name}:reading-leaves-the-state'] = {'unchanged': 'yes' if kept else 'no'}
    return rows


def accounting(tools):
    """How each tool is held: called here, or by the test that drives it, or why nothing holds it yet; a new one must say."""
    def how(name, tool):
        if name in NOT_CALLED: return f'not called: {NOT_CALLED[name]}'
        if tool['annotations'].get('read_only_hint'): return 'called on an empty and on a saved project'
        if name in EMPTY_WRITING: return 'called on an empty project; its success is not locked'
        return WRITING_ELSEWHERE.get(name, UNACCOUNTED)
    return {name: how(name, tool) for name, tool in tools.items()}


def capture(scratch):
    mcp = server()
    behaviour = empty_behaviour(mcp, scratch)
    for frozen in sorted(path for path in SAVED.iterdir() if path.name[0].isdigit()):
        behaviour |= saved_behaviour(mcp, frozen, scratch)
    declared = mcp_declared(mcp)
    return {'cli': cli_declared(), 'mcp': declared, 'behaviour': behaviour, 'accounting': accounting(declared['tools'])}


def save_project(scratch):
    """A real check of the frozen project, no assistant and no external tool, kept under this version's folder."""
    from eaos import __version__
    from eaos.core.project.places import workspace
    from eaos.core.system.version_info import digest
    from eaos.journeys import agent_tools, guided
    from eaos.pipeline.runners import by_rules
    from eaos.pipeline.stages import SkipStage

    def no_engines(context): raise SkipStage('the frozen project runs no external tool', code='engines_not_requested')
    project = new_project(scratch / 'shop')
    os.chdir(project)
    with mock.patch.dict(by_rules.RUNNERS, engines=no_engines, architecture=no_engines), \
            mock.patch.object(guided, 'tools_for_check', return_value={}):
        agent_tools.state_of(str(project))
        agent_tools.choose_branch('main', str(project), 'the saved project')
        agent_tools._audit_job(str(project), {}, None)
    room, output = workspace(project), Path(os.environ['EAOS_OUTPUT']) / project.name
    made_by, places = digest(), (project, room, output, sys.executable)
    _freeze(room, SAVED / __version__ / 'workspace', places, ('runs', 'jobs', 'logs', 'runtime', 'rules.lock', 'state.lock'), made_by)
    _freeze(output, SAVED / __version__ / 'output', places, UNSAVED, made_by)


def _freeze(source, target, values, left_out, made_by):  # limits: parameters -- a private step of save_project, called twice
    """A folder of the check kept with its places as tokens and the fingerprint of the code that made it worn off, so that
    every EAOS reads it as an older one's: it is, from the next change on, and the answer must not turn on that change."""
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source).as_posix()
        if path.is_dir() or any(relative == skip or relative.startswith(skip + '/') for skip in left_out): continue
        data = path.read_bytes()
        for token, value in zip(TOKENS, values): data = data.replace(str(value).encode(), token.encode())
        data = data.replace(made_by.encode(), b'an-older-version')
        (target / relative).parent.mkdir(parents=True, exist_ok=True)
        (target / relative).write_bytes(data)


if __name__ == '__main__':
    place = Path(os.environ['EAOS_CONTRACT_SCRATCH'])
    if '--save-project' in sys.argv: save_project(place)
    else: json.dump(capture(place), sys.stdout, ensure_ascii=False, sort_keys=True)
