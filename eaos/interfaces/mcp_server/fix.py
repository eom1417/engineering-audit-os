"""The MCP tools of the findings, the plan, the run of the app, the fixes and the person's decision on them, registered
on the server eaos/interfaces/mcp_server/server.py builds (each answered as every tool is: its `_answer`)."""
import os
from pathlib import Path

from . import node_jobs
from ...core.project import state as project_state
from ...core.toolchain import catalog as tools_catalog


def _fix_tools(server, reading, working, _answer, _status):
    """The tools of the findings, the plan, the run, the fixes and the person's decision on them, in this order."""
    for group in (_finding_tools, _report_tools, _run_tools, _context_tools, _batch_tools, _edit_tools): group(server, reading, working, _answer)
    _decision_tools(server, working, _answer, _status)


def _finding_tools(server, reading, working, _answer):
    """The problems found, one of them whole, the architecture and the plan."""
    from ...journeys import agent_tools as tools

    @server.tool(annotations=reading, description='The problems found, most important first, filtered by kind, file path (part of it), '
                 'text in the title, or only those EAOS can fix; paged with limit and offset.')
    @_answer
    def findings(kind: str | None = None, path: str | None = None, text: str | None = None, fixable_only: bool = False,
                 limit: int = 30, offset: int = 0, project: str | None = None) -> str:  # limits: parameters -- the MCP tool's schema: each parameter is an argument the assistant passes
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

    @server.tool(annotations=reading, description="What the project's screens are really made of: how many looks each part has (buttons, inputs, "
                 "cards...), how many values each kind has (colours, sizes...), near colours, how dates and numbers show, two libraries for one job.")
    @_answer
    def design(project: str | None = None) -> str:
        return tools.design(project)

    @server.tool(annotations=reading, description='The plan of fixes: milestones in order and their cards (which EAOS can fix, which '
                 'were tried). Pass a milestone id for all of its cards.')
    @_answer
    def plan(milestone: str | None = None, project: str | None = None) -> str:
        return tools.plan(project, milestone)


def _report_tools(server, reading, working, _answer):
    """The look, the report's files, the report for people and the Studio."""
    from ...analysis.target_state import look as design
    from ...journeys import agent_tools as tools, guided

    @server.tool(annotations=reading, description='The look, at almost no tokens: the EAOS design standard (phone first, both '
                 'directions, one theme), the Arabic font catalogue, the free pinned design libraries on this computer, the '
                 'design system UI UX Pro Max suggests for `product` (for example "clinic booking app"), and the project\'s '
                 'look today. For a redesign, or the look of a build.')
    @_answer
    def design_brief(product: str = '', project: str | None = None) -> str:
        return design.for_report(guided.report_of(tools.state_of(project)), product)

    @server.tool(annotations=working, description='Save the look the person chose, one DESIGN.md (Google Stitch\'s format), beside the '
                 'report: the screen review then judges every page against it (audit again_from="visual").')
    @_answer
    def design_choose(content: str, project: str | None = None) -> str:
        return design.choose(guided.report_of(tools.state_of(project)), content)

    @server.tool(annotations=reading, description='A file of the report (for example START-HERE.md, TARGET-ARCHITECTURE.md, '
                 'CURRENT-STATE.md, load-model.json); with no name, the list of files.')
    @_answer
    def report_file(name: str = '', offset: int = 0, limit: int = 20000, project: str | None = None) -> str:
        return tools.report_file(name, project, offset, limit)

    @server.tool(annotations=working, description='Open the report for people (REPORT.html: project summary, gaps and risks, structure '
                 'map, plan and progress, in plain words) in the person\'s browser, rebuilt with the fixes so far. Offer it after '
                 'the check and after each batch of fixes. All outputs are in one folder (~/EAOS/<project>).')
    @_answer
    def open_report(show: bool = True, project: str | None = None) -> str:
        from ...journeys.build_from_plan import steps as build_tools
        state = project_state.load(Path(project or os.getcwd()).expanduser().resolve())
        if (state or {}).get('mode') == 'build' and not guided.scan_done(state): return build_tools.open_blueprint(project, show)
        return tools.open_report(project, show)

    @server.tool(annotations=reading, description='Open the live EAOS Studio of the project in the person\'s browser: every '
                 'card, map, plan and decision of the last check, updating by itself after every check, batch, merge and decision. '
                 'It runs on this computer and is reused while it runs. On a remote server whose ports your environment routes to '
                 'an https address (for example https://<project>--<port>.dev.example.com), pass that address once as `address`: '
                 'the Studio then answers there with a plain address and keeps running after your session ends.')
    @_answer
    def open_studio(show: bool = True, address: str | None = None, project: str | None = None) -> str:
        return tools.open_studio(project, show, address=address)


def _run_tools(server, reading, working, _answer):
    """The AI nodes, the external tools, and the agreement to run the app."""
    from ...journeys import agent_tools as tools

    @server.tool(annotations=working, description='Run the AI nodes on the latest check, any of them at any time (card_triage, '
                 'visual_reviewer, ideal_planner, pipeline_gap_planner, plan_orderer, fix_reviewer; all when none named). Returns a job.')
    @_answer
    def run_nodes(nodes: list[str] | None = None, fresh: bool = False, project: str | None = None) -> str:
        return node_jobs.start(project, nodes, fresh)

    @server.tool(annotations=reading, description='GitHub candidates for a tool a stage lacks: stars, license, latest release assets.')
    @_answer
    def tools_find(need: str, project: str | None = None) -> str:
        return tools_catalog.find(need)

    @server.tool(annotations=working, description='Add a pinned tool (version, sha256 or commit, license) after the person agreed, then install it.')
    @_answer
    def tools_add(entry: dict, person_agreed: bool = False, project: str | None = None) -> str:
        return tools_catalog.add(entry, person_agreed)

    @server.tool(annotations=working, description='Run the app in an isolated copy (a temporary local database, no secrets, nothing '
                 'reaches the internet), found from its files. Needs the person\'s agreement once: without it, returns the question to '
                 'ask. person_agreed=true only after they said yes. Returns a job.')
    @_answer
    def run_setup(person_agreed: bool = False, project: str | None = None) -> str:
        return tools.run_setup(project, person_agreed)


def _context_tools(server, reading, working, _answer):
    """The assistants' context trimmed, the project's extension guide with it, and GitNexus's map for its assistant."""
    from ...journeys import agent_tools as tools

    @server.tool(annotations=working, description="GitNexus's map of the project for its assistant (area skills, its MCP): the index outside "
                 "the project, the skills in a folder git does not take; needs person_agreed=true after the person says yes.")
    @_answer
    def project_map(project: str | None = None, person_agreed: bool = False) -> str:
        return tools.project_map(project=project, person_agreed=person_agreed)

    @server.tool(annotations=reading, description="What a batch of the look would do, nothing written: the raw values it names as tokens, in which files, where the one tokens "
                 "file goes. agreed: [{from, to}], values the person agreed to merge.")
    @_answer
    def design_propose(agreed: list | None = None, project: str | None = None) -> str:
        return tools.design_propose(project, agreed)

    @server.tool(annotations=working, description="Make that batch in an isolated copy, no assistant asked, kept only when the style oracle proves nothing looks different but what "
                 "was agreed; needs person_agreed=true after the person says yes. Returns a job.")
    @_answer
    def design_make(person_agreed: bool = False, agreed: list | None = None, project: str | None = None) -> str:
        return tools.design_make(project=project, agreed=agreed, person_agreed=person_agreed)

    @server.tool(annotations=reading, description="What a batch of the assistants' context would do, nothing written: what the trim "
                 "archives and keeps once, the tokens saved, and the project's extension guide it writes (docs/EXTENDING.md and one "
                 "pointer line in the context files).")
    @_answer
    def context_propose(private_to: str | None = None, project: str | None = None) -> str:
        return tools.context_propose(project, private_to)

    @server.tool(annotations=working, description="Make that batch in an isolated copy, on a branch of its own, every instruction kept; "
                 "needs person_agreed=true after the person says yes. Returns a job.")
    @_answer
    def context_make(person_agreed: bool = False, private_to: str | None = None, project: str | None = None) -> str:
        return tools.context_make(project=project, private_to=private_to, person_agreed=person_agreed)


def _batch_tools(server, reading, working, _answer):
    """Getting the app to run, its recorded screens, and a batch of fixes opened."""
    from ...journeys import agent_tools as tools

    @server.tool(annotations=working, description='Try your proposal to make the app run: {"env": {complete environment}, "start": '
                 '[argv], "install": [[argv]], "prepare": [[argv]], "database": "postgres"|"none", "seed_script": "<Node script run '
                 'after start with BASE_URL and EAOS_STORAGE_STATE: signs in the way the app allows locally, adds a little data, saves '
                 'context.storageState, prints a last JSON line of E2E_* fixture values>", "fixtures": {..}, "screens": {"lang_key": '
                 'the localStorage key keeping the language (or "lang_param" a query parameter), "lang_field" its field when '
                 'it keeps a JSON object, "theme_key"/"theme_field" the same for the theme}: so every screen is pictured in '
                 'each language}; null keeps a field, [] '
                 'removes prepare. mode="baseline" is the production build (add "build": [[argv]]; "app": the folder it starts in, "." for '
                 'a server at the root; "headers": {name: value or {"file": path it writes}} sent with every load request, a '
                 'token). Commands start with npm, npx, node, python, pip, uv, uvicorn or the like. Use "{database_url}" and '
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
                 'you pass), with their automatic fixes (codemods) applied and checked. Returns the cards left for you. Returns a job. '
                 'Optional, as the person set them in the fix preview: base (the branch to build on; default the branch EAOS works '
                 'on), deliver_as (the new branch the fixes arrive on; default eaos/<branch>/wave-N; or an EAOS work branch '
                 'waiting for a decision, to continue on it; or the base branch itself, direct: the fixes land on it once every '
                 'check passed and no branch is left), merge_into (the branch accept '
                 'merges into; default the branch open in the project folder), base_commit (the commit the preview showed for base: '
                 'status base_moved when the branch moved since), assistants (how many assistants fix the batch at once, '
                 'in the Studio\'s speed mode: it starts the others, and you fix the cards it leaves you).')
    @_answer
    def fix_start(cards: list[str] | None = None, size: int = 10, project: str | None = None, base: str | None = None,
                  deliver_as: str | None = None, merge_into: str | None = None, base_commit: str | None = None,
                  assistants: int = 1) -> str:  # limits: parameters -- the MCP tool's schema: each parameter is an argument the assistant passes
        return tools.fix_start(project, cards, size, base=base, deliver_as=deliver_as, merge_into=merge_into, base_commit=base_commit,
                               assistants=assistants)


def _edit_tools(server, reading, working, _answer):
    """The open batch: read, change, leave out, close or abandon."""
    from ...journeys import agent_tools as tools

    @server.tool(annotations=reading, description='Read a file (or list a folder) in the open batch\'s copy, as it is now, with line numbers.')
    @_answer
    def fix_read(path: str, start: int = 1, end: int | None = None, project: str | None = None) -> str:
        return tools.fix_read(path, project, start, end)

    @server.tool(annotations=working, description='Make one card\'s change in the batch\'s copy, then check it at once: the card\'s problem '
                 'is gone, no new broken code, no endpoint gone. Edits: [{"path", "find", "replace"}] (find occurs exactly once), '
                 '[{"path", "content"}] for a whole or new file, [{"path", "delete": true}]. Any file of the project may change. A change '
                 'that fails is taken back with the reason. card="REPAIR" when fix_finish asks for a repair on top of the batch. '
                 'Returns a job.')
    @_answer
    def fix_edit(card: str, edits: list[dict], summary: str = '', project: str | None = None) -> str:
        return tools.fix_edit(card, edits, summary, project)

    @server.tool(annotations=working, description='Leave a card of the open batch out, with the reason (for example: it needs a product '
                 'decision).')
    @_answer
    def fix_skip(card: str, reason: str, project: str | None = None) -> str:
        return tools.fix_skip(card, reason, project)

    @server.tool(annotations=working, description='Close the batch: every kept change together through the project\'s own checks and every '
                 'recorded screen, then the branch eaos/<branch>/wave-N in the person\'s project. Their current branch and files are '
                 'not touched. When the changes fail the checks together, it asks for a repair on top (fix_edit with card="REPAIR"); '
                 'leave_out=true finds the changes responsible and leaves them out instead. Returns a job.')
    @_answer
    def fix_finish(leave_out: bool = False, project: str | None = None) -> str:
        return tools.fix_finish(project, leave_out)

    @server.tool(annotations=working, description='Close the open batch without handing anything over, when fix_finish cannot close it '
                 '(its reason says EAOS cannot check the changes): its copy is removed, the person\'s project is not touched, and '
                 'its cards can be picked again.')
    @_answer
    def fix_abandon(project: str | None = None) -> str:
        return tools.fix_abandon(project)


def _decision_tools(server, working, _answer, _status):
    """The person's decision on the branch, and the note for whoever continues."""
    from ...journeys import agent_tools as tools

    @server.tool(annotations=working, description='Take the waiting branch into the person\'s current branch (whenever they say take it '
                 'in, merge, or accept; never merge it with git yourself), then delete the branch and bring the report and the '
                 'progress up to date, all in this call. Only after they said yes: person_agreed=true. Optional, as the person '
                 'chose: merge_into (the branch to merge into; default the one the fix preview named), delete_after (default '
                 'true; false keeps the branch after merging).')
    @_answer
    def accept(person_agreed: bool = False, project: str | None = None, merge_into: str | None = None, delete_after: bool = True) -> str:
        return tools.accept(project, person_agreed, merge_into=merge_into, delete_after=delete_after)

    @server.tool(annotations=working, description='Leave a note for whoever continues this work (you after a break, or another '
                 'assistant when your usage limit runs out): what you found, what you decided, what you were about to do. One or '
                 'two sentences, after each card and before you stop. Every tool call is already recorded; the note adds the why.')
    @_answer
    def note(text: str, card: str | None = None, project: str | None = None) -> str:
        from ...journeys import handover
        from ..studio_actions import handoff
        handoff.close(Path(project or os.getcwd()).expanduser().resolve(), text)
        return handover.note(text, card, project, _status)

    @server.tool(annotations=working, description='Throw the waiting branch away (while it is not merged): the project is as it was. '
                 'Only after the person said yes: person_agreed=true.')
    @_answer
    def undo(person_agreed: bool = False, project: str | None = None) -> str:
        return tools.undo(project, person_agreed)
