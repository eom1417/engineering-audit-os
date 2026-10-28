"""The MCP tools that build a new project from its plan, milestone after milestone, or extend a checked one, registered
on the server eaos/interfaces/mcp_server/server.py builds (each answered as every tool is: its `_answer`)."""


def _build_tools(server, reading, working, _answer):
    """The tools that build a new project from its plan, milestone after milestone, or extend a checked one, in this order."""
    _plan_tools(server, working, _answer)
    _milestone_tools(server, reading, working, _answer)


def _plan_tools(server, working, _answer):
    """From the plan to the target: the spec, the design; or a feature's spec on a checked project."""
    from ...journeys.build_from_plan import steps as build

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

    @server.tool(annotations=working, description='Extend this checked project with a feature, a page or a part, from its plan (a '
                 'file, a folder with pictures of its screens, or the pasted text): returns the plan, the project as its check '
                 'read it (its parts, layers and rules, the functions to reuse, its look) and the spec format. Then write the '
                 'spec and call extend_plan.')
    @_answer
    def extend_start(source: str | None = None, text: str | None = None, project: str | None = None) -> str:
        from ...journeys import agent_tools, extend, guided
        state = agent_tools.state_of(project)
        return extend.extend_start(state, guided.report_of(state), source, text)

    @server.tool(annotations=working, description='Check the feature\'s spec against itself and against the project (every file in '
                 'a layer it allows, reusing its functions, none written again), then add its cards to the project\'s plan as '
                 'one milestone, ready for a batch: fix_start builds them through every gate of a fix.')
    @_answer
    def extend_plan(spec: dict, project: str | None = None) -> str:
        from ...journeys import agent_tools, extend, guided
        state = agent_tools.state_of(project)
        answer = extend.extend_plan(state, guided.report_of(state), spec)
        if answer['status'] == 'planned':
            guided.save(state)
            guided.publish(state)
        return answer


def _milestone_tools(server, reading, working, _answer):
    """One milestone of the build in its isolated copy: open, read, write, leave out, close."""
    from ...journeys.build_from_plan import steps as build

    # jscpd:ignore-start -- each MCP tool is its own decorated signature: the server reads its schema and words from it
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
    # jscpd:ignore-end
