# NS46.T20: the live scan map

Task: NS46.T20

Scouting record for the owner request of 2026-10-09 (eaos-dev/planning/live-scan-map/PLAN.md): while a check runs,
the Studio shows EAOS's own stage map live. No new package enters EAOS or the Studio for this task. Note: this record
was written in the same branch as the code but after its first commits (the plan's own section "What exists today"
was the scouting); the W2 rule that a record precedes the code is therefore not met for this task, and is said here.

## Recording a run's progress

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| JSON Lines appended by `execute()` itself (`<report>/run-progress.jsonl`) | n/a (EAOS) | 2026-10-09, develop 1b71314 | EAOS | every caller (terminal, assistant job, Studio run) writes it with no change; any reader of the report folder can follow it; the manifest stays the record |
| OpenTelemetry tracing (`opentelemetry-sdk`, spans per stage) | Apache-2.0 | not re-checked | active | a span per stage fits, but needs an exporter and a collector the person does not run; nothing in the Studio reads OTLP |
| The job record of `eaos/jobs.py` | n/a (EAOS) | 2026-10-09 | EAOS | only for jobs the MCP started; `eaos start` from a terminal writes none |
| Prefect / Dagster run events | Apache-2.0 | not re-checked | active | would mean running the pipeline under an orchestrator; far beyond showing its progress |

**Decision**

Build the thin part: `eaos/pipeline/progress.py`, about 150 lines, one JSON line per event, a new file (new inode) per
run, never failing the run. It is glue over the declaration that already exists (`eaos/pipeline/stages.py`).

**Pinned**

none

## Carrying it to the page

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| The existing live feed and stream (`eaos/api/events.py`, sse-starlette, `studio/src/data/live.ts`) | BSD-3 (sse-starlette) | 2026-10-09, as pinned by `mcp` | active | the same numbering, Last-Event-ID replay and guard; a file tail is twenty lines |
| A filesystem watcher (watchdog) | Apache-2.0 | not re-checked | active | pushes changes, but the feed already polls every 0.4 s |
| WebSockets | BSD-3 (websockets) | not re-checked | active | a second channel beside the stream the Studio already reads |

**Decision**

Adopt what is there: the feed tails the progress file and publishes `scan.stage` events; `GET /api/scan-progress`
gives the folded state for a first paint.

**Pinned**

none

## Drawing the live map

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| The Studio's own map parts: `useZoom`, the paths canvas frame, the pinned layered layout (`eaos/arch_map.py` via `eaos/studio/pipeline.py:layout`) | n/a (EAOS) | 2026-10-09 | EAOS | the same places as the other maps, no new dependency |
| React Flow (`@xyflow/react`) with ELK | MIT / EPL-2.0 | not re-checked | active | a full editor for 26 nodes; adds weight and its own styling, and the layout already exists server-side |
| SVG SMIL `animateMotion` / CSS `offset-path` for the moving light | platform | 2026-10-09, Chromium of the pinned Playwright | the browsers | moves a dot along the link's own path, on two or three elements only |

**Decision**

Build the view with the Studio's own parts and SVG `animateMotion`; nothing is added to `studio/package.json`.

**Pinned**

none
