"""The Studio's local server (NS37.T2, docs/STUDIO.md): the read API, the live stream and the built Studio, on
127.0.0.1 only, behind a token made for each launch.

    guard.py   the token, the Host and Origin checks and the CSRF token, on every request
    read.py    the read routes and their OpenAPI document, generated from the contract's schemas
    events.py  the live feed: the project's event log when there is one, else the Studio manifest's digests
    server.py  the app: the Studio's assets, the read API, the stream, the mount point of the action API, and
               `eaos studio` (run_foreground)
    launch.py  the server's record: find, reuse and open the running server of a project, without importing
               the server (agent_tools.open_studio starts one)

Starlette, Uvicorn and sse-starlette are adopted (docs/adoption/ns37-t2-live-server.md); they come with `mcp`.
"""
