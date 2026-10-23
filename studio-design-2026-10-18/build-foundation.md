# Build phase 1: the foundation of the new Studio (lead engineer, 2026-10-18)

Branch `dev/studio-new` in `/workspace/engineering-audit-os` (from develop @b88eb6e), 11 commits, last `4a261f8`.
Nothing merged into develop; main and beta-trial untouched.

## What exists

- **`console/`**: the new Studio source (plain JS modules + CSS, no framework). `console/README.md` (layout, data
  layer, the `eaos` API, the shapes table prototype `D.*` -> real) and `console/PORTING.md` (how to port a screen,
  file ownership) are the builders' instructions.
  - Build: `cd console && npm run build` (esbuild 0.28.2 pinned, `console/node_modules` 12 MB, gitignored; one
    `npm install` on a fresh checkout). Output replaces `eaos/data/studio`: `assets/studio.js` (core), one bundle per
    place (13), `words-ar.js`/`words-en.js`, `style.css` + fonts, `SOURCE.json`. Budgets now: first page 82 KB gzip
    (of 240), stylesheet 18 KB (of 48), whole 892 KB (of 6 MB).
  - Core runtime ported from the prototype: shell (sidebar, tab bar, top bar, live strip, banner, selection bar),
    router with the prototype's addresses, sheets (own address, focus trap, `local()` state, `needs`), dictionary
    (`t`/`tn`/plurals, 2700 words, both languages enforced by the build), language/theme/time zone, search,
    project menu (real projects list), floating assistant frame (conversation comes from the Ask place, A).
  - Data layer ported from `studio/src/data`: sections live (token + CSRF) or offline `.js` twins, lazy per screen,
    live feed `/api/events` with Last-Event-ID (reloads changed sections), run event streams, the full actions
    client, live command state (runs/queue/questions/decisions/sign-in/assistants/progress/freshness/context),
    selection + groups -> contract selection, search normalisation, `model.js` adapter.
  - Lead screens on real data: Status (all folds, freshness and health sheets), Waiting for you (decisions answered
    through `POST /api/decisions/<id>/answer`; delivered branches; real Accept/Reject confirm sheets: preview ->
    confirm token -> `POST /api/runs/<id>/accept|undo`), Problems (filters, groups, selection, 50 at a time), one
    problem with real evidence and code lines, the verb preview on the real preview API (where/assistant/auto-accept
    re-preview, Start with the token), note via the `note` action.
  - Every other place registers its addresses and sheets as outlines ("being built", features covered).
- **Tests**: `tests/test_studio_assets.py` rewritten for console/ (fingerprint, classic scripts, no URLs, one
  dictionary per language, fonts, budgets, places import only `eaos`). `eaos.policy.json`: `console/**` in the
  studio layer. AGENTS.md and tools/validate.py name console/. Full suite: 655 tests OK; validate.py: no errors.
- **Tools** (`console/tools/`, against a served console with its token): `sweep.cjs`, `sheets-sweep.cjs`,
  `targets.cjs`, `axe.cjs`, `presses.cjs` (+ `lib.cjs`). Results on the three lead screens (35 real routes):
  sweep 280 pages 0 issues; sheets-sweep 608 sheets 0 issues (one 503 seen only while a rebuild was replacing the
  served folder); targets ar/en 0 under 44 px, assistant button overlaps 0; axe 280 combos 0 violations; presses
  on the lead's 87 features 70 pass at 390/1440 ar/en, none above 3 presses. The 17 left need builders' screens or
  a live state: DEC-02..05, FIX-08 (questions, A), FIX-10/15/16, CHK-08/10, SET-03/05, OFF-05 (A/B screens and
  sample run ids in their recipes), FIX-07/ACT-01 (a running fix/check), PRB-11 (a new check landing), FIX-14 (the
  close-batch button shows only after a stopped batch).
- **Real end to end** (scratch): Accept and Reject pressed through the confirm sheets merged / deleted real wave
  branches in the scratch repo (toasts, Waiting updated). Offline copy (build + report `.js` twins in one folder,
  opened from `file://`) draws Status/Waiting/Problems read-only.

## How to run

- Preview: systemd unit `eaos-new-studio-8099` (0.0.0.0:8099, `--remote-origin https://engineering-audit-os--8099.dev.remote.e-m.sa`,
  `EAOS_STUDIO_TRUST_REMOTE_LOGIN=1`), serving this checkout's `eaos/data/studio` on the scratch home
  `/workspace/eaos-work/studio-design/build-home` (README there: copy of studio-governance/preview-home with paths
  rewritten). Routed: https://engineering-audit-os--8099.dev.remote.e-m.sa (behind the Remote login). Restart:
  `systemctl restart eaos-new-studio-8099`. Token: `build-home/home/studio/repo-b7d558ac.token` (tools read it).
- A waiting branch to accept/reject: `EAOS_HOME=…/build-home/home .venv/bin/python /workspace/eaos-work/studio-design/scratch/make-waiting.py [TASK-id]`
  (one exists now: wave 11 on TASK-073).
- Checks: `node console/tools/sweep.cjs [--only=…] [--routes=/a,/b]`, `sheets-sweep.cjs`, `targets.cjs ar|en`,
  `axe.cjs`, `presses.cjs [prefix]` (results in `studio-design/presses-results.json`).

## What builders do (details in console/PORTING.md)

- **A**: `places/activity`, `places/project`, `places/ask` (+ `EAOS.askAPI`), `places/waiting/signin.js` and
  `questions.js`, `places/open`; words `words/activity*.js`; css `activity.css`.
- **B**: `places/plan`, `places/understand` and `understand-{change,built,screens,records}`; words
  `words/understand*.js`; css `understand.css`.
- Replace each outline with the port, `D.*` with the model/live data, simulations with the API; parameterize words
  that carried sample facts; update their press recipes' sample ids; run the tools on their routes; build and
  commit `eaos/data/studio` with the source.

## Open issues

1. The team preview `eaos-team-preview-8097` runs this same checkout's EAOS, so it now serves the new console too;
   any rebuild briefly empties `eaos/data/studio` for every server on it (a 503 during the build). Builders in
   parallel on one checkout collide on `eaos/data/studio`: use a worktree each and rebuild on merge.
2. Report prose is single-language (the scratch report is Arabic, no `locales`): English pages show Arabic report
   texts (isolated in their direction). Composed sentences are fully bilingual.
3. Waiting lists delivered branches from Studio runs only (as the old Studio); a wave applied from the terminal
   without a run is not listed (the accept preview knows it: `merge.branch`).
4. `?state=` keeps only loading/empty/offline/reconnecting for review; the prototype's running/signin/stale/fixing
   demos are real states now (gate recipes must start them for real).
5. No JS unit tests yet (the old Studio had vitest for selection/normalize/live); the logic was ported as is.
6. Assistants are not logged in on the scratch home (`HOME=build-home/home-root`), so previews show the hand-off and
   Start stays locked for assistant verbs; log one in there for gate 2.
7. Old `studio/` is unused source, listed for deletion with `tools/studio_fonts.py`; tests that still read its
   fixtures (test_pipeline_sheet, test_studio_paths, test_studio_data_map, test_studio_system) must move first.
8. Scratch to remove at task end: `studio-design/build-home` (504 MB), `studio-design/scratch` (24 MB), the unit.
