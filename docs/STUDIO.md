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
