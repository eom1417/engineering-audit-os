# Build brief: the new Studio (owner approved the design on 2026-10-18: "ابدأ البناء")

## Goal
Turn the approved prototype (`/workspace/eaos-work/studio-design/prototype/`, with `IA.md`, `DESIGN-SYSTEM.md`,
`SCREENS.md`) into the real EAOS Studio, wired to the existing back end, so the owner can use it on his real project.
Same look, same places, same words, same governance. All 198 features of `brief/FEATURES.md` work for real.

## Rules
- Branch `dev/studio-new` in `/workspace/engineering-audit-os` (from develop @b88eb6e). Never touch `main` or
  `beta-trial`. Commit often (English messages ending with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`).
  Sessions restart: commit and keep notes so work resumes.
- **The old front end `studio/` is NOT deleted** (the owner deletes it only after trying the new one). The new source
  lives in a new folder `console/`. Its build replaces what the server serves (`eaos/data/studio/`). Tests that pin the
  old source (`tests/test_studio_assets.py`, `tests/test_js_navigation.py`, stage/boot tests) move to `console/`. The old
  `studio/` becomes unused source, listed for deletion.
- **Light**: keep the prototype's approach (plain modern JavaScript modules, CSS, no UI framework, no heavy library). A
  small build step (esbuild or Vite already in `studio/node_modules` may be reused; no second copy of node_modules,
  link it) bundles, minifies, splits code per place and dictionaries per language. Budgets enforced in the build: first
  page script ≤ 240 KB gzip (target 200), stylesheet ≤ 48 KB gzip, whole Studio ≤ 6 MB (target much less).
- **The back end is reused, not rewritten**: the read API (`eaos/api/read.py`: `/api/manifest`, `/api/sections/<name>`
  incl. `library?only=`, `/api/session`, `/api/progress`, `/api/events` SSE, report files, screens, images), the action
  API (`eaos/studio/actions/__init__.py` routes and `docs/studio-actions.json`: previews with confirm tokens, runs, queue,
  questions, decisions, branches control, usage, assistants, chat, plan, sign-in), projects (`eaos/api/projects.py`).
  The old front end's data-layer logic may be read and ported (it is the feature logic, not the look): `studio/src/data/`
  (loader of sections and `.js` twins for the offline copy, live token/CSRF, SSE with Last-Event-ID), `studio/src/data/actions/`
  (client, run events derivation), selection/group models (`studio/src/command/*model*`), search normalisation
  (`studio/src/search/`). Do NOT port its look or layout.
- Back-end additions only where the design needs data the back end lacks (FEATURES.md appendix G / gate notes): keep
  them minimal, tested, in new small modules if a file is at its size limit (`tests/test_code_limits.py`).
- **Offline copy** (opened from a file): read-only, reads `<section>.js` twins, explains how to open it live.
- **Governance unchanged**: previews free, confirm tokens, owner-only acts in the confirm sheet, never into a protected
  branch, one run at a time per project.
- Words: Arabic first, English equally finished, one dictionary (split per language at build).

## Gates (the supervisor Abdullah checks them himself)
1. The prototype's measured recipes run against the REAL Studio served by `eaos studio` on a scratch home with a real
   report: `presses` (198/198, never four), `axe` (0), `targets` (44 px on the phone, incl. the chips' note), `sweep`
   (no console error, no missing word, no overflow) at 390 and 1440, ar/en, light/dark.
2. Real end-to-end use through the new Studio: start a check (and follow it live), answer a question, preview and run a
   fix, accept and reject a delivered branch through the confirm sheet, a branch merge preview, switch project, sign in
   to an app, ask the floating assistant, open a document, offline copy.
3. Full Python suite + `tools/validate.py` + the console build, green.
4. Budgets met.
