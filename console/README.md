# The console: EAOS Studio

The Studio a person opens with `eaos studio`: the governance console the design committee approved
(its `IA.md`, `DESIGN-SYSTEM.md` and `prototype/`, kept outside the repository). Plain modern JavaScript modules and
CSS, no UI framework, no network beyond the server that serves it. Arabic (right to left) first, English equally
finished, light and dark, phone (390 px) first and desktop (1440 px).

It replaced the old front end (`studio/`, React), since removed.

## Build

```bash
cd console && npm install     # once: esbuild, the one build tool (console/node_modules, 12 MB)
npm run build                 # bundles into ../eaos/data/studio, writes SOURCE.json, checks the budgets
```

`scripts/build.mjs` makes classic scripts (a page opened from a file runs no module script):

| Shipped | From | Read |
|---|---|---|
| `boot.js` | `src/boot.js` | first, before the first paint: language, direction, theme, the launch token, the first downloads |
| `assets/studio.js` | `src/core/main.js` with `src/core`, `src/data` | at once: the shell, router, sheets, search, project menu, floating assistant, data layer |
| `assets/words-<lang>.js` | every `src/words/*.js` | the person's language at once, the other when they switch |
| `assets/<place>.js` | `src/places/<place>/index.js` | when one of its addresses or sheets first opens |
| `assets/style.css` + fonts | `src/css/index.css` | at once |

Budgets (the build fails past them, and `tests/guards/test_studio_assets.py` checks them again): the first page's script
(boot, core, Arabic words, Status) at most 240 KB gzipped (target 200), the stylesheet 48 KB, the whole Studio 6 MB.
The source fingerprint in `SOURCE.json` covers `package.json`, `package-lock.json`, `scripts/build.mjs`, `src/` and
`docs/studio-actions.json`; the suite fails when the source changed without a rebuild.

## Layout

```
src/index.html, src/boot.js     the page and its first script
src/core/                       the runtime every place shares (one bundle)
  main.js        builds self.EAOS (the API below) and starts
  address.js     addresses (#/path?query, the prototype's): parseHash, href, navigate, setQuery, redraw
  router.js      screens, drawing, refresh keeping focus and scroll (the core imports in one direction: no cycle)
  places.js      which bundle holds an address (the IA's prefixes) or a sheet (found by the build)
  shell.js       top bar, tab bar, sidebar, banner, live strip, selection bar; liveNow(), freshness()
  sheets.js      sheets with their own address, focus trap, local() state, needs
  search.js      Search or ask (Ctrl/Cmd+K)        menu.js   the project menu, "Open it live"
  assist.js      the floating assistant (the conversation itself comes from the Ask place: EAOS.askAPI)
  i18n.js prefs.js settings.js format.js notices.js events.js state.js outline.js loading.js a11y.js
src/data/                       the data layer: the report, the live API and its feed
  source.js      the report's sections: live API or the read-only copy's .js twins; need(), section(), reload()
  sse.js         server-sent events over fetch, with Last-Event-ID
  actions.js     the action API client (previews, runs, control, questions, decisions, branches, sign-in…)
  store.js       the live command state: runs and queue, questions, decisions' answers, sign-in, progress, feed
  model.js       the thin adapter: the report's sections in the shapes the screens draw
  selection.js   the selection and the groups picked whole (to the contract's selection)
  derive.js      a run's view from its events          normalize.js   the search's Arabic-aware matching
  contract.js    docs/studio-actions.json (actions, verbs, lifecycle, snapshot)
src/places/<place>/             one bundle per place (status, waiting, problems, plan, activity, project, ask, open,
                                report); src/places/kit/ the helpers several places share
src/words/<file>.js             the dictionary: every key as [Arabic, English]
src/css/                        tokens.css, core.css (shell and the lead's screens), activity.css (A), places.css (B)
tools/                          checks of a served console (below)
```

## The data layer, and the shapes the screens read

Two sources give the same JSON (`source.js`):

- **live**: the page holds the launch token (boot.js keeps it for the tab; `#token=…`, `?token=…` or, behind the Remote
  sign-in, `live-token.js`). Every call sends `X-EAOS-Token`, every POST also `X-EAOS-CSRF` from `GET /api/session`
  (a stale one is fetched again once). Sections: `GET /api/sections/<name>`; the library by parts:
  `libraryItems(ids)` (`?only=`); report files `reportFile(path)`; pictures `tokenImage(path)` (data: address).
- **read-only copy**: opened from a file, or without a token. Sections are the `<name>.js` twins beside `index.html`
  (`window.EAOS_STUDIO[name]`). `EAOS.client` is null and every screen locks its actions (`ctx.offline`), explaining
  how to open it live (sheet `open-live`).

A screen declares the sections it draws (`needs`); the router reads them before drawing and shows the screen's
`loading(ctx)` meanwhile. A section is read once; the live feed (`/api/events`) reloads only the sections whose sha256
changed, and the screen redraws. The live command state (`store.js`, `EAOS.live`) is polled every 3 s (15 s in a
hidden tab) and pushed by the feed; it holds `runs`, `queue`, `questions`, `decisions` (the owner's saved answers),
`signIn`, `assistants`, `progress` (`/api/progress`: the journey and every flow), `freshness` and `context` (git, now).

`model.js` gives the prototype's shapes where the report has the same facts (the prototype's `D`):

| Prototype | Real | Notes |
|---|---|---|
| `D.project` | `model.project()` | name, branch, commit, checked_at, eaos_version, freshness, next_tool |
| `D.totals` | `model.totals()` | problems, fixable, needs_you, by_severity, closed and all_cards (history) |
| `D.health` | `model.health()` | score and areas 0..100, `null` = not measured; history |
| `D.size`, `D.stages` | `model.size()` | files, lines, languages, stages {id, title, state} |
| `D.problems` | `model.problems()`, `model.problem(id)` | the cards; `decision`: {state: fixes, text} or {state: asks, question, decision: 'card:<id>'} |
| `D.evidence[id]` | `model.fact(id)` | {kind, engine, path, line, summary, sites, code {start, line, lines, hidden}, cards} |
| `D.decisions` | `model.decisions()` | report decisions with the saved answer folded in (`state: answered`, `saved`); `source` |
| `D.plan` | `model.plan()` | the fix plan's steps {id, title, gate, tasks [{id, state, title}]} |
| `D.runs` | `EAOS.live.runs` | the action API's runs; `EAOS.store.awaiting()` the delivered branches waiting |
| `D.waiting_branch` | `model.waitingBranches()` | runs whose branch waits for Accept or Reject |
| waiting count | `model.waitingCount()` | decisions + branches + sign-in + run questions: one sum everywhere |
| `S.live` | `EAOS.liveNow()` | what runs or waits now: {kind, text, href, share, you, run} |
| `S.sel` | `EAOS.selection.picked` | `{ids, group}`; `toSelection()` gives the contract's selection |
| `D.now`, `D.tz` | `Date.now()`, `EAOS.prefs.tz` | times in the person's time zone (SET-03) |

Report texts are the report's words (one language, `manifest.language`): draw them with `L(text)`, which shows the
report's translation when it has one (`manifest.locales`). A sentence a screen composes from counts comes from the
dictionary, never from the report's own sentence (so English is finished too).

## The API every place uses (`import { … } from 'eaos'`)

- words: `t(key, vars)`, `tn(key, n, vars)`, `L(text)`, `num(n)`, `has(key)`, `prefs` {lang, theme, tz}
- markup: `esc`, `rich` (report text, paths isolated), `icon`, `code`, `sev`, `chk`, `assistantPicker` (who runs an action), `band`, `fmtWhen`, `fmtTime`,
  `exactTime`, `inMinutes`, `expiresAt`
- addresses: `screen(def)`, `href(path, query)`, `navigate`, `setQuery`, `parseHash`, `refresh`, `offline()`,
  `afterRender`, `a11yRegions`
- sheets: `sheet(name, def)`, `openSheet`, `closeSheet`, `closeSheetThen`, `rerenderSheet`, `local()`
- acts and notices: `act(name, fn)`, `tickAct(name, list, ticks)` (ticking problems in a list), `toast(text, {refusal, link})`, `announce`, `copyText`
- shell: `liveNow()`, `freshness()`, `setSelbar(fn)`; placeholders `outline(def)`, `outlineSheet(name, title, features)`, `loadingHTML()`
- data: `data` (source.js), `client` (actions.js, null offline), `ActionError`, `live` and `store` (store.js), `model`,
  `selection`, `derive`, `normalize`, `contract`; `S` (the page's own state: answers being typed, the assistant)

## Checks of a served console (`tools/`)

They run the prototype's recipes against a real console: by default the scratch preview `http://127.0.0.1:8099/` with
its launch token (`tools/lib.cjs` reads it; `EAOS_STUDIO_URL`, `EAOS_STUDIO_TOKEN[_FILE]` point elsewhere; a `file://`
address checks the read-only copy). Routes default to the lead's on the real report; `--routes=/a,/b` checks others.

```bash
node console/tools/sweep.cjs [--only=390-ar-light]    # every route x 8: console errors, missing words, overflow, h1
node console/tools/sheets-sweep.cjs                    # every sheet those screens offer
node console/tools/targets.cjs [ar|en]                 # 44 px targets at 390, the assistant button never covers a primary
node console/tools/axe.cjs                             # axe-core WCAG A and AA
node console/tools/same.cjs --save=before.json         # a change of the code: every screen and sheet drawn before,
node console/tools/same.cjs --against=before.json --assets=eaos/data/studio   # then the same, or each that differs
```

How a builder ports a prototype screen, and who owns which files: `PORTING.md`.
