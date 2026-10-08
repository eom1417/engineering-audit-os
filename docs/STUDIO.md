# EAOS Studio: decision record and data contract

EAOS Studio is the front end of EAOS. After every check EAOS writes the Studio's data next to the report, and anyone
who ran the check opens it and follows everything about the project from one place: the current state, the ideal
picture and the gap between them, the cards with their evidence, the plans and their sub-plans with their gates, the
decisions waiting for them, the documents, the images and the progress over time.

The strategy behind this record (analysis with EAOS, four independent ideal pictures, reverse engineering, structure,
execution steps) was approved by the owner on 2026-10-07. The steps are NS36 and NS37 in `docs/north-star.json`.

## Decisions

### D1: where the Studio lives

Inside the EAOS package, built at release time and shipped as static assets under `eaos/data/studio/`. Whoever
installs EAOS has the Studio with no extra step and no Node at run time.

### D2: one model for REPORT.html and the Studio

One model inside EAOS (`eaos/studio/model.py`) computes every number once. The Studio, `REPORT.html` and the numbers
external dashboards read are three views of it; none of them reads an internal file or computes a number on its own.

### D3: when building starts

Approved 2026-10-07: after NS30. Amended by the owner on 2026-10-08: the Studio has priority, because it is the guide
for the rest of the work. NS30.T1 (cards on their own files) and NS30.T2 (the field scenarios, which give the scan's
commit the Studio's freshness stamp shows) stay first; then NS36, NS32 (plans and decisions, which feed the Studio's
plan pages) and NS37; NS31 and the rest follow.

### D4: the stack

React and TypeScript built with Vite; React Aria for accessible, right-to-left aware components; design tokens with
CSS Modules (logical properties, so the direction flips by itself); d3 for charts; React Flow with ELK for
diagrams; markdown-it with raw HTML off for documents; Mermaid bundled locally. Fonts (IBM Plex Sans Arabic) are
bundled. Nothing is loaded from the network at run time, and the content security policy forbids it.

### D5: the product plan's order

The Studio is the whole of EAOS's front end, and every later step adds its own page to it. Phase R6G ("Trust, plans
and initiative") runs NS30 → NS36 → NS32 → NS37 → NS31 → NS33 → NS34 → NS35.

### D6: the design direction

Three directions were drawn as static mockups on FleetManageWeb's real report: Instrument, Atlas and Calm. Each
covers Home, the System map and a card's detail on phone and desktop, in Arabic and English, light and dark: 72
shots, all passing the automated gates. On 2026-10-08 the owner approved the recommendation, **Instrument as the
base**, and left the exact blend to the developer, choosing for elegance and practicality:

- **Instrument**: type, colour, density, the desktop sidebar, the phone tab bar with five sections (Home, System,
  Problems, Change, Decisions), and dark and light finished to the same standard.
- **From Atlas**: the System map as a territory, with cluster hulls, map-style labels and label placement by
  priority. Home also opens with Atlas's one-sentence headline, where every number is a link.
- **From Calm**: the phone decision card, with one question, its recommendation and large one-tap answers.

The blended mockup and its design system spec live in `eaos-dev/planning/studio-v2/directions/studio/`
(`DESIGN.md`, `REVIEW.md`); NS37.T1 builds that spec, and no other direction is built.

### D7: Studio first

Decided by the owner on 2026-10-08: the front end is finished, complete and professional, before more engine work,
so that every later engine step visibly fills a page or raises a measured number. The phase is NS46 in
`docs/north-star.json`, placed first in R6G; its spec is `eaos-dev/planning/studio-v2/STUDIO-COMPLETE.md`.

- **Coverage states, never "coming soon".** A page whose data EAOS does not produce yet shows a designed state that
  says what is missing, why, and which step will produce it, read from `studio/coverage.json`. The share of sections
  still "not measured yet" is an indicator that may only fall (F12).
- **Contract v2 is defined now**, as additive sections (below): the pages are built and tested against fixtures, so
  later engine work only fills data.
- **The exit gate** of STUDIO-COMPLETE.md: every route of the experience plan (C-experience §2.2, listed in
  `docs/studio-routes.json`) exists and shows real data or a designed coverage state (F11); the screen gates pass on
  FleetManageWeb, chief-ops, finance-os, EAOS itself and a synthetic project of 5,000 cards and 1,000 components
  (F13); Lighthouse mobile and the speed budgets hold (F14); and the owner reviews it. The engine roadmap resumes
  (NS38.T2 onward) after that gate.

### D8: the command centre

Decided by the owner on 2026-10-08: the Studio becomes the place where EAOS is operated, not only read. "Can we
control it from the UI: see the tasks, press a button to run this step, or pick several tasks or a group and run
them, so the front end sends the work to the assistant we work with and it does it?" Then: "Build it from the
start, while designing and finishing the front end; above all it must give a truly world-class, legendary
experience." The spec is the command-centre section of `eaos-dev/planning/studio-v2/STUDIO-COMPLETE.md`; the
contract is `docs/studio-actions.json` (`docs/studio-actions.md`); the tasks are NS46.T9 (action API and assistant
launcher), NS46.T10 (selection, preview, live run, queue, runs history, inbox) and NS46.T11 (the real trial on
FleetManageWeb), and indicator F15 joins the exit gate of D7.

- **Every MCP tool is an action** with a button, a form or a flow; one card, a selection, a group or a plan step can
  be fixed, verified, explained or planned; a preview comes before anything that changes code.
- **The person's own assistant runs it**, headless (Claude Code `claude -p --output-format stream-json`, Codex
  `codex exec --json`), with the EAOS MCP server and only the EAOS tools to change code; without one, the request is
  handed to the next `status` call and offered as text to copy. Deterministic actions call EAOS directly.
- **The guarantees stay**: changes only in the isolated copy, handed over as a new branch; accept and undo only on the
  person's explicit confirmation; the run consent asked once. The assistant never answers the person's three
  questions: they come back as decisions in the inbox.
- **The server's rules** (127.0.0.1 only, launch token, CSRF and origin checks, every action in the event log)
  supersede the earlier "the Studio only reads" for the local mode: the Studio still never sets a state by hand (no
  "done" button); every action is an EAOS tool call, recorded like the assistant's.

## Data contract v1

EAOS writes `studio/` inside the report folder after every check, in the same publishing step as the report, so the
two never drift. The contract is `contract v1`: every file carries `"contract": 1`, and a change that breaks a
reader raises the version.

| File | Holds |
|---|---|
| `studio/manifest.json` | Which EAOS built it (`version`, `commit`, `digest`, `studio_digest`), the scan, and every section with its sha256. Written last, so a reader never sees a half-written set. |
| `studio/meta.json` | Languages, size, the stages of the check. |
| `studio/head.json` | The scan stamp, freshness (`fresh`, `branch_moved`, `eaos_updated`, `unknown`), the verdict in one sentence, the next step. |
| `studio/health.json` | One score by one formula, its domains, the score after every scan. |
| `studio/cards.json` | Every card on its own file and evidence, its scope (`place` or `group`) and its state from the ledger. |
| `studio/evidence.json` | The facts the cards cite: engine, kind, sites. |
| `studio/story.json` | Current state, target state, the gap per component, indicators today / expected / target. |
| `studio/docs.json` | Every document the check wrote, grouped by purpose, in reading order. |
| `studio/plans.json` | Every plan in one model (below). |
| `studio/decisions.json` | What waits for the person: one question, its recommendation, what it blocks. |
| `studio/media.json` | Screens before and after each batch, diagrams, charts. |
| `studio/system.json` | The project as two territory maps, today and the target (below). |

The schemas are generated by `tools/make_contracts.py` into `schemas/artifacts/studio-*.schema.json`, with a
byte-identical packaged copy in `eaos/data/schemas/artifacts/`. `eaos/artifact_contracts.validate` judges them.

Rules every section follows, enforced by its schema:

- A number the Studio shows is a measure `{value, src}`: `src` names the file and field, or the formula, it comes
  from. What was not measured is `null`, never `0`.
- A ratio is bounded to 0..1.
- A path is relative to the project: never absolute, never `..`, never a home directory. No secret is written.

## Data contract v2: additive sections

Contract v2 (D7) adds sections without breaking a v1 reader: each keeps `"contract": 1` (the number only a breaking
change raises) and carries `"revision": 2`; the manifest carries `"revision": 2` and lists them, and a v1 reader skips
a section it does not know. The schemas are generated by the same `tools/make_contracts.py` (`x-revision: 2`).

| File | Holds |
|---|---|
| `studio/functions.json` | Every function by module: signature, summary, callers and callees, data read and written, size and complexity, its cards. |
| `studio/screens.json` | Every screen: route, shots per viewport before and after each batch, inputs, usability issues pinned to a region. |
| `studio/gaps.json` | The gap register: per component, the operation that closes it, its cards, steps and operations, how far it is closed. |
| `studio/operations.json` | The ordered operations (retain, refactor, rebuild, merge, delete, new), their subject, step and what they wait for. |
| `studio/history.json` | Every scan with its score and open cards by severity, what it added and resolved, and the events between scans. |
| `studio/quality.json` | How good EAOS's own analysis is here: detector precision and recall, capability coverage, the plan's indicators. |
| `studio/paths.json` | The code paths: every page, server route, command or job through its layers (screen, component, handler, call, endpoint, service, data), each node and link with its evidence, a gap where the records stop, the target of each step, the layout and the clustered overview; and the fix plan's timeline (waves, and what each task waits for). |
| `studio/journeys.json` | The user's journeys: every screen (full route, component file, kind) on a pinned grid, the links between screens with the file and line of each, the main tasks as paths from the start, broken links, screens with no way in, dead ends and duplicates, each screen's folder operation, and what the engine does not give yet (`missing`). |
| `studio/hidden.json` | What the user sees against what runs unseen: screen areas, and jobs and triggers, routes that are not pages, server routes, writes, outside services, configuration and secrets, build steps and dead code, each with its evidence, the areas that set it in motion and the component that holds it. |
| `studio/data_paths.json` | Every store (table, API resource, bucket) with its endpoints, writers, readers and request keys; every write as a path from input field to column with its gaps; the stores written from more than one module; the overview laid out today and in the target. |
| `studio/infra.json` | Hosting, CI/CD, environments, databases, queues, external services and observability, each with its evidence, and the target architecture's decision per area. |
| `studio/coverage.json` | Every section with its state (`measured`, `empty`, `partial`, `not_measured`, `failed`), a reason code, the step that will produce it and how. Written by the exporter after every check, last of the sections. |

Small fixtures of each section live in `tests/fixtures/studio/v2/`; `python tools/studio_synthetic.py --out DIR` writes
a whole data folder of 5,000 cards and 1,000 components, every reference resolved, for the pages and the gates.
`docs/studio-routes.json` lists every route the phase must ship, the data it reads and the task that builds it.

`build_info.studio_digest()` fingerprints the built assets and the Studio's schemas apart from `build_info.digest()`,
so a change to the interface alone rebuilds the Studio without forcing a new check.

## The system maps (`studio/system.json`)

The System page, the Home "Land of the project" card and the Change page draw the project as a territory
(the design spec's §6). Everything they draw is written by EAOS (`eaos/studio/system.py`, `eaos/studio/territory.py`);
the Studio computes no position and no number.

- **Today**: the components of `target-architecture.json` (`current_components`), each with its files, kind,
  fan-in/out, findings by severity (a card counts in the deepest component holding its first path, the rule the
  ranked list and the Problems page's component filter use), its operation toward the target (retain, modify,
  rebuild, delete), its target and the structure decision recorded for it. The edges are the resolved imports of
  `facts/graph.json`, counted between the components owning both files; an edge inside one strongly connected group
  is marked as a cycle.
- **The target**: `target_components` and `target_edges`. A target component fed by no component of today is
  introduced, by two or more is a merge, by one takes that component's operation.
- **The layout**, computed once and deterministic: regions split from the folder tree while one region holds most
  components (at most seven; small top-level folders share one; the target's regions are its layers); a squarified
  treemap gives each region its room; a seeded force layout places the dots; marching squares over a summed gaussian
  field draw the land at three levels; labels are placed by priority, a label only where it collides with nothing.
- Every count carries its source (`counts`, `operations`, and `src` for the per-component fields).

This section is the precursor of NS39.T1's unified graph: the same nodes and weighted edges, read by one page. When
the unified graph lands, `system.json` becomes its view rather than its own reading of the records.

The pan and zoom are the Studio's own (about 120 lines, `studio/src/map/useZoom.ts`); the drawing is plain SVG from
React. Neither d3 nor React Flow with ELK is installed: the layout comes from EAOS, so what D4 named them for is done
before the browser (`docs/adoption/studio-maps.md`).

## The code paths (`studio/paths.json`)

System → Paths, a path's own page (`#/flows/<path>`, with its Sequence and Steps views) and Change → Plan timeline
draw what `eaos/studio/paths.py` writes; the Studio computes no position and no number.

- **A path** follows one entry (a page, a server route, a command or a job) through seven swimlanes: screen →
  component → handler → call → endpoint → service → data. Each link says how it is known (`how`): the page's route,
  the page's flow reaching a file (`call`), only the resolved imports reaching it (`imports`, drawn as possible, not
  traced), the HTTP or database call itself (`request`), a server route with the same method and path (`route`) or a
  file-routed candidate (`file_route`), the parts the handler calls or imports, the tables it defines and the
  services it imports by package. Every node and link carries its fact, file and line.
- **Gaps are drawn, never filled.** A call no server route answers in the code EAOS read, a screen whose component file
  is unknown, a flow that stopped at calls it could not resolve, a server entry with no traceable handler: each is a
  gap node in the lane where the path stopped, with its reason, and nothing follows it. The gaps are counted in
  `counts` and in the section's row of `coverage.json` (`parts`).
- **Current, Target and Change** draw the same nodes in the same places: each node names the part of today owning its
  file, and `components` gives that part's operation (retain, refactor, rebuild, merge, delete), its target part and
  layer; `new` lists the target parts nothing of today feeds. A node lists the cards on its file and their plan steps.
- **The layout** is EAOS's own layered layout (`eaos/arch_map.py` barycentre sweeps), with the lanes as the layers,
  computed per path and for the overview, so a node keeps its place between views and between runs on the same code.
- **The overview** draws every path at once as clusters (a lane and a part, a route group, a kind of gap), cut to
  parent folders until at most 150 remain; past 1,000 nodes the Studio never draws every step at once.
- **The plan timeline** is the fix plan in waves (`eaos/plan.py` waves()): each task's step and wave, and what it
  waits for, a prerequisite the plan names or the last task of an earlier wave touching the same file.

## The user journeys and the visible and hidden lens (`journeys.json`, `hidden.json`)

System -> User journeys and System -> Visible and hidden (NS46.T6, STUDIO-COMPLETE's must-haves) are written by
`eaos/studio/journeys.py` and `eaos/studio/hidden.py` from the facts; the Studio only draws.

- **Screens** are the page entry points at their full route (`js_routes` joins a nested React Router route to its
  parent's path); **links** are the `navigation` facts (`js_navigation`: `<Link to>`, `href`, `<Navigate>`,
  `navigate()`, menu entries), each owned by the screens that render its file, or by the menu of the layout route.
  A link whose target opens no screen is broken; a link in a file no screen renders is counted, not drawn.
- **Columns** are clicks from the start (`/`); the order inside a column comes from `arch_map`'s barycentre sweeps; a
  screen keeps its grid cell from the previous `journeys.json` of the report, so it keeps its place across scans and
  between the Today, Change and Target views.
- **Change and Target**: a screen takes its folder's operation and target component. The target architecture decides
  folders, not screens: every screen without a decision of its own is counted in `missing` (step NS44.T1), and so are
  the screen shots the gate has not taken (NS41.T1). A section with `missing` parts is `partial` in `coverage.json`.
- **Hidden**: routes that are not pages (layouts, redirects, catch-alls) are drawn hatched only with "show hidden"; the
  lens groups the unseen work with its evidence and flags what has no screen in front of it; the System map marks the
  components that hold it.
- A large app (more than 250 screens) opens on its areas; an area expands to its screens and their neighbours.

## The data paths and infrastructure maps (`studio/data_paths.json`, `studio/infra.json`)

System → Data and the System map's infrastructure lens. Both are written by EAOS from records only
(`eaos/studio/data_paths.py`, `eaos/studio/infra.py`); a tier or lane the records do not reach is drawn as a gap with
its reason and the plan step that will reach it, and counted in the coverage row's parts.

- **Data paths.** A store is a table (a Supabase `.from(t)` call or a `CREATE TABLE` in the code), a bucket, a database
  function, the auth service, or an API resource of the app's own back end (its endpoints grouped by first path
  segment). Each write is a path through seven tiers: input field, form, request key, calling module, endpoint, server
  handler, column. Today the records reach the calling module and the endpoint everywhere; the request keys where the
  call sends an object literal (`data_access` `keys`); the handler where the repository declares the server route of the
  same method and path, and the columns its flow writes; a Supabase row's keys are its columns. Field and form wait for
  NS40.T2's form extractor, so the section's coverage row is `partial`. An endpoint or a table written from more than
  one module is an ownership violation (A-analysis N6). In the target each writer goes where its component goes
  (`target_component`); a store whose writers land in one target component has a single source there.
- **Layout.** Callers (grouped by component) and stores in two lanes, ordered by barycentre sweeps
  (`arch_map.order_columns`); the target view keeps the stores' places and orders its components against them. Above
  40 nodes a lane is clustered (stores by kind and name prefix, callers by folder) and each cluster expands.
- **Infrastructure.** Seven lanes from runtime, config, resolve, entry point and domain facts, with test files left
  out. The target is `target-architecture.json` `infrastructure` (keep or introduce, per area); a lane the target says
  nothing about (usually queues and services) is "not measured yet" for the target, never shown as fine.

## Live: the local server (NS37.T2)

`eaos studio` (and the `open_studio` tool, for an assistant) rebuilds the Studio data from the ledger, starts a server
for the project on 127.0.0.1 and opens `http://127.0.0.1:<port>/#token=<launch token>` in the browser. The server is
`eaos/api/` on Starlette, Uvicorn and sse-starlette, which come with `mcp` (docs/adoption/ns37-t2-live-server.md). One
server runs per project: its record (port, process, token) is `~/.eaos/studio/<workspace>.json`, readable by the person
only, and a second `eaos studio` or `open_studio` reopens it.

| Route | What |
|---|---|
| `GET /`, `/boot.js`, `/assets/*` | the shipped Studio (eaos/data/studio), served with `connect-src 'self'` in place of the snapshot's `'none'` |
| `GET /api/session` | the mode (`live`), the CSRF token, the project, the feed's source and last id, whether actions are mounted |
| `GET /api/manifest` | studio/manifest.json; 404 `empty` before the first check |
| `GET /api/sections/<name>` | studio/<name>.json byte for byte, for every `studio-<name>` schema of the contract; 404 with the section's coverage row when the check did not write it |
| `GET /api/schemas/<name>`, `GET /api/openapi.json` | the section's JSON Schema, and the OpenAPI 3.1 document of these routes generated from the schemas |
| `GET /api/events` | the live stream (server-sent events), below |

Rules, enforced by `eaos/api/guard.py` and `tests/test_studio_api.py`:

- It listens on 127.0.0.1 only, and answers only to the Host `127.0.0.1:<port>` or `localhost:<port>` (DNS rebinding).
- Every `/api/` call carries `X-EAOS-Token`, compared in constant time. The token travels in the address's fragment,
  which no browser sends to a server; `boot.js` keeps it in the tab's session storage and removes it from the address
  (`#token=…`, or `#/<route>?…&token=…` to open a route). It never reaches a log, the page or the session answer.
- The read API has no write. A write that is mounted beside it (the action API) needs `X-EAOS-CSRF`, from
  `/api/session`, and an Origin (or a Referer) of this server.

**The stream.** The feed (`eaos/api/events.py`) numbers what changed; an event's id is `<epoch>-<seq>`, and a reconnect
with `Last-Event-ID` gets every event it missed, or `reset` (reload everything) when the id is from an earlier server or
older than the 2,000 the feed keeps. The source is the project's event log (`events.jsonl`) once NS39.T2 writes it;
until then the feed watches the manifest's section digests and names the change: `scan.done` (the scan changed),
`batch.delivered` (cards moved to `in_batch` or `on_branch`), `branch.merged` (cards moved to `done`), `decision.asked`
and `decision.answered`, else `studio.updated`. Each event says its source and the sections whose digest changed.

**The Studio's side.** The pages read through one interface (`studio/src/data/source.ts`): the snapshot (the data
scripts beside the Studio, from a file or any static server) or the live server (`live.ts`), chosen by whether the tab
holds a launch token. Both give the same data from the same files. Live, an event reloads only the sections whose
sha256 changed, the pages re-render in place, and a polite live region says what changed in the person's language.

**The action API mounts here.** `create_app(report, mounts=[mount])`, where `mount(ctx)` returns Starlette routes or
`(method, path, handler)` tuples of framework-free handlers (`server.plain`); `eaos.studio.actions.mount` is mounted by
itself when it exists. Mounted routes get the guard (token, CSRF, Origin) and publish into the same stream with
`ctx.publish(kind, data, text)`.

**F9** is measured by `tools/studio_live_trial.py`: the real server on a copy of a report's data, the shipped Studio
in Chromium at 390 (Arabic, light) and 1440 (English, dark), and the four events written the way the exporter writes
them; each must show on the page within 5 s.

## The plan model

One model for every kind of plan: an EAOS fix plan, a build plan, the product plan itself, a plan the owner
registers, and a sub-plan. A plan has a goal and indicators; it holds steps (weight, gate, dependencies); a step
holds tasks (acceptance, rollback); a step may expand into a sub-plan of the same model. Decisions and events
attach to the plan; tasks close cards by their stable key.

Only the words are written by a person. Every state, number and date is computed from git, the gates and the
recorded decisions; nothing is marked done by hand.

A plan's life:

| From | To | Event |
|---|---|---|
| — | `draft` | written |
| `draft` | `registered` | the plan validates |
| `registered` | `approved` / `rejected` | the person's recorded decision |
| `approved` | `active` | the first commit of a step |
| `active` | `review` | every gate passed |
| `review` | `merged` | git sees the branch in the base |
| `merged` | `closed` | the goal is met after a new check |
| `closed` | `regressed` | a criterion no longer holds; back to `active` |
| `closed` | `archived` | kept for the record |

A task is `todo`, `active`, `done`, `blocked` or `regressed`; a card is `open`, `in_batch`, `on_branch`, `done`,
`resolved` or `skipped` (`eaos/ledger.py`).

## Standards

- Truth: every number with its source; the unmeasured never shown as zero; progress only from merges or measured
  indicators; a conflict in the data is shown, not hidden; one number, one value on every page.
- Freshness: the scan stamp on every page; a banner when the branch moved or EAOS changed; rebuilt with every check
  and merge.
- Governance: no "done" button anywhere; every action is an EAOS tool call through the command centre (D8), run by
  EAOS or the person's assistant and logged; in snapshot mode it is a sentence copied to the assistant.
- Clarity: every page answers where we are, where we should be and what is next; one main action per page; every
  chart has a one-sentence title, units, source and a table alternative.
- Quality: designed empty, loading and error states; every entity has a link that restores its view; crowded charts
  fold above 8 items; Arabic and English match.
- Technique: offline (enforced by the content security policy); opens from a file; under two seconds on 5000 cards;
  no serious accessibility violation; motion within its tokens, and stopped for whoever asks.
