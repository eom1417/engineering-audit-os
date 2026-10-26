# EAOS roadmap

**The only plan.** From today's EAOS to the ideal tool of `docs/NORTH-STAR.md`, a complete software engineering firm
in one command, built to `docs/STANDARDS.md` on the layout of `docs/ARCHITECTURE.md`. No other file holds a plan, a
backlog or a status: an open item found anywhere becomes a card here, a plan made in any assistant's plan mode is
copied here before its turn ends, and old plans are deleted once merged (2026-10-25, `docs/DECISIONS.md`).

The owner says "execute Mx" (in any chat, with any assistant): every card of Mx is done in order to the Definition of
Done (`docs/STANDARDS.md` §7), without asking again except for a decision only the owner can take. **After each card,
its row in the status table below is updated in the same change.** Milestones are numbered in the order they run.

## Where we are (2026-10-26, version 0.0.78)

M-1 to M4 are done, M5 but M5.4 (it waits for the owner's HungerLab snapshot), M6, then the code layout; **next is
M7, once the owner has reviewed the layout and says so**. Each done milestone in one line (what each card did:
`docs/archive/ROADMAP-DONE.md`; why and how: `CHANGELOG.md`):

| Milestone | What it delivered | Version |
|---|---|---|
| M-1 Context files | the references (`docs/`), this roadmap, the container's context; any assistant continues from the files | 0.0.71 |
| M0 Foundations and guards | `tools/quality.sh`, the detection baseline, the compatibility corpus, `docs/METRICS.md` from a script | 0.0.72 |
| M1 Disk and outputs diet | one copy of the tools, outputs without duplicates, a lazy facts reader, 8 documents instead of 27 | 0.0.73 |
| M2 Fewer, sharper engines | noisy rules silenced, engines that find nothing unique removed, one engine registry | 0.0.74 |
| M3 The target code layout | ten layers enforced, one state record, one guard and one command layer, giant modules split, one words catalog | 0.0.75 |
| M4 The pipeline as loops | loops as data, the coverage ledger with red gaps, the ideal in 8 minutes, repair or rebuild, the laws over all of EAOS (the Studio's JavaScript included) | 0.0.76 |
| M5 Seeing any app (but M5.4) | the common stacks start from their files, screens found in layers and by the browser agent (explored once, replayed free), signed in by rules, the lock and walk-through per kind of user; the corpus 12 of 12 (2 before) | 0.0.77 |
| M6 The whole system in layers | every check reads the system as layers (each file in its layer and side, the boundaries, what ships to the browser, every endpoint and its guard, the data rules, the rules split, operations, tests) and a fix that breaks a boundary is refused; the option "Try the layers" (the migrations tried with pgTAP and the Supabase advisors, the API with Schemathesis and two accounts, the production build read); the layers first in START-HERE, REPORT.html and the Studio; the detection baseline 15 of 16 (6 before) | 0.0.78 |
| The code layout (owner, 2026-10-26) | every layer split into folders by job, each named by its docstring; the tests mirror the layers; the map in `docs/ARCHITECTURE.md` §1; nothing of the behaviour changed (the public surface and every test the same) | 0.0.78 (no new version) |

## The firm, department by department

What a professional software firm does for its client, and where EAOS delivers each part: done, or the card that
completes it. A department with no card here is a gap in the plan.

| Department | Delivered today | Completed by |
|---|---|---|
| Discovery: the questions only the owner can answer | the intake, the coverage ledger, the sign-in question that says what EAOS tried (M5.3), each layer's questions (M6) | M7.4 (the judge asks what it cannot decide) |
| Architecture: the ideal shape and the decision | the ideal picture, repair or rebuild, target architecture, every project read as layers with its boundaries (M6) | M7.4 (the judge reads the broken boundary) |
| Code quality | dead code, duplication, complexity, the code laws | M8.4 (EAOS itself clean by its own laws) |
| Security | Semgrep, Bandit, CodeQL, gitleaks, osv-scanner; what ships to the browser, every endpoint's guard, the API tried with two accounts (M6) | M7.4 (the judge), M7.5 (the security engines after each batch), M9.2 (logic flaws) |
| Data | the data facts, rule duplication, the data layer's rules read and tried per table, one source of business rules (M6) | M9.2 (logic flaws) |
| Quality assurance | the behaviour lock, acceptance checks, Python suite health, the tests layer: every write no test reaches (M6) | M10.4 (replays) |
| Performance and production | the k6 baseline, production readiness findings, the operations layer (M6) | M9.4 (the final proof) |
| Screens, experience, accessibility | screens of any common stack found in layers and by the browser agent, pictured per kind of user, axe, journeys (M5) | M5.4 (HungerLab), M10 (simulated users) |
| Delivery | the plan, cards, fix batches behind the lock | M7 (reliable fixes, verified after each batch) |
| Hand-over and documents | the four reports, START-HERE, the Studio | M7.1 (a hand-over that resumes) |
| Build from an idea | the build journey and its proof gate | M7.6 (never stalls), M9.3 (proved) |
| Add a feature | the extend journey | M9.3 (proved) |
| Interfaces | CLI, MCP, Studio | M8 (MCP parity, a light Studio) |
| Intelligence and cost | assistants per stage | M9.1 (model tiers) |

## Milestones still to do (in the order they run)

### M5 Seeing any app
- **M5.4** HungerLab joins the corpus (from the owner's snapshot repository).
- **M5.5** The two corpus apps of M6 that do not start without an assistant start by rules: task-api (an Express API
  that needs Supabase keys and listens on the port its code writes, 3000) and next-dashboard (Next.js with Drizzle,
  whose first page needs a Postgres with its tables: `drizzle-kit push` on the run's own database). Today 13 of 15.
- Target: ≥ 90% of the corpus pictures its expected screens; every failure explained with its fix.

### M7 Reliable fixes and hand-over
- **M7.1** The hand-over runs as its own service and resumes where it stopped.
- **M7.2** The change that broke something found from the failure output first; halving last.
- **M7.3** Batches of about 15 cards, each handed over and merged on its own.
- **M7.4** A strict judge inside the existing triage: every finding names the harmed party, the broken boundary (M6)
  and the source evidence (Cloudflare security-audit style). The same judge rules on what a simulated user reports
  (M10.7).
- **M7.5** Each batch checked beyond behaviour: after a batch, M6's layer and security checks run again over the
  changed files, so a fix that opens a boundary is refused like one that breaks a screen. (The layers' gate is in since
  0.0.78: `journeys/fix/execute.py` new_breakage refuses a change that breaks a boundary of the browser, the endpoints, the
  data, the rules or the layers; what is left is the security engines' rerun and saying it in the batch's report.)
- **M7.6** The build journey never stalls: after the third refused proof in a row its last milestone is handed over
  with the list of what stays unproven, shown in the Studio and the report (today `journeys/build_from_plan/steps.py` holds it
  back on every refusal).
- **M7.7** A leftover is never a source file: `facts/defects/leftovers.py` calls a file a build output when its name
  starts with `build_` or a folder of its path is `target`, `out` or `bin`, so source code a project imports
  (EAOS's own `build_info.py`, a Java or Rust project's `target` package in its source tree) became a leftover card
  (found by the code layout, 2026-10-26); a file the project imports, or that sits beside source it imports, is
  source.
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
  lock file for EAOS's Python dependencies so osv-scanner reads them. The packages whose `__init__.py` holds their
  logic (`interfaces/studio_actions/`, `journeys/fix/waves/`, `journeys/guided/`, `report/studio/user_journeys/`,
  `report/studio/paths/`, `report/human_report/`, `engines/`, `analysis/layers/`, `ai/nodes/`) keep only their
  docstring and names there, the logic in a named module beside it (the independent review of the code layout).
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
- Done so far in the order guards, diet, layout, loops, seeing (M-1 to M5): what is removed is not moved, and the big
  work lands on a clean layout; nothing can be judged on an app EAOS cannot run, picture and sign into.
- M6 right after M5: its live part (M6.6, M6.7, the tests run) needs every app running and signed into (M5.1, M5.3);
  its static part may start once M5.1 is done. M7's judge and batch checks then read the boundaries M6 names.
- M7 before M8: fixes that are reliable and verified first, then the interfaces over them and EAOS's own clean-up.
- M9 then M10: the proof of the three journeys and the model tiers come before the simulated users, which stand on M5
  (the browser-agent layer), M7.4 (the judge) and M9.1 (model tiers); built earlier they would be noise and cost.
- Each milestone ends with one version, `beta-trial` updated and a short Arabic summary (`docs/STANDARDS.md` §7).

## Status (updated after every card)

Open cards only; a card once done moves, with what it delivered, to `docs/archive/ROADMAP-DONE.md` at its
milestone's end.

| Card | Status | Version | Date |
|---|---|---|---|
| M5.4 | not started (waits for the HungerLab snapshot) | | |
| M5.5 | not started | | |
| M7.1 | not started | | |
| M7.2 | not started | | |
| M7.3 | not started | | |
| M7.4 | not started | | |
| M7.5 | not started | | |
| M7.6 | not started | | |
| M7.7 | not started | | |
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
