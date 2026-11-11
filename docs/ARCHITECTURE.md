# EAOS architecture

Where everything lives, what may depend on what, and how a check flows. **Before adding a file, find its place in
section 4.** This page is updated in the same change that moves anything (`docs/STANDARDS.md` §8).

## 1. The layout

Ten layers, each a folder of `eaos/`; inside a layer, one folder per job, each opening with a one-line docstring in its
`__init__.py` that says what lives there. Read a path as a sentence: `live/app/detect.py` is *live*: running the app,
*app*: starting it, *detect*: finding its stack. A layer's root holds only its entry points and what its folders share.

```
engineering-audit-os/
  eaos/                    the Python package (only __init__.py and __main__.py at its root)
    interfaces/            thin doors, all calling the same journeys: cli.py (the `eaos` command) with
                           command_groups.py, menu.py (`/eaos` alone), govern.py with govern_words.py (the governance
                           core the terminal and MCP share), runs.py (the run engine wired to the MCP tools), rules.py
                           (the person's own rules through every door: the terminal, MCP and a card's note)
      terminal/            the terminal's governance commands, its branch commands and `eaos rules`
      mcp_server/          `eaos mcp`: the server and its tools (fix, govern, the person's rules, the AI nodes as
                           jobs), person.py (what only the person decides)
    journeys/              the person's journeys: check.py, check_choices.py, handover.py, catalog.py,
                           sign_in_window.py (the person's sign-in to their app in a window, `eaos sign-in`)
      fix/                 fixing in batches: selection, execute (the sandbox and the gates), lanes, regenerate, finish,
                           the context batch and the moves; waves/ a batch fixed at once and handed over as a branch
                           (split: also one branch per kind of fix)
      runs/                the headless run engine: the queue of runs, their turns, answers, previews, outcomes and
                           handoffs (`Actions`)
      branches/            branch control: the inventory, merging, deleting, the remotes, the guards
      agent_tools/         what an assistant does EAOS with (the tools behind MCP)
      guided/              the guided way in: `eaos start`, `next`, `status`, `doctor`, `clean`
    pipeline/              the check: stages.py and loops.py (declared as data), path_choice, run, stage_run, schedule,
                           rounds, coverage, remedies (what EAOS does about a stage that did not run)
      runners/             each stage's runner: by_rules, by_assistant, pages, live_app, sign_in, rules
    report/                what people read: views.py (every view agrees with the ledger)
      documents/           START-HERE, the four reports, RUN.md, the layers for people
      records/             the records of a check the fix, decision, history and AI-node commands read
    ai/                    the person's assistant: ask.py (answers from the records), rule_guard.py (a rule's guard
                           written once)
      assistant/           its adapters (Claude Code, Codex), headless runs and events, readiness, prompts, setup,
                           tiers.py (the model each stage asks)
      nodes/               the AI nodes of the pipeline, declared as data, on framework.py (triage, plan orderer, fix
                           reviewer); evidence.py (what a node may cite)
    analysis/              judging by rules (nothing at the root but __init__.py)
      understanding/       what the program is: features, aspects, measurements, the dossier, the owner's intake and
                           engagement, the project's extension guide
      claims/              one ledger of everything asserted: claims from facts, records, layers, the repository, real
                           data, old engines, one source per pattern and the person's rules; probes, correlation
      assessments/         ready judgements per kind of finding: dead code, dependencies, mechanical, policy, weaknesses,
                           real data in the code, old engines and code never run, one source per pattern (near copies,
                           ways of working)
      layers/              the whole system in layers: placement, boundaries, browser, endpoints, guards, data,
                           the rules split, operations
      maps/                the maps of the code: the code map (hotspots, import clusters), what a change touches
                           (impact), and which paths are tests
      target_state/        where the project should be: references, projection, the declared policy
      planning/            the plan: cards, order, documents, the roadmap, ranking
      rules/               the person's own rules: each one's machine guard (a pattern proved on its examples, a test of
                           the project's own, EAOS's detectors, or none, said), held on a whole check and on a change
                           (only what it brought), the diff-scoped check over the import graph, and the context block
                           and commit hook written from the one registry
      repair/              how a card is fixed and proven: remediation, codemods, the move tool and its gate, the
                           context trim, gates (one_source_gate: no change adds a copy), finish line, acceptance, review
    live/                  the app running in its isolated copy: agent.py (the one browser agent)
      isolation/           the sandbox: run only with consent, without secrets, seeing its own disk
      app/                 starting the app: detect its stack (detect.py JavaScript, detect_python.py, detect_php.py),
                           set it up, run it; page_server.py (a production build that serves only its pages)
      access/              signing in: the session, test accounts and users, each kind of user's views
      behavior/            the behaviour lock: specs written before any change, each pass read, intended changes
      screens/             finding and picturing the screens, and judging them
      testing/             the project's own tests: what they touch and how healthy they are
    facts/                 deterministic reading: run.py, store.py, source.py, scope.py, discovery.py, misread.py,
                           engine_findings.py (the engines' findings as facts)
      code/                symbols, structure, imports resolved, the graph and its queries, flows, entry points,
                           history, configuration
      frameworks/          one detector per framework: entry points, routes, navigation, data access
      dead_code/           what no user can reach and nothing reads, and the registries that keep a name alive
      duplication/         fingerprints, the patterns repeated, redundant work
      repository/          the repository as an engineer and an assistant read it: its layout and its assistants' context
      runtime/             services, configuration files, how each file bounds its load
      domain/              constants, data models, rules and module state
      defects/             broken code, leftover files, committed credentials
    engines/               one adapter per external analyzer, named after its tool, in security/ and code/, beside
                           what they share at the root (contract, tool, process, run, sarif); the registry is
                           eaos/data/toolchain.json
    core/                  what every layer reads; it imports nothing of EAOS
      project/             a project's records: places, state, runs, ledger, jobs, branches, workspace, repo context, and
                           rules.py (the person's own rules: their words, scope, history, breaks; one per project)
      contracts/           artifacts, documents, decisions, check paths, the card kinds and their areas
                           (card_areas.py), the code laws, the owner's share, untrusted text
      language/            the words in both languages, plain words, a person's intents, the language check
      system/              processes, resources, files (the one JSON reader and the one home of reading TOML), the
                           clock (the time now, written once), the web, a local database, the version, usage, launching
                           a durable process
      toolchain/           every external tool at its pinned version, and the catalog the assistant adds to
      progress/            the progress of every long piece of work
    data/ rules/ templates/   contracts, words, catalogs; engine rules; scripts the app runs
  tests/                   the unittest suite, one folder per layer it proves (guards/ for the whole), fixtures/,
                           contracts/ (engines' pinned outputs), and the two helpers every test shares
  tools/                   developer tools: quality (every code law) with code_limits, golden_trial with
                           detection_baseline, corpus, metrics, validate, dev_setup and dev_paths, platform_assets,
                           upstream_check; the proofs with the real assistant (fix, tidy, rules); judging/ (the
                           precision of detectors); the contracts' makers (make_contracts, contracts_ai,
                           contract_shapes), the progress checks; public_contract/ (the lock on what the CLI and MCP
                           promise, what reads them and the mutations that prove it)
  upstreams/               the licences of the pinned external tools (THIRD_PARTY_NOTICES.md)
  docs/                    this page and the other references
```

A folder is never named after what EAOS skips or calls a build output in a project it reads (`build`, `dist`,
`target`, `out`, `bin`, `vendor`, `coverage`: `core/project/workspace.py` `SKIP_DIRS`, `facts/defects/leftovers.py`
`BUILD_DIRS`), or EAOS would not read it, or would call it a leftover.


## 2. The layers and the dependency rule

**A layer imports only the layers under it**, directly or not, in one order (enforced by `import-linter`'s layers
contract in `pyproject.toml`, run by `tools/quality.sh`, with no exception):

`interfaces → journeys → pipeline → report → ai → analysis → live → (facts → engines) → core`

- `core` imports nothing of EAOS; `engines` only `core`; `facts` reads the engines' findings.
- `analysis` judges by rules what the facts and the app's run gave; `ai` sits above it because the assistant judges
  the rules' findings (the triage) and their verdicts come back as data.
- `report` renders the analysis and the assistant's verdicts; it computes nothing of its own.
- `pipeline` runs the stages, `journeys` combine the pipeline with the person's steps, `interfaces` stay thin.
- The order is one line, not groups of peers: reports read the analysis and the assistant reads both.

## 3. The pipeline as loops

Stages stay declared as data (`eaos/features/check/journey/stages.py`: what each needs, produces, reads). Each stage belongs to a
loop; a loop runs until its exit condition holds or its rounds are spent, then acts as declared. Reordering the
pipeline, or turning a step into a loop, is a change of data, never of code.

```python
Loop(name, stages, needs=(...), max_rounds=N, on_fail='explain' | 'escalate' | 'stop', switch='<check path>')
```

`eaos/features/check/journey/loops.py` is the declaration: every stage of `stages.py` in one loop, the stages' order the loops'
order. A loop's exit: `met` (every stage ok or absent with its reason), `explained` (a stage of `needs` absent with its
reason) or `not_met` (a stage broke). Not met, it runs its broken stages again while its rounds last
(`pipeline/rounds.py`), hiding what it broke from the other loops until then; then `explain`, `escalate` or `stop`.
A loop with a `switch` runs only when the check follows that path (alone or beside `complete`). The loops, by the
stages' real dependencies:

| Loop (`loops.py`) | Stages | needs, rounds, on_fail |
|---|---|---|
| understand | facts, features, roles, intake, engines, policy, rules | facts; 1; stop |
| run_and_see | setup, verify, session, crawl, lock, record, journeys, screens, layers | setup, screens; 2; explain |
| judge | measure, architecture, claims, probe, plan, triage, cards | claims, triage; 1; explain |
| plan | order, steps | steps; 1; explain |
| hand_over | reports, translate | reports; 1; escalate |

The fix journey follows the check: batches of up to ten cards (`journeys/fix/selection.py`), each card fixed or left
with its reason, every batch handed over as a branch that waits for the owner's decision (`journeys/fix/waves/`).

Every loop writes its part of the **coverage ledger** (`pipeline/coverage.py`, `coverage` in the checkpoint and the
manifest): what it covered, what it could not, and why; a big gap (a stage broke, or one its goal stands on is absent
for a reason the person did not choose) shows in red at the top of START-HERE.md and RUN.md.

## 4. Where a new file goes

Which files to read and touch, in order, for each kind of addition: `docs/EXTENDING.md`.

| It is… | It goes in |
|---|---|
| any new module | the folder whose `__init__.py` docstring names its job (section 1); none fits: a new folder with its one-line docstring, once it holds two modules or more |
| something every layer reads (a contract, a path, a word, the store) | `core/` (`project/`, `contracts/`, `language/`, `system/`, `toolchain/`, `progress/`): it imports nothing of EAOS |
| a read of an http(s) address | `core/system/web.py` `opened`: http and https only (urllib also opens `file://`) |
| a rule that reads source and produces facts | `facts/<its folder>` (`code/`, `dead_code/`, `duplication/`, `repository/`, `runtime/`, `domain/`, `defects/`); a framework's detector in `facts/frameworks/` |
| a rule of the system's layers (a boundary, an endpoint's guard, a data rule, what ships to the browser) | `analysis/layers/`: its sentence, boundary, severity and fix in `catalog.py`, its check in the module of its boundary; findings become cards through `analysis/claims/from_layers.py` |
| an adapter for an external tool | `engines/<kind>/<name>.py` (`security/`, `code/`) + its entry in `eaos/data/toolchain.json` (`check: engines`); a library with no command (Presidio) is run by EAOS's own script in `templates/<tool>/` with its environment's Python (`install.library`) |
| old engines still wired in | the switches: `rules/ast-grep/rules/flags.yml`; what ran of the project while EAOS ran its tests, its server and its pages: `live/testing/ran.py` (`live/ran-*.json`); sorted in `analysis/assessments/old_engines.py` and `never_run.py`, the cards in `analysis/claims/from_old_engines.py` (made beside the runtime claims, since they read what ran) |
| real data written in the code | the values: Presidio's script `templates/presidio/scan.py` and its words `rules/personal-data.json`; the tables: `rules/ast-grep/rules/data-tables.yml`; sorted on evidence in `analysis/assessments/real_data.py`, its cards in `analysis/claims/from_real_data.py` |
| running the app, signing in, finding screens | `live/`: how a stack starts in `live/app/detect.py` (JavaScript, static sites), `live/app/detect_python.py` or `live/app/detect_php.py`; the test account by rules in `live/access/test_account.py`; `live/screens/` for the crawl, the audit and the pages files name (`file_routes.py`) |
| driving the browser for a goal, recording, replaying | `live/agent.py` with `templates/screens/agent.mjs` (the one browser-agent layer): the assistant is passed in, never imported |
| judging findings by rules, cards, plan | `analysis/<its folder>`: a claim in `claims/`, a ready judgement in `assessments/`, the plan in `planning/`, how a card is fixed in `repair/` |
| a card's area and severity | `core/contracts/card_areas.py` (`PATTERNS`, `classify`); its kind in `core/contracts/card_kinds.py` |
| judging findings with an assistant (the triage, the fix review) | `ai/nodes/`; what a node may cite in `ai/nodes/evidence.py`; `analysis/` takes its verdicts as data |
| which model a stage asks (the light, standard and deep tiers) | `ai/assistant/tiers.py` (each stage's tier as data, the escalation rule, each assistant's model or effort); `ai/nodes/runner.py` asks again higher |
| anything that calls an assistant | `ai/` |
| what people read (START-HERE, the four reports, RUN.md) | `report/documents/` |
| a stage or loop declaration | `pipeline/stages.py` and `pipeline/loops.py`; its runner in `pipeline/runners/` |
| a journey's steps (check, fix batches) | `journeys/` (`fix/` with `fix/waves/`, `guided/` the terminal's way in, `agent_tools/` what MCP calls, `runs/` the run queue, `branches/` branch control; a check at its root) |
| a CLI command or MCP tool | `interfaces/`: thin, calling a journey |
| the person's own rules | the record in `core/project/rules.py`; a kind of guard in `analysis/rules/guards.py`, where it is held in `analysis/rules/held.py`; every door through `interfaces/rules.py`; the card in `analysis/claims/from_rules.py`, made last in the ledger (a detector's guard reads the other claims) |
| a word naming a concept (a stage, a path, a kind of problem) | `eaos/data/words.json`, every form beside the others; the engine reads it through `core/language/words.py` |
| a sentence composed with values | beside the code that composes it, Arabic and English together |
| a test | `tests/<layer>/test_<what it proves>.py`, beside the tests of the layer it proves (a guard of the whole in `tests/guards/`), one test per real behaviour |
| a developer tool | `tools/` |
| scratch of a task | a folder outside the repository, removed when the task ends: never in the repository |

## 5. Check paths

| Path | What runs |
|---|---|
| Full check | every loop; the saved journeys replayed without AI after the lock's run (`record`), each a row of behavior-lock/results.json |
| A focused path (code, security, look, speed) | only the stages it needs (`core/contracts/check_paths.py`); the person's own rules (the `rules` stage and their cards, `check_paths.HELD`) on every path |
| What changed (`eaos check --changed`) | no loop: the files a change touches and those importing them, each rule's guard on what the change brought and the code laws' gates over them, in seconds and without AI; the commit hook runs it on the staged files, the pinned rules alone refusing |

## 6. Outputs (what a check leaves)

- `~/EAOS/<project>/` (`core/project/places.py`; `EAOS_OUTPUT` moves it): `README.md` (what each part is),
  `HANDOVER.md`, `fixes/`, `logs/`, and `technical/`: `START-HERE.md`, the four reports (`CURRENT-STATE.md`,
  `TARGET-STATE.md`, `GAP-AND-STRATEGY.md`, `EXECUTION-PLAN.md`), `RUN.md` and the index `README.md`, plus `PLAN/`
  (STEPS, WAVES, one TASK card each), which assistants read when fixing cards. The contract of each:
  `core/contracts/artifacts.py`.
- `technical/layers.json`: the system in layers, what START-HERE's layers section reads; its findings are also the
  `boundaries` fact set the claims make cards of.
- `technical/`: records later stages read. Caches never live here. A run removes the documents a check no longer
  writes (`eaos/features/check/journey/run.py` RETIRED).
- `runtime/` in the project's folder of EAOS's home (`~/.eaos/projects/<project>-<id>/`): working copies, caches, batch
  copies, bounded by a retention rule.

### Evidence and runtime boundaries

Unsupported claims are set aside with reasons rather than aborting the dossier. Import-chain claims retain the external
fact that supports them. Layer placement reads generated multi-runtime bindings through `analysis/layers/runtime_guards.py`:
only a parsed positive Node branch with all runtime flags validated is excluded from Node text evidence. Static imports
and other Node text remain evidence. The fix handover reads large lock-version moves through `core/project/jumps.py`.
