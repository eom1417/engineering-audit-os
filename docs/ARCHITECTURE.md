# EAOS architecture

Where everything lives, what may depend on what, and how a check flows. **Before adding a file, find its place in
section 4.** Section 1 is today; sections 2-3 are the target that milestones M3 and M4 (`ROADMAP.md`) build; this page
is updated in the same change that moves anything.

## 1. Today (0.0.72)

```
engineering-audit-os/
  eaos/            the Python package (62k lines, 297 files): 119 modules flat at its root (29k of those lines) plus
    api/           the local HTTP server, its guard, events, sign-in
    assistants/    Claude Code and Codex adapters, readiness probes
    compose/       the written reports (four reports, labels, markup)
    engines/       one adapter per external analyzer (semgrep, codeql, reforge, ...)
    facts/         deterministic extractors (syntax, structure, graph, flows, secrets, ...)
    pipeline/      stages declared as data (stages.py), runners, scheduler, run/resume
    progress/      the live progress log and its estimates
    screens/       the crawl and the screen audit
    studio/        the Studio's data layer (sections) and its actions (runs, chat, branches)
    data/          contracts, words, catalogs, the built Studio (data/studio)
  console/         the Studio UI (JS, esbuild; built into eaos/data/studio)
  tests/           unittest suite
  tools/           developer tools: quality (every code law), golden_trial with detection_baseline, corpus,
                   metrics, validate, code_limits, dev_setup
  upstreams/       the pinned external tools (registry, licenses)
  docs/            this page and the other references
```

Known debts this layout carries (removed by M3): flat root without layers; the CLI (`guided.py`), MCP
(`agent_tools.py`, `mcp_server.py`) and Studio (`studio/actions`) each hold their own command layer; two request
guards (`api/guard.py`, `studio/actions/security.py`); the largest modules `human_report.py` (2,097 lines),
`guided.py` (1,223), `agent_tools.py` (1,187), `studio/actions/branches.py` (1,140).

## 2. Target layers (M3)

```
eaos/
  core/        state store (the one truth), contracts, paths, jobs, ledger, words (i18n), errors
  engines/     one adapter per tool + one registry (toolchain.json): run, parse, normalise
  facts/       deterministic extractors over one snapshot
  live/        run the app in its sandbox, sign-in, screen discovery (rules -> AI explorer -> replay), behaviour lock,
               the one browser-agent layer (drive towards a goal, record each step, replay without AI)
  analysis/    claims, correlation, weaknesses, debt, cards, plan, estimates (repair or rebuild)
  ai/          assistant adapters, model tiers and escalation, prompts, AI nodes (triage, semantic, ideal),
               the simulation's scenario planner, data generator and actors (M9)
  journeys/    repair (check -> envision -> plan -> fix batches -> hand over), build (from an idea), extend
  pipeline/    loops and stages declared as data, one runner
  report/      REPORT.html and the few documents people read
  interfaces/  cli, mcp, api, studio data layer: thin, all calling the same journeys
console/       the Studio UI: optional and light
```

**Dependency rule** (enforced by `import-linter`: today's direct imports since M0.1, these layers from M3.1): a layer imports only the layers to its right.

`interfaces → journeys → pipeline → (analysis | ai | live | report) → (facts | engines) → core`

Layers in one group (`analysis | ai | live | report`, `facts | engines`) do not import each other: `pipeline` and
`journeys` combine them. No layer imports `interfaces`; `core` imports nothing of EAOS; the interfaces (CLI, MCP, API,
Studio) never hold logic of their own.

## 3. The pipeline as loops (M4)

Stages stay declared as data (`eaos/pipeline/stages.py`: what each needs, produces, reads). Each stage belongs to a
loop; a loop runs until its exit condition holds or its rounds are spent, then acts as declared. Reordering the
pipeline, or turning a step into a loop, is a change of data, never of code.

```python
Loop(name, stages, exit=<measurable condition>, max_rounds=N, on_fail='explain' | 'escalate' | 'stop')
```

The table names the main stages of each loop; M4.2 assigns all 38 of `stages.py` and removes those with no consumer.

| Loop | Stages (today's names) | Exit condition |
|---|---|---|
| L1 Understand | facts, features, intake, policy, engines | facts complete; coverage ledger written |
| L2 Run and see | setup, session, crawl, screens, journeys, lock, record | expected screens pictured, or the AI explorer tried, or a failure explained |
| L2b Try as a user (optional, M9) | replay of saved journeys (always); scenario, data, actors, tickets (short or full simulation) | replays green or their breaks shown; each persona reached its goals or its difficulties recorded with evidence |
| L3 Judge | claims, probe, triage, weaknesses, visual, the simulation's difficulties | every finding confirmed / needs validation / rejected, with evidence |
| L4 Envision | semantic, ideal, target, reconcile, estimate | ideal picture; repair-or-rebuild decision with its estimate |
| L5 Plan | plan, order, cards, steps | every card has an acceptance check and a place in the order |
| L6 Fix | fix batches (~15 cards) | every card fixed, or left with its reason |
| L7 Hand over | handover, report | one clear report; a branch waiting for the owner's decision |

Every loop writes its part of the **coverage ledger**: what it covered, what it could not, and why; a big gap shows in
red at the top of the report.

## 4. Where a new file goes

| It is… | It goes in |
|---|---|
| a rule that reads source and produces facts | `facts/` (target: `facts/`) |
| an adapter for an external tool | `engines/` + its entry in `upstreams/registry.yaml` and `eaos/data/toolchain.json` |
| running the app, signing in, finding screens | today `live_*.py`, `screens/`, `pipeline/pages.py` → target `live/` |
| judging findings by rules, cards, plan, estimates | today flat modules (`claims.py`, `plan.py`, …) → target `analysis/` |
| judging findings with an assistant (triage, the strict judge of M6.4) | today `studio/nodes/` → target `ai/`; `analysis/` takes its verdicts as data |
| driving the browser for a goal, recording, replaying | target `live/` (the one browser-agent layer, M5.2) |
| a simulated user: scenario, personas, data, actors, tickets | target `ai/` (M9); its replays run from `live/` |
| anything that calls an assistant | today `assistants/`, `studio/nodes/`, `studio/ideal*.py` → target `ai/` |
| a journey's steps (check, fix batches, build, extend) | today `guided.py`, `waves.py`, `blueprint.py`, `extend.py` → target `journeys/` |
| a stage or loop declaration | `pipeline/stages.py` (target: plus `pipeline/loops.py`) |
| what people read (REPORT.html, the few documents) | today `human_report.py`, `compose/` → target `report/` |
| a CLI command, MCP tool, API route or Studio section | target `interfaces/`: thin, calling a journey |
| words shown to people | the one words catalog (`eaos/data/`; target `core/words`) |
| a Studio screen | `console/src/places/<place>/` (only core places; see `ROADMAP.md` M7) |
| a test | `tests/test_<module>.py`, one test per real behaviour |
| a developer tool | `tools/` |
| scratch of a task | `/workspace/eaos-work/<task>/`, removed when the task ends: never in the repository |

## 5. Check paths

| Path | What runs |
|---|---|
| Full check | every loop; L2b replays the saved journeys without AI; the short simulation only when chosen in the check's preview, which shows its time and cost |
| A focused path (look, security, …) | only the loops it needs |
| Try the experience (M9) | L1 and L2 as far as needed to run the app, then L2b's full simulation, L3 and the experience report |

## 6. Outputs (what a check leaves)

- `output/<project>/REPORT.html`: the one page people read; `START-HERE.md`, the four reports, `TARGET-ARCHITECTURE.md`
  and `RUN.md` beside it (M1.4 reduces the 27 documents to these).
- `technical/`: records later stages and the Studio read. Caches never live here (M1.2).
- `runtime/` in EAOS's home: working copies, caches, batch copies, bounded by a retention rule (M1.1).
