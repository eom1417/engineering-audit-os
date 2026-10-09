"""`eaos mcp`: EAOS inside the person's AI assistant, as MCP tools (docs/MCP.md).

The assistant drives: it checks the project, reads the evidence and the code, gets the app running in an
isolated copy, writes the fixes, and hands them over as a branch. EAOS gives it the evidence, the copy and the
gates (eaos/agent_tools.py). Long work is a job the assistant follows with `wait`. Registered for Claude Code
and Codex by `eaos assistant install`, which install.sh runs.
"""
import functools
import inspect
import json
import os
from pathlib import Path

from . import __version__

INSTRUCTIONS = """EAOS (Engineering Audit OS) checks a whole software project, finds its structural, security and
performance problems with evidence, and fixes them safely: each fix is made in an isolated copy, checked (the
problem is gone, nothing broke, no endpoint disappeared, the project's own checks and every recorded screen still
pass) and handed over as a new git branch, eaos/wave-N. The person's current branch and files are never touched.

The person is usually not a developer. Speak to them in their language, in plain words, without jargon.
Work on your own until the job is done; do not come back to them between steps. Ask them only:
  1. which branch to work on, when the project has several (status asks it; choose_branch only with their answer);
  2. once, before running their app and preparing fixes (run_setup gives the exact question);
  3. at the end, whether to take the branch in (accept) or throw it away (undo).

For a project that exists only as a plan (a PRD, notes, any file or pasted text), build it instead:
  blueprint_start -> blueprint_spec (until complete; research, recommend, ask only real choices) -> blueprint_design
  -> build_start (one agreement) -> build_edit per card -> build_finish, milestone after milestone -> accept.
  Write the least code that meets each card, in the folder it names, reusing what exists; the gates refuse copies,
  cycles, layer breaks and a vendor outside its adapter.

The whole way for an existing project, in order (`status` always says the next tool):
  (when the project has several branches with different code, status first asks which one: ask the person, then
   choose_branch; everything after follows that branch)
  audit -> overview / findings / finding / structure / plan  (understand; explain the main problems simply)
     and open_report (the report for people, in their browser: offer it after the check and after each batch)
  run_setup (after the person agrees) -> run_try until the app runs (you read the failure and the code, and
     propose the environment, commands, or a seed script that signs in; EAOS refuses anything unsafe)
  safety_net (records every screen before any change)
  fix_start -> for each card: finding + fix_read, then fix_edit (fix_skip only with a real reason) -> fix_finish
  then tell the person what changed and ask: accept or undo. `accept` merges, deletes the branch and updates the
  report and the progress in one call: never merge or delete a branch with git yourself.
Only the plan's cards count as progress: do not do work outside them. Call `status` first in every session: its
`handover` says what the last assistant (you, or another one after a usage limit) did and how to continue; add the
why with `note` after each card and before you stop.
When the person types /eaos alone, or asks what EAOS can do here, call `menu` and show its options as one choice
(the recommended one first); once they chose, do what that option says at once. For questions about their code,
`impact` (what changing a file touches) and `ask` answer from the check's records; `tools_check` says what is installed.
Long steps return a job: call `wait` with it until it is done (a check takes 5-30 minutes). Keep every feature,
route and behaviour when fixing: a fix that deletes what users reach is refused. Never invent results: report
what the tools returned."""

# Every capability of the guided way (eaos/guided.py STEPS and its commands), and the tool that gives it to the
# assistant. X8 counts those registered and exercised by tests/test_mcp.py.
CAPABILITIES = {'where things stand': 'status', 'read any plan': 'blueprint_start', 'check the product spec': 'blueprint_spec',
                'draw the target and the build plan': 'blueprint_design', 'build a milestone': 'build_edit',
                'hand a milestone over': 'build_finish', 'check the project': 'audit', 'follow long work': 'wait',
                'show the report for people': 'open_report', 'offer what EAOS can do now': 'menu',
                'what a change touches': 'impact', 'answer from the records': 'ask', 'check the tools': 'tools_check',
                'read the evidence': 'finding', 'run the app': 'run_try', 'record the screens': 'safety_net',
                'fix a card': 'fix_edit', 'hand fixes over': 'fix_finish', 'accept': 'accept', 'undo': 'undo',
                'hand the work to another assistant': 'note', 'choose the branch': 'choose_branch'}


# What only the person decides. In a run the Studio started (EAOS_STUDIO_RUN set by eaos/studio/actions), the assistant
# asks instead, and the person answers in the Studio, which calls these itself.
PERSON_ONLY = ('accept', 'undo', 'choose_branch')
STUDIO = 'EAOS Studio'           # the name the Studio's own calls are recorded under


def _status(project=None):
    """The status tool of the project's way: fixing, or building from a plan; with the request the Studio handed to the
    next assistant, when one waits (eaos/studio/actions/handoff.py)."""
    from .build_tools import status_of
    result = status_of(project)
    if isinstance(result, dict) and not os.environ.get('EAOS_STUDIO_RUN'):
        from .handover import assistant
        from .studio.actions import handoff
        if assistant() != STUDIO: result.update(handoff.for_status(Path(project or os.getcwd()).expanduser().resolve(), assistant()))
    return result


def _answer(function):
    """A tool's dict as JSON text; an error as the reason and what to do, never a bare traceback. Every call is written
    to the project's journal and its HANDOVER.md (eaos/handover.py), so another assistant can take over."""
    signature = inspect.signature(function)

    @functools.wraps(function)
    def call(*args, **kwargs):
        from .guided import explain
        from .handover import record
        try:
            if function.__name__ in PERSON_ONLY and os.environ.get('EAOS_STUDIO_RUN'):
                raise PermissionError(f'{function.__name__} is the person\'s decision, and they make it in the EAOS Studio: ask them '
                                      'with an eaos-question block and stop')
            result = function(*args, **kwargs)
        except LookupError as problem:
            result = {'error': str(problem)}
        except Exception as problem:            # every failure reaches the assistant as words it can act on
            known = explain(problem)
            result = {'error': f'{type(problem).__name__}: {problem}'[:2000],
                      **({'what_now': known['en']['fix'] + ' ' + ' '.join(known['en']['commands'])} if known['id'] != 'unknown' else {})}
        try: arguments = dict(signature.bind_partial(*args, **kwargs).arguments)
        except TypeError: arguments = dict(kwargs)
        record(function.__name__, arguments, result, _status)
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

    @server.tool(annotations=reading, description='Where this project is in the EAOS way, the next tool to call, the progress, and the '
                 'handover (what the last assistant did and noted, and how to continue without asking the person again). Call it '
                 'first, every session.')
    @_answer
    def status(project: str | None = None) -> str:
        return _status(project)

    @server.tool(annotations=reading, description='The project\'s branches (the person\'s own; bots\' and EAOS\'s are left out): '
                 'when each last changed, how far each is ahead of and behind the main branch, which is checked out, which EAOS '
                 'works on, and the recommendation.')
    @_answer
    def branches(project: str | None = None) -> str:
        return tools.branches_of(project)

    @server.tool(annotations=working, description='Work on this branch from now on: the check, the run, the fixes, the progress and '
                 'every merge follow it; each branch keeps its own. person_said: the person\'s reply to which branch, as they wrote '
                 'it; ask them first and wait for it (never choose for them, never write a reply they did not give). The '
                 'person\'s checkout is not switched (EAOS uses its own copy of the branch).')
    @_answer
    def choose_branch(branch: str, person_said: str = '', project: str | None = None) -> str:
        return tools.choose_branch(branch, project, person_said)

    @server.tool(annotations=reading, description='What to offer the person who typed /eaos alone, or asked what EAOS can do: '
                 'the options that make sense for this project now, the recommended one first, each with its words in their language, '
                 'a description from the project\'s own numbers, and what to do once it is chosen; cut into pages of at most four. '
                 'Show it as a choice (how_to_show). ' + project_doc)
    @_answer
    def menu(project: str | None = None, lang: str | None = None) -> str:
        from .menu import menu as offer
        return offer(project, lang)

    @server.tool(annotations=reading, description='This EAOS (version, commit) and every external tool it runs: installed or not, '
                 'at which version, whether this project needs it (needed_here), and the one command that installs what it '
                 'misses. ' + project_doc)
    @_answer
    def tools_check(project: str | None = None) -> str:
        return tools.tools_check(project)

    @server.tool(annotations=reading, description='What changing a file or a symbol touches, from the check\'s facts: the files that '
                 'import it (direct and further), the flows and entry points through it, the tests that cover it, and the files '
                 'that change with it in the history. target: a path or a symbol name. ' + project_doc)
    @_answer
    def impact(target: str, project: str | None = None) -> str:
        return tools.impact(target, project)

    @server.tool(annotations=reading, description='Search the check\'s records (facts, claims, report sections) for a question, '
                 'each answer with its place. Records use the code\'s own words: ask with identifiers or paths. '
                 'NOT_IN_RECORDS means no record answers it: say so, never guess. ' + project_doc)
    @_answer
    def ask(question: str, project: str | None = None) -> str:
        return tools.ask(question, project)

    @server.tool(annotations=working, description='Check the whole project (26 stages: files, features, tools, tests, structure, '
                 'security, load, plan). Returns a job to follow with `wait`; when the project was already checked at this commit, '
                 'returns the overview at once. fresh=true checks again from the start. A started check answers with `watch`, '
                 'its live map in the EAOS Studio, opened in the person\'s browser. ' + project_doc)
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

    @server.tool(annotations=reading, description='Open the report for people (REPORT.html: project summary, gaps and risks, structure '
                 'map, plan and progress, in plain words) in the person\'s browser, rebuilt with the fixes so far. Offer it after '
                 'the check and after each batch of fixes. All outputs are in one folder (~/EAOS/<project>).')
    @_answer
    def open_report(show: bool = True, project: str | None = None) -> str:
        from . import build_tools, guided
        from pathlib import Path
        import os
        state = guided.load(Path(project or os.getcwd()).expanduser().resolve())
        if (state or {}).get('mode') == 'build' and not guided.scan_done(state): return build_tools.open_blueprint(project, show)
        return tools.open_report(project, show)

    @server.tool(annotations=reading, description='Open the live EAOS Studio of the project in the person\'s browser: every '
                 'card, map, plan and decision of the last check, updating by itself after every check, batch, merge and decision. '
                 'It runs on this computer only (127.0.0.1) and is reused while it runs. Offer it with open_report.')
    @_answer
    def open_studio(show: bool = True, project: str | None = None) -> str:
        from .api.launch import open_studio as launch
        return launch(project, show)

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

    @server.tool(annotations=working, description='Take the waiting branch into the person\'s current branch (whenever they say take it '
                 'in, merge, or accept; never merge it with git yourself), then delete the branch and bring the report and the '
                 'progress up to date, all in this call. Only after they said yes: person_agreed=true.')
    @_answer
    def accept(person_agreed: bool = False, project: str | None = None) -> str:
        return tools.accept(project, person_agreed)

    @server.tool(annotations=working, description='Leave a note for whoever continues this work (you after a break, or another '
                 'assistant when your usage limit runs out): what you found, what you decided, what you were about to do. One or '
                 'two sentences, after each card and before you stop. Every tool call is already recorded; the note adds the why.')
    @_answer
    def note(text: str, card: str | None = None, project: str | None = None) -> str:
        from . import handover
        from .studio.actions import handoff
        handoff.close(Path(project or os.getcwd()).expanduser().resolve(), text)
        return handover.note(text, card, project, _status)

    @server.tool(annotations=working, description='Throw the waiting branch away (while it is not merged): the project is as it was.')
    @_answer
    def undo(project: str | None = None) -> str:
        return tools.undo(project)

    from . import build_tools as build

    @server.tool(annotations=working, description='Build a new project from its plan (a PRD, notes, any file: Markdown, text, PDF, '
                 'Word, HTML; or the pasted text). Reads the plan and returns it with the product-spec format and the technology '
                 'catalogue. The project folder may be empty or new. Then write the spec (research what the plan leaves thin, '
                 'recommend, ask the person only real choices) and call blueprint_spec.')
    @_answer
    def blueprint_start(source: str | None = None, text: str | None = None, project: str | None = None) -> str:
        return build.blueprint_start(source, text, project)

    @server.tool(annotations=working, description='Check the product spec you wrote from the plan: returns what is missing (fix it) '
                 'and the questions for the person (choices with your recommendation). Call again after each change.')
    @_answer
    def blueprint_spec(spec: dict, project: str | None = None) -> str:
        return build.blueprint_spec(spec, project)

    @server.tool(annotations=working, description='Draw the target from the checked spec: the technologies (the person\'s choices, '
                 'else the recommendation; each kept in one adapter folder so it can be changed later), the layers and rules, and '
                 'the build plan as milestones of cards. `stack` overrides choices, e.g. {"database": "supabase"}.')
    @_answer
    def blueprint_design(stack: dict | None = None, project: str | None = None) -> str:
        return build.blueprint_design(stack, project)

    @server.tool(annotations=working, description='Open the next milestone of the build in an isolated copy (the first time it asks '
                 'the person\'s agreement: person_agreed=true only after their yes). Returns the cards to build.')
    @_answer
    def build_start(person_agreed: bool = False, project: str | None = None) -> str:
        return build.build_start(project, person_agreed)

    @server.tool(annotations=reading, description='Read a file (or list a folder) in the build\'s copy, with line numbers.')
    @_answer
    def build_read(path: str = '.', start: int = 1, end: int | None = None, project: str | None = None) -> str:
        return build.build_read(path, project, start, end)

    @server.tool(annotations=working, description='Write one build card: edits as in fix_edit ([{"path", "content"}] for new files, '
                 '[{"path", "find", "replace"}], [{"path", "delete": true}]). Kept only if every gate passes: the planned folders '
                 'and layers, each vendor only in its adapter, no import cycle, no broken reference, no copied code, a test for '
                 'the card, and the project\'s typecheck, lint and tests. Otherwise taken back with the reasons. card="FIX" for a '
                 'correction the milestone needs. Returns a job.')
    @_answer
    def build_edit(card: str, edits: list[dict], summary: str = '', project: str | None = None) -> str:
        return build.build_edit(card, edits, summary, project)

    @server.tool(annotations=working, description='Leave a build card out, with the reason (for example: the person decided against it).')
    @_answer
    def build_skip(card: str, reason: str, project: str | None = None) -> str:
        return build.build_skip(card, reason, project)

    @server.tool(annotations=working, description='Close the milestone (every gate on the whole copy; at the last milestone, no dead '
                 'code either) and hand it to the project as the branch eaos/build-N, stacked on the previous one. Returns a job.')
    @_answer
    def build_finish(project: str | None = None) -> str:
        return build.build_finish(project)

    @server.prompt(name='build', description='Build a new project from its plan, with the best structure · ابنِ مشروعًا من خطة')
    def build_prompt() -> str:
        return ('Use the eaos tools to build my project from its plan, end to end: blueprint_start with my plan file (or the text '
                'I paste), write the product spec, research what the plan leaves thin and recommend, ask me only real choices '
                '(including technology preferences), blueprint_design, then build_start and every milestone with build_edit and '
                'build_finish, without coming back to me between steps. At the end, tell me simply what was built and ask whether '
                'to take it in.')

    @server.prompt(name='audit', description='Check this project and explain its problems simply · افحص المشروع')
    def audit_prompt() -> str:
        return ('Use the eaos tools to check this project: call `status`, then `audit` and `wait` until it is done. Then explain, '
                'in my language and in plain words, how healthy the project is, its five most important problems (why each '
                'matters), and what you recommend. Show evidence from `finding` for the top ones.')

    @server.prompt(name='fix', description='Fix the next batch of problems safely, end to end · أصلح الدفعة التالية')
    def fix_prompt() -> str:
        return ('Use the eaos tools to fix this project safely, end to end, without coming back to me between steps: follow '
                '`status` (audit if needed, then run_setup, run_try until the app runs, safety_net, fix_start, fix_edit for each '
                'card, fix_finish). Ask me only the question run_setup gives. At the end, tell me simply what was fixed and on which '
                'branch, and ask whether to accept or undo.')

    @server.prompt(name='status', description='Where this project is, and what comes next · أين وصلنا؟')
    def status_prompt() -> str:
        return 'Call the eaos `status` tool and tell me simply where my project is and what comes next.'

    from .menu import OPTIONS

    def shortcut(key, description):
        """/eaos:<key> in Claude Code: one menu option, straight away (the same words as eaos/menu.py)."""
        words = f'Use the eaos tools: {OPTIONS[key][2]} Speak to me in my language, in plain words.'
        if key == 'ask':                                  # /eaos:ask <the question>
            def prompt(question: str = '') -> str:
                return words + (f' My question: {question}' if question.strip() else '')
        else:
            def prompt() -> str:
                return words
        server.prompt(name=key, description=description)(prompt)

    shortcut('continue', 'Continue the open EAOS work where it stopped · تابع من حيث توقفنا')
    shortcut('report', 'Open the interactive report, one file to share · افتح التقرير التفاعلي')
    shortcut('tasks', 'What is done and what comes next · المنجز والقادم')
    shortcut('ask', 'Ask about your code: what a change touches, where a thing is used · اسأل عن مشروعك')
    shortcut('tools', 'Which EAOS and tools are installed, what is missing · الأدوات والمحركات')
    return server


def functions():
    """{tool name: the function the MCP server calls}, each answering JSON text and recorded in the journal like an
    assistant's call: what the Studio's command centre calls for a direct action (eaos/studio/actions)."""
    return {tool.name: tool.fn for tool in build()._tool_manager.list_tools()}


def reading():
    """The tools marked read-only: they change nothing, so the Studio answers them at once."""
    return {tool.name for tool in build()._tool_manager.list_tools() if tool.annotations and tool.annotations.read_only_hint}


def main():
    build().run('stdio')
    return 0
