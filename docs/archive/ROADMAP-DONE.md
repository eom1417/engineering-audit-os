# EAOS roadmap: the done cards

The cards of `ROADMAP.md` once done, each with what it delivered, moved here so the plan holds only what is left.
Not read at the start of a session; why and how each version changed: `CHANGELOG.md`.

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
| M5.1 | done: `live/setup_python.py` starts Django, Flask, FastAPI and Streamlit from their files (install, migrations or `init-db`, start, the names the code reads); Expo on the run's port; a static site built and served by Python's server; a site of pages alone is a project; Redis, mail and database values a client can parse; a version check on a loaded host never "not installed"; SvelteKit's empty code block no longer breaks the facts. The corpus' 12 apps all run (4 before) | 0.0.77 | 2026-10-25 |
| M5.2 | done: screens in layers: the pages framework files make (`live/screens/file_routes.py`: Next, Nuxt, SvelteKit, Astro, Vue Router, Expo Router, Streamlit, Django's URL configuration), the code's hash routes and menus at their `/#/` address, a server's GET routes (Flask's own list), kept only when they answer with a page; a page the code names is its own template; never a page that signs out. Then the browser agent (`live/agent.py` + `templates/screens/agent.mjs`): the assistant's smallest model drives towards a goal, each step with its picture, saved in the runtime and replayed with no assistant (a trial: Claude reached 3 screens behind buttons, the replay reached them again alone). Open-source agents not adoptable (`docs/DECISIONS.md`). Corpus: 12 of 12 picture their expected screens (2 before) | 0.0.77 | 2026-10-25 |
| M5.3 | done: a test account by rules (`live/test_account.py`, `templates/setup/sign-up.cjs`: the app's own sign-in, after its sign-up; Django's account by its own command) before any assistant (the corpus' sign-in app signed in alone); the question to the person says what EAOS tried; the sign-in and sign-up pages pictured as a visitor too; the behaviour lock and the walk-through run as each kind of user over its own pages (`lock_folder.lend_kinds`, results keyed by kind; a trial: the administrator's page recorded with the administrator's session) | 0.0.77 | 2026-10-25 |

| M6.0 | done: `tests/fixtures/baseline-app` gained the nine boundary defects (16 planted problems), `tests/fixtures/baseline-clean` its clean twin; three corpus apps of the stacks the layers matter for (insights-lm: React + Vite + Supabase with migrations and edge functions; task-api: Express + SQLite + `openapi.json`; next-dashboard: Next.js with API routes and server actions). Before M6: 6 of 16 found, none of the ten boundary ones; no layer finding existed on the twin (7 cards of other kinds) | 0.0.78 | 2026-10-25 |
| M6.1 | done: `analysis/layers/placement.py`: each file in a layer of its reference type by its path, else by what it imports into the layer of that role its imports keep (each layer of `reference-architectures.json` has a `role`), with its reason and confidence; a file in none is a listed gap; its side (browser, server, shared, database, test, build); the map and the target projection place by the same path rule (`reference_architecture.layer_of`) | 0.0.78 | 2026-10-25 |
| M6.2 | done: `analysis/layers/boundaries.py`: every import into a layer its layer may not use is a card at its line (a low-confidence placement a question); the project's own policy stays the policy stage's; dependency-cruiser gets the same rules plus browser-to-server reachability; the fix gate refuses a change that breaks a boundary (`journeys/execute.py`). import-linter and go-arch-lint not added (DECISIONS) | 0.0.78 | 2026-10-25 |
| M6.3 | done: `analysis/layers/browser.py`: secret-named settings shipped, privileged keys in browser code and built output (the project's, and the production build of the isolated copy in the `layers` option), source maps shipped, server code imported by browser code, a database driver or SQL in a screen | 0.0.78 | 2026-10-25 |
| M6.4 | done: `analysis/layers/endpoints.py` + `guards.py`: the endpoint table (method, route, handler, sign-in, ownership, input check, data, write) for Next.js routes and server actions, Express-like, node:http, FastAPI, Flask, Django and Supabase edge functions (`facts/frameworks/server_entries.py`); a write with no sign-in, a row by its id with no owner check, a read of guarded data with no guard are cards; an unknown middleware a question | 0.0.78 | 2026-10-25 |
| M6.5 | done: `analysis/layers/data.py`: no row-level security, a write policy open to everyone (moved from the hidden access gaps), security with no policy, a security-definer function or view the public may run, a public bucket anyone may list; readers and writers of each table, with their side | 0.0.78 | 2026-10-25 |
| M6.6 | done: `live/data_trial.py` in the `layers` option: the migrations applied to the run's own PostgreSQL over stand-ins of Supabase's schemas, the Supabase CLI's security advisors (pinned 2.122.0) and pgTAP (pinned 1.3.4) tests per table as no one and as another user; on the planted app the two planted policies fail, on its twin every test passes | 0.0.78 | 2026-10-25 |
| M6.7 | done: `live/api_trial.py`: Schemathesis (pinned 4.32.4, seed 1, 240 s) over the project's OpenAPI or one derived from the endpoint table, two test accounts as peers; on a trial app with sign-up it found another user's object, a sign-in ignored and bad input accepted, each with its request and response | 0.0.78 | 2026-10-25 |
| M6.8 | done: `analysis/layers/rules_split.py`: a number's limits a screen checks before a write that its endpoint (or the table's check constraints) does not; a money value a screen computes and sends to be saved | 0.0.78 | 2026-10-25 |
| M6.9 | done: `analysis/layers/operations.py`: each missing item of the reference's infrastructure baseline, read by `target_projection.infrastructure`, is a finding naming the item, shown in the layers (the target's infrastructure rows plan it: no second card) | 0.0.78 | 2026-10-25 |
| M6.10 | done: the project's runners found (Vitest, Jest, Mocha, Node, Playwright, Cypress, AVA, pytest, Go), the layers no test reaches, every write no test names (route or handler), and the project's own tests failing when the check ran them (`verification.json`) | 0.0.78 | 2026-10-25 |
| M6.11 | done: START-HERE.md and REPORT.html open the layers with the broken critical boundaries in red; the Studio's page "The system in layers" (`studio/layers.json`, S-36); each card names its boundary and the reference's fix (its render params, which M7.4's judge reads) | 0.0.78 | 2026-10-25 |
| M6.12 | done: the golden trial finds 15 of the 16 planted problems (6 before M6; the sign-in still missed) and nothing on the clean twin (0 layer findings on 10 files, 10 endpoints, 2 tables); the three corpus apps of M6.0 judged by hand: 37 layer findings, 2 false (5%: task-api's /triage said to write); the static part reads EAOS's 572 files in 6 s; the live part is the option "Try the layers" (up to 15 minutes, said before it starts; 10 s on the planted app, 4 min with Schemathesis on the notes trial app); the corpus 13 of 15 (the 12 before all pass; task-api needs real Supabase keys and its fixed port, next-dashboard a Postgres with its tables: both an assistant's to set up); `docs/METRICS.md` measured | 0.0.78 | 2026-10-25 |
## M5 cards as planned (done, 0.0.77)

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

## M6 cards as planned (done, 0.0.78)

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
