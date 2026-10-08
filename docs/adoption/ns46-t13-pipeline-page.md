# The pipeline map's page and report sheet: what was adopted

Task: NS46.T13

Checked on 2026-10-08 against the npm registry and the projects' repositories, for System → Pipeline and the report's
pipeline sheet (STUDIO-COMPLETE.md, "The pipeline map"; `docs/STUDIO.md` D9). The engine (NS46.T12,
`ns46-t12-pipeline-engine.md`) writes each stage's `layer` and `order` with EAOS's layered ordering (`eaos/arch_map.py`),
so what is left for the page is drawing and routing the links between placed stages.

## Drawing the flowchart (stages, routers, forks and joins, failure lane, hidden channels)

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| ELK (`elkjs`) | EPL-2.0 | 0.12.0 (2026-07-17) | active (Eclipse) | Layered layout with edge routing; 1.4 MB bundled or a web worker a page opened from a file may not start; it would recompute the places EAOS already wrote, so the Studio would no longer only draw (the pitfall of NS46.T13: the page computes no position) |
| React Flow (`@xyflow/react`) | MIT | 12.12.0 (2026-09-24) | active | Interactive node canvas with its own DOM nodes, styles and pan/zoom: a second zoom model beside the map's, and its nodes outside our tokens |
| d3 (`d3-shape`, `d3-zoom`) | ISC | 3.2.0 (2023-04-12) / 3.0.0 (2022-06-14) | stable, no release since | Curve and zoom helpers; the Studio's own `useZoom` (studio-maps.md) already does the zoom, and a cubic Bézier between two ports is one line |
| The Studio's own SVG with the maps' pieces (`map/useZoom.ts`, `map/parts.tsx` FitIcon, the code paths' canvas frame and legend styles) | ours | — | in the Studio | Places come from `pipeline.json`; links are curves between the placed ports; reused, not copied |

**Decision**: build on what the Studio has, no package. `studio/src/pages/pipeline/Flowchart.tsx` draws the stages where
EAOS placed them (left to right on a wide screen, top to bottom on the phone), with the maps' pan and zoom and the code
paths' canvas, toolbar, legend box and inspector styles imported, not copied. A long pipeline (more than 200 stages)
draws only the stages in view. The only places drawn that EAOS does not write are the failure lane's ends and the
ideal's new stages, which the contract gives no layer: they are set in the order the data lists them (requested from
the engine: a `layer`/`order` for the ideal's new stages and the failure ends). ELK stays the candidate if the engine
ever stops writing places.

**Pinned**: none

## The report's pipeline sheet (REPORT.html and its PDF)

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| Mermaid flowchart rendered at report time | MIT | 12.1.0 (2026-10-02) | active | Needs Node or a browser at report time; lays out on its own, so the report and the Studio would place stages differently |
| Graphviz `dot` | EPL-1.0 | 16.1.0 (2026-09-04) | active | A system binary EAOS does not require; its own layout |
| Static SVG from the same section the Studio reads | ours | — | — | `human_report` already draws its maps as inline SVG; the same `layer`/`order` give the same places |

**Decision**: `eaos/compose/pipeline_sheet.py` renders the flowchart, the stage table and the gap as inline SVG and
tables from `eaos.studio.pipeline.from_report` (D2: one model, the Studio and the report show the same numbers). The PDF
is the page printed (`@media print`, a page break before the sheet).

**Pinned**: none
