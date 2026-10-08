# EAOS Studio (source)

The front end of EAOS (`docs/STUDIO.md`). This folder is the source; the build ships to `eaos/data/studio/`, which is
what the package installs. Nothing here runs at EAOS's run time: no Node is needed to open the Studio.

```bash
cd studio
npm ci                       # the pinned packages (docs/adoption/ns37-t1-studio-shell.md)
npm run build                # stylelint, tsc, vitest, vite build, then scripts/ship.mjs -> eaos/data/studio
npm run gates                # = python tools/studio_gates.py --studio -> $EAOS_MEASURE/studio-gates/gates.json
STUDIO_DATA=<report>/studio npm run dev   # live development on a report's data, port 5180
```

- `tests/test_studio_assets.py` recomputes the source fingerprint `ship.mjs` records: a change here without
  `npm run build` fails the Python suite.
- The screen gate is EAOS's one gate, `tools/studio_gates.py` (`eaos/screens/`): `--studio` lays out the shipped
  build with a report's data scripts (`--data <report>/studio`, default `$EAOS_MEASURE/FleetManageWeb/studio`) in a
  temporary folder, serves it on loopback and audits every page of `gate-matrix.json` at 390, 768 and 1440, ar/en,
  light/dark: no horizontal overflow (layout width = viewport width), opens at scroll 0, axe with no serious or
  critical violation, 44px targets on the phone, no clipped text, no letter-spaced Arabic, no script error, no
  request outside the Studio's folder, the language, direction and theme applied, Home within two phone screens; the
  palette and a sheet are opened by actions before the check, and Home is also opened from `file://`. Home and
  Problems are held to Lighthouse mobile ≥ 90 performance and 100 accessibility, and the stylesheet's design-drift
  counts (css-analyzer) are recorded. `--only home,problems` or `--quick` iterate faster but mark the run
  incomplete. `python tools/north_star.py measure --only F8` reads the result, only when it ran in full on the
  shipped build. Playwright, axe-core, Lighthouse and css-analyzer come from the EAOS toolchain (`~/.eaos/tools`).

## Layout

| Folder | Holds |
|---|---|
| `src/design/` | `tokens.css` (the only file with raw values), `fonts.css`, `global.css` |
| `src/i18n/` | the word catalogue (Arabic and English for every key), language/theme preferences, the bidi helpers `Txt`, `Id`, `N` |
| `src/components/` | the design system's components, each with its CSS Module |
| `src/gallery/` | `#/_gallery`: every component × state; `?view=matrix` shows the four language × theme frames |
| `src/shell/` | sections, sidebar/rail, tab bar, top bar, sheets, the Cmd/Ctrl-K palette, page layouts |
| `src/search/` | the Arabic normaliser and the MiniSearch index, with their unit tests |
| `src/data/` | contract v1 types and the loader (classic `<name>.js` scripts beside `index.html`) |
| `src/pages/` | the section pages on real data |
| `src/pages/problems/` | Problems (search, facets with counts, grouping, every state in the address) and `#/evidence/<factId>`; `model.ts` is the list logic, timed at 5,000 cards by `tools/studio_budgets.py` |
| `src/pages/data/` | System → Data (`studio/data_paths.json`): the seven links of every write, the map of writers and stores with its gaps hatched, a store's chain, the steps view, the gallery fixture |
| `src/pages/infra/` | The infrastructure lens (`#/system?lens=infra`, `studio/infra.json`): the context diagram, Today / Change / Target, the steps view |
| `src/data/actions/` | the command centre's client against `docs/studio-actions.json` (bundled from the file): live (launch token, CSRF, SSE over fetch with `Last-Event-ID`) and demo (a recorded run replayed on the open report, `#/runs?demo=1`), the run view derived from events, the shared runs/queue/questions state |
| `src/command/` | selection (check boxes, shift ranges, groups), the action bar, the preview sheet, run questions and their toast, the run pill |
| `src/pages/runs/` | Runs (now, queue, history) and the live run |
| `src/map/` | the territory map (`studio/system.json`): drawing, pan and zoom, legend, minimap, ego diagram, inspector, ranked list, the Home and Change pieces, and its own word catalogue |

## Rules the build enforces

- Logical properties only, colours only through tokens (`.stylelintrc.json`; checked again by the Python test).
- Nothing from the network: the content security policy forbids it, fonts are bundled, data is read from the
  Studio's own folder.
- A section whose page is not built yet is hidden unless the developer flag is on (`?dev=1` once; `?dev=0` turns it
  off), so a person never meets a "coming soon".
- `?lang=ar|en` and `?theme=light|dark` set the display once and are kept as the person's choice.
