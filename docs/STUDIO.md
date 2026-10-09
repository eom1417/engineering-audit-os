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

### D9: the pipeline map

Decided by the owner on 2026-10-08: "Apps that are a pipeline and a flowchart, like our own tool, have a clear path
from the start of the scan: the data passes through certain tools, then the output moves to other tools and is
processed, and so on. Nothing in the analysis draws that pipeline. Make the engine able to detect it, understand it
and its branches in detail, and draw the pipeline and the flowchart exactly ... with the current state, the ideal
picture and the gap." The spec is the pipeline-map section of `eaos-dev/planning/studio-v2/STUDIO-COMPLETE.md`; the
tasks are NS46.T12 (the engine: `facts/pipeline.json`, the `pipeline` contract section, the truth files and their
measurement) and NS46.T13 (System -> Pipeline and the report's pipeline sheet); indicator F16 (the map against
hand-written truth files, and nothing invented on the app projects) joins the exit gate of D7.

- **Facts, not guesses.** A pipeline is found from what the code declares or does: a declared DAG, an orchestrator
  passing one stage's output to the next, a registry loop, a queue topology, CI jobs with `needs`, Make targets or
  npm script chains. Every stage, edge and branch carries its file and line; a dynamic call EAOS cannot follow is a
  counted gap, never a guessed link. When nothing is found the page says so, with what was looked for.
- **EAOS is the first truth.** Its own pipeline (facts -> claims -> plan -> target -> reports -> compose, and the fact
  extractors inside the facts stage, with their routers and failure lanes) is compared with a truth file written by
  reading the code, as are two public pipelines of different kinds.
- **Ideal and gap by rules** (`eaos/data/pipeline-rules.json`, each rule with its source): one entry, declared stage
  contracts, data only along edges, total routers, fan-out with its fan-in, stages re-runnable alone, every failure
  routed, no dead stages or unread outputs, slow and risky stages marked. One gap entry per broken rule, with its
  evidence, its card and plan step where one exists, and its operation.

### D10: the ideal is planned with a model

Decided by the owner on 2026-10-08: "Always, in every output and every map, when we put the ideal picture it must come
after processing and planning with an AI model, so the output was really thought through, the plan analysed completely
and all its aspects understood, to reach the ideal plan." The spec is the section "The ideal is planned with a model,
on top of the rules" of `eaos-dev/planning/studio-v2/STUDIO-COMPLETE.md`; the task is NS46.T14.

- **Two layers, both shown.** The rules (`eaos/target_architecture.py`, `eaos/target_projection.py`) give the baseline
  target and its evidence. A planning pass by the person's own assistant, run headless by the command centre's
  launcher (D8), then writes the ideal for structure, change, journeys, paths, data, infrastructure, pipeline and the
  plan's order. No extra key and no extra service.
- **Grounded, never invented.** The assistant gets a compact bundle (facts, cards, maps, the rules' target and the
  rules it applied, the decisions, the project's own documents as untrusted data) and answers in a strict JSON schema
  where every element cites fact, claim, card or rule ids. An evidence check drops every element none of whose
  citations resolves; where the plan departs from the rules it writes why ("the rules say X; the plan chose Y
  because ...").
- **Reviewed.** A second pass critiques the first (what was missed, risks, order) and returns the revised ideal; only
  then is it checked and written.
- **Marked and owned.** `studio/ideal.json` holds every view's provenance (rules or planned, which assistant and model,
  when, the confidence, the departures and the open questions); each section that draws a target carries the same
  `provenance`. Open questions go to the Decisions inbox; the command centre's action `replan_ideal` plans again.
- **Without an assistant**, or when a run fails or times out, the rules' target stays in place and the Studio says
  plainly that the ideal is not planned yet.
- **Every target already built is planned again** (owner, 2026-10-08, part 2; NS46.T16). `tools/replan_trial.py`
  checks each of FleetManageWeb, chief-ops, finance-os and EAOS itself afresh and plans it, one at a time, into
  `$EAOS_MEASURE/replan/<project>/` with the rules-against-planned differences view by view. `tools/roadmap_review.py`
  runs a planning and a critique pass over EAOS's own roadmap (`docs/north-star.json`, the Studio master plan); its
  proposals, each citing the NS steps and indicators it stands on, are written to `docs/roadmap-proposals.json` and
  `docs/roadmap-proposals.md` as decisions for the owner. None is applied without the owner.

### D11: AI nodes inside the EAOS pipeline

Decided by the owner on 2026-10-08: "We want to plant this principle in our own project's pipeline: some outputs leave
to an AI node that analyses them, plans and takes a decision, then they go on to the next stage of the pipeline
according to the results." The spec is the section "AI nodes inside the EAOS pipeline" of
`eaos-dev/planning/studio-v2/STUDIO-COMPLETE.md`; the task is NS46.T15, after the planned ideal (D10, node 1).

- **A first-class stage.** An AI node takes a deterministic output (the cards, the plan, the rules' target, the
  pipeline map's gap, a fix batch), analyses it, plans and decides, and writes a **structured decision** in one shared
  shape (contract `ai-node`): the decision, its options, the evidence ids it stands on, the confidence, why, and the
  open questions. The nodes are declared as data (`eaos/studio/nodes/__init__.py` `NODES`), in this order: the ideal
  planner, the card triage, the pipeline-gap planner, the plan orderer and the fix reviewer.
- **The decision routes the pipeline.** After each node a router of declared branches sends each subject on by its
  decision: a card confirmed goes to the plan, a doubtful one to a probe, a rejected one to the library's feedback; a
  fix accepted is handed over, retried, or asked of the person; anything that needs the person goes to the Decisions
  inbox and that branch waits.
- **Guards on every node.** An evidence check drops a decision none of whose ids resolve, and lists it. Planning nodes
  make a critique pass. Without an assistant, or when the node times out, goes over its cost budget or fails, the
  rules decide alone and the route says "rules only". Each run records the prompt's digest, the model, the inputs'
  digest and the output in the run log (`<report>/nodes/runs.jsonl`), and a re-run on the same inputs returns the
  cached result without asking again.
- **The person's own assistant**, through the command centre's launcher (D8): no extra key and no extra service.
- **Drawn.** The nodes have their own shape and colour on the pipeline map, their routers show each branch's
  condition, EAOS's own map shows them, and EAOS's truth file (`evaluations/pipelines/eaos.json`) includes them.
  `studio/nodes.json` holds every node's last run for the Studio.
- **A model's opinion is not a label.** The triage's verdicts feed the precision measure as their own column; they are
  never mixed with the hand-written truth.

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
| `studio/cards.json` | Every card on its own file and evidence, its scope (`place` or `group`), its state from the ledger and `why` it matters (`{ar, en}`, from the plan's impact sentence). |
| `studio/evidence.json` | The facts the cards cite: engine, kind, sites, and `code`: the lines around the fact's line as the check read them (`git show <scanned commit>:<path>`, else the working copy; never for a secret, and a line where any fact found a secret is written empty and named in `hidden`). |
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
| `studio/functions.json` | Every function by module: signature, summary, callers and callees, data read and written, size and complexity, its cards; each language's state, and what is not measured (`missing`). |
| `studio/screens.json` | Every screen: route, shots per viewport before and after each batch, inputs, usability issues pinned to a region; what is not captured or read yet (`missing`). |
| `studio/gaps.json` | The gap register: per component, the operation that closes it, its cards, steps and operations, how far it is closed. |
| `studio/operations.json` | The ordered operations (retain, refactor, rebuild, merge, delete, new), their subject, step and what they wait for. |
| `studio/history.json` | Every check the ledger recorded with its score and open cards by severity (null where the ledger did not record them), the progress of the fixes taken in, the events between checks, and the cards that closed or appeared. |
| `studio/quality.json` | How good EAOS's own analysis is here: each detector's precision and recall on the labelled set, whether it meets the bar, what it produced in this report (and on a labelled project its own true and false positives); the plan's capabilities and indicators that judge the analysis. |
| `studio/library.json` | The Library's content: the text of every document of `docs.json`, every image of `media.json` as a data URI and every diagram's source, so the reader shows them from the Studio's own folder. Not read at start: the reader asks for it. |
| `studio/paths.json` | The code paths: every page, server route, command or job through its layers (screen, component, handler, call, endpoint, service, data), each node and link with its evidence, a gap where the records stop, the target of each step, the layout and the clustered overview; and the fix plan's timeline (waves, and what each task waits for). |
| `studio/journeys.json` | The user's journeys: every screen (full route, component file, kind) on a pinned grid, the links between screens with the file and line of each, the main tasks as paths from the start, broken links, screens with no way in, dead ends and duplicates, each screen's folder operation, and what the engine does not give yet (`missing`). |
| `studio/hidden.json` | What the user sees against what runs unseen: screen areas, and jobs and triggers, routes that are not pages, server routes, writes, outside services, configuration and secrets, build steps and dead code, each with its evidence, the areas that set it in motion and the component that holds it. |
| `studio/data_paths.json` | Every store (table, API resource, bucket) with its endpoints, writers, readers and request keys; every write as a path from input field to column with its gaps; the stores written from more than one module; the overview laid out today and in the target. |
| `studio/infra.json` | Hosting, CI/CD, environments, databases, queues, external services and observability, each with its evidence, and the target architecture's decision per area. |
| `studio/pipeline.json` | The pipeline map: whether the project (or a part) is a pipeline, with its confidence, evidence and what was looked for; each pipeline's stages (entry, tools, inputs, outputs, side effects), edges matched by value flow, routers with their labelled branches, fan-out and fan-in, error lanes, hidden side channels, dead stages and unread outputs, the steps EAOS could not follow, and the current, ideal and gap views by rules. |
| `studio/ideal.json` | The ideal of every Target/Ideal view (system, change, journeys, paths, data_paths, infra, pipeline, plan_order): the rules' baseline with its evidence, the ideal the person's assistant planned on top of it (D10) with every element's citations, each view's `provenance`, the elements the evidence check dropped, the critique, the open questions and the planning runs. Every section that draws a target carries its view's `provenance`. |
| `studio/nodes.json` | The AI nodes of EAOS's pipeline: each node's passes, the nodes it waits for, its router's declared branches with their condition and how many subjects took each, how its last run was decided (by which assistant and model, or by the rules alone, and why), its budget and cost, its decisions with their evidence, what the evidence check dropped, and its run log. |
| `studio/coverage.json` | Every section with its state (`measured`, `empty`, `partial`, `not_measured`, `failed`), a reason code, the step that will produce it and how. Written by the exporter after every check, last of the sections. |

Small fixtures of each section live in `tests/fixtures/studio/v2/`; `python tools/studio_synthetic.py --out DIR` writes
a whole data folder of 5,000 cards and 1,000 components, every reference resolved, for the pages and the gates.
`docs/studio-routes.json` lists every route the phase must ship, the data it reads and the task that builds it.

`build_info.studio_digest()` fingerprints the built assets and the Studio's schemas apart from `build_info.digest()`,
so a change to the interface alone rebuilds the Studio without forcing a new check.

## Problems and evidence (NS46.T2)

`#/problems` lists the cards: search (the Studio's Arabic normaliser: hamza, ta marbuta, alef maqsura, diacritics,
tatweel and the article folded on both sides; every word must appear in the title, id, paths, kind, area or why it
matters), who acts, and the facets severity, area, state, plan step and component (the map's owner of the card's
first path), each value with the number of cards choosing it would show given the other filters, and grouping by
area, component or plan step. Every choice is in the address (`q`, `who`, `severity`, `area`, `state`, `step`,
`component`, `group`, `card`; a facet takes several values joined by commas). Facet values and groups keep one order
for the report, so nothing moves under the person's finger; the list draws 30 rows and "show more" adds to the end;
a newer check arriving while the list is open waits behind "Show changes". `?card=` opens the detail: why it matters,
place and component, confidence in words with its meter and source, the evidence with the code at its line, its place
in the plan (step, task k of n, the step's gate, the operation on its component) and the other problems in the same
file. `#/evidence/<factId>` shows one fact with its code, the other places it names and every card resting on it.
The code is in `studio/src/pages/problems/`; the list logic (`model.ts`) is pure and unit-tested at 5,000 cards.

`python tools/studio_budgets.py` measures the filter budget in a browser on the shipped build and a synthetic report
of 5,000 cards (typing Arabic and Latin searches, ticking facets, grouping, clearing; each step from the input event
to the first frame painted after the list changed, on a desktop and on a phone profile with the CPU slowed four times)
and writes `filter_5000_ms` (the slowest step median on the phone profile) to `$EAOS_MEASURE/studio-gates/budgets.json`
with the build's source fingerprint (F14, NS46.T2's acceptance).

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

## Change: the Bridge, the gaps, the plan board and the operations (`gaps.json`, `operations.json`)

Written by `eaos/studio/change.py` from the check's own records (NS46.T3); read by `studio/src/pages/change/`.

- **Gaps**: one per component of today (`target-architecture.json` relation: retain, refactor, rebuild, delete), one
  per target component fed by two or more (merge) or by none (new). Each carries its target and responsibility, why
  (the target's own reason), its cards (`gap-matrix.json` blocking tasks), how far they cover it (`cover`), its steps,
  operations and structure decision. `closed` is cards done / cards; a gap no card closes is null with the reason in
  its source, never 0.
- **Operations**: one per gap that changes something. An operation sits in the step holding most of its cards, else in
  the plan's own `build:<target>` step, else in none ("not in a step of the plan"). It waits for another (`after`) only
  where one of its cards waits for one of the other's (a prerequisite, or an earlier task on the same file); a merge
  carries its sources' cards but owns none. `order` never puts an operation before what it waits for.
- **Pages**: `#/change/bridge` (a sankey of files from today's components to the target's, ribbons coloured by
  operation, the smallest components folded into "Other" past 24 rows; the phone and `?view=table` show the transfer
  list by target), `#/change/gaps?relation=` and `#/change/gaps/<id>`, `#/plans`, `#/plans/<plan>?view=timeline|graph|board`
  (steps in order with task states and waits; the step graph where an arrow is a task waiting for another step's task,
  from `paths.json`'s timeline; the operations in order, a lane per kind), `#/plans/<plan>/<step>`, `#/tasks/<id>` and
  `#/ops/<id>`. A section the report does not hold shows its `coverage.json` row ("not measured yet"), never a guess.

## The function explorer and the screens gallery (`studio/functions.json`, `studio/screens.json`)

System -> Functions (`#/system/functions`, `#/system/f/<functionId>`) and System -> Screens (`#/screens`,
`#/screens/<screenId>`), NS46.T5. Everything is read from the check's facts (`eaos/studio/functions.py`,
`eaos/studio/screens.py`); the Studio computes no number.

- **Functions** are the parser's functions and methods (`facts/syntax.json` symbol), and the functions Lizard measured in
  a language the parser does not read. Complexity is Lizard's cyclomatic complexity where Lizard ran, else the lexical
  branch count + 1 of `facts/metrics.json`; `src` says which, and a function with neither is `null`. react-docgen's
  components give the kind and the props as the signature. Calls are resolved as the flow tracer resolves them
  (`facts/flows.py`: same file, else exactly one imported file); a call that does not resolve is left out and counted
  (`counts.calls` of `counts.call_sites`). Reads and writes are the data accesses and environment reads on the
  function's lines; cards are those whose evidence sits on them.
- **Each language is a row** of `languages`: measured (functions and calls), partial (Lizard only: no calls) or not
  measured. A language that is not fully measured is written in `missing` and its coverage row is `partial`, so the
  page names it rather than showing an empty list.
- **The explorer**: a list sorted by complexity, callers, size or name, filtered by what a function touches, its
  problems, its kind or its file, searched with the shared Arabic normaliser; one function's plain summary, signature,
  size and complexity against Lizard's warning line (15), its callers and callees, a two-step call graph on wider
  screens (each column capped at five, the rest counted), its data, problems and place. `functions.json` is the
  largest section, so `boot.js` does not preload it: its pages load it when they open.
- **Screens** are the pages of the user's journeys (`journeys.json`, kind page). A shot is a `media.json` image of
  kind screen tied to the screen's route; a logo or icon of the project never counts. Until the screens are captured
  (NS41.T1) and a UI extractor reads the inputs (NS40.T2), `missing` names shots, issues and inputs: a card says "not
  captured", the screen says its issues are "not checked yet", never "no issues". When shots exist, the screen shows
  them at their true width with the issues pinned, and before / after / a slider when a batch changed it.

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

## The Library, History and EAOS quality (`library.json`, `history.json`, `quality.json`)

The pages of NS46.T4 read what `eaos/studio/library.py`, `history.py` and `quality.py` write; they compute nothing but
counts and chart geometry.

- **Library** (`#/library/docs`, `#/library/docs/<path>?h=<heading>`, `#/library/images/<id>`). `docs.json` lists the
  documents the check wrote, in the reading order of the report's own index (`README.md`'s links, after the start
  documents), with their headings; the engines' copies of the project (`engines/`) and the built site are not EAOS's
  documents and are left out. Search folds Arabic spellings over titles, paths and headings. The reader draws the
  Markdown with `marked`'s lexer into the Studio's own elements (no HTML string is injected): 68ch measure, contents
  beside it on a wide screen and in a sheet on the phone, card ids and document links as Studio links, code and tables
  with their own left-to-right scroll, the previous and next documents in reading order. `library.json` carries the
  text (and images as data URIs, a Mermaid diagram as its source, with a link to the Studio map that draws the same
  facts); the machine's folders in the text become the project name and `~`. It is the largest section, so `boot.js`
  leaves it out and the reader loads it on demand (the snapshot's script or the live API).
- **History** (`#/history`, `#/history/<check>`, `#/history/compare/<a>..<b>`). From the ledger: every `baseline` and
  `recheck` point is a check; the last is this report, with its score and open cards by severity. An older check has
  them only when the ledger recorded them (NS31.T1 adds `scores` to each point); until then they are null and the
  coverage row of `history` says so (partial, step NS31.T1). The score line, the open problems by severity and the
  progress of the fixes taken in are drawn only with two points or more; one check shows the designed "one check so
  far" state. Two checks compare by their recorded numbers and by the ledger's cards closed between them.
- **EAOS quality** (`#/quality`). `eaos/data/engine-quality.json` (generated by `python tools/engine_quality.py` from
  `docs/engine-precision.json` and `docs/north-star.json`; `--check` says when it is stale) packages each detector's
  precision and recall on the labelled set and the plan's indicators of the capabilities that judge the analysis
  (C2-C8, C10), with plain names in both languages. The page shows the detectors that produced something in this report,
  shown or held back by the bar, this project's own true and false positives when it is a labelled project, the
  coverage rows of this report, and the indicators; every unmeasured value is a counted "not measured yet" state.

## The live check (`run-progress.jsonl`, NS46.T20)

Owner request 2026-10-09 (eaos-dev/planning/live-scan-map/PLAN.md). While a check runs, whoever started it (the
assistant's job, `eaos start`, the Studio), the Studio shows EAOS's own stage map live at `#/scan` ("الفحص الآن").
This is EAOS's own pipeline, not the audited project's (that is the pipeline map below).

- **The record.** `eaos/pipeline/run.py:execute` appends one JSON line per event to `<report>/run-progress.jsonl`
  (`eaos/progress/log.py`; the events are declared in `eaos/data/schemas/progress.json`, version 1): `run.started` with the declared stages as data (name, requires, produces, necessity,
  description, absent_when) and the last run's seconds per stage, `stage.started`, `stage.step` (each extractor inside
  `facts`, each tool of the engine registry inside `engines`, with its own status), exactly one `stage.ended` per
  stage with its status, reason, seconds, artifacts and short scalars of what it reported, and `run.ended`. A run
  replaces the file (a new inode); writing it never fails the run. Folded (`eaos/progress/fold.py`), it equals
  `run-manifest.json` at the end. A stopped or broken run ends the stage it was in and every stage it did not reach
  before `run.ended`. While a stage runs, code inside it reports counted loops with `progress.count(name, done,
  total)` (at most 4 lines a second per step), the external programs the run started are written as
  `stage.activity` (read from `ps` every 2 s), and `run.alive` follows 10 s of silence; the server shows a run that
  promised heartbeats and stayed silent 30 s as `stalled`. Other flows write `<folder>/progress/<flow>.jsonl`.
- **The server.** The feed tails every progress file (the check's, and `<runtime>/progress/<flow>.jsonl` of setting
  up, recording the screens and fixing) and publishes each new line as a `progress` event (source `progress`, the
  line plus its `flow`) in the same numbering and replay; what the files held when the server started is state, not
  events. `GET /api/progress` gives the journey (`eaos/guided.py:journey`) and every flow folded, each stage's `layer`
  and `order` from the pinned layered layout, its time left, the server's clock, and `interrupted` or `stalled` for a
  run nobody hears from; a flow that has not run yet is its declared stages, waiting. `GET /api/scan-progress` is its
  check flow alone. `GET /api/report-file?path=` gives a produced file: a relative path inside the report folder only
  (resolved, so no `..` and no link leads out), text types only, at most 2 MB, as `text/plain` so it is never rendered.
- **Getting there.** The assistant's `audit`, `run_setup`, `safety_net` and `fix_start` open the Studio once on
  `#/scan` (`open_studio`) and answer with its address in `watch` (the routed address when the Studio was started
  with `--remote-origin`); in a run the Studio itself started, no other tab opens. `eaos start` prints and opens the
  same address when the project's Studio is running (`--no-watch` skips it). `open_studio` starts the server from the
  EAOS workspace folder with `PYTHONSAFEPATH=1`, so a check of EAOS's own repository never loads the checked code.
- **The page.** The map is drawn from that data, so a new stage or tool appears with no front-end change; the
  orientation is whichever reads larger in the box. The running stage glows; a light runs along each link into it
  and once along each link out of a stage that just ended to the stages it opened. The panel tells the chosen stage:
  what it does, its live timer, its steps, what it produced, why it did not run. The stage list under the map is the
  keyboard and touch path to every stage. The run line says stage n of N, the elapsed time, and a time left only from
  the last run of the same project. A banner on every page links to it while a check runs. With reduced motion nothing
  moves. The check's `progress` events go to the map (`studio/src/data/scan.ts`) and never reload the report's sections.
- **Limits.** Precision is per stage, and per step inside `facts` and `engines`; inside one tool there is no
  percentage. The snapshot opened from a file says the live map needs the live Studio. A check made before this
  feature shows the designed empty state. The flows after the scan (setting the app up, screens, fixes) do not write
  this file yet.
- **Proof.** `tests/test_live_scan_map.py` (fake runners, the feed, the stream with Last-Event-ID), `studio/src/data/
  scan.test.ts`, and the real trial `tools/live_scan_map_trial.py` with `tools/live_scan_map_trial.mjs`, judged by
  `acceptance/test_live_scan_map.py`.

## The pipeline map (`studio/pipeline.json`)

System -> Pipeline and the report's pipeline sheet (NS46.T13) draw what `eaos/studio/pipeline.py` writes from
`facts/pipeline.json` (`eaos/facts/pipeline.py`, run by the facts stage like every extractor); the Studio computes no
position and no number.

- **Detection.** `detected`, `confidence` (the highest product pipeline's), `kinds`, project-level `evidence`, and
  `looked_for`: every kind looked for (declared DAGs, registry loops, orchestrators, Airflow, Prefect, Dagster, Luigi,
  Celery, LangGraph, n8n, Node-RED, Temporal, Step Functions, GitHub Actions, Make, just, npm scripts, queues, chained
  CLIs) with how many were found and how, so "none found" is said with what was searched. Build and CI chains are
  `role: tooling`, never a product pipeline.
- **Pipelines and stages.** Each pipeline names its kind, entry, evidence and `parent` (the stage whose function runs it:
  a sub-pipeline to zoom into). Each stage has its entry (file, line, fact), symbol, tools (third-party modules it
  calls), inputs and outputs (value, file, table, artifact, topic, env, context), side effects, marks (slow, risky, ai,
  external), `sub_pipeline`, the cards on its file and their plan steps, and its `layer` and `order` from
  `arch_map` (cycle edges set aside, longest-path layers, barycentre order), so every view keeps the same places.
- **Edges** say how they are known (`matched_by`: value, file, table, artifact, topic, declared, order) and the data
  names on them. **Routers** (registry, dict dispatch, if-chain, match/switch, branch operators, conditional edges)
  list each branch with its condition, target and line, whether they are total and what they leave unhandled. **Fans**
  pair a fork with its join (or none), **control** holds loops, retries and conditional skips, **error lanes** say
  where failures go. **Hidden** holds side channels (a shared context key, a global, an environment variable one stage
  writes and another reads), dead stages and unread outputs. **Unresolved** steps are counted and drawn as gaps.
- **Views.** `current` lists the stages and edges; `ideal` gives each stage its operation (retain, refactor, rebuild,
  merge, delete, new) with the rule that asks it, plus the new joins, failure lanes and explicit edges the rules call
  for; `gap` has one entry per broken rule with its evidence, card, plan step and operation. `ideal.made_by` is
  `rules` until the model-planned ideal (STUDIO-COMPLETE.md) exists. The rules (P1-P9) and their sources are in
  `rules`, from `eaos/data/pipeline-rules.json`.
- **Truth.** `evaluations/pipelines/` holds hand-written truth files (EAOS itself, public pipelines pinned to a commit,
  and the app projects that must show none); `tools/pipeline_truth.py measure` writes recall and precision of stages,
  edges and router branches to `$EAOS_MEASURE/pipeline/<name>/measure.json`, read by indicator F16.

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
