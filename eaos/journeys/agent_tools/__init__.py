"""What an AI assistant does EAOS with (docs/MCP.md): the tools behind eaos/interfaces/mcp_server/server.py.

The assistant is the one who thinks: it reads the evidence, reads the code, proposes how the app runs, writes
the fixes. EAOS gives it the evidence, the isolated copy and the gates, and never calls a model itself here.
Every tool returns a plain dict; one that takes longer than a tool call waits returns a job (eaos/core/project/jobs.py) that
`wait` follows. The person's project is only ever written through git: a branch `eaos/<branch>/wave-N`, fetched in.

State is the guided commands' own (~/.eaos/projects/<name>-<hash>/state.json), so the two ways meet: a check
started with `eaos start` is the one `overview` reads, and the other way round.
"""
from ..fix import finish as batch_finish
from .checking import _audit_job
from .fixing import _fix_edit_job, _fix_start_job
from .tidying import _context_job, _moves_job
from .running import _run_job, _safety_job

# The names other modules call through the package (agent_tools.status, agent_tools.accept ...), each kept in one module here.
from .checking import PERMISSION, _assistant_not_ready, assistant_check, audit, overview  # noqa: F401
from .deciding import _merge_problem, accept, undo  # noqa: F401
from .evidence import (ask, finding, findings, impact, open_report, plan, report_file, structure, tools_check)  # noqa: F401
from .edits import _apply, _inside  # noqa: F401
from .fixing import (_chosen, _no_safety_net, _still_open, delivery, fix_abandon, fix_edit,  # noqa: F401
                     fix_finish, fix_read, fix_skip, fix_start, waiting_on, work_branches)
from .tidying import context_make, context_propose, moves_make, moves_propose  # noqa: F401
from .project import (ANSWER_SECONDS, EVIDENCE, PAGE, SeveralProjects, TOOLS_FIRST, WAIT, _current, _head,  # noqa: F401
                      _now, _read, _report, _start, _watch, locate, open_studio, repositories_under, state_of,
                      tool_digest, wait)
from .running import CONSENT, run_setup, run_try, safety_net  # noqa: F401
from .where import OLDER_CHECK, _branch, _fresh_report, branches_of, choose_branch, status  # noqa: F401


JOBS = {'audit': _audit_job, 'run_try': _run_job, 'safety_net': _safety_job, 'fix_start': _fix_start_job,
        'fix_edit': _fix_edit_job, 'fix_finish': batch_finish.finish_job,
        'moves_make': _moves_job, 'context_make': _context_job}
