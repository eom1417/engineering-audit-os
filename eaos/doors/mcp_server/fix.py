"""The MCP tools of the findings, the plan, the run of the app, the fixes and the person's decision on them, registered
on the server eaos/doors/mcp_server/server.py builds (each answered as every tool is: its `_answer`)."""
import os
from pathlib import Path

from . import node_jobs
from ...kernel.toolchain import catalog as tools_catalog


def _fix_tools(server, reading, working, _answer, _status):
    """The tools of the findings, the plan, the run, the fixes and the person's decision on them, in this order."""
    for group in (_finding_tools, _report_tools, _run_tools, _context_tools, _batch_tools, _edit_tools):
        group(server, reading, working, _answer)
    _decision_tools(server, working, _answer, _status)


def _finding_tools(server, reading, working, _answer):
    """The problems found, one of them whole, the architecture and the plan."""
    from ...features.guided.interface import agent_tools as tools

    @server.tool(annotations=reading,
                 description='The problems found, most important first, filtered by kind, file path (part of it), '
                 'text in the title, or only those EAOS can fix; paged with limit and offset.')
    @_answer
    def findings(kind: str | None = None, path: str | None = None, text: str | None = None,
                 fixable_only: bool = False,
                 limit: int = 30, offset: int = 0, project: str | None = None) -> str:  # limits: parameters -- the MCP tool's schema: each parameter is an argument the assistant passes
        return tools.findings(project, kind, path, text, fixable_only, limit, offset)

    @server.tool(annotations=reading,
                 description='One problem whole, by card (TASK-…) or claim (CLM-…) id: what and why, the evidence '
                 'with the code around it, the rule it breaks, the suggested change, how it is proven gone, what '
                 'depends on it.')
    @_answer
    def finding(id: str, project: str | None = None) -> str:
        return tools.finding(id, project)

    @server.tool(annotations=reading,
                 description='The architecture: current and target components, forbidden and target dependencies, '
                 'decisions, gaps, import cycles, and the documents that explain them.')
    @_answer
    def structure(project: str | None = None) -> str:
        return tools.structure(project)

    @server.tool(annotations=working,
                 description='The plan of fixes: milestones in order and their cards (which EAOS can fix, which '
                 'were tried). Pass a milestone id for all of its cards.')
    @_answer
    def plan(milestone: str | None = None, project: str | None = None) -> str:
        return tools.plan(project, milestone)


def _report_tools(server, reading, working, _answer):
    """The report's files and the report for people."""
    from ...features.guided.interface import agent_tools as tools

    @server.tool(annotations=reading,
                 description='A file of the report (for example START-HERE.md, '
                 'CURRENT-STATE.md, dossier.json); with no name, the list of files.')
    @_answer
    def report_file(name: str = '', offset: int = 0, limit: int = 20000, project: str | None = None) -> str:
        return tools.report_file(name, project, offset, limit)

    # jscpd:ignore-start -- each MCP tool is its own decorated signature: the server reads its schema and words from it
    # Not read-only, for it rebuilds the report and saves the state; no destructive hint, for what it regenerates
    # is overwritten.
    @server.tool(annotations=reading.model_copy(update={'read_only_hint': False}),
                 description='The report for people (START-HERE.md and the reports: what was found, what EAOS '
                 'fixes alone, the plan and progress, in plain words), rebuilt with the fixes so far. Offer it after '
                 'the check and after each batch of fixes. All outputs are in one folder (~/EAOS/<project>).')
    @_answer
    def open_report(show: bool = True, project: str | None = None) -> str:
        return tools.open_report(project, show)


def _run_tools(server, reading, working, _answer):
    """The AI nodes, the external tools, and the agreement to run the app."""
    from ...features.guided.interface import agent_tools as tools

    @server.tool(annotations=working,
                 description='Run the AI nodes on the latest check, any of them at any time (card_triage, '
                 'plan_orderer, fix_reviewer; all when none named). Returns a job.')
    @_answer
    def run_nodes(nodes: list[str] | None = None, fresh: bool = False, project: str | None = None) -> str:
        return node_jobs.start(project, nodes, fresh)

    @server.tool(annotations=reading,
                 description='GitHub candidates for a tool a stage lacks: stars, license, latest release assets.')
    @_answer
    def tools_find(need: str, project: str | None = None) -> str:
        return tools_catalog.find(need)

    @server.tool(annotations=working,
                 description='Add a pinned tool (version, sha256 or commit, license) after the person agreed, '
                 'then install it.')
    @_answer
    def tools_add(entry: dict, person_agreed: bool = False, project: str | None = None) -> str:
        return tools_catalog.add(entry, person_agreed)

    @server.tool(annotations=working,
                 description='Run the app in an isolated copy (a temporary local database, no secrets, nothing '
                 'reaches the internet), found from its files. Needs the person\'s agreement once: without it, returns '
                 'the question to ask. person_agreed=true only after they said yes. Returns a job.')
    @_answer
    def run_setup(person_agreed: bool = False, project: str | None = None) -> str:
        return tools.run_setup(project, person_agreed)
    # jscpd:ignore-end


def _context_tools(server, reading, working, _answer):
    """The assistants' context trimmed, and the project's extension guide with it."""
    from ...features.guided.interface import agent_tools as tools

    @server.tool(annotations=reading,
                 description="What a batch of the assistants' context would do, nothing written: what the trim "
                 "archives and keeps once, the tokens saved, and the project's extension guide it writes "
                 "(docs/EXTENDING.md and one pointer line in the context files).")
    @_answer
    def context_propose(private_to: str | None = None, project: str | None = None) -> str:
        return tools.context_propose(project, private_to)

    @server.tool(annotations=working,
                 description="Make that batch in an isolated copy, on a branch of its own, every instruction kept; "
                 "needs person_agreed=true after the person says yes. Returns a job.")
    @_answer
    def context_make(person_agreed: bool = False, private_to: str | None = None, project: str | None = None) -> str:
        return tools.context_make(project=project, private_to=private_to, person_agreed=person_agreed)


def _batch_tools(server, reading, working, _answer):
    """Getting the app to run, its recorded screens, and a batch of fixes opened."""
    from ...features.guided.interface import agent_tools as tools

    @server.tool(annotations=working,
                 description='Try your proposal to make the app run: {"env": {complete environment}, "start": '
                 '[argv], "install": [[argv]], "prepare": [[argv]], "database": "postgres"|"none", "seed_script": '
                 '"<Node script run after start with BASE_URL and EAOS_STORAGE_STATE: signs in the way the app allows '
                 'locally, adds a little data, saves context.storageState, prints a last JSON line of E2E_* fixture '
                 'values>", "fixtures": {..}, "screens": {"lang_key": the localStorage key keeping the language (or '
                 '"lang_param" a query parameter), "lang_field" its field when it keeps a JSON object, '
                 '"theme_key"/"theme_field" the same for the theme}: so every screen is pictured in each language}; '
                 'null keeps a field, [] removes prepare. mode="baseline" is the production build (add '
                 '"build": [[argv]]; "app": the folder it starts in, "." for a server at the root; "headers": '
                 '{name: value or {"file": path it writes}} sent with every load request, a token). Commands start '
                 'with npm, npx, node, python, pip, uv, uvicorn or the like. Use "{database_url}" and "{run_dir}". '
                 'Unsafe proposals are refused with the reason. Returns a job.')
    @_answer
    def run_try(proposal: dict | None = None, mode: str = 'lock', project: str | None = None) -> str:
        return tools.run_try(proposal, mode, project)

    @server.tool(annotations=working,
                 description='Record every screen of the running app, and its speed under load when the production '
                 'build runs: what every fix is compared with. Returns a job.')
    @_answer
    def safety_net(project: str | None = None) -> str:
        return tools.safety_net(project)

    @server.tool(annotations=working,
                 description='Open a batch of fixes in an isolated copy: the next cards EAOS can fix (or the card ids '
                 'you pass), with their automatic fixes (codemods) applied and checked. Returns the cards left for '
                 'you. Returns a job. Optional, as the person set them in the fix preview: base (the branch to build '
                 'on; default the branch EAOS works on), deliver_as (the new branch the fixes arrive on; default '
                 'eaos/<branch>/wave-N; or an EAOS work branch waiting for a decision, to continue on it; or the base '
                 'branch itself, direct: the fixes land on it once every check passed and no branch is left), '
                 'merge_into (the branch accept merges into; default the branch open in the project folder), '
                 'base_commit (the commit the preview showed for base: status base_moved when the branch moved since), '
                 'assistants (how many assistants fix the batch at once, in the Studio\'s speed mode: it starts the '
                 'others, and you fix the cards it leaves you).')
    @_answer
    def fix_start(cards: list[str] | None = None, size: int = 10, project: str | None = None,
                  base: str | None = None,
                  deliver_as: str | None = None, merge_into: str | None = None, base_commit: str | None = None,
                  assistants: int = 1) -> str:  # limits: parameters -- the MCP tool's schema: each parameter is an argument the assistant passes
        return tools.fix_start(project, cards, size, base=base, deliver_as=deliver_as, merge_into=merge_into,
                               base_commit=base_commit, assistants=assistants)


def _edit_tools(server, reading, working, _answer):
    """The open batch: read, change, leave out, close or abandon."""
    from ...features.guided.interface import agent_tools as tools

    @server.tool(annotations=reading,
                 description='Read a file (or list a folder) in the open batch\'s copy, as it is now, with line numbers.')
    @_answer
    def fix_read(path: str, start: int = 1, end: int | None = None, project: str | None = None) -> str:
        return tools.fix_read(path, project, start, end)

    @server.tool(annotations=working,
                 description='Make one card\'s change in the batch\'s copy, then check it at once: the card\'s problem '
                 'is gone, no new broken code, no endpoint gone. Edits: [{"path", "find", "replace"}] (find occurs '
                 'exactly once), [{"path", "content"}] for a whole or new file, [{"path", "delete": true}]. A change '
                 'to files beyond the card\'s own paths is kept only with beyond_why: why each other file must change '
                 '(one sentence per file, or one for all, in the language of summary); it is said at the hand-over '
                 'and in the commit. A change that fails is taken back with the reason. Never write a lock file\'s '
                 'hashes by hand: each hash a change adds is checked against its registry and a wrong one is refused. '
                 'card="REPAIR" when fix_finish asks for a repair on top of the batch. '
                 'summary: the commit message, in the language of the project\'s own commits (English unless they are '
                 'not): one line under 72 characters saying what changed; then, only for a change that is not obvious, '
                 'a blank line and why. Returns a job.')
    @_answer
    def fix_edit(card: str, edits: list[dict], summary: str = '', project: str | None = None,
                 beyond_why: str = '') -> str:
        return tools.fix_edit(card, edits, summary, project, beyond_why)

    @server.tool(annotations=working,
                 description='Leave a card of the open batch out, with the reason (for example: it needs a product '
                 'decision), written in the person\'s language: they read it.')
    @_answer
    def fix_skip(card: str, reason: str, project: str | None = None) -> str:
        return tools.fix_skip(card, reason, project)

    @server.tool(annotations=working,
                 description='Close the batch: every kept change together through the project\'s own checks and '
                 'every recorded screen, then the branch eaos/<branch>/wave-N in the person\'s project. Their current '
                 'branch and files are not touched. When the changes fail the checks together, it asks for a repair '
                 'on top (fix_edit with card="REPAIR"); leave_out=true finds the changes responsible and leaves them '
                 'out instead. Returns a job.')
    @_answer
    def fix_finish(leave_out: bool = False, project: str | None = None) -> str:
        return tools.fix_finish(project, leave_out)

    @server.tool(annotations=working,
                 description='Close the open batch without handing anything over, when fix_finish cannot close it '
                 '(its reason says EAOS cannot check the changes): its copy is removed, the person\'s project is not touched, and its cards can be picked again.')
    @_answer
    def fix_abandon(project: str | None = None) -> str:
        return tools.fix_abandon(project)


def _decision_tools(server, working, _answer, _status):
    """The person's decision on the branch, and the note for whoever continues."""
    from ...features.guided.interface import agent_tools as tools

    @server.tool(annotations=working,
                 description='Take the waiting branch into the person\'s current branch (whenever they say take it '
                 'in, merge, or accept; never merge it with git yourself), then delete the branch and bring the report '
                 'and the progress up to date, all in this call. Only after they said yes: person_agreed=true. '
                 'Optional, as the person chose: merge_into (the branch to merge into; default the one the fix preview '
                 'named), delete_after (default true; false keeps the branch after merging).')
    @_answer
    def accept(person_agreed: bool = False, project: str | None = None, merge_into: str | None = None,
               delete_after: bool = True) -> str:
        return tools.accept(project, person_agreed, merge_into=merge_into, delete_after=delete_after)

    @server.tool(annotations=working,
                 description='Leave a note for whoever continues this work (you after a break, or another '
                 'assistant when your usage limit runs out): what you found, what you decided, what you were about to '
                 'do. One or two sentences, after each card and before you stop. Every tool call is already recorded; '
                 'the note adds the why.')
    @_answer
    def note(text: str, card: str | None = None, project: str | None = None) -> str:
        from ...features.guided.journey import handover
        from ...features.studio.journey.runs import handoff
        handoff.close(Path(project or os.getcwd()).expanduser().resolve(), text)
        return handover.note(text, card, project, _status)

    @server.tool(annotations=working,
                 description='Throw the waiting branch away (while it is not merged): the project is as it was. '
                 'Only after the person said yes: person_agreed=true.')
    @_answer
    def undo(person_agreed: bool = False, project: str | None = None) -> str:
        return tools.undo(project, person_agreed)
