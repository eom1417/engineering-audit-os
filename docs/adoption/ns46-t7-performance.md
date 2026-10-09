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
No new dependency, module script, network service or worker. Rejected: module chunks (refused from file://), a
second build with shared globals (duplicate React contexts), and idle preloading (bytes during first load).

Home folds its secondary decisions at six with "Show all N" (DESIGN.md list folding, two phone screens).
