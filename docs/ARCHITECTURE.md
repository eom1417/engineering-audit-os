# EAOS architecture

Where everything lives, what may depend on what, and how a check flows. **Before adding a file, find its place in
section 4.** Sections 1-2 are the layout and its rule (M3.1); section 3 is the target of M4 (`ROADMAP.md`); this page
is updated in the same change that moves anything.

## 1. The layout (M3.1)

```
engineering-audit-os/
  eaos/            the Python package: ten layers, each a folder; only __init__.py and __main__.py at its root
    core/          what every layer reads: the run store (store.py), contracts, workspace and places, jobs, the ledger,
                   decisions, words (words.py), documents, processes (process.py), the tools registry (toolchain.py),
                   the Studio's launch and guard, progress/
    engines/       one adapter per external analyzer; the registry is eaos/data/toolchain.json
    facts/         deterministic extractors over one snapshot (syntax, structure, graph, flows, dead code, registries ...)
    live/          the app run in its sandbox, sign-in, test users, roles, the behaviour lock, load plans, the tests' run
                   (verify.py), screens/ (the crawl and the screen audit)
    analysis/      claims, correlation, weaknesses, the debt register, cards and plan, probes, the model of a report
                   (model.py), the pipeline map (pipeline_map.py), the target projection
    ai/            the assistants (Claude Code, Codex), their readiness and headless runs, prompts, the ideal picture,
                   nodes/ (triage, plan orderer, reviewers ...)
    report/        REPORT.html (human_report.py), START-HERE, the four reports, TARGET-ARCHITECTURE, RUN.md (run.py),
                   studio/ (the data the Studio reads)
    pipeline/      stages declared as data (stages.py), runners, schedule and estimate, check paths, run/resume
    journeys/      check and fix (agent_tools.py, guided.py, waves.py, execute.py, batches, hand-over), build, extend
    interfaces/    the CLI, MCP (mcp_server.py), api/ (the local server), studio/ (the Studio's actions)
    data/ rules/ templates/   contracts, words, catalogs, the built Studio; engine rules; scripts the app runs
  console/         the Studio UI (JS, esbuild; built into eaos/data/studio)
  tests/           unittest suite
  tools/           developer tools: quality (every code law), golden_trial with detection_baseline, corpus,
                   metrics, validate, code_limits, dev_setup
  upstreams/       the licences of the pinned external tools (the registry is eaos/data/toolchain.json)
  docs/            this page and the other references
```


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
| run_and_see | setup, verify, session, crawl, lock, record, journeys, screens, baseline | setup, screens; 2; explain |
| judge | measure, architecture, load, readiness, claims, probe, sustainability, transform, semantic, plan, target, proposals, triage, visual, cards | claims, triage; 1; explain |
| envision | ideal, pipeline_gaps, reconcile (the repair-or-rebuild decision: `analysis/repair_or_rebuild.py`) | ideal, reconcile; 1; explain |
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
| something every layer reads (a contract, a path, a word, the store) | `core/`: it imports nothing of EAOS |
| a read of an http(s) address | `core/web.py` `opened`: http and https only (urllib also opens `file://`) |
| a rule that reads source and produces facts | `facts/` |
| an adapter for an external tool | `engines/<name>.py` + its entry in `eaos/data/toolchain.json` (`check: engines`) |
| running the app, signing in, finding screens | `live/`: how a stack starts in `setup_detect.py` (JavaScript, static sites) or `setup_python.py`; the test account by rules in `test_account.py`; `live/screens/` for the crawl, the audit and the pages files name (`file_routes.py`) |
| driving the browser for a goal, recording, replaying | `live/agent.py` with `templates/screens/agent.mjs` (the one browser-agent layer, M5.2): the assistant is passed in, never imported |
| judging findings by rules, cards, plan, estimates | `analysis/` |
| judging findings with an assistant (triage, the strict judge of M7.4) | `ai/` (`ai/nodes/`); `analysis/` takes its verdicts as data |
| anything that calls an assistant | `ai/` |
| a simulated user: scenario, personas, data, actors, tickets | `ai/` (M10); its replays run from `live/` |
| what people read (REPORT.html, the few documents, the Studio's data) | `report/` (`report/studio/`) |
| a stage or loop declaration | `pipeline/stages.py` (M4: plus `pipeline/loops.py`) |
| a journey's steps (check, fix batches, build, extend) | `journeys/` |
| a CLI command, MCP tool, API route or Studio action | `interfaces/`: thin, calling a journey |
| a word naming a concept (a stage, a path, a kind of problem) | `eaos/data/words.json`, every form beside the others; the engine reads it through `core/words.py`, the Studio's build makes its keys from it |
| a sentence composed with values | beside the code that composes it, Arabic and English together |
| a Studio screen | `console/src/places/<place>/` (only core places; see `ROADMAP.md` M8) |
| a test | `tests/test_<module>.py`, one test per real behaviour |
| a developer tool | `tools/` |
| scratch of a task | `/workspace/eaos-work/<task>/`, removed when the task ends: never in the repository |
| the done cards of the roadmap, the reasoning of done milestones | `docs/archive/`: not read at the start of a session |

## 5. Check paths

| Path | What runs |
|---|---|
| Full check | every loop; L2b replays the saved journeys without AI; the short simulation only when chosen in the check's preview, which shows its time and cost |
| A focused path (look, security, …) | only the loops it needs |
| Try the experience (M10) | L1 and L2 as far as needed to run the app, then L2b's full simulation, L3 and the experience report |

## 6. Outputs (what a check leaves)

- `output/<project>/REPORT.html`: the one page people read; beside it eight documents: `START-HERE.md`, the four reports
  (`CURRENT-STATE.md`, `TARGET-STATE.md`, `GAP-AND-STRATEGY.md`, `EXECUTION-PLAN.md`), `TARGET-ARCHITECTURE.md`, `RUN.md`
  and the index `README.md`; plus `PLAN/` (STEPS, WAVES, one TASK card each) and `adr/`, which assistants read when
  fixing cards (M1.4: the other 19 Markdown renderings removed; their records stay).
- `technical/`: records later stages and the Studio read. Caches never live here (M1.2). A run removes the documents
  a check no longer writes (`eaos/pipeline/run.py` RETIRED).
- `runtime/` in EAOS's home: working copies, caches, batch copies, bounded by a retention rule (M1.1).
