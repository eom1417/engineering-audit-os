# EAOS metrics

Measured at each milestone end by `tools/metrics.py <check output> <project home> --write "<title>"` (its docstring
names this container's folders): the repository as it is, the latest check of `develop`, the corpus
(`tools/corpus.json`) and the detection baseline (`tests/fixtures/baseline-problems.json`). Numbers are compared with
the section before; a worse number needs its reason here.

## Baseline: 0.0.71 (2026-10-23), EAOS's own check of `develop`

| Measure | Value |
|---|---|
| Python lines (`eaos/`) | 62,123 in 297 files (119 flat at the package root) |
| Studio UI (`console/src`) | 13,274 JS lines in 98 files (words 3,087) |
| Tests | 19,978 lines in 124 files, 699 tests, ~7 min |
| Check time | 3,599 s wall (ideal 1,462 · verify 650 · triage 490 · engines 291 · app stages ~1,100) |
| Stages / documents / engines | 38 / 27 `.md` / 41 tools |
| Output | 409 MB, 2,483 files (`facts` 281 MB: syntax 77, structure 77, syntax-cache 63) |
| Runtime | 873 MB (`run-data` 783 MB, never removed) |
| Cards on itself | 515 (271 complexity hotspots, 137 design reviews, 3 security) |
| Engine findings | 3,853 (`semgrep` 1,672 of which 1,554 one rule; `reforge` 1,557) |
| Compatibility corpus | not built yet (M0.3) |
| Detection baseline | not built yet (M0.2) |

## After M0: 0.0.72 (2026-10-23)

The check figures are those of the last check of `develop` (2026-10-22, 0.0.71): M0 changed no code a check runs.
The cards are counted as the plan's tasks and the claims they come from (the baseline counted every card record); the
stages as the manifest recorded them (37 of the 38 declared ran); the runtime without the tools it links (the baseline
counted them through the links).

| Measure | Value |
|---|---|
| Python lines (`eaos/`) | 62,125 in 297 files (119 flat at the package root) |
| Studio UI (`console/src`) | 13,274 JS lines in 98 files (words 3,087) |
| Tests | 19,988 lines in 123 files, 705 test functions |
| Check time | 3,599 s wall (ideal 1,462 · verify 650 · triage 490 · engines 291) |
| Stages / documents / engines | 37 / 27 `.md` / 41 tools |
| Output | 403 MB, 2,483 files |
| Runtime | 773 MB |
| Cards on itself | 101 plan tasks (45 hotspot, 13 extend_feature, 12 canonicalize) from 418 claims |
| Engine findings | 3,853 (`semgrep` 1,673, `reforge` 1,557) |
| Compatibility corpus | 2 of 12 apps pass (12 pinned) |
| Detection baseline | 5 of 8 planted problems found |

## After M1: 0.0.73 (2026-10-24), the rules' part of a check of `develop`

Measured on `eaos audit --engines` with no assistant and no app run (306 s), against the same parts of the 0.0.71
check: the stages that need the assistant or the running app did not run, so the cards are the rules' (no triage
merges them) and the runtime was not measured. The full check's figures come at its next run.

| Measure | 0.0.71 (same parts) | 0.0.73 |
|---|---|---|
| Output | 390 MB in the full report; `facts` 281 MB, `engines` 29 MB | 95 MB, 468 files; `facts` 74 MB, `engines` 6 MB |
| Documents (`.md` at the top) | 27 | 8 |
| Engine findings | 3,853 | 3,785 (reforge −50, lizard −12, complexipy −10, jscpd −4, codeql −1, semgrep +9: the code M1 removed) |
| Debt items | 341 (after the assistant) | 378 (rules only) |
| Rules' part time | engines 291 s alone | 306 s for all 20 stages |

- **Target met:** output ≤ 150 MB (95). **Not yet:** ≤ 400 files: 353 of the 468 are `PLAN/TASK-*.md`, one per card
  (351 rules' cards without the assistant's triage, about 100 with it); the runtime ≤ 100 MB awaits the full check.

## Findings of the M-1 measurement (inputs for M1-M7)

- **Disk:** `live_run.py:114` never removes `run-data`; output cleared only for `BULKY` (`pipeline/run.py:307`); Studio
  sections written twice (`studio/export.py:366`); engine findings stored three times; `human/index.html` copies
  `REPORT.html` (`guided.py:442`); stale translations never cleared (`bilingual.py:150`: 1,070 of 1,214 Library docs).
- **Reading all facts per call** (~280 MB): `agent_tools.py:478`, `execute.py:36`, `codemods.py:245`,
  `debt_register.py:65`, `intake.py:33`, `nfr.py:20`, `indicators.py:14`.
- **Documents read by nobody but the Studio Library:** CONTRACTS, FLOWS, DOMAIN-AND-DATA, ONBOARDING, DECISION-BRIEF,
  RISK-REGISTER, ROADMAP, EVOLUTION, PROVENANCE, FEATURES, LOAD-MODEL, MEASUREMENTS, SUSTAINABILITY, SEMANTIC,
  POLICY, ENGINES, transform-plan.
- **Records read by nobody or only by AI prompts:** `live/sign-in.json`, `proposals.json`, `reports.json`,
  `architecture/map.json`, `readiness.json`, `transform-plan.json`, `live/lock.json`, `live/journeys.json`.
- **Engine overlap (files):** complexity: `reforge` 230 (119 unique), `complexipy` 85 (8), `lizard` 77 (4),
  `enola` 38 (2); dead code: `enola` 31 (30 unique), `vulture` 5 (4); security: `semgrep` 91 (77), `bandit` 22 (8),
  `codeql` 6 (2). One Python project: confirm on the corpus before removing any engine.
- **Tests:** duplicates D1 "no assistant, rules decide" ×5 (`test_ai_nodes:413`, `test_ideal_planner:215,397`,
  `test_ai_in_the_pipeline:92`, `test_joint_decision:89`); D2 two guards (`api/guard.py`, `studio/actions/security.py`);
  D3 `test_journey` runs the journey twice; D4 engine contracts in three files; D5 branches ×3. Sleeps:
  `test_mcp:350`, `test_pipeline_parallel:206`, `test_sandbox:138-160`, `test_studio_actions:547-610`.
- **Studio:** core places status, waiting, activity, ask, problems, screens, open (+ branches, plan); the
  understand-* views (17 screens) ≈ 5.4k lines and ~200 KB of bundle; ideal/nodes, system/territory, history and
  coverage stay because core places read them.
