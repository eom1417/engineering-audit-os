"""The run engine (eaos/journeys/runs) wired to this EAOS's MCP tools: the `Actions` that eaos govern, the terminal
and the MCP governance tools build."""
import functools

from ..journeys import runs as engine


@functools.lru_cache(maxsize=1)
def server_tools():
    """MCP tool name -> callable returning its JSON text: what a direct run calls."""
    from .mcp_server import server as mcp_server
    return mcp_server.functions()


@functools.lru_cache(maxsize=1)
def reading_tools():
    """The tools answered at once, not queued: those the MCP server marks read-only, and ANSWERED_AT_ONCE."""
    from .mcp_server import server as mcp_server
    return mcp_server.reading() | set(engine.ANSWERED_AT_ONCE)


def rule_shown(project, rule):
    """What a change of one of the person's rules touches (eaos/interfaces/rules.py touches)."""
    from .rules import touches
    return touches(project, rule)


class Actions(engine.Actions):
    """`eaos.journeys.runs.Actions` with this EAOS's tools, read-only tools and rules."""
    def __init__(self, project, **options):
        super().__init__(project,
                         **{'tools': server_tools, 'reading': reading_tools, 'rule_shown': rule_shown, **options})


_where_of = engine._where_of
