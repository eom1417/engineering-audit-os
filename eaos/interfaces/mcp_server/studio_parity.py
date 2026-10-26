"""Parity with the Studio (docs/MCP.md "Parity with the Studio", M8.1): everything the Studio does has an MCP tool.

PARITY maps each Studio endpoint (its read server, eaos/interfaces/studio_server, and its action API, the contract's
endpoints of docs/studio-actions.json) to the tools that do the same and the command that does it from a terminal;
NO_TOOL names the few that have none on purpose, and why. tests/interfaces/test_parity.py derives the endpoints from
the code, so a new Studio endpoint without a row, or a row naming a tool that does not exist, fails.

The tools added here call the Studio's own core (eaos/interfaces/govern.py over studio_actions, and studio_server),
never a second implementation; like the governance tools they are registered by `eaos mcp` only (mcp_server/govern.py
main), not in the Studio's own direct actions (server.functions()).
"""
from .. import govern
from ..studio_actions import GET_ROUTES

# endpoint -> (the MCP tools that do it, the terminal command; None: none yet)
PARITY = {
    'GET /api/manifest': (('report_file',), None),
    'GET /api/sections/{name}': (('overview', 'findings', 'finding', 'structure', 'plan', 'report_file'), 'eaos problems'),
    'GET /api/events': (('runs', 'wait'), 'eaos watch'),
    'GET /api/progress': (('status', 'runs'), 'eaos status'),
    'GET /api/scan-progress': (('status', 'runs', 'wait'), 'eaos watch'),
    'GET /api/report-file': (('report_file',), None),
    'GET /api/screen': (('open_report',), None),
    'GET /api/report-image': (('open_report',), None),
    'GET /api/report-ticket': (('open_report',), None),
    'GET /report/{ticket}': (('open_report',), None),
    'GET /api/projects': (('projects',), 'eaos projects'),
    'POST /api/projects/open': (('open_studio',), 'eaos studio <folder>'),
    'GET /api/sign-in': (('waiting', 'status'), 'eaos waiting'),
    'POST /api/sign-in/skip': (('waiting',), 'eaos sign-in --signed-out'),
    'POST /api/sign-in/forget': (('sign_in_forget',), 'eaos sign-in --forget'),
    'GET /api/assistants': (('assistant_check',), 'eaos doctor'),
    'GET /api/usage': (('history',), 'eaos usage'),
    'POST /api/plan': (('blueprint_start',), None),
    'POST /api/actions/<id>/preview': (('act', 'runs'), 'eaos fix|verify|explain|plan, eaos check'),
    'POST /api/runs': (('act', 'runs', 'replan_ideal'), 'eaos check, eaos fix|verify|explain|plan'),
    'GET /api/runs': (('runs',), 'eaos runs'),
    'GET /api/runs/<id>': (('runs',), 'eaos watch <run>'),
    'GET /api/runs/<id>/events': (('runs',), 'eaos watch <run>'),
    'POST /api/runs/<id>/pause': (('runs',), 'eaos pause'),
    'POST /api/runs/<id>/resume': (('runs',), 'eaos resume'),
    'POST /api/runs/<id>/stop': (('runs',), 'eaos stop'),
    'POST /api/runs/<id>/retry': (('runs',), 'eaos retry'),
    'POST /api/runs/reorder': (('reorder',), None),
    'GET /api/questions': (('waiting',), 'eaos waiting'),
    'POST /api/questions/<id>/answer': (('waiting',), 'eaos answer'),
    'POST /api/runs/<id>/accept': (('accept',), 'eaos accept'),
    'POST /api/runs/<id>/undo': (('undo',), 'eaos undo'),
    'GET /api/decisions': (('waiting',), 'eaos waiting'),
    'POST /api/decisions/<id>/answer': (('waiting',), 'eaos answer'),
    'GET /api/freshness': (('branch_view', 'status'), 'eaos status'),
    'GET /api/context': (('branch_view',), 'eaos branch'),
    'GET /api/branches': (('branch_view', 'branches'), 'eaos branches'),
    'GET /api/branches/detail': (('branch_view',), None),
    'POST /api/branches/analysis': (('choose_branch',), 'eaos branch <name>'),
    'POST /api/branches/merge/preview': (('branch_change',), 'eaos branches merge'),
    'POST /api/branches/merge': (('branch_change',), 'eaos branches merge'),
    'POST /api/branches/conflict': (('branch_change',), None),
    'POST /api/branches/delete/preview': (('branch_change',), 'eaos branches delete'),
    'POST /api/branches/delete': (('branch_change',), 'eaos branches delete'),
    'POST /api/branches/restore': (('branch_change',), 'eaos branches restore'),
    'POST /api/branches/fetch': (('branch_change',), None),
    'POST /api/branches/protect/preview': (('branch_change',), 'eaos branches protect'),
    'POST /api/branches/protect': (('branch_change',), 'eaos branches protect|unprotect'),
    'POST /api/branches/cleanup/preview': (('branch_change',), 'eaos branches cleanup'),
    'POST /api/branches/cleanup': (('branch_change',), 'eaos branches cleanup'),
}
# endpoint -> why it has no tool
PAGE = 'the page\'s own plumbing (its words, token, schemas); an assistant reads the same through its tools list and menu'
CHAT = 'the Studio\'s chat with the person\'s assistant: through MCP that assistant is the chat itself'
SIGN_IN = 'the person signs in to their app themselves, never the assistant (in the Studio, or with eaos sign-in)'
NO_TOOL = {
    'GET /api/locales/{lang}': PAGE, 'GET /api/session': PAGE, 'GET /api/schemas/{name}': PAGE, 'GET /api/openapi.json': PAGE,
    'GET /api/actions': PAGE, 'POST /api/chat': CHAT, 'GET /api/chat/<id>': CHAT, 'GET /api/chat/control': CHAT,
    'POST /api/chat/control': CHAT, 'POST /api/sign-in/open': SIGN_IN, 'POST /api/sign-in/input': SIGN_IN,
    'POST /api/sign-in/done': SIGN_IN,
}
# branch_view's op -> the Studio's own GET route of it
VIEWS = {'inventory': ('branches',), 'detail': ('branches', 'detail'), 'freshness': ('freshness',), 'context': ('context',)}


def view_branches(op='inventory', name=None, remote=None, base=None, project=None):
    """What the Studio's branch screens read, by the same routes: every local and remote branch, one branch's drawer, the
    freshness of the check, the four branches (checkout, analysis, report, base)."""
    if op not in VIEWS: raise ValueError('op is one of ' + ', '.join(VIEWS))
    query = {'name': name, 'kind': 'remote' if remote else 'local', 'remote': remote, 'base': base}
    return GET_ROUTES[VIEWS[op]](govern.core(project), query)


def queue_replan(assistant=None, project=None):
    """The Studio's Re-plan the ideal: a run of the person's assistant over the latest check, queued, the host woken."""
    actions = govern.core(project)
    record = actions.create({'action': 'replan_ideal', 'assistant': assistant})
    govern.wake(actions.project)
    return {'run': actions.public(record), 'what_now': 'Follow it with runs(op=show).'}


def forget_sign_ins(person_agreed=False, project=None):
    from ..studio_server import sign_in as page
    if not person_agreed:
        return {'status': 'needs_the_person', 'why': 'forgetting the kept sign-ins is the person\'s decision',
                'what_now': 'Ask them; only after their yes, call again with person_agreed=true.'}
    return page.forget(govern.core(project).project)


def register(server, reading, working, answer):
    """The tools the Studio has and the other tools lack, on `server`, answered as every tool is (`answer`)."""
    doc = ' project: the project folder (default: the folder the assistant was opened in).'

    @server.tool(annotations=reading, description='Every project EAOS knows on this computer (the Studio\'s project switcher): '
                 'name, folder, score, when it was checked, whether its Studio runs, which one is this. open_studio(project=its '
                 'folder) opens one.' + doc)
    @answer
    def projects(project: str | None = None) -> str:
        from ..studio_server.projects import listing
        return listing(project or '.')

    @server.tool(annotations=reading, description='The branches as the Studio\'s branch screens show them: op=inventory (every '
                 'local and remote branch: owner, protected, ahead/behind of base), detail (one branch, name, remote for a '
                 'remote one: its commits ahead of base, files, diff, checks, runs and every command with why it is blocked), '
                 'freshness (is the check current for the branch EAOS works on), context (the checkout, analysis, report and '
                 'base branches).' + doc)
    @answer
    def branch_view(op: str = 'inventory', name: str | None = None, remote: str | None = None, base: str | None = None,
                    project: str | None = None) -> str:
        return view_branches(op, name, remote, base, project)

    @server.tool(annotations=working, description='Put the queued runs in this order (run ids first, the rest after), as the '
                 'Studio\'s queue is dragged.' + doc)
    @answer
    def reorder(order: list[str], project: str | None = None) -> str:
        return {'queue': govern.core(project).manager.reorder(order)}

    @server.tool(annotations=working, description='Re-plan the ideal structure of the latest check with the person\'s assistant '
                 '(claude or codex; the first ready by default), as the Studio does: a run, followed with runs(op=show).' + doc)
    @answer
    def replan_ideal(assistant: str | None = None, project: str | None = None) -> str:
        return queue_replan(assistant, project)

    @server.tool(annotations=working, description='Forget the sign-ins to the app EAOS kept for this project. The person\'s '
                 'decision: person_agreed=true only after their yes.' + doc)
    @answer
    def sign_in_forget(person_agreed: bool = False, project: str | None = None) -> str:
        return forget_sign_ins(person_agreed, project)
