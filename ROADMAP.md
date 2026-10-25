# EAOS roadmap

**The only plan.** From today's EAOS to the ideal tool of `docs/NORTH-STAR.md`, a complete software engineering firm
in one command, built to `docs/STANDARDS.md` on the layout of `docs/ARCHITECTURE.md`. No other file holds a plan, a
backlog or a status: an open item found anywhere becomes a card here, a plan made in any assistant's plan mode is
copied here before its turn ends, and old plans are deleted once merged (2026-10-25, `docs/DECISIONS.md`).

The owner says "execute Mx" (in any chat, with any assistant): every card of Mx is done in order to the Definition of
Done (`docs/STANDARDS.md` §7), without asking again except for a decision only the owner can take. **After each card,
its row in the status table below is updated in the same change.** Milestones are numbered in the order they run.

## Where we are (2026-10-25, version 0.0.76)

M-1 to M4 are done; **next is M5**. Each done milestone in one line (what each card did: the status table; why and
how: `CHANGELOG.md`):

| Milestone | What it delivered | Version |
|---|---|---|
| M-1 Context files | the references (`docs/`), this roadmap, the container's context; any assistant continues from the files | 0.0.71 |
| M0 Foundations and guards | `tools/quality.sh`, the detection baseline, the compatibility corpus, `docs/METRICS.md` from a script | 0.0.72 |
| M1 Disk and outputs diet | one copy of the tools, outputs without duplicates, a lazy facts reader, 8 documents instead of 27 | 0.0.73 |
| M2 Fewer, sharper engines | noisy rules silenced, engines that find nothing unique removed, one engine registry | 0.0.74 |
| M3 The target code layout | ten layers enforced, one state record, one guard and one command layer, giant modules split, one words catalog | 0.0.75 |
| M4 The pipeline as loops | loops as data, the coverage ledger with red gaps, the ideal in 8 minutes, repair or rebuild, the laws over all of EAOS (the Studio's JavaScript included) | 0.0.76 |

## The firm, department by department

What a professional software firm does for its client, and where EAOS delivers each part: done, or the card that
completes it. A department with no card here is a gap in the plan.

| Department | Delivered today | Completed by |
|---|---|---|
| Discovery: the questions only the owner can answer | the intake, the coverage ledger | M5.3 (sign-in questions) |
| Architecture: the ideal shape and the decision | the ideal picture, repair or rebuild, target architecture | M6 (every project checked as layers) |
| Code quality | dead code, duplication, complexity, the code laws | M8.4 (EAOS itself clean by its own laws) |
| Security | Semgrep, Bandit, CodeQL, gitleaks, osv-scanner | M6.3-M6.7 (between the layers), M7.4 (the judge), M9.2 (logic flaws) |
| Data | the data facts, rule duplication | M6.5, M6.6 (who may see what), M6.8 (one source of rules) |
| Quality assurance | the behaviour lock, acceptance checks, Python suite health | M6.10 (the project's own tests), M10.4 (replays) |
| Performance and production | the k6 baseline, production readiness findings | M6.9 (the operations layer) |
| Screens, experience, accessibility | screens pictured, axe, journeys | M5 (any app), M10 (simulated users) |
| Delivery | the plan, cards, fix batches behind the lock | M7 (reliable fixes, verified after each batch) |
| Hand-over and documents | the four reports, START-HERE, the Studio | M7.1 (a hand-over that resumes) |
| Build from an idea | the build journey and its proof gate | M7.6 (never stalls), M9.3 (proved) |
| Add a feature | the extend journey | M9.3 (proved) |
| Interfaces | CLI, MCP, Studio | M8 (MCP parity, a light Studio) |
| Intelligence and cost | assistants per stage | M9.1 (model tiers) |

## Milestones still to do (in the order they run)

### M5 Seeing any app
- **M5.1** Running the app detected for the common stacks; green on the corpus. An engine's version check never takes
  a slow, loaded host for "not installed" (today it gives up after 120 s, `eaos/engines/tool.py`); SvelteKit's facts
  no longer crash (`eaos/facts/broken.py` `_stale_in_span` on a script with no text).
- **M5.2** Layered screen discovery: rules, then an AI explorer driving the browser, its steps saved and replayed
  without AI next time. The explorer is built as **the one browser-agent layer** (drive with a goal, record each step
  with its picture, replay without AI) that M10's simulated users reuse; an open-source agent (`browser-use`,
  `Stagehand` or Playwright MCP) is adopted only if it measures better than our own on the corpus.
- **M5.3** Sign-in handled generically: a test account per kind of user, clear questions when the owner is needed. The
  walk-through and the behaviour lock run for each kind of user (today one session, `eaos/pipeline/pages.py`), so a fix
  that breaks a page only an admin opens is caught.
- **M5.4** HungerLab joins the corpus (from the owner's snapshot repository).
- Target: ≥ 90% of the corpus pictures its expected screens; every failure explained with its fix.

### M6 The whole system in layers
A professional firm checks a product as layers: the browser holds no secret and no privileged rule, every endpoint
authenticates, authorises and validates, the business rules live in one place, the data layer enforces who sees what,
the operations and the tests hold it up, and each layer speaks only to the layers it may. EAOS knows the right layers
of ten project types (`eaos/rules/reference-architectures.json`) but enforces them only when a project declares its
own `eaos.policy.json`, and checks no endpoint guard, no row-level security and nothing of what ships to the browser
(owner's review, 2026-10-25, `docs/DECISIONS.md`). Every card adds evidence through the existing fact and engine
layers; a new tool is pinned with its licence recorded; nothing is written into the project; a placement EAOS is unsure
of becomes a question, never a finding.

- **M6.0** The proof first. `tests/fixtures/baseline-app` gains one planted defect per boundary, each in
  `baseline-problems.json`: a screen that queries the database directly, a business rule only in the browser for a
  write, a secret-named variable exposed to the browser (`VITE_`/`NEXT_PUBLIC_`), a privileged key in the built
  output, a write endpoint with no authentication, a read endpoint that returns another user's row (BOLA), a table
  without row-level security, a policy open to everyone (`using (true)`), a critical endpoint no test covers. A clean
  twin holds the same app done right. The corpus gains three apps of the stacks the layers matter for: React + Vite +
  Supabase with its migrations, a Node REST API with an OpenAPI file, a Next.js app with API routes and server actions
  (HungerLab of M5.4 when it arrives). Today's numbers recorded: planted defects found, findings on the clean twin.
- **M6.1** The layer map by default: every file of the project placed in a layer of its reference type, with the
  reason (its path, what it imports: React/JSX, a database client, an HTTP framework; its markers: `'use client'`,
  `server-only`) and a confidence; a file in no layer is a listed gap; the project's own policy file overrides. One
  fact set `layers`, extending `analysis/target_projection.py`'s placement rather than a second one.
- **M6.2** The boundaries enforced by default: each layer's `allowed_dependencies` of the reference become rules,
  written to the work folder: `dependency-cruiser` for JavaScript and TypeScript (reachability through other files,
  type-only imports allowed), `import-linter` for Python, `go-arch-lint` for Go. Each breach is a finding with
  file:line and the boundary it breaks; one of a low-confidence placement is a question. The project's own laws in its
  policy file are gates of its fixes.
- **M6.3** The browser holds no secret: `gitleaks` also over the built output and its source maps (the build run in
  the isolated copy when the person consented, otherwise said as a gap); EAOS's own rules (Semgrep/ast-grep, beside
  their examples): a secret-named variable exposed to the browser, a privileged key (`service_role`, `sb_secret_`) in
  anything shipped, source maps shipped, a server-only module imported by browser code, a database or SQL call in a
  UI file.
- **M6.4** Every endpoint and its guard: one table, a row per endpoint (method, path, handler, authentication,
  authorisation, input validation, the data it touches), from the entry-point facts and EAOS's own rules, for Next.js
  (app and pages routes, server actions), Express, Fastify, Hono, FastAPI, Flask, Django/DRF and Supabase edge
  functions. An endpoint that writes, or reads private data, with no guard is a finding; a guard EAOS cannot read is
  a question. The table feeds M6.7, M6.10 and the report.
- **M6.5** The data layer's rules, read from the migrations (no database needed): a table without row-level security,
  security enabled with no policy, a write policy open to everyone, a security-definer view or function the public
  role can run, a public storage bucket that can be listed; and for each table who reads it and who writes it (the
  data-access facts), so a table written from the browser is seen.
- **M6.6** The data layer's rules, tried: in the isolated copy with the migrations applied, the Supabase CLI's
  security advisors (`supabase db advisors --type security`, MIT, pinned) and pgTAP tests EAOS writes per table, run
  as no one, as the row's owner and as another user (M5.3's test accounts); a policy that lets another user read or
  change a row is a finding with the failing test as its evidence.
- **M6.7** The API tried against the running app: `Schemathesis` (MIT, pinned, fixed seed, a time budget) over the
  project's OpenAPI, or one EAOS writes from M6.4's table and marks as derived: an endpoint that ignores
  authentication, one user reaching another's object (two test accounts of M5.3), bad input accepted. Each failure is
  a finding with its request and response.
- **M6.8** One source of business rules: the validation and the rules of a write compared between browser and server
  (zod/yup/pydantic fields and limits, prices, roles, extending `facts/domain.py`'s rule duplication); a rule kept only
  in the browser for a write is a finding (the server trusts the client); a business calculation inside a UI component
  is flagged by an ast-grep rule.
- **M6.9** The operations layer, read from the facts (nothing deployed): the build and deploy pipeline and what it
  checks, environments and configuration kept apart from the code, where secrets live, error tracking and logs, health
  checks, migrations and backups, the infrastructure files (Checkov); each missing piece a finding that names the item
  of the reference type's infrastructure baseline it fails (extending `analysis/production_readiness.py`).
- **M6.10** The tests layer: the project's own tests found for every stack (Vitest, Jest, Playwright, pytest, Go),
  run in the isolated copy, their pass rate, and which layers and critical paths (M6.4's endpoints that write, the
  data rules) no test covers; an untested critical path is a finding.
- **M6.11** The layers for people: in the report and the Studio, each layer with its files and its state in plain
  words (breaches, unguarded endpoints, open tables, secrets, missing operations, untested paths); a broken critical
  boundary in red at the top; each finding a card that names the broken boundary and the reference's fix (move into the
  data layer, add the guard, enable row-level security), done behind the behaviour lock; M7.4's judge reads the broken
  boundary from it.
- **M6.12** The proof and the numbers: the golden trial finds every planted defect of M6.0 and nothing on the clean
  twin; on the three corpus apps of M6.0 every layer finding is judged by hand, at most 10% false; the static part
  (M6.1-M6.5, M6.8-M6.10 without running the tests) adds at most two minutes to a full check, the live part (M6.6,
  M6.7, the tests run) is an option with its time shown before it starts; `docs/METRICS.md` updated.
- Target: every planted boundary defect found with its evidence; none on the clean twin; at most 10% false on the
  corpus; every file of every corpus app in a layer or listed as a gap.

### M7 Reliable fixes and hand-over
- **M7.1** The hand-over runs as its own service and resumes where it stopped.
- **M7.2** The change that broke something found from the failure output first; halving last.
- **M7.3** Batches of about 15 cards, each handed over and merged on its own.
- **M7.4** A strict judge inside the existing triage: every finding names the harmed party, the broken boundary (M6)
  and the source evidence (Cloudflare security-audit style). The same judge rules on what a simulated user reports
  (M10.7).
- **M7.5** Each batch checked beyond behaviour: after a batch, M6's layer and security checks run again over the
  changed files, so a fix that opens a boundary is refused like one that breaks a screen.
- **M7.6** The build journey never stalls: after the third refused proof in a row its last milestone is handed over
  with the list of what stays unproven, shown in the Studio and the report (today `journeys/build_tools.py` holds it
  back on every refusal).
- Target: a batch that breaks behaviour or a boundary never reaches the person's branch; every journey ends.

### M8 Interfaces: CLI and MCP first, Studio light, EAOS clean
- **M8.1** Parity: everything the Studio does is done through MCP; the whole journey tested from the CLI alone.
- **M8.2** Studio: core places stay; the deep "understand" views (17 screens, ~5.4k lines) become one report page;
  size and memory budgets; the code's 26 references to the missing `docs/STUDIO.md` resolved.
- **M8.3** Tests diet: duplicates merged (D1-D5 in `docs/METRICS.md`), tests of removed code removed, sleeps
  replaced by awaited conditions, coverage not lower.
- **M8.4** EAOS clean by its own laws: every medium or high finding of its own check fixed, or justified on its line
  (`tools/quality.json`: Semgrep's subprocess and innerHTML findings first); knip's unused exports and jscpd's clones
  to zero; the functions over 50 lines or 5 parameters to zero or justified; a lint of the Studio's JavaScript for
  undefined names and unused imports in `tools/quality.sh` (the M4.6 lesson: a name defined nowhere broke a page); a
  lock file for EAOS's Python dependencies so osv-scanner reads them.
- Target: everything from the CLI and MCP; `tools/quality.json` holds no medium or high finding and no listed
  exception without its reason.

### M9 Intelligence, cost and the final proof
- **M9.1** Model tiers (light / standard / deep) per stage with escalation; a cheaper model never drops or closes
  anything. Simulated users act on the light tier; the scenario planner and the judge use the deep one. The ideal's
  critique answers in its schema the first time (today it retries, about 3 minutes lost). A small fast model for
  triage and easy tasks (Jev, the owner's suggestion) is measured as the light tier, for the economy and balanced
  modes, when the effort of each stage chooses its model.
- **M9.2** Logic-vulnerability hunting (from Cloudflare's security-audit skill) as an optional deep check.
- **M9.3** The three journeys proved end to end, from the CLI and from the Studio: repair a corpus app, build from a
  PRD, add a feature; the runtime target of M1 (≤ 100 MB) measured on a full check.
- **M9.4** The owner's decision on the official Semgrep rules (internal use only under their licence): kept while each
  person runs EAOS on their own code; rewritten as EAOS's own before EAOS is ever offered as a service.
- Target: the three journeys green on the corpus; cost per check measured and lower; every number of
  `docs/METRICS.md` at or above its target.

### M10 The user's full experience, simulated
A professional firm has people try the program as its users would. Here AI actors do it in the isolated copy, from
EAOS's understanding of the project, and every difficulty they meet becomes evidence. Three levels:

| Level | What runs | Cost | When |
|---|---|---|---|
| Replay | the saved journeys, step by step, **without AI** | almost none | **in every full check** |
| Short simulation | one persona doing the app's main task, within a step budget | about the ideal picture's | an **option of the full check**, its time and cost shown before it starts |
| Full simulation | several personas, hand-offs between them, support tickets, complete data | high | **its own check path** ("try the experience"), runnable alone |

- **M10.1** Scenario planner: from the facts, features, roles and screens, the personas, each one's goals and the
  hand-offs between them (the user asks, the admin approves, the user goes on), written as data.
- **M10.2** Domain data: realistic dummy data fitting the project; the key flows are entered through the UI, bulk
  history is seeded into the copy's database; external services (mail, payment, paid APIs) are stubbed, and what
  needs a real one is said as not covered.
- **M10.3** One actor, complete: drives the browser towards its goal on the M5.2 layer, within step, time and cost
  budgets; every step recorded with its picture.
- **M10.4** Save and replay: a finished journey is saved and replayed without AI in every full check, as part of the
  behaviour lock; a replay that breaks shows in red.
- **M10.5** Several actors and hand-offs: an actor waits for the event another one makes (approval, reply), then goes on.
- **M10.6** Support and tickets: an actor stuck sends a ticket, a support actor answers or escalates; the friction log
  records what was hard to find, understand or finish.
- **M10.7** Judging: each difficulty is confirmed by a second independent attempt and its evidence (steps, pictures),
  ruled on by the M7.4 judge, then becomes a fix card with its steps to reproduce.
- **M10.8** The experience report: the user's story step by step with pictures, difficulties ranked, time per task, the
  tickets; in the Studio, the CLI and MCP.
- **M10.9** The paths: "try the experience" as its own check path; the short simulation as an option of the full check
  with its estimate; the replay always in the full check.
- **M10.10** Proof and decision: three app kinds of the corpus simulated; time, cost and the quality of the findings
  measured in `docs/METRICS.md`; the owner decides from the numbers whether the short simulation becomes part of
  every full check.
- Target: the full simulation runs on the corpus apps that have more than one role; every finding carries evidence;
  replays are free and green.

## Order and why
- M-1 and M0 first: without references, guards and measures, any clean-up can break something silently.
- M1-M2 before M3: what is removed is not moved. M3 before M4-M5: the big work lands on a clean layout.
- M5 next: nothing else can be judged on an app EAOS cannot run, picture and sign into; it is the most important
  milestone for the people who use EAOS.
- M6 right after M5: its live part (M6.6, M6.7, the tests run) needs every app running and signed into (M5.1, M5.3);
  its static part may start once M5.1 is done. M7's judge and batch checks then read the boundaries M6 names.
- M7 before M8: fixes that are reliable and verified first, then the interfaces over them and EAOS's own clean-up.
- M9 then M10: the proof of the three journeys and the model tiers come before the simulated users, which stand on M5
  (the browser-agent layer), M7.4 (the judge) and M9.1 (model tiers); built earlier they would be noise and cost.
- Each milestone ends with one version, `beta-trial` updated and a short Arabic summary (`docs/STANDARDS.md` §7).

## Status (updated after every card)

| Card | Status | Version | Date |
|---|---|---|---|
| M-1.1 | done | 0.0.71 (docs only) | 2026-10-23 |
| M-1.2 | done | 0.0.71 (docs only) | 2026-10-23 |
| M-1.3 | done: a cold-start assistant answered 11 of 11 from the files; its 17 notes fixed | 0.0.71 | 2026-10-23 |
| M0.1 | done: `tools/quality.sh` (code limits incl. length and parameters, 5 layer contracts, jscpd, vulture, knip, bandit, semgrep, gitleaks, osv-scanner) records today's numbers in `tools/quality.json` and refuses a worse one; the beta update runs it | 0.0.72 | 2026-10-23 |
| M0.2 | done: `tests/fixtures/baseline-app` with 8 planted problems; the golden trial refuses finding fewer (`tools/detection_baseline.py`); today 5 of 8 (command injection, sign-in, logic flaw missed) | 0.0.72 | 2026-10-23 |
| M0.3 | done: 12 pinned apps in `tools/corpus.json`, `tools/corpus.py` records ran and screens pictured; today 2 of 12 pass (Python apps not started without an assistant, Expo and the static site never answered, SvelteKit's facts failed, CoreUI and Vitesse missing screens) | 0.0.72 | 2026-10-23 |
| M0.4 | done: `tools/metrics.py` fills `docs/METRICS.md` from the repository, the latest check, the corpus and the baseline | 0.0.72 | 2026-10-23 |
| M1.1 | done: an EAOS run in a sandbox uses the one copy of the tools (611 MB were installed again), the run's pip and npm caches go with it, batch patches kept for the last two batches, the AI run log without copies of its outputs; old scratch and the autopilot's 21 MB removed | 0.0.73 | 2026-10-23 |
| M1.2 | done: the syntax cache in the runtime (63 MB out of the report), no `.js` twins of the Studio data, engine findings once in `engines.json` and their raw outputs removed, REPORT.html a second name of the page, compact facts, stale translations cleared | 0.0.73 | 2026-10-23 |
| M1.3 | done: one reader (`eaos/facts/store.py`: `facts(kind)`, `by_id`, lazy `Sets`) reads only the sets that can hold what is asked; the 7 copies of "read every set" removed; a field every fact of a set repeats written once (EAOS's facts 281 → ~74 MB) | 0.0.73 | 2026-10-23 |
| M1.4 | done: 8 documents (START-HERE, the four reports, TARGET-ARCHITECTURE, RUN, README) plus PLAN/ and adr/; the 19 others removed with their writers and tests, their JSON records kept, every claim shown in full in debt-register.json, a run removes the retired documents of a check before | 0.0.73 | 2026-10-23 |
| M1.5 | done: `reports.json` removed (the four reports already name each number's source in their text); the other records the M-1 measurement listed have a reader and stay: `live/sign-in.json` (the detection baseline), `proposals.json` (the declared mark of the stage the triage, ideal and pipeline-gap planners require), and five read by `eaos/analysis/aspects.py` for the target and the four reports; a run removes a previous check's `reports.json` | 0.0.73 | 2026-10-23 |
| M2.1 | done: `html-in-template-string` silenced (1,554 of semgrep's 1,673 findings on EAOS, none a weakness; the DOM sinks stay); the rest reviewed: EAOS's own `command-from-text-js` finds the baseline's command injection the official rule missed (`exec` from `node:child_process`): a card now, the detection baseline 6 of 8 | 0.0.74 | 2026-10-24 |
| M2.2 | done: every engine run on the 12 corpus apps, the baseline app and EAOS; complexipy removed (nothing unique on the corpus, its EAOS files judged by EAOS's own count); Reforge and Lizard stay beside EAOS's count; a count one engine states exactly is a claim alone (+94 work targets, none lost but 3 test functions EAOS never counts); a card is rechecked only by the engine that states its target | 0.0.74 | 2026-10-24 |
| M2.3 | done: vulture removed (21 of 21 findings names called by dispatch, once its names were read right: they had all been dropped); Trivy without its vulnerability scan (OSV-Scanner found every package it did; its per-advisory cards, 119 on one app, and its 1.6 GB daily database gone); one card for dead code EAOS's detector also reports; the code laws count dead code with EAOS's own detector; every other engine finds something no other does | 0.0.74 | 2026-10-24 |
| M2.4 | done: `eaos/data/toolchain.json` the only registry; the engines stage takes its adapters from it; `upstreams/toolchain.json` (a copy) and `upstreams/registry.yaml` (stale) removed | 0.0.74 | 2026-10-24 |
| M3.1 | done: the 290 modules in ten layers (`eaos/core` … `eaos/interfaces`, only `__init__` and `__main__` at the root); one order, `interfaces → journeys → pipeline → report → ai → analysis → live → facts → engines → core`, held by import-linter's layers contract with no exception (the plan's groups of peers would have needed a rewrite: one order needed five moves of code); `eaos.policy.json` declares the same layers | 0.0.75 | 2026-10-24 |
| M3.2 | done: `eaos/core/project_state.py` the one record of a project (load, write, every, current, the run's folder): the CLI, MCP, the Studio, the API and the sandbox read it there (they read `state.json` four ways); the journeys save through `guided.save`, which tidies the batches first; a test refuses `state.json` named anywhere else; MCP's `agent_tools.project_state` is `state_of` | 0.0.75 | 2026-10-24 |
| M3.3 | done: one request guard (`core/security.py` `refusal`, the server's guard an adapter over it); one check (`journeys/check.py`: the CLI's own copy had no remedies), one branch choice (`guided.choose(via=)`), one waiting batch, one consent owner, one judgement of the app's run and the safety net, one branch protection (`core/branches.py` `policy`: MCP's accept now refuses a protected branch, as the Studio did); the runs' commands were already one (`interfaces/govern.py` for the CLI, MCP and the Studio). Kept apart by purpose: the CLI's step list and MCP's next tool (same judgements), the person's branch choice list and the Studio's git view | 0.0.75 | 2026-10-24 |
| M3.4 | done: `human_report.py` (13 modules), `guided.py` (7), `agent_tools.py` (8) and the Studio's `branches.py` (7 mixins) are packages; with M3's target every module of EAOS is under 400 lines and every function under complexity 10 | 0.0.75 | 2026-10-24 |
| M3.5 | done: `eaos/data/words.json` the one catalog of the words that name EAOS's concepts (37 stages, 5 paths, 24 kinds of problem), each with every form its readers need (a stage's title, what it does, what EAOS says while doing it; a kind's name for one card, for a group, why it matters); the engine reads it (`core/words.py` `catalog`), the Studio's build makes its keys from it (93 duplicated keys removed); it brought 2 stages the terminal named by their ids, 10 kinds the Studio had no name for, and dropped the words of 9 stages long gone. A sentence that composes values stays beside its code | 0.0.75 | 2026-10-24 |
| M4.1 | done: `eaos/pipeline/loops.py` declares six check loops as data (understand, run_and_see, judge, envision, plan, hand_over; the fix batches are the fix journey's) with `needs`, `max_rounds`, `on_fail` and an optional `switch` (a check path, or an option beside `complete`); the stages' order is the loops' order; one runner (`pipeline/rounds.py` with the scheduler): a loop not met runs its broken stages again while its rounds last (run_and_see: 2, a browser that timed out), hides what it broke from other loops until then, and `understand` not met stops the check; the manifest keeps each loop's outcome (`loops`) | 0.0.76 | 2026-10-24 |
| M4.2 | done: the 37 stages each in one loop, checked by `stages.errors()`; every stage's output has a reader (a stage or the reports), so none was removed. The table's loop names are today's dependencies: plan, target and cards sit in judge because the triage needs them | 0.0.76 | 2026-10-24 |
| M4.3 | done: the coverage ledger (`pipeline/coverage.py`) in the checkpoint and the manifest (`coverage`): each loop's covered stages, those not covered with why, and whether the gap is big (a stage broke, or one its goal stands on is absent for a reason the person did not choose); START-HERE.md and RUN.md open with the big gaps in red, RUN.md has a table per loop | 0.0.76 | 2026-10-24 |
| M4.4 | done: the ideal picture in 7.9 min instead of 24 on EAOS's own check (real trial, 112 elements, none dropped): the plan pass in three parts side by side (2.5-3 min each instead of 7), the critique answers only its changes (applied by `ai/ideal_passes.py`) instead of writing the ideal again (35,000 tokens, two of three tries broken JSON); reuse when the bundle did not change was already there. The critique still retried twice on broken JSON in the trial: the next gain | 0.0.76 | 2026-10-24 |
| M4.5 | done: `analysis/repair_or_rebuild.py`: rebuild when the target rebuilds or deletes half of today's files, else repair; each option's cards and sizes or files, and its time by the fix preview's rough rule (now one rule, said as such); START-HERE.md shows it. On EAOS: repair, 101 cards, 5-14 hours, against 55-147 hours to rebuild | 0.0.76 | 2026-10-24 |
| M4.6 | done: one complexity count (`core/code_laws.py` `complexity`, the code laws' and the hotspots', a nested function counted alone; other languages 1 + their lexical branches without nested functions); the Studio's JavaScript under the laws with no exception (`tools/code_limits.py` `studio`): its 48 functions over 10 split into helpers beside them, its 4 long modules split (the word tables by place, the branches into `branch.js` and `git.js`), proved by `console/tools/same.cjs` (every screen and sheet the Studio offers, 400 addresses x 2 languages and widths, drawn the same before and after, on the working Studio's data); GitNexus's cycles (6 now) all its misreading of Python (`from . import core`, `import html`), left out by the adapter | 0.0.76 | 2026-10-25 |
| M5.1 | not started | | |
| M5.2 | not started | | |
| M5.3 | not started | | |
| M5.4 | not started (waits for the HungerLab snapshot) | | |
| M6.0 | not started | | |
| M6.1 | not started | | |
| M6.2 | not started | | |
| M6.3 | not started | | |
| M6.4 | not started | | |
| M6.5 | not started | | |
| M6.6 | not started | | |
| M6.7 | not started | | |
| M6.8 | not started | | |
| M6.9 | not started | | |
| M6.10 | not started | | |
| M6.11 | not started | | |
| M6.12 | not started | | |
| M7.1 | not started | | |
| M7.2 | not started | | |
| M7.3 | not started | | |
| M7.4 | not started | | |
| M7.5 | not started | | |
| M7.6 | not started | | |
| M8.1 | not started | | |
| M8.2 | not started | | |
| M8.3 | not started | | |
| M8.4 | not started | | |
| M9.1 | not started | | |
| M9.2 | not started | | |
| M9.3 | not started | | |
| M9.4 | not started | | |
| M10.1 | not started | | |
| M10.2 | not started | | |
| M10.3 | not started | | |
| M10.4 | not started | | |
| M10.5 | not started | | |
| M10.6 | not started | | |
| M10.7 | not started | | |
| M10.8 | not started | | |
| M10.9 | not started | | |
| M10.10 | not started | | |
