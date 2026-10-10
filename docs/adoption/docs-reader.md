# The document reader drawn like a good docs site: what was adopted

Task: the owner's request of 2026-10-10 ("read any .md file professionally, with charts, tables and diagrams drawn
in the best possible way"), on the Library reader of NS46.T4 (`ns46-t4-library-history-quality.md`).

Checked on 2026-10-10 against the npm registry (version, release date, licence of the exact tarball) and the
projects' repositories. The NS46.T4 record rejected Mermaid because its one-file build is 5.5 MB and the Studio could
not then split a chunk that a page opened from a file still loads. The Studio's build now does (`vite.config.ts`
`classicChunks`), so the decision is revisited here.

## Mermaid diagrams and charts in documents

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| `mermaid` (ESM build, bundled and split) | MIT | 12.1.0 (2026-10-02) | active, releases monthly | Draws every type the reports write (flowchart, sequence, class, state, ER, gantt, pie, xychart, mindmap, C4, timeline…); its ESM build imports each diagram type on demand, which the Studio's classic chunk loader serves from its own folder; themed by variables (the Studio's tokens), strict security level sanitises labels with DOMPurify |
| `mermaid` one-file build (`mermaid.min.js`) | MIT | 12.1.0 | as above | 5.5 MB read whole for any diagram |
| `beautiful-mermaid`, `mermaid-isomorphic` | MIT | — | small projects | Render in Node or a headless browser at report time: EAOS writes reports without either |
| `@mermaid-js/tiny` | MIT | 11.x | follows mermaid | No mindmap or architecture types; still one file |
| The Studio's own maps | ours | — | in the Studio | Draw the project's own structure only, not the diagrams a report writes in its documents |

**Decision**: adopt `mermaid`'s ESM build, imported only by `studio/src/pages/library/diagramEngine.ts`, which the
reader loads when a document holds a ```` ```mermaid ```` block. The build keeps it out of every other page: Mermaid's
own chunks are named `mermaid.*` and their dependency list travels in the engine's chunk, not in `assets/studio.js`.
ELK (`elkjs`, 1.5 MB, EPL-2.0) is not shipped: the build removes its registration, and a diagram that asks for the ELK
layout falls back to the default one, as Mermaid's own small build does. Error and warning messages naming the
projects' sites are stripped at build time (no address outside the Studio ships). Shipped transitive licences: MIT,
ISC, BSD-3-Clause (d3 parts), Apache-2.0 (chevrotain), MPL-2.0 OR Apache-2.0 (DOMPurify), Unlicense
(robust-predicates, public domain).

**Pinned**: `mermaid@12.1.0`

## Syntax highlighting of code blocks

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| `lowlight` (highlight.js grammars, hast output) | MIT | 3.3.0 (2024-12-14) | stable, unified collective | Returns a tree of spans, drawn as React elements (no HTML string injected); the grammars are imported one by one, so the chunk carries only the 21 languages reports use (about 90 kB) |
| `highlight.js` alone | BSD-3-Clause | 11.11.1 (2024-12-25) | stable | Returns an HTML string to inject |
| `shiki` | MIT | 3.x | active | TextMate grammars and a WASM regex engine: several hundred kB more, async start |
| `prismjs` / `refractor` | MIT | 1.30.0 / 5.0.0 | Prism in maintenance mode | Prism registers languages on a global; refractor is the same idea as lowlight on Prism's grammars |

**Decision**: adopt `lowlight` with `highlight.js`'s grammars, in a lazy chunk (`studio/src/pages/library/highlight.ts`)
read when a document holds code in a known language; the scopes are folded into ten Studio colours
(`--syntax-*` in `tokens.css`).

**Pinned**: `lowlight@3.3.0`, `highlight.js@11.11.1`

## Alerts, footnotes, task lists, tables and figures

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| `marked-alert`, `marked-footnote` | MIT | 2.1.2 / 1.4.0 | small, active | Extensions for marked's HTML renderer; the reader does not render HTML, it walks the lexer's tokens |
| Our own reading of the tokens | ours | — | — | An alert is a quote whose text opens with `[!KIND]`; a footnote definition is a line outside a fence; about 70 lines with unit tests (`gfm.ts`) |

**Decision**: build: `studio/src/pages/library/gfm.ts`, drawn by `markdown.tsx`.

**Pinned**: none
