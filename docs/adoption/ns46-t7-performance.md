# NS46.T7 / F14: startup and search preparation

Saved NS46.T4 and T5 Lighthouse reports show Home/Problems below the mobile
performance floor, with 181–195 kB of unused transferred JavaScript and substantial
main-thread blocking. Those reports are evidence of failure, not a comparable
before/after trial: their builds and host loads differ.

Reuse pinned MiniSearch 7.2.0, React 19.3.0 memoization and the existing screen
and Lighthouse gates. No new dependency, worker protocol, module-only bundle or
network service is adopted. Preserve the classic script's file:// support.

Build the search index only on the first nonblank query. Cache each raw indexed
term's normalized forms within that index, avoiding repeated Unicode normalization
of common words and path segments. Empty palette queries still return pages.
The first nonblank query includes indexing; measure it separately from warm search,
so moving startup cost cannot masquerade as a filter-budget pass.

Memoize Home's counts and the map's sorted drawing arrays on their immutable report
inputs. All nodes, regions, navigation, localization and responsive presentations
remain present. Shared Shell/DataProvider localization work belongs to integration.

Evidence is saved under the worker's own directory. Node search timings are
microbenchmarks, never the shipped-browser F14 timing. Only shipped-browser runs
with SOURCE.json identity can supply studio-gates/budgets.json. Final F13/F14 and
four-project acceptance await NS46.T2–T6 integration.

## Follow-up: measured eager grouping and cold matching

The saved 4x CPU Home profile attributes 217.751ms self time to groupsOf and
275.971ms to component ownership callbacks, before its closed sheet is opened. Reuse Map/Set
buckets with in-place appends to newly owned arrays, one milestone bucket per
report, and ancestor lookup for component ownership. Preserve order, duplicate
card IDs, operation de-duplication, deepest path ownership and root fallback.
Build groups when their existing sheet opens. No new capability or dependency.

Problems needs membership, not relevance order: reuse MiniSearch with a single
combined field for its index, retaining all searchable text, normalization,
prefix/fuzzy and AND behavior. The palette retains its weighted fields.
Compare matching sets against the original index, including bilingual terms.

Compact Home's secondary decision rows without truncating questions or
recommendations, removing only their repeated decorative inbox icon. Keep every
decision and link, all answer controls, and the 44px target minimum. Do not alter
budgets or acceptance. Final combined gates remain integration-owned.

The first follow-up shipped trial still fails cold filtering (218.670814ms).
Its query CPU profile points to MiniSearch result scoring/addTerm in addition to
construction. Adopt the existing pinned MiniSearch public SearchableMap subpath
for a membership-only inverted index: exact/prefix/fuzzy term unions and AND
posting intersections, without BM25 scoring or result metadata. Fuzzy distance
keeps MiniSearch 7.2.0's rounded 0.15 distance (max 6, words longer than four),
Arabic bare query forms and all indexed forms. Palette ranking stays unchanged.
This replaces the unsuccessful combined-field experiment; preserve its artifacts.

The second phone matrix still exceeds height (1693px Arabic / 1731px English).
Use a Home-only compact first-decision presentation: tighter spacing and the
recommendation label beside its full text when it fits, wrapping freely when
long. Retain the recommended blue answer, all choices, hints and card links.
Shared Story owner-control work must keep its authority/dispatch implementation.

## Final combined source (Claude Code, 2026-10-09)

Ported onto the integrated Studio (owner controls, the current Problems model) by source review. Not ported: the
obsolete Problems page and its membership index; the current Problems model matches by normalised substring, and
its matching, counts, facets and Home's critical,high links are unchanged.

Cold Problems filter. A trace of the first query (4x CPU) showed one 42–75 ms input task, most of it the router
writing the address on the keystroke and redrawing its subscribers. Reuse React state and memo: the list filters on
the typed words at once and the words reach the address 300 ms after typing pauses (a change of the address from
elsewhere still replaces them); the who/filter controls are memoised. No index, prewarming or exact-ID shortcut.

Staged report loading. Lighthouse showed boot reading every section before the first page. boot.js reads the
frame's sections and the opened page's (Home, Problems, a card's detail; the same lists as src/data/stages.ts,
kept equal by a test) and the rest load when a page, the palette or the selection sheet asks, with a loading state
in Arabic and English. A page naming no list waits for the whole report, as before; nothing is dropped.

Code splitting with classic scripts. The monolithic 1.4 MB script was the largest request before the first paint.
D1 and file:// need classic scripts with fixed names, and Rolldown cannot split IIFE output. Reuse Rolldown's
CommonJS chunks and TanStack Router's lazyRouteComponent and intent preloading: a Vite plugin (vite.config.ts
classicChunks) wraps each chunk as a classic script registering its body and gives assets/studio.js a 20-line
loader that reads a page's chunks from its own folder, as boot.js reads data. Home and Problems stay in the entry.
No new dependency, module script, network service or worker. Rejected: module chunks (refused from file://) and a
second build with shared globals (duplicate React contexts). Chunks are read on idle only once the report is drawn
(below), never during the first load.

Main-thread work at start (CPU profile of a cold Home at 4x). Lighthouse total blocking time was 629 ms: the report
drawn in one synchronous render, the palette building an entry for every card while closed, closed sheets
formatting dates, and a new Intl.DateTimeFormat per date. Reuse React's own scheduler: the loaded report and each
later section are applied in startTransition, so React draws them in slices (time slicing); closed palette and
sheets draw nothing of their bodies; a prefs object keeps its two date formats. No worker or virtualisation.

Home before its counts. Home and the frame read the cards (139 KB gzipped on 5,000 cards) and the story only to count
them. Home now draws from the frame's small sections (head's verdict, health, decisions, docs, the map) and the
cards and story are asked for when the browser is idle after it is drawn (useSections(..., 'idle'), shell/later.ts
whenIdle over requestIdleCallback, a timer where it is missing). Until they arrive Home's counts show an ellipsis
announced as "Counting…"/"يحسب…", its sentence has no number links and the navigation shows no count: nothing reads
as 0 and nothing is dropped. Problems still waits for its cards, story and plans: its rows, matching and facets read
them, and they are unchanged.

The frame's on-demand parts as chunks. The palette (with React Aria's ListBox and Autocomplete and MiniSearch) and
the command centre's selection and preview sheets are React.lazy chunks through the same classic loader, drawn from
their first opening (useOpenedOnce, so they close as they opened) and read on idle once the report is drawn, so
they open at once later. assets/studio.js: 234.6 KB to 202.5 KB gzipped.

Fonts beside the script. The first view's fonts were requested only after the script had drawn. boot.js, which
already knows the language, adds preload links for the fonts of src/design/fonts.css the first view uses (Latin and
Mono, plus Arabic when the Studio speaks Arabic) over HTTP; a file:// page reads them when it draws, as before. A
test keeps each preloaded name a shipped font of style.css. Lighthouse FCP 1.8 s to 1.05 s, LCP unchanged.

Home folds its secondary decisions at six with "Show all N" (DESIGN.md list folding, two phone screens).

## Unicode-range font subsets (Claude Code, 2026-10-09)

Before Home's largest paint the browser downloaded the design's seven font files, 210 KB (Fontsource's Arabic file
of each weight carries Arabic Supplement, Extended-A/B and the presentation forms beside the Arabic block). DESIGN.md
keeps its families (IBM Plex Sans Arabic, IBM Plex Mono) and weights (400/500/600): the fonts are cut, not changed.

**Candidates**

| Candidate | Licence | Version checked (2026-10-09) | Maintenance |
|---|---|---|---|
| fontTools `pyftsubset` (fonttools/fonttools) | MIT | 4.60.1 | Active, monthly releases; the subsetter Google Fonts and Fontsource themselves use |
| `subset-font` (npm, harfbuzzjs + wawoff2) | BSD-3-Clause | 2.9.0 | Maintained by one author; a new npm dependency in the build for a cut that changes only when Fontsource does |
| glyphhanger (npm, Puppeteer + pyftsubset) | MIT | 6.0.0 | Last published 2026-06; needs a headless browser and still shells out to fontTools |
| Fontsource's own range files only | OFL-1.1 | 5.3.0 (already pinned) | The Arabic file mixes the common block with the rare ranges, so every Arabic page reads both |

**Decision**: adopt fontTools as a development tool, not a runtime or build dependency. `tools/studio_fonts.py` cuts
each pinned Fontsource file into four range files (Arabic block; rarer Arabic ranges and presentation forms; Latin
and punctuation, which Arabic pages need for digits; Mono) and commits them with `src/design/fonts/SOURCE.json`
(the digests of the Fontsource sources and outputs; `--check` runs without fontTools and in
`tests/test_studio_assets.py`). Outputs are byte-reproducible (`recalcTimestamp=False`). Hinting, outlines, advances,
kerning and every OpenType feature are kept: an unhinted cut saved 41 KB more on an Arabic first view but changed
Chrome's glyph rasterisation and line wrapping on Linux (Problems on the phone grew 21–103 px), so it was rejected;
with hinting the phone and desktop screenshots of Home, Problems and Decisions in Arabic and English are
pixel-identical to the Fontsource files. Each face keeps `font-display: swap`; a local fallback face sized to Plex's
metrics (`size-adjust`, `ascent-override`, `descent-override`) sits next in `--font-sans`/`--font-mono` so the swap
does not move the text. boot.js preloads only the first view's faces (Latin 400/500/600 and Mono 400, plus Arabic
400/500/600 in Arabic); the rare Arabic ranges are read only when text contains them. file:// keeps working: the
files are local assets like before. Arabic first view: 209 KB of fonts to 162 KB.

**Pinned**: `fonttools@4.60.1`, `brotli@1.1.0` (Python, development only, installed by `tools/dev_setup.sh`).
