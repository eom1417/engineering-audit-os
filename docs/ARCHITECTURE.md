# EAOS architecture

Where everything lives, what may depend on what, and how a check flows. **Before adding a file, find its place in
section 4.** Sections 1-2 are the layout and its rule (M3.1); section 3 is the target of M4 (`ROADMAP.md`); this page
is updated in the same change that moves anything.

## 1. The layout

Ten layers, each a folder of `eaos/`; inside a layer, one folder per job, each opening with a one-line docstring in its
`__init__.py` that says what lives there. Read a path as a sentence: `live/app/detect.py` is *live*: running the app,
*app*: starting it, *detect*: finding its stack. A layer's root holds only its entry points and what its folders share.

```
engineering-audit-os/
  eaos/                    the Python package (only __init__.py and __main__.py at its root)
    interfaces/            thin doors, all calling the same journeys: cli.py (the `eaos` command), menu.py (`/eaos` alone),
                           govern.py with govern_words.py (the governance core the terminal, MCP and the Studio share)
      terminal/            the terminal's governance commands and its branch commands
      mcp_server/          `eaos mcp`: the server and its tools (build, fix, govern, the AI nodes as jobs)
      studio_server/       the Studio's local server: the guard, the read API, the live stream, the built Studio
      studio_actions/      the Studio's actions (docs/studio-actions.json): runs, chat, lanes; branches/ its branch control
    journeys/              the person's journeys: check.py, check_choices.py, extend.py, handover.py, catalog.py
      fix/                 fixing in batches: selection, execute (the sandbox and the gates), lanes, regenerate, finish;
                           waves/ a batch fixed at once and handed over as a branch
      build_from_plan/     build from a plan: the blueprint, the assistant's steps, the checks and the look
      agent_tools/         what an assistant does EAOS with (the tools behind MCP)
      guided/              the guided way in: `eaos start`, `next`, `status`, `doctor`, `clean`
    pipeline/              the check: stages.py and loops.py (declared as data), path_choice, run, stage_run, schedule,
                           rounds, coverage, estimate, remedies (what EAOS does about a stage that did not run)
      runners/             each stage's runner: by_rules, by_assistant, pages, live_app, sign_in, layers_live
    report/                what people read: views.py (every view agrees with the ledger)
      documents/           START-HERE, the four reports, RUN.md, the layers for people
      target_architecture/ TARGET-ARCHITECTURE: the picture, its decisions, gaps, reconciliation, ADRs
      blueprint/           the blueprint of a project built from its plan: design, spec, view
      human_report/        REPORT.html, one self-contained page in both languages
      studio/              the data the Studio reads; user_journeys/ (the app's screens and the links between them),
                           paths/ (the code paths through their layers)
    ai/                    the person's assistant: ask.py (answers from the records), semantic.py (the model's layer)
      assistant/           its adapters (Claude Code, Codex), headless runs and events, readiness, prompts, setup
      ideal/               the ideal, planned with a model on top of the rules
      nodes/               the AI nodes of the pipeline, declared as data, on framework.py (triage, plan orderer, ...)
    analysis/              judging by rules (nothing at the root but __init__.py)
      understanding/       what the program is: features, aspects, measurements, the dossier, the owner's intake and
                           engagement, the bounded source the model reads
      claims/              one ledger of everything asserted: claims from facts, records and layers, probes, correlation
      assessments/         ready judgements per kind of finding: dead code, dependencies, mechanical, policy, weaknesses,
                           the debt register
      layers/              the whole system in layers (M6): placement, boundaries, browser, endpoints, guards, data,
                           the rules split, operations
      maps/                the maps people read: architecture, system, pipeline, C4, impact, and their layout
      target_state/        where the project should be: references, projection, repair or rebuild, transform,
                           sustainability, the declared policy, the look
      readiness/           production readiness and the load model
      planning/            the plan: cards, order, documents, the plan the person brings, the roadmap, ranking
      repair/              how a card is fixed and proven: remediation, codemods, gates, finish line, acceptance, review
      presentation/        the one model of a report and the counts every view shows
    live/                  the app running in its isolated copy: agent.py (the one browser agent)
      isolation/           the sandbox: run only with consent, without secrets, seeing its own disk
      app/                 starting the app: detect its stack (detect.py JavaScript, detect_python.py), set it up, run it
      access/              signing in: the session, test accounts and users, each kind of user's views
      behavior/            the behaviour lock: specs written before any change, each pass read
      screens/             finding and picturing the screens, and judging them
      trials/              trials on the running app: its API, its data rules, its load
      testing/             the project's own tests: what they touch and how healthy they are
    facts/                 deterministic reading: run.py, store.py, source.py, scope.py, discovery.py,
                           engine_findings.py (the engines' findings as facts)
      code/                symbols, structure, imports resolved, the graph and its queries, flows, entry points,
                           history, configuration
      frameworks/          one detector per framework: entry points, routes, navigation, data access
      declared_pipelines/  pipelines a project declares (its Python code and frameworks, LangGraph, build files, queues)
      dead_code/           what no user can reach and nothing reads, and the registries that keep a name alive
      duplication/         fingerprints, repeated sequences, redundant work
      runtime/             services, configuration files, how each file bounds its load
      domain/              constants, data models, rules and module state
      defects/             broken code, leftover files, committed credentials
    engines/               one adapter per external analyzer, named after its tool, flat by design, beside what they
                           share (contract, tool, process, sarif, openapi); the registry is eaos/data/toolchain.json
    core/                  what every layer reads; it imports nothing of EAOS
      project/             a project's records: places, state, runs, ledger, jobs, branches, workspace, repo context
      contracts/           artifacts, documents, decisions, check paths, the code laws, the owner's share
      language/            the words in both languages, plain words, a person's intents, the language check
      system/              processes, resources, the web, a local database, the version, usage, the Studio's launch
                           and who may talk to it
      toolchain/           every external tool at its pinned version, and the catalog the assistant adds to
      progress/            the progress of every long piece of work
    data/ rules/ templates/   contracts, words, catalogs, the built Studio; engine rules; scripts the app runs
  console/                 the Studio UI (JS, esbuild; built into eaos/data/studio)
  tests/                   the unittest suite, one folder per layer it proves (guards/ for the whole), fixtures/,
                           contracts/ (engines' pinned outputs), and the two helpers every test shares
  tools/                   developer tools: quality (every code law) with code_limits, golden_trial with
                           detection_baseline, corpus, metrics, validate, dev_setup and dev_paths, the contracts'
                           makers (make_contracts, contracts_*), the Studio's synthetic data, upstream_check
  upstreams/               the licences of the pinned external tools
  docs/                    this page and the other references; archive/ the done history
```

A folder is never named after what EAOS skips or calls a build output in a project it reads (`build`, `dist`,
`target`, `out`, `bin`, `vendor`, `coverage`: `core/project/workspace.py` `SKIP_DIRS`, `facts/defects/leftovers.py`
`BUILD_DIRS`), or EAOS would not read it, or would call it a leftover.


## 2. The layers and the dependency rule

**A layer imports only the layers under it**, directly or not, in one order (enforced by `import-linter`'s layers
contract in `pyproject.toml`, run by `tools/quality.sh`; since M3.1 with no exception):

`interfaces → journeys → pipeline → report → ai → analysis → live → (facts → engines) → core`

- `core` imports nothing of EAOS; `engines` only `core`; `facts` reads the engines' findings.
- `analysis` judges by rules what the facts and the app's run gave; `ai` sits above it because the assistant judges
  the rules' findings (triage, the strict judge of M7.4) and their verdicts come back as data.
- `report` renders the analysis and the assistant's verdicts; it computes nothing of its own.
- `pipeline` runs the stages, `journeys` combine the pipeline with the person's steps, `interfaces` stay thin.
- The order was one line, not groups of peers (the plan of M-1): on today's code reports read the analysis and the
  assistant reads both, so groups that never import each other would have needed a rewrite, where one order needed
  five moves of code (M3.1).

## 3. The pipeline as loops (M4)

Stages stay declared as data (`eaos/pipeline/stages.py`: what each needs, produces, reads). Each stage belongs to a
loop; a loop runs until its exit condition holds or its rounds are spent, then acts as declared. Reordering the
pipeline, or turning a step into a loop, is a change of data, never of code.

```python
Loop(name, stages, needs=(...), max_rounds=N, on_fail='explain' | 'escalate' | 'stop', switch='<check path>')
```

`eaos/pipeline/loops.py` is the declaration (M4.1): every stage of `stages.py` in one loop, the stages' order the loops'
order. A loop's exit: `met` (every stage ok or absent with its reason), `explained` (a stage of `needs` absent with its
reason) or `not_met` (a stage broke). Not met, it runs its broken stages again while its rounds last
(`pipeline/rounds.py`), hiding what it broke from the other loops until then; then `explain`, `escalate` or `stop`.
A loop with a `switch` runs only when the check follows that path (alone or beside `complete`). Today's loops, by the
stages' real dependencies:

| Loop (`loops.py`) | Stages | needs, rounds, on_fail |
|---|---|---|
| understand | facts, features, roles, intake, engines, policy | facts; 1; stop |
| run_and_see | setup, verify, session, crawl, lock, record, journeys, screens, baseline, layers | setup, screens; 2; explain |
| try_layers (switch `layers`) | layers_trial | layers_trial; 1; explain |
| judge | measure, architecture, load, readiness, claims, probe, sustainability, transform, semantic, plan, target, proposals, triage, visual, cards | claims, triage; 1; explain |
| envision | ideal, pipeline_gaps, reconcile (the repair-or-rebuild decision: `analysis/target_state/repair_or_rebuild.py`) | ideal, reconcile; 1; explain |
| plan | order, steps | steps; 1; explain |
| hand_over | reports, translate | reports; 1; escalate |

The target loops of the North Star, which these grow into:

| Loop | Stages (today's names) | Exit condition |
|---|---|---|
| L1 Understand | facts, features, intake, policy, engines | facts complete; coverage ledger written |
| L2 Run and see | setup, session, crawl, screens, journeys, lock, record | expected screens pictured, or the AI explorer tried, or a failure explained |
| L2b Try as a user (optional, M10) | replay of saved journeys (always); scenario, data, actors, tickets (short or full simulation) | replays green or their breaks shown; each persona reached its goals or its difficulties recorded with evidence |
| L3 Judge | claims, probe, triage, weaknesses, visual, the simulation's difficulties | every finding confirmed / needs validation / rejected, with evidence |
| L4 Envision | semantic, ideal, target, reconcile, estimate | ideal picture; repair-or-rebuild decision with its estimate |
| L5 Plan | plan, order, cards, steps | every card has an acceptance check and a place in the order |
| L6 Fix | fix batches (~15 cards) | every card fixed, or left with its reason |
| L7 Hand over | handover, report | one clear report; a branch waiting for the owner's decision |

Every loop writes its part of the **coverage ledger** (`pipeline/coverage.py`, `coverage` in the checkpoint and the
manifest): what it covered, what it could not, and why; a big gap (a stage broke, or one its goal stands on is absent
for a reason the person did not choose) shows in red at the top of START-HERE.md and RUN.md.

## 4. Where a new file goes

| It is… | It goes in |
|---|---|
| any new module | the folder whose `__init__.py` docstring names its job (section 1); none fits: a new folder with its one-line docstring, once it holds two modules or more |
| something every layer reads (a contract, a path, a word, the store) | `core/` (`project/`, `contracts/`, `language/`, `system/`, `toolchain/`, `progress/`): it imports nothing of EAOS |
| a read of an http(s) address | `core/system/web.py` `opened`: http and https only (urllib also opens `file://`) |
| a rule that reads source and produces facts | `facts/<its folder>` (`code/`, `pipelines/`, `deadcode/`, `duplication/`, `runtime/`, `domain/`, `defects/`); a framework's detector in `facts/frameworks/` |
| a rule of the system's layers (a boundary, an endpoint's guard, a data rule, what ships to the browser) | `analysis/layers/`: its sentence, boundary, severity and fix in `catalog.py`, its check in the module of its boundary; findings become cards through `analysis/claims/from_layers.py` |
| trying a layer on the running app or a database of the run's own | `live/trials/data.py` (migrations, Supabase advisors, pgTAP), `live/trials/api.py` (Schemathesis); the stage that joins them is `pipeline/runners/layers_live.py` |
| an adapter for an external tool | `engines/<name>.py` + its entry in `eaos/data/toolchain.json` (`check: engines`) |
| running the app, signing in, finding screens | `live/`: how a stack starts in `live/app/detect.py` (JavaScript, static sites) or `live/app/detect_python.py`; the test account by rules in `live/access/test_account.py`; `live/screens/` for the crawl, the audit and the pages files name (`file_routes.py`) |
| driving the browser for a goal, recording, replaying | `live/agent.py` with `templates/screens/agent.mjs` (the one browser-agent layer, M5.2): the assistant is passed in, never imported |
| judging findings by rules, cards, plan, estimates | `analysis/<its folder>`: a claim in `claims/`, a ready judgement in `assessments/`, the plan in `planning/`, how a card is fixed in `repair/` |
| judging findings with an assistant (triage, the strict judge of M7.4) | `ai/` (`ai/nodes/`); `analysis/` takes its verdicts as data |
| anything that calls an assistant | `ai/` |
| a simulated user: scenario, personas, data, actors, tickets | `ai/` (M10); its replays run from `live/` |
| what people read (REPORT.html, the few documents, the Studio's data) | `report/` (`report/studio/`) |
| a stage or loop declaration | `pipeline/stages.py` and `pipeline/loops.py`; its runner in `pipeline/runners/` |
| a journey's steps (check, fix batches, build, extend) | `journeys/` (`fix/` with `fix/waves/`, `build_from_plan/`, `guided/` the terminal's way in, `agent_tools/` what MCP calls; a check and an extension at its root) |
| a CLI command, MCP tool, API route or Studio action | `interfaces/`: thin, calling a journey |
| a word naming a concept (a stage, a path, a kind of problem) | `eaos/data/words.json`, every form beside the others; the engine reads it through `core/language/words.py`, the Studio's build makes its keys from it |
| a sentence composed with values | beside the code that composes it, Arabic and English together |
| a Studio screen | `console/src/places/<place>/` (only core places; see `ROADMAP.md` M8) |
| a test | `tests/<layer>/test_<what it proves>.py`, beside the tests of the layer it proves (a guard of the whole in `tests/guards/`), one test per real behaviour |
| a developer tool | `tools/` |
| scratch of a task | `/workspace/eaos-work/<task>/`, removed when the task ends: never in the repository |
| the done cards of the roadmap, the reasoning of done milestones | `docs/archive/`: not read at the start of a session |

## 5. Check paths

| Path | What runs |
|---|---|
| Full check | every loop; L2b replays the saved journeys without AI; the short simulation only when chosen in the check's preview, which shows its time and cost |
| A focused path (look, security, …) | only the loops it needs |
| Try the layers (`layers`, beside `complete` an option of the full check) | L1-L2 as far as needed to run the app, then try_layers: the production build read, the migrations tried per table with pgTAP and the Supabase advisors, the API tried by Schemathesis with two test accounts (up to 15 minutes, said before it starts) |
| Try the experience (M10) | L1 and L2 as far as needed to run the app, then L2b's full simulation, L3 and the experience report |

## 6. Outputs (what a check leaves)

- `output/<project>/REPORT.html`: the one page people read; beside it eight documents: `START-HERE.md`, the four reports
  (`CURRENT-STATE.md`, `TARGET-STATE.md`, `GAP-AND-STRATEGY.md`, `EXECUTION-PLAN.md`), `TARGET-ARCHITECTURE.md`, `RUN.md`
  and the index `README.md`; plus `PLAN/` (STEPS, WAVES, one TASK card each) and `adr/`, which assistants read when
  fixing cards (M1.4: the other 19 Markdown renderings removed; their records stay).
- `technical/layers.json`: the system in layers (M6), what START-HERE's layers section, REPORT.html's and the Studio's
  `studio/layers.json` read; its findings are also the `boundaries` fact set the claims make cards of.
- `technical/`: records later stages and the Studio read. Caches never live here (M1.2). A run removes the documents
  a check no longer writes (`eaos/pipeline/run.py` RETIRED).
- `runtime/` in EAOS's home: working copies, caches, batch copies, bounded by a retention rule (M1.1).
