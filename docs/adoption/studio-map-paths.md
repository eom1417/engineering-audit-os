# The Studio's code paths, sequences and plan timeline: what was adopted

Checked on 2026-10-08 against the npm registry and the projects' repositories, for System → Paths (the code path of
each entry through its layers, as swimlanes), Paths → Sequence and Change → Plan timeline (STUDIO-COMPLETE.md, "The
owner's must-haves"; `docs/STUDIO.md`, "The code paths"). The maps' rules are §6 of the design spec
(`eaos-dev/planning/studio-v2/directions/studio/DESIGN.md`) and the must-haves: pinned positions, three views,
clusters at 1,000 nodes, a linear steps view.

## Layered layout of the swimlanes

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| ELK (`elkjs`) | EPL-2.0 or GPL-3.0 | 0.12.0 (2026-07-17) | active (Eclipse) | The reference layered layout, with partitions that could hold the swimlanes; 1.4 MB bundled (`elk.bundled.js`) or a web worker, which a page opened from a file may not start; it lays out in the reader's browser on every open, so the places are only as stable as the input order |
| dagre (`@dagrejs/dagre`) | MIT | 3.1.1 (2026-08-08) | active, community | Layered layout without lanes: ranks are computed from the edges, not given |
| d3-dag | MIT | 1.2.2 (2026-07-05) | maintained | Sugiyama layouts in the browser; layers from the edges by default; the same in-browser trade-off as ELK |
| EAOS's own layered layout (`eaos/arch_map.py`: `order_columns`, barycentre sweeps) | ours, in EAOS since the component map | — | used by `human/index.html` | The lanes are the layers, given, so only the ordering inside each lane is left to compute, which is exactly what `order_columns` does; runs in Python at export, like the System map's territory |

**Decision**: reuse, not adopt a package. A path's lanes are fixed by the records (screen, component, handler, call,
endpoint, service, data), so the layering step that ELK and dagre exist for is not needed; what remains is ordering
the nodes inside each lane to cross fewer links, which EAOS already does for its component map (Tarjan, Eades and
barycentre sweeps in `eaos/arch_map.py`). `eaos/studio/paths.py` calls `arch_map.order_columns` once per path and once
for the clustered overview, and writes the lanes' order into `studio/paths.json`: every reader sees the same places,
the Current, Target and Change views share them, the page opens from a file with no worker, and the Studio carries no
1.4 MB engine. This follows the System map's choice (`studio-maps.md`: EAOS lays out, the Studio only draws). ELK stays
the candidate if a later map needs layering computed from edges (the data paths, the infrastructure); then it would
be adopted with its own record. A package added to the Studio now would also be counted by W2 against the rule that a
record precedes the Studio's first code.

**Pinned**: none

## Sequence diagrams

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| Mermaid (`mermaid`) | MIT | 12.1.0 (2026-10-02) | active | Sequence diagrams from text; a large bundle with its parsers and its own styles; D4 reserves it for documents, and its boxes would not be the map's nodes with their evidence and colours |
| `js-sequence-diagrams` | — | 0.0.1-security (2022-05-06) | the npm name is a security placeholder: the package was withdrawn | — |
| Plain SVG from React over the steps EAOS orders | ours | — | — | A sequence is lifelines in a row and arrows in order: no layout problem left once EAOS writes the order |

**Decision**: build the drawing (about 150 lines, `studio/src/pages/paths/Sequence.tsx`): the participants are the
lanes a path crosses plus the person, the messages are the path's steps in the order EAOS wrote them
(`paths.json#paths[].steps`). No package.

**Pinned**: none

## Plan timeline

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| `frappe-gantt` | MIT | 1.2.2 (2026-02-25) | active | A Gantt of dated tasks; the fix plan has waves, not dates, and its bars carry their own styles outside our tokens |
| vis-timeline | Apache-2.0 or MIT | 8.5.4 (2026-08-12) | active | Dated items on a time axis, its own styles; the plan has no dates |
| A grid of waves by plan steps, drawn from `paths.json#timeline` | ours | — | — | The plan's order is its waves (`eaos/plan.py` waves()); what a task waits for is written by EAOS |

**Decision**: build a grid (waves as columns, the plan's steps as rows, each cell the tasks of that step in that wave)
with the waits drawn on selection. No package.

**Pinned**: none
