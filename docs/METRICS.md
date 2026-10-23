# EAOS metrics

Measured at each milestone end (M0.4 makes this a script). Numbers are compared with the line before; a worse number
needs its reason here.

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
