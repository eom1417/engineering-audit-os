# EAOS roadmap

**The only plan.** From today's EAOS to the ideal tool of `docs/NORTH-STAR.md`, built to `docs/STANDARDS.md` on the
layout of `docs/ARCHITECTURE.md`. The owner says "execute Mx" (in any chat, with any assistant): every card of Mx is
done in order to the Definition of Done (`docs/STANDARDS.md` §7), without asking again except for a decision only the
owner can take. **After each card, its row in the status table below is updated in the same change.**

## Milestones

### M-1 Context files (before M0)
- **M-1.1** The references: `docs/NORTH-STAR.md` (+ `.ar.md`), `docs/ARCHITECTURE.md`, `docs/STANDARDS.md`,
  `docs/DECISIONS.md`, `docs/METRICS.md`, this roadmap; `AGENTS.md` rewritten as their index.
- **M-1.2** The container's context (`/workspace/AGENTS.md`, `CLAUDE.md`, `HANDOFF.md`) rewritten on the same rules;
  nothing about the work kept in an account's folders.
- **M-1.3** Proof: an assistant with no context answers "next milestone, Definition of Done, where a new file goes,
  the complexity limit" from the files alone.

### M0 Foundations and guards (before touching anything)
- **M0.1** `tools/quality.sh`: one command for every law of `docs/STANDARDS.md` §1-2 (code limits, function length
  and parameters, `jscpd`, `vulture`/`enola`/`knip`, `bandit`/`semgrep`/`gitleaks`/`osv-scanner`, `import-linter`
  with today's layers as the contract); records today's numbers; refuses a change that worsens one.
- **M0.2** Detection baseline: a trial app with known problems (a vulnerability, a secret, dead code, duplication, a
  broken screen, sign-in, a logic flaw) and what EAOS finds today; part of the golden trial.
- **M0.3** Compatibility corpus: about 12 pinned open-source apps (React/Vite with and without hash routes, Next.js,
  Vue, Svelte, Expo web, Flask, Django, Streamlit, one with sign-in, one with a welcome screen) and a runner that
  records: app ran, screens pictured, screens expected. Today's pass rate recorded.
- **M0.4** `docs/METRICS.md` filled by a script from a real check: lines, files, check time, output size, cards,
  corpus pass rate, baseline findings.

### M1 Disk and outputs diet
- **M1.1** Runtime cleanup: `run-data` (783 MB: tools linked, not copied), `waves`, `triage/runs`,
  `nodes/runs.jsonl`; retention: the last check and the last two batches.
- **M1.2** Outputs without duplicates: caches out of the output, one copy of the Studio data (no `.js` twins), one
  copy of engine findings, no copy of `REPORT.html`, compact JSON, stale files and translations cleared.
- **M1.3** A lazy facts reader: a caller loads the facts file it needs, not all of them (~280 MB per call today).
- **M1.4** Documents from 27 to about 8 (START-HERE, the four reports, TARGET-ARCHITECTURE, RUN); the rest merged or
  removed with their writers and tests.
- **M1.5** Records nobody reads removed (`proposals.json`, `reports.json`, `live/sign-in.json`, ...).
- Target: output ≤ 150 MB and ≤ 400 files, runtime ≤ 100 MB, same findings.

### M2 Fewer, sharper engines
- **M2.1** `semgrep`: the noisy rule silenced (`javascript.lang.security.html-in-template-string`, 1,554 of 1,672
  findings), the remaining rules reviewed.
- **M2.2** Complexity: overlap measured on the corpus; keep one or two; a card is rechecked by the engine that found it.
- **M2.3** Dead code, duplication, security: keep each engine that finds what no other finds; remove the rest.
- **M2.4** One engine registry (`eaos/data/toolchain.json`) for install, run and display.
- Target: fewer engines and a shorter install, same or more findings.

### M3 The target code layout
- **M3.1** Modules moved into the layers of `docs/ARCHITECTURE.md` §2 with no change of behaviour; `import-linter`
  enforces the dependency rule.
- **M3.2** One source of truth: `core/state` reads and writes the state; Studio, CLI and MCP read through it; no
  parallel record.
- **M3.3** One implementation per behaviour: one request guard; one command layer used by CLI, MCP and Studio.
- **M3.4** The giant modules split under the target laws (`human_report.py`, `guided.py`, `agent_tools.py`,
  `studio/actions/branches.py`).
- **M3.5** One words catalog for Arabic and English.
- Target: `tools/quality.sh` passes at the target limits; EAOS's check of itself shows no dead-code, duplication,
  complexity or security card.

### M4 The pipeline as loops
- **M4.1** `Loop` declared as data with one runner; reordering is a data change. A loop may be optional, switched on
  by a check path or an option of the full check (the simulation of M9 is the first such loop).
- **M4.2** The 38 stages assigned to the seven loops; a stage with no consumer removed.
- **M4.3** The coverage ledger: each loop writes what it covered and what it could not; big gaps in red at the top.
- **M4.4** The ideal picture faster, never dropped: a compact bundle, reuse when the code did not change, parallel
  calls. Target: from 24 minutes to under 8.
- **M4.5** The repair-or-rebuild decision with the time and effort of each option.

### M5 Seeing any app
- **M5.1** Running the app detected for the common stacks; green on the corpus.
- **M5.2** Layered screen discovery: rules, then an AI explorer driving the browser, its steps saved and replayed
  without AI next time. The explorer is built as **the one browser-agent layer** (drive with a goal, record each step
  with its picture, replay without AI) that M9's simulated users reuse; an open-source agent (`browser-use`,
  `Stagehand` or Playwright MCP) is adopted only if it measures better than our own on the corpus.
- **M5.3** Sign-in handled generically: a test account, clear questions when the owner is needed.
- **M5.4** HungerLab joins the corpus (from the owner's snapshot repository).
- Target: ≥ 90% of the corpus pictures its expected screens; every failure explained with its fix.

### M6 Reliable fixes and hand-over
- **M6.1** The hand-over runs as its own service and resumes where it stopped.
- **M6.2** The change that broke something found from the failure output first; halving last.
- **M6.3** Batches of about 15 cards, each handed over and merged on its own.
- **M6.4** A strict judge inside the existing triage: every finding names the harmed party, the broken boundary and
  the source evidence (Cloudflare security-audit style). The same judge rules on what a simulated user reports (M9.7).

### M7 Interfaces: CLI and MCP first, Studio light
- **M7.1** Parity: everything the Studio does is done through MCP; the whole journey tested from the CLI alone.
- **M7.2** Studio: core places stay; the deep "understand" views (17 screens, ~5.4k lines) become one report page;
  size and memory budgets.
- **M7.3** Tests diet: duplicates merged (D1-D5 in `docs/METRICS.md`), tests of removed code removed, sleeps
  replaced by awaited conditions, coverage not lower.

### M8 Intelligence, cost and the final proof
- **M8.1** Model tiers (light / standard / deep) per stage with escalation; a cheaper model never drops or closes
  anything. Simulated users act on the light tier; the scenario planner and the judge use the deep one.
- **M8.2** Logic-vulnerability hunting (from Cloudflare's security-audit skill) as an optional deep check.
- **M8.3** The three journeys proved end to end, from the CLI and from the Studio: repair a corpus app, build from a
  PRD, add a feature.

### M9 The user's full experience, simulated
A professional firm has people try the program as its users would. Here AI actors do it in the isolated copy, from
EAOS's understanding of the project, and every difficulty they meet becomes evidence. Three levels:

| Level | What runs | Cost | When |
|---|---|---|---|
| Replay | the saved journeys, step by step, **without AI** | almost none | **in every full check** |
| Short simulation | one persona doing the app's main task, within a step budget | about the ideal picture's | an **option of the full check**, its time and cost shown before it starts |
| Full simulation | several personas, hand-offs between them, support tickets, complete data | high | **its own check path** ("try the experience"), runnable alone |

- **M9.1** Scenario planner: from the facts, features, roles and screens, the personas, each one's goals and the
  hand-offs between them (the user asks, the admin approves, the user goes on), written as data.
- **M9.2** Domain data: realistic dummy data fitting the project; the key flows are entered through the UI, bulk
  history is seeded into the copy's database; external services (mail, payment, paid APIs) are stubbed, and what
  needs a real one is said as not covered.
- **M9.3** One actor, complete: drives the browser towards its goal on the M5.2 layer, within step, time and cost
  budgets; every step recorded with its picture.
- **M9.4** Save and replay: a finished journey is saved and replayed without AI in every full check, as part of the
  behaviour lock; a replay that breaks shows in red.
- **M9.5** Several actors and hand-offs: an actor waits for the event another one makes (approval, reply), then goes on.
- **M9.6** Support and tickets: an actor stuck sends a ticket, a support actor answers or escalates; the friction log
  records what was hard to find, understand or finish.
- **M9.7** Judging: each difficulty is confirmed by a second independent attempt and its evidence (steps, pictures),
  ruled on by the M6.4 judge, then becomes a fix card with its steps to reproduce.
- **M9.8** The experience report: the user's story step by step with pictures, difficulties ranked, time per task, the
  tickets; in the Studio, the CLI and MCP.
- **M9.9** The paths: "try the experience" as its own check path; the short simulation as an option of the full check
  with its estimate; the replay always in the full check.
- **M9.10** Proof and decision: three app kinds of the corpus simulated; time, cost and the quality of the findings
  measured in `docs/METRICS.md`; the owner decides from the numbers whether the short simulation becomes part of
  every full check.
- Target: the full simulation runs on the corpus apps that have more than one role; every finding carries evidence;
  replays are free and green.

## Order and why
- M-1 and M0 first: without references, guards and measures, any clean-up can break something silently.
- M1-M2 before M3: what is removed is not moved.
- M3 before M4-M5: the big work lands on a clean layout.
- M9 last: it stands on M5 (seeing and signing into any app, the browser-agent layer), M6.4 (the judge) and M8.1
  (model tiers); built earlier it would be noise and cost on a base that cannot yet picture every app.
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
| M1.2 | not started | | |
| M1.3 | not started | | |
| M1.4 | not started | | |
| M1.5 | not started | | |
| M2.1 | not started | | |
| M2.2 | not started | | |
| M2.3 | not started | | |
| M2.4 | not started | | |
| M3.1 | not started | | |
| M3.2 | not started | | |
| M3.3 | not started | | |
| M3.4 | not started | | |
| M3.5 | not started | | |
| M4.1 | not started | | |
| M4.2 | not started | | |
| M4.3 | not started | | |
| M4.4 | not started | | |
| M4.5 | not started | | |
| M5.1 | not started | | |
| M5.2 | not started | | |
| M5.3 | not started | | |
| M5.4 | not started (waits for the HungerLab snapshot) | | |
| M6.1 | not started | | |
| M6.2 | not started | | |
| M6.3 | not started | | |
| M6.4 | not started | | |
| M7.1 | not started | | |
| M7.2 | not started | | |
| M7.3 | not started | | |
| M8.1 | not started | | |
| M8.2 | not started | | |
| M8.3 | not started | | |
| M9.1 | not started | | |
| M9.2 | not started | | |
| M9.3 | not started | | |
| M9.4 | not started | | |
| M9.5 | not started | | |
| M9.6 | not started | | |
| M9.7 | not started | | |
| M9.8 | not started | | |
| M9.9 | not started | | |
| M9.10 | not started | | |
