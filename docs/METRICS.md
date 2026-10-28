# EAOS metrics

The numbers of EAOS, measured at each milestone end, oldest first. `tools/metrics.py <check output> <project home>
--write "<title>"` measures the repository as it is, the latest check of `develop`, the compatibility corpus
(`tools/corpus.json`) and the detection baseline (`tests/fixtures/baseline-problems.json`); the proofs with the real
assistant (`tools/*_proof.py`) measure the journeys. Numbers are compared with the section before; a worse number
needs its reason here.

Latest: **0.0.87**, M14 (below). M7 (0.0.79) has no section of its own: what it changed is proved by the
fix proof in the golden trial, not by a number.

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

## After M5: 0.0.77 (2026-10-25)

The check's rows (time, stages, documents, output, cards, engine findings) repeat the last full check of `develop`,
from before M5, as after M0; no new full check ran for this milestone.

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

## After M9: 0.0.81 (2026-10-26)

| Measure | Value |
|---|---|
| Runtime of a full check of EAOS (`--run-app --assistant claude`, 39 stages) | **68 MB** in 176 files (target ≤ 100; 760 MB at M5); its largest part `syntax-cache.json` 65 MB |
| That check | 3,474 s wall, $9.09; output 125 MB in 959 files; 56 plan tasks from 184 claims; 1,394 engine findings (`reforge` 1,013, `enola` 182) |
| Repair end to end (flaskr, real assistant) | CLI 19 min, $2.24; Studio action API 19 min, $2.32 (the check 80% of both) |
| Build from a PRD to the first milestone's proof gate (MCP) | 378 s, $0.95, its screens reviewed |
| Add a feature (CLI and MCP; Studio) | a page of its own: 90 s, $0.49; Studio plan and build 631 s (400 of them queued), $0.88; a link on every page refused by the behaviour lock (it knows no intended change) |
| The tidy on three corpus apps (flaskr, task-api, flask-microblog) | no move batch proved (moves unwritable, no runnable tests, an app that stops starting); the target shape's moves made unproven: same answers (10/10), tokens +9% and +16% |
| Model tiers | each stage's tier recorded per run; the next check of `develop` measures the cost per check against 0.0.80 |

## After M10: 0.0.82 (2026-10-27)

The simulated users on three corpus apps of different kinds (`tools/experience_proof.py`, the real assistant):

| App | Whole simulation (`--path experience`) | Found | The short option beside the complete check | The replays in that full check |
|---|---|---|---|---|
| flask-microblog (sign-in) | 3 personas, 11 goals (9 waiting on a hand-off that never came), 3 tickets; the stage 504 s, 50 calls, check $2.31 | 1 confirmed (search crashes with a technical Elasticsearch page: 2 pictures, 4 steps to reproduce), 3 doubted, 7 rejected | 62 s, 7 calls | 3 skipped (no goal reached to replay) |
| django-locallibrary (two roles) | 4 personas, 9 goals, 2 reached, 2 tickets; the stage 391 s, 38 calls, check $7.62 | 6 doubted, 1 rejected | 11 s, 1 call | 2 green, 2 skipped, no AI call |
| next-dashboard (Next.js, sign-in) | 2 personas, 4 goals, 1 reached, 2 stuck, 2 tickets; the stage 155 s, 14 calls, check $7.50 | 2 doubted, 2 rejected | 21 s, 2 calls | 1 green, 2 skipped, no AI call |

The short simulation adds 11-62 s and 1-7 light calls to a complete check and confirmed nothing on these runs; the whole
simulation found one real failure a person would meet. The replays cost nothing and are green.

## After M15: 0.0.88 (2026-10-28), one source per pattern

| Measure | Value |
|---|---|
| EAOS by its own law (`tools/quality.json`) | near copies **43 to 0**, the look written outside `tokens.css` **290 to 0**, screen patterns **26 to 0**, ways of working **2 to 0**; the tolerant JSON reader once (`core/system/files.py`, 176 places), the time once (`core/system/clock.py`, 40 places); 5 copies kept on purpose, each with its reason (the MCP tools' signatures, and a JSON read in three programs that cannot import one another) |
| Detection baseline | 35 planted problems, the near copy, the JSON read three ways, the pop-up on three screens, the colour a shade off, the sizes off the scale, the date three ways and the repeated guard among them; 9 examples that must stay, two parts alike that change apart among them |
| Precision on the corpus, judged from outside by an independent judge, with the three conditions | near copies **0.643** on 14 (0.459 on 85 before the conditions); screen patterns **0.0** on 6 (0.091 on 11); the look 4 judged, the ways of working 1 (the bar is 5): every one kept aside, its cards hidden and the reason said (`eaos/data/detector-verdicts.json`) |
| What was alike in shape only | said in the report as a likeness, never a card nor a breach of the law |
| Cost | no token; the sorting 0.04-0.41 s an app on the corpus; jscpd's near modes ride on the code stage already running |

## After M14: 0.0.87 (2026-10-28), how the data is saved and kept

| Measure | Value |
|---|---|
| Detection baseline | **28 of 28** planted problems found (21 before: the whole-state saves, "Saved" before the answer, the queue over quota, the base64 logos, the backup of the orders only, the page that sends back the whole report); the 6 examples that must stay not found |
| The baseline app's page saves (no database of its own) | 5 pages read, one save sent on every visit with all 3 records the page read: one card; the server's state file found (data in files only) |
| flaskr (SQLite) | its two empty tables given 365 records each (a year of dates, every post pointing at a user); the database's own dump restored and compared: both tables back whole; no backup declared: one card |
| PostgreSQL, the same steps on the run's own server | 6 rows grown to 300 per table; whole documents (20 KB a row) and 300 pictures as text read; two tables sharing values found; the dump restored, every table the same, the restored database removed |
| Compatibility corpus, every app through the new stage | **15 of 15** run and pictured |
| What this version does not check (`unchecked`) | **empty**: the score and its areas read from their own measures |

### The cost of adding a tool

| Tool or rule | Files | Lines | Core changed | Time |
|---|---|---|---|---|
| Squawk (M14.3) | the registry entry, the adapter (63), its licence | ~90 | no | under 1 h, most of it reading which of its rules are style |
| ast-grep saving rules (M14.3) | the rule file and its examples | ~190 | no | about 1 h (a comma inside a pattern of YAML's short form split it) |
| The `keeping` stage (M14.1-M14.4) | its runner (60), `live/keeping/` (database 100, volume 90, synthetic 120, stored 60, restore 130, writes 80, files 30, lost update 80), a Playwright script (75) | ~830 | no: a stage is its declaration, its loop, its runner and its words, as every stage before | about 5 h |
| The sorting and its cards (M14.2-M14.4) | one assessment (190), one claims module (130), one line each in the probes, the remediation, the words, the score's patterns, the debt register, the check paths | ~335 | no | about 2 h |

## After M13: 0.0.86 (2026-10-28), old engines

| Measure | Value |
|---|---|
| Detection baseline | **21 of 21** planted problems found (19 before: the switched-off export and the two totals each a card); the 4 examples that must stay not found |
| What ran, on the baseline app's check | the tests: 1 file; the Node server while the pages were opened: 4 files, 10 functions ran, 7 never; the browser: no script named as a project file (its page's script is inline) |
| The switched-off export | CONFIRMED: the server's run measured `export.js` and never ran `oldExportFile` |
| False alarms on EAOS's own code (the tests and the built Studio excluded) | 0 old-engine cards, after `new`, `next` and `previous` stopped counting as markers (4 before) and a pair was held to one folder and one language |
| False alarms on the compatibility corpus (15 apps, the code alone) | 0 |
| Compatibility corpus, every app's server run with coverage on | **15 of 15** run and pictured, after two defects it found were fixed (a Python server's `-u` given to Coverage.py; a bundler's workers still writing after the stop) |

### The cost of adding a tool

| Tool or rule | Files | Lines | Core changed | Time |
|---|---|---|---|---|
| ast-grep switch rules (M13.1) | the rule file (142) and its examples (78) | 220 | no; the ast-grep adapter now keeps a branch body's lines (8 lines), for any rule that captures one | under 1 h |
| Coverage while the app runs (M13.2) | `live/testing/ran.py` (157), a Node preload (4), the crawl's JS coverage (20), the tests' record (17) | 198 | yes, small: the app's start goes through one function that turns coverage on (12 lines in `live/app/run.py`), and the shared app's close records it (5) | about 3 h |
| The sorting and its cards (M13.1, M13.3, M13.4) | two assessments (250, 100), one claims module (147), one line each in the probes, the remediation, the words, the score's patterns, the debt register, the check paths | 497 + 15 | no | about 3 h |

## After M12: 0.0.85 (2026-10-27), real data in the code

| Measure | Value |
|---|---|
| Detection baseline | **19 of 19** planted problems found (16 before; the staff table, the monthly table and the server's administrator each a card); the 3 examples that must stay (the menu, John Doe, the tests' people) not found |
| False alarms on EAOS's own code (731 files, the tests and the built Studio excluded) | 0 findings |
| False alarms on the compatibility corpus (15 apps, Presidio and ast-grep alone) | 1 finding, right: the users written into CoreUI's dashboard screen; 2 menu tables read as people before the fix of this version, 0 after |
| Presidio's read of EAOS's string literals | about 4 s (literals only, the model only on name fields) |
| Presidio's environment | 398 MB (spaCy and its small English model), its own |

### The cost of adding a tool

| Tool or rule | Files | Lines | Core changed | Time |
|---|---|---|---|---|
| Presidio (M12.1) | the registry entry (24), the adapter (63), its script (179), its words (38), the licences | 304 | yes, once: the toolchain knew a Node library with no command, not a Python one (`install.library` for pip, 1 line), nor a wheel pinned at its address beside a tool (6 lines); the engine registry took a tool with no command (1 line). Fixed in general, so the next Python library adds none | about 3 h, with the lab's choice made before |
| ast-grep data-table rules (M12.2) | the rule file (90) and its examples (47) | 137 | no | under 1 h |
| The sorting and its card (M12.3) | one assessment (209), one claims builder (108), one line each in the ledger, the probes, the remediation, the words, the score's patterns, the debt register, the check paths | 330 + 15 | no: the registries a card kind joins, as every kind before | about 2 h |

## The final proof: 0.0.83 (2026-10-27)

| Measure | Value |
|---|---|
| Compatibility corpus | **15 of 15** apps run and pictured |
| Detection baseline | **16 of 16** planted problems found; the fix proof and the clean twin green |
| Repair (flaskr, CLI, real assistant) | check 738 s $1.02, a card fixed and handed over 118 s $0.36 |
| Add a feature: a link on the navigation every page shows | 120 s $0.43, through the behaviour lock (M9.7) |
| Build from a PRD to the first milestone's proof gate | 338 s $0.91 |
| Simulated users (flask-microblog, whole) | 6 of 10 goals reached (3 of 11 before), 3 tickets, 6 confirmed, 5 fix cards (0 before), 142 calls, $6.37; 2 of the 6 came from the route prefix fixed in this version |

## Findings of the M-1 measurement (the inputs of M1-M4, kept as where they started)

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
