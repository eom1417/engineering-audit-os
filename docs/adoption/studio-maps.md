# The Studio's System maps: what was adopted

Checked on 2026-10-08 against the npm registry and the projects' repositories, for the territory map of the System
page, the Home "Land of the project" card and the Change page (`docs/STUDIO.md`, "The system maps"). The design spec
is §6 of `eaos-dev/planning/studio-v2/directions/studio/DESIGN.md`; its reference implementation is the approved
mockup's `tools/geo.py` and `tools/terrain.py` (Python, numpy).

## Layout: regions, positions, land and labels

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| ELK (`elkjs`) | EPL-2.0 or GPL-3.0 | 0.12.0 (2026-07-17) | active (Eclipse) | Layered and force layouts in the browser; no contour land, no label placement by priority; 1.4 MB worker |
| d3-force + d3-contour | ISC | 3.0.0 (2022-06-14) / 4.0.2 (2023-01-11) | stable, no release since 2023 | The same algorithms as the mockup, but in the browser on every open: the map would move between machines unless seeded, and a 5,000-file project would lay out on the reader's phone |
| graphology + ForceAtlas2 | MIT | 0.26.0 (2025-01-26) / 0.10.1 (2024-11-08) | slow | Force layout only; the land and labels still to write |
| The mockup's own `geo.py` / `terrain.py` | ours | — | — | Exactly the approved picture; needs numpy, which EAOS does not ship |

**Decision**: build, by porting the mockup to plain Python inside EAOS (`eaos/studio/territory.py`): squarified treemap
for the regions' rooms, a seeded force layout, marching squares over a summed gaussian field with Chaikin smoothing,
labels by priority with collision tests. EAOS computes it once per check (0.2 s on FleetManageWeb's 47 components)
and writes it into `studio/system.json`, so every reader sees the same map and the Studio only draws. No numpy: EAOS's
dependencies stay `mcp` and `pypdf`.

**Pinned**: none

## Drawing, pan and zoom

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| d3-zoom + d3-selection | ISC | 3.0.0 (2022-06-14) | stable, no release since 2022 | Robust pan and zoom with touch; needs d3-selection to own the SVG's events beside React; ≈ 20 kB |
| React Flow (`@xyflow/react`) | MIT | 12.12.0 (2026-09-24) | active | Pan, zoom, minimap built in; nodes are HTML boxes, not the territory's dots and land; brings its own layout model and ≈ 150 kB |
| `react-zoom-pan-pinch` | MIT | 4.2.0 (2026-09-03) | active | Zooms an HTML element by CSS transform: SVG strokes and labels would scale with it |
| Our own hook over pointer events | ours | — | — | Drag, wheel, two-finger pinch, buttons, centring; transform kept in the SVG's own units |

**Decision**: build. The map is drawn as plain SVG from React from the positions EAOS wrote; pan and zoom are about
120 lines (`studio/src/map/useZoom.ts`) on pointer events, so no library owns the SVG's events beside React. A
package added now would also come after the Studio's first code, which W2 counts against it. If touch handling proves
weak on real phones, d3-zoom is the first fallback. React Flow with ELK stays the choice for box-and-arrow diagrams
(flows, plans), not for the territory.

**Pinned**: none
