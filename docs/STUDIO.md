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
- Governance: no "done" button anywhere; the Studio only reads; every action is a sentence copied to the assistant
  with the tool's name.
- Clarity: every page answers where we are, where we should be and what is next; one main action per page; every
  chart has a one-sentence title, units, source and a table alternative.
- Quality: designed empty, loading and error states; every entity has a link that restores its view; crowded charts
  fold above 8 items; Arabic and English match.
- Technique: offline (enforced by the content security policy); opens from a file; under two seconds on 5000 cards;
  no serious accessibility violation; motion within its tokens, and stopped for whoever asks.
