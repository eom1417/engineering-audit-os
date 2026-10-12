# EAOS Studio (source)

The front end of EAOS (`docs/STUDIO.md`). This folder is the source; the build ships to `eaos/data/studio/`, which is
what the package installs. Nothing here runs at EAOS's run time: no Node is needed to open the Studio.

```bash
cd studio
npm ci                       # the pinned packages (docs/adoption/ns37-t1-studio-shell.md)
npm run build                # stylelint, tsc, vitest, vite build, then scripts/ship.mjs -> eaos/data/studio
STUDIO_DATA=<report>/studio npm run dev   # live development on a report's data, port 5180
```

- `tests/test_studio_assets.py` recomputes the source fingerprint `ship.mjs` records: a change here without
  `npm run build` fails the Python suite.

## Layout

| Folder | Holds |
|---|---|
| `src/design/` | `tokens.css` (the only file with raw values), `fonts.css`, `global.css` |
| `src/i18n/` | the word catalogue (Arabic and English for every key), language/theme preferences, the bidi helpers `Txt`, `Id`, `N` |
| `src/components/` | the design system's components, each with its CSS Module |
| `src/shell/` | sections, sidebar/rail, tab bar, top bar, sheets, the Cmd/Ctrl-K palette, page layouts |
| `src/search/` | the Arabic normaliser and the MiniSearch index, with their unit tests |
| `src/data/` | contract v1 types and the loader (classic `<name>.js` scripts beside `index.html`) |
| `src/pages/` | the section pages on real data |
| `src/pages/problems/` | Problems (search, facets with counts, grouping, every state in the address) and `#/evidence/<factId>`; `model.ts` is the list logic, timed at 5,000 cards by `tools/studio_budgets.py` |
| `src/pages/data/` | System → Data (`studio/data_paths.json`): the seven links of every write, the map of writers and stores with its gaps hatched, a store's chain, the steps view |
| `src/pages/infra/` | The infrastructure lens (`#/system?lens=infra`, `studio/infra.json`): the context diagram, Today / Change / Target, the steps view |
| `src/pages/change/` | Change (`studio/gaps.json`, `operations.json`, `story.json`, the plans): the Bridge, the gap register and a gap, the plans with their timeline, step graph and operations board, a step, a task, an operation |
| `src/data/actions/` | the command centre's client against `docs/studio-actions.json` (bundled from the file): live (launch token, CSRF, SSE over fetch with `Last-Event-ID`), the run view derived from events, the shared runs/queue/questions state |
| `src/command/` | selection (check boxes, shift ranges, groups), the action bar, the preview sheet, run questions and their toast, the run pill |
| `src/pages/runs/` | Runs (now, queue, history) and the live run |
| `src/pages/functions/` | System → Functions (`studio/functions.json`, loaded when the page opens): the list, one function with its two-step call graph, the per-language coverage |
| `src/pages/screens/` | System → Screens (`studio/screens.json`): the gallery, one screen with its shots, pinned issues and before/after slider, and the "not captured yet" states |

| `src/pages/library/` | Library (`studio/docs.json`, `media.json`, `library.json` loaded on demand): the documents in reading order with search, the reader (marked's lexer drawn as Studio elements, contents, next in reading order; alerts, footnotes, tables with number columns; code highlighted by `highlight.ts` and Mermaid diagrams drawn by `diagramEngine.ts`, each a lazy chunk), images and diagrams |
| `src/pages/history/` | History (`studio/history.json`): checks, the score, open problems and progress charts (two points or more), a check, two checks compared |
| `src/map/` | the territory map (`studio/system.json`): drawing, pan and zoom, legend, minimap, ego diagram, inspector, ranked list, the Home and Change pieces, and its own word catalogue |

## Rules the build enforces

- Logical properties only, colours only through tokens (`.stylelintrc.json`; checked again by the Python test).
- Nothing from the network: the content security policy forbids it, fonts are bundled, data is read from the
  Studio's own folder.
- `?lang=ar|en` and `?theme=light|dark` set the display once and are kept as the person's choice.
