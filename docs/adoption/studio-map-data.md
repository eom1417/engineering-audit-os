# The Studio's data paths map and infrastructure lens: what was adopted

Checked on 2026-10-08 against the npm registry and the projects' repositories, for System → Data (each piece of data
from input field to column, the writers and readers of every store) and the System map's infrastructure lens
(hosting, CI/CD, environments, databases, queues, services, observability), as STUDIO-COMPLETE.md's must-haves ask:
three views (Current, Target, Change), pinned positions, clusters at 1,000 nodes, a linear steps view, gaps drawn.

## Layout of the data paths overview

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| ELK (`elkjs`) | EPL-2.0 or GPL-3.0 | 0.12.0 (2026-07-17) | active (Eclipse) | The reference layered layout; here the layers are given (callers, then stores), so its layering is unused; 1.4 MB, laid out on every open in the reader's browser, places stable only as the input order |
| dagre (`@dagrejs/dagre`) | MIT | 3.1.1 (2026-08-08) | active, community | Layers computed from the edges, not given; no lanes |
| d3-dag | MIT | 1.2.2 (2026-07-05) | maintained | Sugiyama in the browser; the same trade-off as ELK |
| EAOS's own `arch_map.order_columns` (barycentre sweeps), as the code paths map uses it | ours | — | in EAOS since the component map | Orders the nodes inside given lanes to cross fewer links, in Python at export |

**Decision**: reuse, not adopt. The lanes are fixed by the records (calling component, store), so only the order
inside each lane is computed, by `arch_map.order_columns` in `eaos/studio/data_paths.py` at export. The target view
keeps the stores' order and places its components against it, so a store keeps its place across views and the
Studio only draws. The chain of one path (field → form → key → caller → endpoint → handler → column) is a fixed row of
seven tiers: no layout problem to adopt for. The same choice as the System map and the code paths
(`studio-maps.md`, the code paths record): EAOS lays out, the Studio draws plain SVG, no engine in the bundle.

**Pinned**: none

## Infrastructure lens

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| Mermaid C4 / architecture diagrams (`mermaid`) | MIT | 12.1.0 (2026-10-02) | active | Text-to-diagram for documents; D4 keeps Mermaid for documents only; its boxes would not carry evidence links or the Studio's tokens |
| Structurizr (C4 model) | Apache-2.0 | server and DSL, Java | active | A modelling tool and its own renderer, not a component for a static page |
| React Flow (`@xyflow/react`) | MIT | 12.12.0 (2026-09-24) | active | Box-and-arrow canvas with its own layout model; ≈ 150 kB for seven fixed lanes around one application |
| Plain SVG from React over seven fixed lanes | ours | — | — | A context diagram (the application in the middle, one lane per kind of infrastructure) has fixed slots: nothing to lay out |

**Decision**: build the drawing (plain SVG, the lanes in fixed slots around the application), reusing the System
map's pan and zoom (`studio/src/map/useZoom.ts`) for the phone's full-screen sheet. No package.

**Pinned**: none
