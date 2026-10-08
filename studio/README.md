# EAOS Studio (source)

The front end of EAOS (`docs/STUDIO.md`). This folder is the source; the build ships to `eaos/data/studio/`, which is
what the package installs. Nothing here runs at EAOS's run time: no Node is needed to open the Studio.

```bash
cd studio
npm ci                       # the pinned packages (docs/adoption/ns37-t1-studio-shell.md)
npm run build                # stylelint, tsc, vitest, vite build, then scripts/ship.mjs -> eaos/data/studio
node scripts/gates.mjs       # the screen gates (DESIGN.md §7) -> $EAOS_MEASURE/studio-gates/gates.json
STUDIO_DATA=<report>/studio npm run dev   # live development on a report's data, port 5180
```

- `tests/test_studio_assets.py` recomputes the source fingerprint `ship.mjs` records: a change here without
  `npm run build` fails the Python suite.
- `scripts/gates.mjs` copies the shipped build and a report's data scripts (`--data <report>/studio`, default
  `$EAOS_MEASURE/FleetManageWeb/studio`) to a temporary folder, serves it on loopback and checks every route and the
  gallery at 390, 768 and 1440, ar/en, light/dark, plus the palette and the sheet open, and the page opened from a
  file. Playwright and axe-core come from the EAOS toolchain (`~/.eaos/tools`). `python tools/north_star.py measure
  --only F8` reads its result, only when it ran in full on the shipped build.

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
| `src/map/` | the territory map (`studio/system.json`): drawing, pan and zoom, legend, minimap, ego diagram, inspector, ranked list, the Home and Change pieces, and its own word catalogue |

## Rules the build enforces

- Logical properties only, colours only through tokens (`.stylelintrc.json`; checked again by the Python test).
- Nothing from the network: the content security policy forbids it, fonts are bundled, data is read from the
  Studio's own folder.
- A section whose page is not built yet is hidden unless the developer flag is on (`?dev=1` once; `?dev=0` turns it
  off), so a person never meets a "coming soon".
- `?lang=ar|en` and `?theme=light|dark` set the display once and are kept as the person's choice.
