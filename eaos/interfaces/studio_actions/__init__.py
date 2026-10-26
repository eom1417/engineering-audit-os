"""The command centre's action API (docs/studio-actions.json): run EAOS from the Studio.

Framework-agnostic: `Actions.handle(method, path, headers, body)` answers every endpoint of the contract with
`(status, dict)`, and `Actions.sse(run, last_event_id, follow)` yields a run's events as Server-Sent Events frames. The
local server (NS37.T2) mounts them with `mount(...)` (eaos/interfaces/studio_actions/serve.py); the tests call them directly.

    actions = Actions(project, port=8765)            # the launch token and the CSRF token are made here
    status, payload = actions.handle('POST', '/api/runs', headers, {'action': 'audit'})
    for frame in actions.sse(run_id, last_event_id=12, follow=True): ...

Every call passes the locks of eaos/core/system/studio_access.py first; every accepted action becomes an `action` event
before it runs; reading actions answer at once, the others queue as runs (eaos/interfaces/studio_actions/runs.py).
The code is in eaos/interfaces/studio_actions/centre.py; this package names what the rest of EAOS imports.
"""
from .centre import GET_ROUTES, Actions, contract, mount
from .previews import _where_of

__all__ = ['GET_ROUTES', 'Actions', 'contract', 'mount', '_where_of']
