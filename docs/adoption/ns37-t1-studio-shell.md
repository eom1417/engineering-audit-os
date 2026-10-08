# NS37.T1, the Studio's design system and shell: what was adopted

Checked on 2026-10-08 against the npm registry (version, release date, licence of the exact tarball) and the
projects' repositories. Inputs: `docs/STUDIO.md` (D4 the stack, D6 the design), the design spec
`eaos-dev/planning/studio-v2/directions/studio/DESIGN.md`, and lens E of the v2 plan (§7, §10, §11, §17).
"Release" is the date of the version checked; "maintenance" is the last release of the package.

## Accessible components (buttons, dialogs, sheets, lists, segmented controls, search fields)

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| React Aria Components | Apache-2.0 | 1.22.0 (2026-10-08) | Adobe, released monthly | Headless, WAI-ARIA patterns, built-in RTL (`I18nProvider`, `isRTL`), focus management, `Modal`/`Dialog`, `ListBox`, `ToggleButtonGroup`, `SearchField`, `Autocomplete`; styled by our own CSS Modules |
| Radix UI primitives | MIT | `@radix-ui/react-dialog` 1.2.0 (2026-10-05) | active | Good primitives, but RTL by a separate `DirectionProvider` per tree and no collection/virtual-focus model for the palette |
| shadcn/ui | MIT | copy-in source | active | Built on Radix + Tailwind; the design is fixed by D6 and Tailwind is not in D4 |
| Headless UI | MIT | 2.x | active | Few components (no segmented control, no autocomplete with virtual focus); no RTL helpers |

**Decision**: adopt React Aria Components (already chosen in D4). Its `Sheet` component (new in 1.22, swipe and snap
points) is not used yet: the phone sheet is a `ModalOverlay` + `Modal` + `Dialog` placed at the bottom by CSS, which
is stable API; `Sheet` is re-evaluated when a sheet needs swipe-to-dismiss. Its `Toast` is still exported as
`UNSTABLE_`, so the one-line toast the spec asks for (one polite live region, 2.2 s) is built here in about 20 lines.

**Pinned**: `react-aria-components@1.22.0`, `react@19.3.0`, `react-dom@19.3.0`, `@types/react@19.3.0`,
`@types/react-dom@19.3.0`

## Icons

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| Lucide (`lucide-react`) | ISC | 1.53.0 (2026-10-08) | active, weekly releases | 1,600+ stroke icons on a 24 grid, stroke width settable (the design's 1.5 at 16 px), one ES module per icon so only the used icons are bundled; every icon of the mockup's sprite has an equivalent |
| Tabler Icons | MIT | 3.49.0 (2026-10-05) | active | Similar stroke set; heavier default stroke, more filled variants than needed |
| Phosphor | MIT | 2.1.10 (2025-05-22) | slower (last release 2025-05) | Six weights; the extra weights are unused |
| The mockup's own sprite (`tools/common.py` ICONS) | ours | — | — | 40 hand-drawn paths; adding an icon means drawing it |

**Decision**: adopt Lucide, drawn at 16 px with stroke 1.5 to match the mockup. Icons that point (chevrons, back,
arrows) carry a `mirror` flag and are flipped in right-to-left by CSS; the rest are never mirrored.

**Pinned**: `lucide-react@1.53.0`

## Search with Arabic normalisation

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| MiniSearch | MIT | 7.2.0 (2025-09-16) | stable, small (≈ 7 kB gz), last release 2025-09 | Full-text index in the browser, prefix and fuzzy search, field boosts, custom `tokenize` and `processTerm` (where the normaliser plugs in), serialisable index for a prebuilt one later |
| Orama | Apache-2.0 | 3.1.18 (2025-12-19) | active | Has an Arabic stemmer, but its Arabic tokenizer drops ء and آ (lens E §11), so normalisation is needed anyway; larger |
| FlexSearch | Apache-2.0 | 0.8.212 (2025-09-06) | active | Fast; more complex API, its Arabic charset does not fold ta marbuta or alef maqsura |
| Fuse.js | Apache-2.0 | 7.5.0 (2026-07-13) | active | Fuzzy match over a list with no index: slow at 5,000 cards (NS37.T3 needs ≤ 100 ms) |

The Arabic normaliser itself: no library found folds what Arabic users type interchangeably (alef forms أ إ آ ٱ → ا,
ة → ه, ى → ي, ؤ → و, ئ → ي, diacritics and tatweel removed, Arabic-Indic digits → 0-9). Orama's stemmer and the
Python packages (`pyarabic`, GPL-3.0, not embeddable) were looked at; lens E §18 lists it under "build ourselves".

**Decision**: adopt MiniSearch for the index and query; build the normaliser (one function, `studio/src/search/
normalize.ts`, used for both the indexed text and the query, with unit tests). Orama's stemmer stays "evaluate" until
a labelled Arabic query set shows stemming improves recall.

**Pinned**: `minisearch@7.2.0`

## Command palette (Cmd/Ctrl-K)

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| React Aria `Autocomplete` + `ListBox` in a `Modal` | Apache-2.0 | 1.22.0 (2026-10-08) | as above | Virtual focus: the caret stays in the input while arrows move the active row; filtering can be ours (MiniSearch); sections; RTL; no new dependency |
| cmdk | MIT | 1.1.1 (2025-03-14) | quiet since 2025-03 | Popular; brings Radix Dialog and its own fuzzy scorer (no Arabic folding); a second focus model next to React Aria |
| kbar | MIT | 1.0.0 (2026-08-10) | active | Opinionated actions model and animations; same duplication |

**Decision**: adopt React Aria's `Autocomplete` (already pinned): the palette is the modal, the search field and a
list whose rows come from the MiniSearch index above. cmdk and kbar are rejected as duplicates of React Aria.

**Pinned**: none new (`react-aria-components@1.22.0`, `minisearch@7.2.0`)

## Routing (hash routes that open from a file, stacked navigation on the phone)

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| TanStack Router | MIT | 1.170.41 (2026-09-30) | active | Typed routes and search params (the URL holds `focus`, filters, the selected card), hash history so `#/problems/TASK-001` works from `file://`, history-based back for the phone stack; lens E §11 adopts it for P3 |
| wouter | Unlicense | 3.13.0 (2026-09-30) | active | Tiny, hash location hook; untyped search params, which the Studio's views need |
| React Router | MIT | 7.x | active | Data routers aimed at servers; heavier; not chosen in lens E |
| A hand-written hash router | ours | — | — | Possible in 60 lines, but typed search params and preloading would be rebuilt later |

**Decision**: adopt TanStack Router with hash history (code-based routes, no file-based generator).

**Pinned**: `@tanstack/react-router@1.170.41`

## Fonts

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| Fontsource `@fontsource/ibm-plex-sans-arabic` and `@fontsource/ibm-plex-mono` | OFL-1.1 | 5.3.0 (2026-07-19) | active | The exact WOFF2 subsets (Arabic and Latin) the mockup used, from npm with a pinned version |
| IBM's `@ibm/plex` | OFL-1.1 | 6.x | active | Every family and format in one large package |
| Google Fonts CDN | OFL-1.1 | — | — | Loads from the network at run time: forbidden by D4 and the content security policy |

**Decision**: adopt Fontsource; the build copies the WOFF2 files and the licence beside the Studio. Weights 400, 500
and 600 only (the spec uses no other).

**Pinned**: `@fontsource/ibm-plex-sans-arabic@5.3.0`, `@fontsource/ibm-plex-mono@5.3.0`

## Build, types and unit tests

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| Vite + `@vitejs/plugin-react` | MIT | 8.3.4 (2026-10-08) / 6.1.2 (2026-10-05) | active | D4; builds one classic script with fixed names so the Studio opens from a file |
| TypeScript | Apache-2.0 | 7.0.2 (2026-07-08) | active | D4; type checking only (`tsc --noEmit`) |
| Vitest | MIT | 5.0.3 (2026-09-30) | active | Runs on Vite's config; unit tests of the normaliser and the search index without a browser |
| Jest | MIT | 30.x | active | Needs a separate TypeScript transform; Vitest reuses Vite's |

**Decision**: adopt Vite, TypeScript and Vitest.

**Pinned**: `vite@8.3.4`, `@vitejs/plugin-react@6.1.2`, `typescript@7.0.2`, `@types/node@22.20.5`, `vitest@5.0.3`

## Style rules: logical properties only, colours only from tokens

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| stylelint | MIT | 17.16.0 (2026-10-01) | active | The CSS linter; runs before every build |
| `stylelint-use-logical` | CC0-1.0 | 2.1.3 (2026-02-04) | maintained by csstools | Fails on `left`, `right`, `margin-left`, `padding-right`, `text-align: left`…: the task's pitfall "no physical left/right property" becomes a build error |
| `stylelint-declaration-strict-value` | MIT | 1.12.1 (2026-08-24) | active | Fails on a raw colour in a component: colours only through `var(--token)` |
| A grep in a test | ours | — | — | Misses shorthands and values; stylelint parses CSS |

**Decision**: adopt the three; `src/design/tokens.css` is the only file allowed raw colours.

**Pinned**: `stylelint@17.16.0`, `stylelint-use-logical@2.1.3`, `stylelint-declaration-strict-value@1.12.1`

## Component gallery

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| A gallery route inside the Studio (`#/_gallery`) | ours | — | — | Renders every component × state with the Studio's real tokens, fonts and shell; the same gate (Playwright + axe) runs on it as on the pages; no second build |
| Storybook | MIT | 10.6.1 (2026-09-29) | active | Full catalogue tool; a second build, its own runtime and addons to keep in step, its own preview frame that the gates would have to learn |
| Ladle | MIT | 5.1.1 (2025-11-04) | quieter | Lighter Storybook; same second-build cost |

**Decision**: build the gallery route (lens E §11 already expected "a gallery route inside the Studio + Playwright
may be enough"); Storybook stays "evaluate" for when the component count outgrows one page.

**Pinned**: none

## Screen gates (no horizontal overflow, initial scroll, axe, 44 px targets, no Arabic tracking, offline)

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| Playwright + axe-core, already pinned by EAOS (`upstreams/toolchain.json`) | Apache-2.0 / MPL-2.0 | 1.63 / 4.14 | active | The browser and the WCAG rules; installed under the EAOS tools, not in the Studio's packages |
| The design direction's `tools/shoot.mjs` checks | ours | — | — | The geometry checks no tool does (lens E §7 "EAOS still builds") |
| `tools/studio_gates.py` (`eaos/screens/`) | ours | in progress on another branch | — | The shared gate for every Studio screen; not on this branch yet |

**Decision**: the Studio's `scripts/gates.mjs` drives the pinned Playwright and axe-core with the shoot.mjs checks
over the gallery and the shell; when `tools/studio_gates.py` lands on develop it replaces the script's own checks.

**Pinned**: none in the Studio (the browser tools are EAOS toolchain entries)

## Not needed by this task

d3, React Flow + ELK, markdown-it and Mermaid (D4) serve the map, the diagrams and the document reader of later tasks
(NS37.T3, the System page); TanStack Query, Virtual and Table arrive with the data interface and the long lists
(NS37.T2, NS37.T3). They are added, with their record, by the task that first uses them.
