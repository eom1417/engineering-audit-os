"""The Studio's local server (NS37.T2, docs/STUDIO.md): the read API, the live stream and the built Studio, on
127.0.0.1 only, behind a token made for each launch.

    guard.py   the token, the Host and Origin checks and the CSRF token, on every request
    read.py    the read routes and their OpenAPI document, generated from the contract's schemas
    events.py  the live feed: the project's event log when there is one, else the Studio manifest's digests
    server.py  the app: the Studio's assets, the read API, the stream, and the mount point of the action API
    launch.py  `eaos studio` and the `open_studio` tool: start or reuse the server of a project, open its address

Starlette, Uvicorn and sse-starlette are adopted (docs/adoption/ns37-t2-live-server.md); they come with `mcp`.
"""
