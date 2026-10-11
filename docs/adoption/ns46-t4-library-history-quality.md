# The Library, History and EAOS-quality pages: what was adopted

Task: NS46.T4

Checked on 2026-10-09 against the npm registry and the projects' repositories, for the document reader, the images
and diagrams, the history charts and the quality page (STUDIO-COMPLETE.md, "What complete means": Library, History,
EAOS quality; C-experience 3.10 and 3.11). The data is EAOS's (`eaos/studio/library.py`, `history.py`, `quality.py`);
the pages only read and draw it.

## Reading Markdown documents (the reader)

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| `marked` | MIT | 18.1.0 (2026-10-05) | active, weekly downloads in the millions | A fast CommonMark/GFM lexer whose tokens (headings, lists, tables, code, links) the Studio turns into React elements itself: no HTML string is ever injected, so a report's text cannot run anything; about 40 kB minified |
| `markdown-it` | MIT | 14.1.0 (2026-09-12) | active | Same reach; its token stream is flat (open/close pairs), so turning it into React needs a nesting pass; larger |
| `micromark` (+ `mdast-util-from-markdown`, `react-markdown`) | MIT | 4.0.2 (2026-09-26) | active (unified) | The safest parser, but react-markdown pulls the unified ecosystem (about ten packages) for the same result |
| Rendering Markdown to HTML in the exporter (Python) | — | — | — | EAOS has no Markdown library among its dependencies; the HTML would then have to be sanitised in the browser |

**Decision**: adopt `marked`, its lexer only (`marked.lexer`): the reader walks the tokens and draws each with the
Studio's own elements, so headings get anchors for the table of contents, card ids and document links become Studio
links, code and tables keep their own left-to-right scroll, and raw HTML in a document is shown as text.

**Pinned**: `marked@18.1.0`

## Diagrams (Mermaid sources the report writes)

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| `mermaid` | MIT | 12.1.0 (2026-10-02) | active | Renders every Mermaid diagram in the browser, but its one-file build (`mermaid.min.js`, needed because the Studio opens from a file where module chunks are refused) is 5.5 MB: four times the whole Studio |
| `beautiful-mermaid`, `mermaid-isomorphic` | MIT | — | small projects | Server-side or headless rendering: needs Node or a browser at report time |
| The Studio's own maps | ours | — | in the Studio | The report's diagrams (`architecture/system.mmd`, `architecture/current/diagram.mmd`, `architecture/target/diagram.mmd`) are drawn from the same facts the Studio already draws natively: the System map (today and the target) and the journeys |

**Decision**: reject Mermaid for now. A diagram's page shows its source, readable and copyable, and links to the
Studio's own map that draws the same facts. Revisit if the report writes a diagram the Studio cannot draw, with a lazily
loaded Mermaid chunk once the build can split one that a page opened from a file still loads. (Revisited on
2026-10-10: adopted as lazy chunks, `docs-reader.md`.)

**Pinned**: none

## History charts (score over checks, open problems by severity, progress)

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| `d3-scale` + `d3-shape` | ISC | 4.0.2 / 3.2.0 (2023-04-12) | stable, no release since | C-experience 4 names them for timelines; here each chart is one linear scale per axis and a polyline or stacked band: two lines of arithmetic each |
| Recharts, Chart.js | MIT | — | active | Rejected by C-experience 4 (weak RTL, bundle size) |
| The Studio's own SVG | ours | — | in the Studio | Same tokens, logical direction (time runs from inline-start), labelled points, keyboard readout through the list beside it |

**Decision**: build the three small charts in SVG inside `studio/src/pages/history/` with the Studio's tokens; no package.

**Pinned**: none

## Long lists and search (300 documents, 40 detectors)

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| `@tanstack/react-virtual` | MIT | 3.14.13 (2026-09-14) | active | Virtualisation pays above a few thousand rows; the Library groups and folds its rows (at most a screen per group by default) |
| MiniSearch with the Studio's Arabic normaliser | MIT | 7.2.0 (already pinned) | active | Already in the Studio (`src/search/`): the Library's search reuses it over titles, headings and paths |

**Decision**: reuse the Studio's search; no virtual list.

**Pinned**: none
