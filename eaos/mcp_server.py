"""`eaos mcp`: EAOS inside the person's AI assistant, as MCP tools (docs/MCP.md).

The assistant drives: it checks the project, reads the evidence and the code, gets the app running in an
isolated copy, writes the fixes, and hands them over as a branch. EAOS gives it the evidence, the copy and the
gates (eaos/agent_tools.py). Long work is a job the assistant follows with `wait`. Registered for Claude Code
and Codex by `eaos assistant install`, which install.sh runs.
"""
import functools
import json

from . import __version__

INSTRUCTIONS = """EAOS (Engineering Audit OS) checks a whole software project, finds its structural, security and
performance problems with evidence, and fixes them safely: each fix is made in an isolated copy, checked (the
problem is gone, nothing broke, no endpoint disappeared, the project's own checks and every recorded screen still
pass) and handed over as a new git branch, eaos/wave-N. The person's current branch and files are never touched.

The person is usually not a developer. Speak to them in their language, in plain words, without jargon.
Work on your own until the job is done; do not come back to them between steps. Ask them only:
  1. once, before running their app and preparing fixes (run_setup gives the exact question);
  2. at the end, whether to take the branch in (accept) or throw it away (undo).

The whole way, in order (`status` always says the next tool):
  audit -> overview / findings / finding / structure / plan  (understand; explain the main problems simply)
  run_setup (after the person agrees) -> run_try until the app runs (you read the failure and the code, and
     propose the environment, commands, or a seed script that signs in; EAOS refuses anything unsafe)
  safety_net (records every screen before any change)
  fix_start -> for each card: finding + fix_read, then fix_edit (fix_skip only with a real reason) -> fix_finish
  then tell the person what changed and ask: accept or undo.
Long steps return a job: call `wait` with it until it is done (a check takes 5-30 minutes). Keep every feature,
route and behaviour when fixing: a fix that deletes what users reach is refused. Never invent results: report
what the tools returned."""

# Every capability of the guided way (eaos/guided.py STEPS and its commands), and the tool that gives it to the
# assistant. X8 counts those registered and exercised by tests/test_mcp.py.
CAPABILITIES = {'where things stand': 'status', 'check the project': 'audit', 'follow long work': 'wait',
                'read the evidence': 'finding', 'run the app': 'run_try', 'record the screens': 'safety_net',
                'fix a card': 'fix_edit', 'hand fixes over': 'fix_finish', 'accept': 'accept', 'undo': 'undo'}


def _answer(function):
    """A tool's dict as JSON text; an error as the reason and what to do, never a bare traceback."""
    @functools.wraps(function)
    def call(*args, **kwargs):
        from .guided import explain
        try:
            result = function(*args, **kwargs)
        except LookupError as problem:
            result = {'error': str(problem)}
        except Exception as problem:            # every failure reaches the assistant as words it can act on
            known = explain(problem)
            result = {'error': f'{type(problem).__name__}: {problem}'[:2000],
                      **({'what_now': known['en']['fix'] + ' ' + ' '.join(known['en']['commands'])} if known['id'] != 'unknown' else {})}
        return json.dumps(result, ensure_ascii=False, indent=1, default=str)
    return call


def build():
    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations
    from . import agent_tools as tools

    server = MCPServer(name='eaos', title='Engineering Audit OS', version=__version__, instructions=INSTRUCTIONS)
    reading = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
    working = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    project_doc = 'The project folder (default: the folder the assistant was opened in).'

    @server.tool(annotations=reading, description='Where this project is in the EAOS way, and the next tool to call. Call it first.')
    @_answer
    def status(project: str | None = None) -> str:
        return tools.status(project)

    @server.tool(annotations=working, description='Check the whole project (26 stages: files, features, tools, tests, structure, '
                 'security, load, plan). Returns a job to follow with `wait`; when the project was already checked at this commit, '
                 'returns the overview at once. fresh=true checks again from the start. ' + project_doc)
    @_answer
    def audit(project: str | None = None, fresh: bool = False) -> str:
        return tools.audit(project, fresh)

    @server.tool(annotations=reading, description='Follow a job (audit, run_setup, run_try, safety_net, fix_start, fix_edit, fix_finish): '
                 'waits up to `seconds` (default 50) and returns its progress, or its result once done.')
    @_answer
    def wait(job: str, seconds: int = 50) -> str:
        return tools.wait(job, seconds)

    @server.tool(annotations=reading, description="The project's health after the check: counts, kinds of problems (with plain titles), "
                 'milestones of the plan, what did not complete. ' + project_doc)
    @_answer
    def overview(project: str | None = None) -> str:
        return tools.overview(project)

    @server.tool(annotations=reading, description='The problems found, most important first, filtered by kind, file path (part of it), '
                 'text in the title, or only those EAOS can fix; paged with limit and offset.')
    @_answer
    def findings(kind: str | None = None, path: str | None = None, text: str | None = None, fixable_only: bool = False,
                 limit: int = 30, offset: int = 0, project: str | None = None) -> str:
        return tools.findings(project, kind, path, text, fixable_only, limit, offset)

    @server.tool(annotations=reading, description='One problem whole, by card (TASK-…) or claim (CLM-…) id: what and why, the evidence '
                 'with the code around it, the rule it breaks, the suggested change, how it is proven gone, what depends on it.')
    @_answer
    def finding(id: str, project: str | None = None) -> str:
        return tools.finding(id, project)

    @server.tool(annotations=reading, description='The architecture: current and target components, forbidden and target dependencies, '
                 'decisions, gaps, import cycles, and the documents that explain them.')
    @_answer
    def structure(project: str | None = None) -> str:
        return tools.structure(project)

    @server.tool(annotations=reading, description='The plan of fixes: milestones in order and their cards (which EAOS can fix, which '
                 'were tried). Pass a milestone id for all of its cards.')
    @_answer
    def plan(milestone: str | None = None, project: str | None = None) -> str:
        return tools.plan(project, milestone)

    @server.tool(annotations=reading, description='A file of the report (for example START-HERE.md, TARGET-ARCHITECTURE.md, '
                 'SECURITY-SURFACE.md, LOAD-MODEL.md); with no name, the list of files.')
    @_answer
    def report_file(name: str = '', offset: int = 0, limit: int = 20000, project: str | None = None) -> str:
        return tools.report_file(name, project, offset, limit)

    @server.tool(annotations=working, description='Run the app in an isolated copy (a temporary local database, no secrets, nothing '
                 'reaches the internet), found from its files. Needs the person\'s agreement once: without it, returns the question to '
                 'ask. person_agreed=true only after they said yes. Returns a job.')
    @_answer
    def run_setup(person_agreed: bool = False, project: str | None = None) -> str:
        return tools.run_setup(project, person_agreed)

    @server.tool(annotations=working, description='Try your proposal to make the app run: {"env": {complete environment}, "start": '
                 '[argv], "install": [[argv]], "prepare": [[argv]], "database": "postgres"|"none", "seed_script": "<Node script run '
                 'after start with BASE_URL and EAOS_STORAGE_STATE: signs in the way the app allows locally, adds a little data, saves '
                 'context.storageState, prints a last JSON line of E2E_* fixture values>", "fixtures": {..}}; null keeps a field, [] '
                 'removes prepare. mode="baseline" is the production build (add "build": [[argv]]). Use "{database_url}" and '
                 '"{run_dir}". Unsafe proposals are refused with the reason. Returns a job.')
    @_answer
    def run_try(proposal: dict | None = None, mode: str = 'lock', project: str | None = None) -> str:
        return tools.run_try(proposal, mode, project)

    @server.tool(annotations=working, description='Record every screen of the running app, and its speed under load when the production '
                 'build runs: what every fix is compared with. Returns a job.')
    @_answer
    def safety_net(project: str | None = None) -> str:
        return tools.safety_net(project)

    @server.tool(annotations=working, description='Open a batch of fixes in an isolated copy: the next cards EAOS can fix (or the card ids '
                 'you pass), with their automatic fixes (codemods) applied and checked. Returns the cards left for you. Returns a job.')
    @_answer
    def fix_start(cards: list[str] | None = None, size: int = 10, project: str | None = None) -> str:
        return tools.fix_start(project, cards, size)

    @server.tool(annotations=reading, description='Read a file (or list a folder) in the open batch\'s copy, as it is now, with line numbers.')
    @_answer
    def fix_read(path: str, start: int = 1, end: int | None = None, project: str | None = None) -> str:
        return tools.fix_read(path, project, start, end)

    @server.tool(annotations=working, description='Make one card\'s change in the batch\'s copy, then check it at once: the card\'s problem '
                 'is gone, no new broken code, no endpoint gone. Edits: [{"path", "find", "replace"}] (find occurs exactly once), '
                 '[{"path", "content"}] for a whole or new file, [{"path", "delete": true}]. Any file of the project may change. A change '
                 'that fails is taken back with the reason. Returns a job.')
    @_answer
    def fix_edit(card: str, edits: list[dict], summary: str = '', project: str | None = None) -> str:
        return tools.fix_edit(card, edits, summary, project)

    @server.tool(annotations=working, description='Leave a card of the open batch out, with the reason (for example: it needs a product '
                 'decision).')
    @_answer
    def fix_skip(card: str, reason: str, project: str | None = None) -> str:
        return tools.fix_skip(card, reason, project)

    @server.tool(annotations=working, description='Close the batch: every kept change together through the project\'s own checks and every '
                 'recorded screen (a change that breaks them is found and left out), then the branch eaos/wave-N in the person\'s '
                 'project. Their current branch and files are not touched. Returns a job.')
    @_answer
    def fix_finish(project: str | None = None) -> str:
        return tools.fix_finish(project)

    @server.tool(annotations=working, description='Take the waiting branch into the person\'s current branch (fast-forward only). Only after '
                 'they said yes: person_agreed=true.')
    @_answer
    def accept(person_agreed: bool = False, project: str | None = None) -> str:
        return tools.accept(project, person_agreed)

    @server.tool(annotations=working, description='Throw the waiting branch away (while it is not merged): the project is as it was.')
    @_answer
    def undo(project: str | None = None) -> str:
        return tools.undo(project)

    @server.prompt(name='audit', description='Check this project and explain its problems simply')
    def audit_prompt() -> str:
        return ('Use the eaos tools to check this project: call `status`, then `audit` and `wait` until it is done. Then explain, '
                'in my language and in plain words, how healthy the project is, its five most important problems (why each '
                'matters), and what you recommend. Show evidence from `finding` for the top ones.')

    @server.prompt(name='fix', description='Fix the next batch of problems safely, end to end')
    def fix_prompt() -> str:
        return ('Use the eaos tools to fix this project safely, end to end, without coming back to me between steps: follow '
                '`status` (audit if needed, then run_setup, run_try until the app runs, safety_net, fix_start, fix_edit for each '
                'card, fix_finish). Ask me only the question run_setup gives. At the end, tell me simply what was fixed and on which '
                'branch, and ask whether to accept or undo.')

    @server.prompt(name='status', description='Where this project is, and what comes next')
    def status_prompt() -> str:
        return 'Call the eaos `status` tool and tell me simply where my project is and what comes next.'

    return server


def main():
    build().run('stdio')
    return 0
