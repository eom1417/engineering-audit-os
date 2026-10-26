"""A check of a project, one implementation for the CLI (`eaos start`, `eaos next`), MCP (`audit`) and the Studio (its audit
run calls MCP's): the code it reads and that code's provenance taken first, the pipeline and the remedies that need no
person, START-HERE.md even when composing did not run, then the state stamped, its stale batch retired, the pages
published and the state saved (M3.3: the CLI had its own copy, without the remedies or the tools' fingerprint).
"""
from datetime import datetime, timezone
from pathlib import Path

from ..core.project import branches, state as project_state
from .guided.batches import retire_stale_batch
from .guided.project import chosen_assistant, publish, report_of, save, source, tip
from ..core.system.version_info import digest
from ..pipeline import check, remedies
from ..report.documents.start_here import start_here


def run(state, options, again_from=None, go_on=False):
    """(the check's manifest, the state saved after it, the page people read). `options`: eaos/journeys/check_choices.py options. `again_from`:
    the last check goes on from that stage, on the code it checked; `go_on`: a check that did not end goes on."""
    out = report_of(state)
    code = source(state, state.get('scanned_commit') if again_from else None)
    # taken before the check reads: a commit made meanwhile is not in it
    read = {} if again_from else {'scanned_commit': tip(state) or None, **branches.scan_provenance(state, code)}
    done = check(str(code), out, again_from, state.get('scanned_dirty') is False, go_on=go_on, **options)
    done = remedies.apply(done, lambda stages: check(str(code), out, stages, True, **options), out, options,
                          chosen_assistant(state))
    if not (out / 'START-HERE.md').is_file(): start_here(out, state.get('lang') or 'en', Path(state['project']).name)
    state = project_state.load(state['project'])            # as the check's stages left it
    state.update(scanned=datetime.now(timezone.utc).isoformat(timespec='seconds'), scanned_with=digest(), **read)
    retire_stale_batch(state)
    page = publish(state)
    save(state)
    return done, state, page
