# The Studio's user journeys and visible-and-hidden maps: what was adopted

Checked on 2026-10-08, for the two maps of NS46.T6 that STUDIO-COMPLETE.md names first: System -> Journeys (the screens
a person opens, the links between them, the main tasks as paths) and the visible and hidden lens. Registry facts for
ELK and d3 are the ones `studio-maps.md` recorded the same day.

## Layout of the journeys: a layered graph of screens

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| ELK (`elkjs`), layered | EPL-2.0 or GPL-3.0 | 0.12.0 (2026-07-17) | active (Eclipse) | The reference layered layout; in the browser it adds a 1.4 MB worker to a Studio already near its Lighthouse budget, and lays out on every open, so a screen would not keep its place across scans unless its positions were stored anyway |
| dagre | MIT | 0.8.5 (2020) | unmaintained | Layered, smaller, but abandoned |
| EAOS's own layered layout (`eaos/arch_map.py`: Tarjan groups, Eades' feedback edges, longest-path layers, barycentre sweeps) | ours | — | — | Already used for the report's component map and flow charts, tested; runs in the exporter, so the Studio only draws |

**Decision**: adopt what EAOS already has. `eaos/studio/journeys.py` lays the screens out once per check with
`arch_map.order_columns` (barycentre sweeps) on columns that mean something to a person: the clicks from the start.
Positions are cells of a grid, and a screen that was on the previous `journeys.json` of the report keeps its cell, which
a browser layout could not promise. No new package (W2 unchanged).

**Pinned**: none

## Drawing, pan and zoom, clustering

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| React Flow (`@xyflow/react`) | MIT | 12.x | active | Nodes as DOM, edges, pan and zoom; 150 kB more, and its own styling to undo for the design tokens |
| d3-zoom | ISC | 3.0.0 (2021) | stable | Pan and zoom only; `studio-maps.md` records it as the fallback |
| The territory map's own pieces (`studio/src/map/useZoom.ts`, the map frame) | ours | — | — | Already shipped and gated on the System map |

**Decision**: reuse the System map's pan and zoom and its frame. The frame (toolbar and zoom buttons) was drawn out of
`MapCanvas` into `CanvasFrame` so both maps share it instead of copying it; the drawing is plain SVG from React. Above
250 screens the map opens on its areas (one frame per area, the links between areas counted) and an area expands to its
screens and their neighbours, so a 1,000-screen app never draws everything at once (the synthetic project: 1,102
screens in 22 areas).

**Pinned**: none

## The visible and hidden lens

**Decision**: build: two columns placed by the data's own order (areas by name, groups in the contract's order), so
the drawing never moves between scans; nothing to adopt for a two-column diagram.

**Pinned**: none
