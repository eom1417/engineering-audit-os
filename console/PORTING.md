# Porting a prototype screen into the console

The prototype (its `assets/screens/*.js`, kept outside the repository) is the approved look, words and
behaviour; the console draws the same markup with the same CSS classes on the real report and the real API. Port the
markup as it is; replace what it reads and what it does. The lead's ports are the model: `src/places/status/index.js`,
`src/places/waiting/list.js`, `src/places/problems/{list,detail,preview}.js`.

## Who owns what (two builders work in parallel; each edits only their own files)

| Owner | Files |
|---|---|
| **Builder A** | `src/places/activity/` (S-11..S-16: Activity, runs, one run, check preview, More work and every action, stages); `src/places/project/` (S-46..S-51: branches, one branch, your app, assistants and cost, tools, settings); `src/places/ask/` (S-52 and `EAOS.askAPI`, the conversation the floating assistant shows); `src/places/waiting/signin.js` (S-04) and `src/places/waiting/questions.js` (S-05); `src/places/open/` (S-53 opening states and old links, the project switch); `src/words/activity.js` (add more `src/words/activity-*.js` freely); `src/css/activity.css` |
| **Builder B** | `src/places/plan/` (S-08..S-10 and the impact sheet S-54); `src/places/understand/` (S-17) and `src/places/understand-{change,built,screens,records}/` (S-18..S-45, the library and the records); `src/words/understand.js` (and `understand-*.js`); `src/css/understand.css` |
| **Lead** | everything else: `src/core/`, `src/data/`, `src/index.html`, `src/boot.js`, `scripts/`, `tools/`, `src/places/{status,waiting/list.js,waiting/index.js,problems}`, `src/words/{core,status,waiting,problems}.js`, `src/css/{tokens,core,index}.css` |

A change you need in a lead file (a model getter, a core helper, a word in core.js, a fix in the shell): ask the lead,
or write it in your own place and say so in your handover. Never edit another builder's files. A new sheet needs no
core change: the build finds every `sheet('<name>'` in your place and loads your bundle when its address opens. A new
file in your place is imported from your place's `index.js`.

## Step by step

1. **Copy the screen's code** into your place (one file per screen or per group of screens), as an ES module:
   `const { D, S, t, … } = EAOS` becomes `import { t, tn, L, esc, icon, screen, sheet, act, … } from 'eaos'`. A place
   imports `'eaos'` and its own files only (the build refuses anything else).
2. **Data: replace `D.*` by the model or the live state** (table in `README.md`). Declare the report sections the
   screen draws: `screen({ …, needs: ['cards', 'plans'] })` (or `needs: ctx => […]`); for a sheet, `sheet(name, {
   needs: […] })`. The router reads them first and draws `loading(ctx)` meanwhile (the prototype's loading state).
   A section not in the model: read it with `data.section('<name>')` (the JSON of `schemas/artifacts/studio-<name>.schema.json`)
   and, when several screens need the same shape, write the getter in your place's own `model.js`. Large sections:
   functions, library (`data.libraryItems(ids)`), paths: only on the screens that show them.
3. **Actions: replace the simulation by the API** (`client`, null in the read-only copy):
   - a preview first, always: `client.preview(id, body)` returns what will happen and `confirm.token`; then
     `client.start({ action, inputs, verb, selection, assistant, confirm: token, where })`. A refusal is an
     `ActionError` with `message` in the person's language and `needs` (`confirm`, `preview`, `refresh`, `in_flight`):
     say it in the sheet (`role="alert"`), never swallow it. `needs: 'preview'` asks for the preview again.
   - keep what the person chose in the sheet's `local()` (it survives the redraws the live data causes); ask the
     preview again when a choice the token is bound to changes (`problems/preview.js again()`).
   - runs: `client.runs()`, `client.run(id)`, `client.follow(id, after, onEvent, onStatus)` (SSE with Last-Event-ID;
     returns the stop), `client.control(id, 'pause'|'resume'|'stop'|'retry')`, `client.reorder(order)`;
     `derive.deriveRun(events, run)` gives the run page's view. Questions: `client.questions()`, `client.answer(id,
     option, text)`. Sign-in: `client.signIn.{status, open, input, done, skip, forget}`. Branches:
     `client.branches.*`. Assistants and cost: `client.assistants()`, `client.usage()`. Conversation:
     `client.chat(message, session, context, model)` then `client.chatProgress(turn)`; `client.chatControl(on)`.
     Projects: `client.projects()`, `client.openProject(workspace)`.
   - after a change: `store.refresh()` (the runs), `store.patchRun(id, run)` to show it at once.
4. **States**: `ctx.state` is `''`, `'loading'`, `'empty'` (no check yet) or what the address asks for review
   (`?state=loading|empty|offline|reconnecting`); `ctx.offline` (or `offline()`) is the read-only copy, where every
   action is locked and offers `open-live`. A state that is a fact of the project (running, paused, waiting for a
   sign-in, a stale check, no assistant) comes from the data (`live`, `liveNow()`, `freshness()`, `live.assistants`),
   never from the address: the prototype's `?state=running|signin|…` demos are not ported.
5. **Words**: the prototype's keys are already in `src/words/activity.js` / `understand.js` as `'key': [ar, en]`.
   A word that carried a sample fact (a number, a branch, a time, "R-14") must become a parameter filled from the
   data (`'st.verdict': ['{problems}، منها {fixable} يصلحها EAOS وحده.', …]`); remove the sample word when nothing
   uses it. A plural is `[{zero, one, two, few, many, other}, {one, other}]` with `{n}`. Arabic first, English
   equally finished; the build stops on a key without both languages or a key defined twice. A name from the report
   with no word (a new kind) is shown as it is: `has(key) ? t(key) : name`.
   Moved to core (use these): `as.ph` (was `ac.ask.ph`), `as.depth`, `as.depth.quick|balanced|deep`. Removed with
   their sample facts: `st.opt.1..5` and their `.sub` (the launcher composes its recommended options from the data).
6. **Labelled examples are not ported.** The prototype filled gaps of its sample with examples (`example: true`,
   "this copy carries n of m"); the console shows the real data, and an honest empty or not-measured state where
   the report has nothing (never an invented number).
7. **Check it** on the served preview (`README.md`, Checks): `node console/tools/sweep.cjs --routes=…` and
   `sheets-sweep.cjs`, `targets.cjs`, `axe.cjs` on your routes, at 390 and 1440, Arabic and English, light and dark:
   0 console errors, 0 missing words, 0 overflow, 0 axe violations, every control 44 px on the phone. Build
   (`cd console && npm run build`) and run `tests.test_studio_assets` before each commit; commit `eaos/data/studio`
   with your source (one build per commit; on a conflict in `eaos/data/studio`, rebuild).

## Shared pieces you will need

- the verb preview over a selection (Fix, Verify, Explain, Plan): open `?sheet=verb:<verb>` (the current selection),
  `verb:<verb>:<problem>`, `verb:<verb>:step:<step>`, `verb:<verb>:fixable`; it lives in the problems bundle.
- Accept / Reject a delivered branch: `?sheet=accept:<run>` / `reject:<run>` (waiting bundle).
- the selection: `selection.picked`, `selection.pick(ids, group)`, `selection.toggle`, `selection.groupsOf(problems)`;
  draw the selection bar with `setSelbar(fn)` when your screen selects (the plan does).
- the live strip and "what runs now": `liveNow()`; the waiting count: `model.waitingCount()`.
- times: `fmtWhen(iso)`, `fmtTime(iso)`, `exactTime(iso)`, all in the person's time zone (`prefs.tz`, set in Settings
  with `setTimeZone(zone)`).
