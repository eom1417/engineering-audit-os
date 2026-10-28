"""`eaos mcp`: EAOS inside the person's AI assistant, as MCP tools (docs/MCP.md).

The assistant drives: it checks the project, reads the evidence and the code, gets the app running in an
isolated copy, writes the fixes, and hands them over as a branch. EAOS gives it the evidence, the copy and the
gates (eaos/journeys/agent_tools/). Long work is a job the assistant follows with `wait`. Registered for Claude Code
and Codex by `eaos assistant install`, which install.sh runs. The tools of the check are here; those of the fixes are in
interfaces/mcp_server/fix.py, those that build from a plan in interfaces/mcp_server/build.py, the governance tools in interfaces/mcp_server/govern.py.
"""
import functools
import inspect
import json
import os
from pathlib import Path

from ... import __version__
from ...core.contracts.code_laws import LAWS

INSTRUCTIONS = """EAOS (Engineering Audit OS) checks a whole software project, finds its structural, security and
performance problems with evidence, and fixes them safely: each fix is made in an isolated copy, checked (the
problem is gone, nothing broke, no endpoint disappeared, the project's own checks and every recorded screen still
pass) and handed over as a new git branch, eaos/<branch>/wave-N. The person's current branch and files are never touched.

The person is usually not a developer. Speak to them in their language, in plain words, without jargon.
Work on your own until the job is done; do not come back to them between steps. Ask them only:
  1. which branch to work on, when the project has several (status asks it; choose_branch only with their answer);
  2. once, before running their app and preparing fixes (run_setup gives the exact question);
  3. at the end, whether to take the branch in (accept) or throw it away (undo), each with person_agreed after their yes.

For a project that exists only as a plan (a PRD, notes, any file or pasted text), build it instead:
  blueprint_start -> blueprint_spec (until complete; research, recommend, ask only real choices) -> blueprint_design
  -> build_start (one agreement) -> build_edit per card -> build_finish, milestone after milestone -> accept.
  Write each card in the folder it names, reusing what exists; the gates refuse copies, cycles, layer breaks and a
  vendor outside its adapter.
To add a feature, a page or a part to a project already checked: extend_start -> extend_plan (until it fits the
  project) -> the person agrees -> fix_start with its cards, built and checked as any fix.

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
Without the Studio, the same governance is yours through runs (the queue: estimate, check, show, stop...), waiting (what
waits for the person), act (fix, verify, explain, plan on cards or a group, previewed first), history and branch_change:
what is the person's there (an answer, a branch change, a Fix that accepts itself) takes their word and the preview's token.
When the person states a requirement that must hold ("never...", "always...", "the data lives only in..."), keep it in
their words with rule(op=add) and write its guard once (rule op=guard); the cards list in your_rules the rules each
fix must keep, and check_changed checks a change on them in seconds before it lands.
Only the plan's cards count as progress: do not do work outside them. Call `status` first in every session: its
`handover` says what the last assistant (you, or another one after a usage limit) did and how to continue; add the
why with `note` after each card and before you stop.
When the person types /eaos alone, or asks what EAOS can do here, call `menu` and show its options as one choice
(the recommended one first); once they chose, do what that option says at once. For questions about their code,
`impact` (what changing a file touches) and `ask` answer from the check's records; `tools_check` says what is installed.
The Studio is the person's view of all of it: at the start of the work, and right after EAOS was installed or updated,
call open_studio and send them its address without being asked (on a remote server whose ports your environment routes
to https addresses, pass that address once: the Studio then stays there, on the server, whichever assistant comes next).
Long steps return a job: call `wait` with it until it is done (a check takes 5-30 minutes). When a check waits for the
person to sign in to their app (status: next tool sign_in), tell them to open Waiting for you in the Studio, or to run
`eaos sign-in` in a terminal; never sign in for them, and never ask for their password. Keep every feature,
route and behaviour when fixing: a fix that deletes what users reach is refused, and so is one that changes a
public function or class (its name, its parameters, the module it is defined in): split inside, keep the outside. Never invent results: report
what the tools returned.

""" + LAWS


# What only the person decides: these tools, and these operations of the governance tools and commands (eaos/interfaces/govern.py).
# In a run the Studio started (EAOS_STUDIO_RUN set by eaos/interfaces/studio_actions), the assistant asks instead, and the person
# answers in the Studio, which calls these itself.
PERSON_ONLY = ('accept', 'undo', 'choose_branch', 'answer', 'branches merge', 'branches delete', 'branches protect', 'branches cleanup',
               'branches restore', 'auto_accept', 'sign_in_forget', 'logic_flaws', 'rule pin', 'rule unpin', 'rule change', 'rule hook')
STUDIO = 'EAOS Studio'           # the name the Studio's own calls are recorded under


def refuse_in_studio_run(name):
    """PermissionError for a decision only the person makes (PERSON_ONLY), asked inside a run the Studio started."""
    if name in PERSON_ONLY and os.environ.get('EAOS_STUDIO_RUN'):
        raise PermissionError(f"{name} is the person's decision, and they make it in the EAOS Studio: ask them with an "
                              'eaos-question block and stop')


def _status(project=None):
    """The status tool of the project's way: fixing, or building from a plan; with the request the Studio handed to the
    next assistant, when one waits (eaos/interfaces/studio_actions/handoff.py)."""
    from ...journeys.build_from_plan.steps import status_of
    result = status_of(project)
    if isinstance(result, dict) and not os.environ.get('EAOS_STUDIO_RUN'):
        from ...journeys.handover import assistant
        from ..studio_actions import handoff
        if assistant() != STUDIO: result.update(handoff.for_status(Path(project or os.getcwd()).expanduser().resolve(), assistant()))
    return result


SPOKEN = {'ar': 'Arabic', 'en': 'English'}


def _answer(function):
    """A tool's dict as JSON text; an error as the reason and what to do, never a bare traceback. Every call is written
    to the project's journal and its HANDOVER.md (eaos/journeys/handover.py), so another assistant can take over."""
    signature = inspect.signature(function)

    @functools.wraps(function)
    def call(*args, **kwargs):
        from ...journeys.guided import explain
        from ...journeys.handover import record
        try:
            refuse_in_studio_run(function.__name__)
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
        # a long Studio run forgets its first words: every answer carries the person's language (a real build drifted to English)
        if isinstance(result, dict) and os.environ.get('EAOS_STUDIO_LANG') in SPOKEN:
            result['notes_language'] = f"{SPOKEN[os.environ['EAOS_STUDIO_LANG']]}: the person reads every note you write, live."
        return json.dumps(result, ensure_ascii=False, indent=1, default=str)
    return call


def build(more=None):
    """The server; `more(server, reading, working, _answer)` adds tools to it (eaos/interfaces/mcp_server/govern.py: the governance tools,
    which the Studio itself never calls: functions, reading)."""
    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations
    from . import build as mcp_build, fix as mcp_fix, rules as mcp_rules

    server = MCPServer(name='eaos', title='Engineering Audit OS', version=__version__, instructions=INSTRUCTIONS)
    reading = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
    working = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    _check_tools(server, reading, working)
    mcp_fix._fix_tools(server, reading, working, _answer, _status)
    mcp_build._build_tools(server, reading, working, _answer)
    mcp_rules.register(server, reading, working, _answer)
    if more: more(server, reading, working, _answer)
    _prompts(server)
    return server


PROJECT_DOC = 'The project folder (default: the folder the assistant was opened in).'


def _check_tools(server, reading, working):
    """The tools of the check: where things stand, the branches, the menu, the tools, the check and its overview, in this order."""
    for group in (_way_tools, _record_tools, _audit_tool, _follow_tools): group(server, reading, working)


def _way_tools(server, reading, working):
    """Where things stand, the branches and the one to work on, and the menu."""
    from ...journeys import agent_tools as tools

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
                 'Show it as a choice (how_to_show). ' + PROJECT_DOC)
    @_answer
    def menu(project: str | None = None, lang: str | None = None) -> str:
        from ..menu import menu as offer
        return offer(project, lang)


def _record_tools(server, reading, working):
    """The tools installed, and what the check's records say about a change or a question."""
    from ...journeys import agent_tools as tools

    @server.tool(annotations=working, description='This EAOS (version, commit) and every external tool it runs: installed or not, '
                 'at which version, whether this project needs it (needed_here), what the check waits for here (for_the_check: '
                 'pending, failed with why, ready), and the one command that installs what it misses. retry=true starts the '
                 'install again (what failed is tried again). ' + PROJECT_DOC)
    @_answer
    def tools_check(project: str | None = None, retry: bool = False) -> str:
        return tools.tools_check(project, retry)

    # jscpd:ignore-start -- each MCP tool is its own decorated signature: the server reads its schema and words from it
    @server.tool(annotations=reading, description='What changing a file or a symbol touches, from the check\'s facts: the files that '
                 'import it (direct and further), the flows and entry points through it, the tests that cover it, and the files '
                 'that change with it in the history. target: a path or a symbol name. ' + PROJECT_DOC)
    @_answer
    def impact(target: str, project: str | None = None) -> str:
        return tools.impact(target, project)

    @server.tool(annotations=reading, description='Search the check\'s records (facts, claims, report sections) for a question, '
                 'each answer with its place. Records use the code\'s own words: ask with identifiers or paths. '
                 'NOT_IN_RECORDS means no record answers it: say so, never guess. ' + PROJECT_DOC)
    @_answer
    def ask(question: str, project: str | None = None) -> str:
        return tools.ask(question, project)
    # jscpd:ignore-end

    @server.tool(annotations=reading, description='How the app\'s users fared in the last experience run: each persona\'s goals in '
                 'order with their result, time and steps counted, the difficulties ranked (confirmed first, then by severity), '
                 'the tickets, the replays that broke, the services not covered, and the records missing. The full story with '
                 'pictures is EXPERIENCE.md in the report (report_file). ' + PROJECT_DOC)
    @_answer
    def experience(project: str | None = None) -> str:
        from ...journeys import guided
        from ...report.experience.story import story, summary
        return summary(story(guided.report_of(tools.state_of(project))))

    @server.tool(annotations=working, description='Hunt logic flaws after a check (skipped steps, races, wrong checks): the person\'s '
                 'assistant reads the code twice on its deep tier, then the check goes on from its claims so the cards include them. '
                 'It spends: without person_agreed it answers needs_agreement with what it costs; ask the person, and only after '
                 'their yes call again with person_agreed=true. minutes: the most it may take (default 40). Returns a job. ' + PROJECT_DOC)
    @_answer
    def logic_flaws(person_agreed: bool = False, minutes: int | None = None, project: str | None = None) -> str:
        from .. import deep_checks
        return deep_checks.logic_flaws_tool(project, person_agreed, minutes)


def _audit_tool(server, reading, working):
    """The check itself, with every choice the person makes for it."""
    from ...journeys import agent_tools as tools

    @server.tool(annotations=working, description='Check the whole project (40 stages: files, features, tools, tests, structure, '
                 'security, load, plan). Returns a job to follow with `wait`; when the project was already checked at this commit, '
                 'returns the overview at once, also when the code moved on since (it says so): fresh=true checks again from the '
                 'start, only when the person asks for a new check. A started check answers with `watch`, '
                 'its live map in the EAOS Studio, opened in the person\'s browser (first "Preparing the tools" while the tools the check '
                 'needs are installing: the check starts by itself once they are ready). use_assistant: before their first check, ask the '
                 'person once whether EAOS may use their AI assistant in it (it interprets the facts and plans the ideal; '
                 'everything it says stays a hypothesis tied to evidence) and pass their answer; it is kept. assistant: which one '
                 '(claude or codex), when they say; `assistant_check` shows which is ready. A chosen assistant that is not ready '
                 'stops the check before it starts (status assistant_not_ready, with the reason and its fix). without_tools=true: '
                 'only when the person chose to start without tools whose install failed (the report records it). again_from=<stage>: '
                 'the last check goes on from that stage (one whose tool failed, or one to redo): it and the stages reading it run '
                 'again on the checked commit, the rest is kept; engines=[names] with again_from=engines runs only those tools. '
                 'paths=[...] checks only those paths, when the person has a clear goal: security, look (the screens), code '
                 '(structure, quality, dead code), speed (load and scale), experience (simulated users try the running app; beside complete '
                 'its short option, off by default: say its time and calls from the estimate first); complete by default. mode=speed runs several '
                 'assistants at once: faster, more tokens; say so before choosing it (kept). sign_in: when the app has a sign-in, how '
                 'its pages are opened (kept): hand (the person signs in on the sign-in page when the check asks; status then says '
                 'so), test_user (a seed script signs a test user in), none (signed out). published=<https address>: only when the '
                 'person names it, its pages are read signed in, read only, for this check. run_app=true: only once the person '
                 'said yes to running their app in an isolated copy (its pages, sign-in and speed need it; kept). go_on=true: only '
                 'when the person asks to continue a check they stopped: it goes on from where it stopped; any other check '
                 'starts from nothing. fixed=true: the person said their assistant is fixed: the check starts without asking '
                 'whether it is ready. ' + PROJECT_DOC)
    @_answer
    def audit(project: str | None = None, fresh: bool = False, use_assistant: bool | None = None, without_tools: bool = False,
              assistant: str | None = None, without_ai: bool = False, again_from: str | None = None, engines: list[str] | None = None,
              paths: list[str] | None = None, mode: str | None = None, sign_in: str | None = None, published: str | None = None,
              run_app: bool = False, go_on: bool = False, fixed: bool = False, person_agreed: bool = False) -> str:  # limits: parameters -- the MCP tool's schema: each parameter is an argument the assistant passes
        return tools.audit(project, fresh, use_assistant, without_tools, assistant, without_ai, again_from, engines, paths, mode, sign_in,
                           published, run_app, go_on, fixed, person_agreed)


def _follow_tools(server, reading, working):
    """Whether an assistant is ready, a job followed, and the health after the check."""
    from ...journeys import agent_tools as tools

    @server.tool(annotations=reading, description='Before a check: each AI assistant (Claude Code, Codex) on this computer, really asked '
                 'for one word: ready, or the exact reason (not installed, not signed in, sign-in expired, usage limit, no answer) '
                 'with its fix; the person\'s choice for this project, and what the assistant may do in the check. fresh=true asks '
                 'again (an answer is kept a few minutes); assistant=claude|codex asks only that one. ' + PROJECT_DOC)
    @_answer
    def assistant_check(project: str | None = None, fresh: bool = False, assistant: str | None = None) -> str:
        return tools.assistant_check(project, fresh, assistant)

    @server.tool(annotations=reading, description='Follow a job (audit, run_setup, run_try, safety_net, fix_start, fix_edit, fix_finish): '
                 'waits up to `seconds` (default 50) and returns its progress, or its result once done. ' + PROJECT_DOC)
    @_answer
    def wait(job: str, seconds: int = 50, project: str | None = None) -> str:
        return tools.wait(job, seconds, project)

    @server.tool(annotations=reading, description="The project's health after the check: counts, kinds of problems (with plain titles), "
                 'milestones of the plan, what did not complete. ' + PROJECT_DOC)
    @_answer
    def overview(project: str | None = None) -> str:
        return tools.overview(project)


def _prompts(server):
    """The prompts, and the /eaos:<option> shortcuts of Claude Code."""
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

    from ..menu import OPTIONS

    def shortcut(key, description):
        """/eaos:<key> in Claude Code: one menu option, straight away (the same words as eaos/interfaces/menu.py)."""
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


def functions():
    """{tool name: the function the MCP server calls}, each answering JSON text and recorded in the journal like an
    assistant's call: what the Studio's command centre calls for a direct action (eaos/interfaces/studio_actions)."""
    return {tool.name: tool.fn for tool in build()._tool_manager.list_tools()}


def reading():
    """The tools marked read-only: they change nothing, so the Studio answers them at once."""
    return {tool.name for tool in build()._tool_manager.list_tools() if tool.annotations and tool.annotations.read_only_hint}


def main():
    build().run('stdio')
    return 0
