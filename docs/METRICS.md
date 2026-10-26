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

## After M2: 0.0.74 (2026-10-24), the rules' part of a check of `develop`

Measured as after M1 (`eaos audit --engines` by the beta-trial EAOS, no assistant, no app run), against the M1 numbers.
The machine was busy: the time is not comparable, and Checkov's version probe took 111 s of its
120 s limit, so this run counted it as not installed (it is installed).

| Measure | After M1 (0.0.73) | After M2 (0.0.74) |
|---|---|---|
| Engines / tools in the registry | 24 / 41 | 22 / 39 (complexipy, vulture removed) |
| Engine findings | 3,785 (`semgrep` 1,682) | 2,054 (`semgrep` 116; `trivy` 0: secrets and misconfigurations only) |
| Output | 95 MB, 468 files | 88 MB, 494 files (`engines` 4 MB; 379 `PLAN/` files) |
| Rules' cards / debt items | 351 / 378 | 377 / 396: 110 hotspots, as a count one engine states (parameters, nesting) is now a claim; 98 dead code, 96 of them the Studio's modules EAOS's detector cannot reach (open item) |
| Trivy's database on the computer | 1.6 GB, downloaded daily | none (3 MB of misconfiguration checks) |
| Rules' part time | 306 s | 868 s, loaded host (semgrep 524 s with no per-rule limit, CodeQL 295 s, GitNexus 252 s) |
| Python lines (`eaos/`) | 61,014 in 293 files | 60,678 in 290 files |
| Detection baseline | 5 of 8 | 6 of 8 (the command injection a card) |
| Compatibility corpus | 2 of 12 | 2 of 12 (not run again: M2 changed no app run or screen) |

- **The engines measured on the claims they lead to** (the 12 corpus apps, the baseline app and EAOS, the same facts read
  by the code before and after): 1,012 claims became 871. Lost: 141 duplicates (136 Trivy cards of one advisory each,
  beside OSV-Scanner's per package; 2 dead-code cards beside EAOS's own; 3 complexity targets in test functions EAOS
  never counts). Gained: 94 work targets (55 on EAOS, 37 on CoreUI), counts one engine states exactly.
- **Per engine on that corpus**, places only it reached: complexity reforge 157, lizard 4, enola 4, complexipy 8 (EAOS
  only, judged by EAOS's count); dead code EAOS's own detector 125, enola 6, vulture 0 of 21 standing, knip's files
  unconfirmed without its plugins but its unused dependencies its own; security semgrep 93, bandit 9, CodeQL 2,
  gitleaks 1, checkov 5, Trivy 0 vulnerable packages beyond OSV-Scanner.

## After M4: 0.0.76 (2026-10-24)

M4 changed how the check runs, not what the engines find, so the engine measure was not run again. Measured:

| Measure | Before M4 | After M4 |
|---|---|---|
| The ideal picture (EAOS's own check, real trial with Claude) | 1,461 s: plan 7 min, critique 18 min (3 tries, the whole ideal written again) | 474 s: three plan parts side by side 149-181 s, critique 287 s (3 tries, changes only, 15 KB instead of 65 KB) |
| Its output and cost | 119 elements, 4 dropped; $5.75 | 112 elements, 0 dropped; $6.00 |
| GitNexus import cycles on EAOS | 10 (6 on today's code) | 0: all six its misreading of Python |
| The Studio's JavaScript over the laws | not measured | 0 (48 functions over complexity 10 and 4 modules over 400 lines split; every screen and sheet drawn the same before and after) |
| Repair or rebuild of EAOS | none | repair: 101 cards, 5-14 hours; rebuild 549 files, 55-147 hours (rough rule) |

- The critique still broke its JSON twice in the trial (Arabic text in a long answer): without the retries the ideal
  takes about 5 minutes.

## After M3: 0.0.75 (2026-10-24), the rules' part of a check of `develop`

Measured as after M2 (`eaos audit --engines` by the beta-trial EAOS on `develop` at `484debd1`, no assistant, no app
run), against the M2 numbers. The machine was quiet, so the time is comparable to M1's, not M2's.

| Measure | After M2 (0.0.74) | After M3 (0.0.75) |
|---|---|---|
| Engine findings | 2,054 (`semgrep` 116) | 1,488 (`reforge` 1,095, `enola` 179, `semgrep` 97, `lizard` 36, `jscpd` 28, `gitnexus` 26, `bandit` 19, `codeql` 4) |
| Output | 88 MB, 494 files (379 `PLAN/` files) | 88 MB, 350 files (243 `PLAN/` files) |
| Rules' cards / debt items | 377 / 396 | 241 / 254: maintainability 137, reliability 88, security 19, architecture 10 |
| Rules' part time | 868 s, loaded host | 334 s |
| Python lines (`eaos/`) | 60,678 in 290 files | 65,202 in 399 files, the largest 400 lines, every function ≤ 10 by the code laws' count |
| Detection baseline | 6 of 8 | 6 of 8 |
| Compatibility corpus | 2 of 12 | 2 of 12 (not run again: M3 changed no app run or screen) |

- **What the laws did not reach yet** (inputs for M4, settled in M4.6): the Studio's JavaScript (`console/src`) is under no complexity law,
  and 32 hotspots remain, most of them there (17-20 branches: `stages.js` `render`, `actions.js` `liveClient`,
  `kit.js` `zoomable`); EAOS's own hotspot count (the facts' metrics) adds nested functions into the one that holds them,
  the code laws count each alone, so `interfaces/mcp_server/fix.py` `_fix_tools` (19 tools registered inside it) is a hotspot of 20 that
  the laws pass. `reforge` counts complexity per file (its 1,095 findings), not the laws' per-function measure.
- **Security, untriaged**: 19 items without the assistant's triage: 5 are test fixtures' sample tokens, the rest
  single-engine audit rules (semgrep's subprocess call in 30 files, CWE-78; CodeQL 4) that a full check's triage settles (card M8.4).
- **Architecture**: GitNexus reports 10 import cycles (`eaos/ai/nodes`, `core/language/markup.py`, `report/human_report/html.py`)
  that import-linter's layers and the dependency-cruiser pass: lazy imports inside functions; settled in M4.6 (all six GitNexus's misreading).
- The cards' titles of agreeing engines were stored in Arabic and printed so in an English check: stored in English
  since this measure (`eaos/analysis/claims/ledger.py`), the reports render them from the template in the reader's language.

## After M5: 0.0.77 (2026-10-25)

| Measure | Value |
|---|---|
| Python lines (`eaos/`) | 66,501 in 408 files (2 flat at the package root) |
| Studio UI (`console/src`) | 14,012 JS lines in 105 files (words 3,006) |
| Tests | 20,502 lines in 129 files, 728 test functions |
| Check time | 3,599 s wall (ideal 1,462 · verify 650 · triage 490 · engines 291) |
| Stages / documents / engines | 37 / 27 `.md` / 39 tools |
| Output | 401 MB, 2,482 files |
| Runtime | 760 MB |
| Cards on itself | 101 plan tasks (45 hotspot, 13 extend_feature, 12 canonicalize) from 418 claims |
| Engine findings | 3,853 (`semgrep` 1,673, `reforge` 1,557) |
| Compatibility corpus | 12 of 12 apps pass (12 pinned) |
| Detection baseline | 6 of 8 planted problems found |


## After M8: 0.0.80 (2026-10-26)

Measured on the code (no check of `develop` ran for this milestone; the next one from the Studio measures the check's
rows on 0.0.80).

| Measure | Before M8 (0.0.79) | After M8 |
|---|---|---|
| Python lines (`eaos/`) | 69,553 in 470 files | 71,615 in 490 files (the move tool, its gate, the context batch, MCP parity) |
| Studio UI (`console/src`) | 14,091 JS lines in 106 files | 10,119 in 79 files |
| Built Studio | 1,405 KB | 1,039 KB (budgeted) |
| Studio routes with an MCP tool | 42 of 62 | 50 of 62, the other 12 with their reason |
| Tests | 20,930 lines in 134 files, 748 test functions | 21,538 lines in 141 files, 774 test functions |
| Engine findings on EAOS's own code (`tools/quality.json`) | 276 | 0 |
| Functions over 50 lines / over 5 parameters | 5 / 129 listed | 0 / 0 listed (the justified ones say why on their line) |
| Repository and context findings on EAOS | 4 | 0 (a law of `tools/quality.sh`) |
| Python dependencies read by osv-scanner | 0 | 57 |

## After M6: 0.0.78 (2026-10-25)

The check's rows (time, output, cards, engine findings) are the last check of `develop` the working Studio holds, from
before M6; the next check of `develop` from the Studio measures them on 0.0.78.

| Measure | Value |
|---|---|
| Python lines (`eaos/`) | 68,923 in 427 files (2 flat at the package root) |
| Studio UI (`console/src`) | 14,090 JS lines in 106 files (words 3,029) |
| Tests | 20,637 lines in 131 files, 736 test functions |
| Check time | 3,599 s wall (ideal 1,462 · verify 650 · triage 490 · engines 291) |
| Stages / documents / engines | 37 / 27 `.md` / 42 tools |
| Output | 401 MB, 2,482 files |
| Runtime | 760 MB |
| Cards on itself | 101 plan tasks (45 hotspot, 13 extend_feature, 12 canonicalize) from 418 claims |
| The layers on itself | 572 files read in 6 s (python-cli; measured on today's code apart from a check, 2026-10-25): no boundary finding after the false ones it showed were fixed (console's Node tools, the API server's guard) |
| Engine findings | 3,853 (`semgrep` 1,673, `reforge` 1,557) |
| Compatibility corpus | 13 of 15 apps pass (15 pinned) |
| Detection baseline | 15 of 16 planted problems found |
| Layer findings judged on the corpus | 37 findings on 3 apps, 2 false (5%) |


## Findings of the M-1 measurement (inputs for M1-M4; what remained became cards of `ROADMAP.md`)

- **Disk:** `live_run.py:114` never removes `run-data`; output cleared only for `BULKY` (`pipeline/run.py:307`); Studio
  sections written twice (`studio/export.py:366`); engine findings stored three times; `human/index.html` copies
  `REPORT.html` (`guided.py:442`); stale translations never cleared (`core/language/bilingual.py:150`: 1,070 of 1,214 Library docs).
- **Reading all facts per call** (~280 MB): `agent_tools.py:478`, `journeys/fix/execute.py:36`, `analysis/repair/codemods.py:245`,
  `analysis/assessments/debt_register.py:65`, `analysis/understanding/intake.py:33`, `live/trials/load_plans.py:20`, `indicators.py:14`.
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
  `test_mcp:350`, `test_parallel:206`, `test_sandbox:138-160`, `test_studio_actions:547-610`.
- **Studio:** core places status, waiting, activity, ask, problems, screens, open (+ branches, plan); the
  understand-* views (17 screens) ≈ 5.4k lines and ~200 KB of bundle; ideal/nodes, system/territory, history and
  coverage stay because core places read them.
