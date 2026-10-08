# NS37.T2: the Studio's local read server and live stream

Task: NS37.T2

Scouting record for the read API on 127.0.0.1, its live stream (SSE) and the server the command centre's action API
(NS46.T9, `docs/studio-actions.json`) mounts next to it. Written 2026-10-08, before the task's code. The candidates
come from lens E of the v2 plan (`eaos-dev/planning/studio-v2/E-adopt-before-build.md`, the P3 platform rows) and
from what EAOS already installs; the versions are the ones resolved in the development environment that day.

## HTTP framework and server

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| FastAPI | MIT | 0.142.4 (2026-10-07), lens E | very active, 100k+ stars | typed routes and an OpenAPI document generated from Pydantic models; a new dependency on every install |
| Starlette | BSD-3-Clause | 1.7.0, installed with `mcp` | active (Encode) | the ASGI toolkit under FastAPI; already a dependency of `mcp`, which EAOS requires |
| Uvicorn | BSD-3-Clause | 0.54.0, installed with `mcp` | active (Encode) | the ASGI server; already a dependency of `mcp` |
| Python's `http.server` (stdlib) | PSF | Python 3.10+ | part of Python | no dependency; one thread per stream, hand-written routing, SSE and shutdown |
| aiohttp | Apache-2.0 | not re-checked | active | a second async stack beside the one `mcp` brings |

**Decision**

Adopt Starlette on Uvicorn, already installed by every EAOS install through `mcp` (its server transports need them),
so the live server adds no download. FastAPI is rejected for now: its gain is an OpenAPI document generated from
Pydantic models, a second source of the shapes, while the Studio's source of truth is the JSON Schemas of the contract
(`schemas/artifacts/studio-*.schema.json`). The read API's routes and its OpenAPI document are generated from those
schemas directly (`eaos/api/read.py`), which is what D-platform asks for. The stdlib server would mean writing
routing, streaming and graceful shutdown by hand, for less. The packages are declared in `pyproject.toml` because
EAOS now imports them itself.

**Pinned**

`starlette@1.7.0` and `uvicorn@0.54.0` (declared as `starlette>=1.7,<2` and `uvicorn>=0.54,<1`)

## Server-sent events

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| sse-starlette | BSD-3-Clause | 3.4.11 installed with `mcp`; 3.5.0 (2026-09-28) in lens E | maintained, 855 stars | `EventSourceResponse`: the wire format, keep-alive pings, client disconnects |
| A hand-written `StreamingResponse` | n/a | n/a | n/a | the same in about 30 lines, without the disconnect handling |
| WebSockets (`websockets`) | BSD-3-Clause | not re-checked | active | two-way, not needed for a read stream; no built-in replay |

**Decision**

Adopt sse-starlette, already installed through `mcp`. Replay of what a client missed (`Last-Event-ID`) is EAOS's own:
the events carry a sequence number, and the feed (`eaos/api/events.py`) keeps them. The project's event log
(`events.jsonl`, NS39.T2) is not written yet, so the feed derives its events from the Studio manifest's section digests
(a new scan, a batch, a merge, a decision), and says so in every event (`source: manifest`); when the event log exists,
the feed reads it instead.

**Pinned**

`sse-starlette@3.4.11` (declared as `sse-starlette>=3.4,<4`)

## The Studio's live data source

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| The browser's `EventSource` | n/a (web platform) | every browser | standard | cannot send a header, so the run token would go in the address |
| `fetch` with a stream reader | n/a (web platform) | every browser | standard | sends the token header and `Last-Event-ID`; about 60 lines to parse the format |
| @microsoft/fetch-event-source | MIT | not re-checked | last release 2021 | the same as a package; unmaintained |
| TanStack Query | MIT | not re-checked | active | caching and refetching; the Studio holds one report in memory and reloads it whole |

**Decision**

Build the thin adapter in `studio/src/data/` over the web platform's `fetch`: the token stays in a header (never in
the address or a log), and a missed event is replayed by `Last-Event-ID`. The package that does the same is
unmaintained, and a cache library is not needed for one report reloaded on an event. No package is added to the Studio.

**Pinned**

none
