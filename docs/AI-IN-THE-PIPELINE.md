# AI in the pipeline

Where the person's own assistant (Claude Code or Codex, `eaos/ai/__init__.py`) makes EAOS's outcome better, and how
each use is bounded. The rules stay the baseline everywhere: the assistant adds to them and never replaces them, and a
check without an assistant runs the same way on the rules alone.

## The bounds every AI step keeps

1. **Citations.** Every output cites ids of the report: facts (`FACT-`), claims (`CLM-`), cards (`TASK-`) or rules
   (`RULE-`). A deterministic check drops an output whose citations do not resolve, and lists it.
2. **Hypotheses.** Nothing the assistant says reaches CONFIRMED by itself; only a probe can raise a claim.
3. **A fallback.** No assistant, a "no" to the consent question, a stuck assistant, a failure, or an answer outside its
   schema: the step is recorded as unavailable with its reason, the rules' result stands, and the check never fails
   because of AI.
4. **Time to do it well, never a cut-off.** An AI step takes the time and money the work needs; both are recorded and
   shown, never used to stop it. Only the person's stop ends it, or a hang: an assistant silent for 20 minutes is
   ended as stuck (`eaos/core/system/process.py` `STUCK`, reason `ai_stuck`). A check stopped during an AI step resumes
   at that step. Speed comes from clear prompts (the goal, the exact evidence, the output schema, what a good answer
   is, what not to do), not from limits.
5. **The project's text is untrusted data.** Code, pages and documents reach every prompt marked as data, never as
   instructions (`eaos/core/contracts/untrusted.py`).
6. **On by default, never silently off.** The check uses the person's assistant unless they said no (`use_assistant`,
   kept in the project's state; the MCP `audit` passes it). Before a check starts, the assistant is asked for one word
   (`eaos/ai/assistant/readiness.py`); when it does not answer, the check does not start and the reason and its fix
   are said, with the choice to start without AI (`without_ai`). An assistant that stops answering during the check
   gives its reason on the live map and in the report. `EAOS_ASSISTANT=none` turns every assistant off on a computer.

## Model tiers: a cheaper model never closes anything alone

Each stage asks on a tier, set as data in `eaos/ai/assistant/tiers.py`:

| Tier | Claude Code | Codex | Stages |
| --- | --- | --- | --- |
| Light | haiku | low effort | a card's first triage (`card_triage`), the translation, each simulated user's step (`experience_actor`) |
| Standard | sonnet | medium effort | the visual review, the pipeline gap planner, the plan's order, the experience's support desk |
| Deep | the person's own model | high effort | the ideal, the fix review, the experience's scenario, data and judge; every stage not listed |

- **Escalation.** A tier that fails, or leaves batches unanswered, is asked again one tier up. A cheaper tier that
  would close something (set a card aside, call a gap no gap, call a picture clean: `CLOSING`) is asked again on the
  deep tier. Each run records its tier and any escalation; the caches key on the tier.
- **Speed mode.** The check's speed mode (`--mode speed`) lowers standard stages to light.
- **Overrides.** `EAOS_TIER_<STAGE>` sets one stage's tier; `EAOS_CLAUDE_MODEL_<TIER>` sets a tier's Claude model, and
  `EAOS_CLAUDE_MODEL` the deep one.

## Where the assistant decides in a check

A check is 40 stages (`eaos/pipeline/stages.py`). It gathers the evidence first, lets the tools propose, lets the
assistant decide with them, applies the decisions through deterministic guards, and writes the reports last.

| Stage | Kind | What it decides |
| --- | --- | --- |
| `facts` … `probe` | rules | The evidence and measures, static (`engines`) and live once the person agreed to run the app; claims settled mechanically. Three AI stages sit among them: |
| `roles` | AI | The app's kinds of users, each with the code that makes it one and its pages, so the app is opened as each |
| `session` | AI | Test users signed in on the running copy, one per kind of user; else the person signs in by hand |
| `experience` | AI | Simulated users try the running app (only on the `experience` path, or its short option beside the complete check) |
| `semantic` | AI | Responsibilities, boundaries and root causes, as hypotheses with a falsifier (at most 3 rounds) |
| `plan`, `target`, `proposals` | rules | The candidate cards and the tools' target proposal |
| `triage` | AI | Each candidate card confirmed, doubted or rejected on its own evidence, with why |
| `visual` | AI | What a person would notice on each screen picture, each finding with its picture and a region inside it |
| `cards` | guard | The verdicts applied once: a rejected card leaves the plan and its claim is refuted; a doubted one waits for a person and is never fixed automatically; each visual finding becomes a design card |
| `ideal` | AI | Each target proposal accepted, modified or rejected, with evidence, then critiqued |
| `pipeline_gaps` | AI | How each broken pipeline rule is closed, then reviewed |
| `reconcile` | guard | The final target: the assistant's decision where it cites evidence and passes the guards (a known component, the owner's policy and protected features kept), the rule's elsewhere; every component says who decided it (`agreed`, `ai_modified`, `rule_only`, `disagreement`, `ai_added`) |
| `order` | AI | The confirmed cards ordered and grouped into steps with why, then reviewed |
| `steps` | guard | The assistant's steps when every card is placed once and every prerequisite kept, else the rules' waves |
| `reports` | rules | The reports, written from the final records |
| `translate` | AI | Each document whole in Arabic and English: only the pieces in the other language, on the light tier |

When the rule and the assistant differ, the assistant decides if it cites evidence and passes the guards; the rule's
view is kept beside it (`decided_by.rule`, `disagreements`). A record left by an earlier check is never read as this
check's decision: a guard reads an AI stage's output only when that stage ended well in this run. Without an assistant
the AI stages say `no_provider`, the guards keep every card and proposal (`rule_only`), and the plan is the rules'.

## The triage and the strict judge

The triage (`eaos/ai/nodes/triage.py`, node `card_triage`) reads every open card in batches of 40, each with up to 4 of
its facts (those carrying a measurement first) and a short excerpt of the code at each fact's line, and decides:

- **confirm** when the evidence shows the problem. A confirm is strict: it names who the problem harms and how
  (`detail.harmed`), cites the facts that show it, and names the boundary it breaks when it is one. A confirm that
  names no one harmed is kept as a doubt.
- **doubt** when the evidence neither shows nor contradicts it. A doubted card is judged again on up to 12 of its
  facts; one still doubted waits for a person and is never fixed automatically.
- **reject** when the evidence contradicts it: a false alarm, set aside, and its rule is told. A reject on the light
  tier is always asked again on the deep tier.

A verdict that cites neither the card nor one of its facts falls back to the rules. The same strict judge rules on the
simulated users' difficulties and on the logic-flaw hunt's cards, which reach the plan through the triage like any card.

## Optional deep checks

Both run only when the person asks, each saying its time and cost first, and both feed back into the check's claims so
their findings become cards like any other.

**Logic-flaw hunting** (`eaos logic-flaws`, MCP `logic_flaws`; `eaos/analysis/logic_flaws/`). Flaws in what a program
allows, which no scanner finds because every line is valid code: skipped steps, races, quantities, wrong checks,
trusted input, time, fallbacks, feature abuse. The method is adapted from Cloudflare's security-audit skill (MIT).
The assistant reads the project read-only on its deep tier, twice: the hunt, then a second reading that tries to
disprove each candidate (holds, unsure, refuted). A candidate is kept only when it points at a real line of a source
file, says what a layer finding does not already say, and was not refuted. The check then goes on from its claims, so
the triage judges the new cards. The hunt is bounded by a wall clock (40 minutes by default, `--minutes`), its spend
shows in `eaos usage`, and through MCP it needs the person's agreement.

**Simulated users** (`eaos experience`, `--path experience`, MCP `experience`; `eaos/analysis/experience/`,
`eaos/live/experience/`). The scenario planner (deep) names personas, their goals and the hand-offs between them, as
data repaired by rules; the domain data (deep) seeds the run's own database. Each persona (the actor, light) drives
the app's isolated copy in a browser within its budgets (25 steps, 600 seconds, 30 calls), every step with its picture
and a friction note where it found something hard. A support desk (standard) answers or escalates tickets. Each
difficulty is met again by a fresh persona that does not see the first attempt, then ruled on by the judge (deep) as
strictly as the triage. A confirmed difficulty becomes a fix card with its steps to reproduce, built from the recorded
journey, never by the assistant. The story is `EXPERIENCE.md`. The journeys reached are saved and replayed without AI
in every later full check, as rows of the behaviour lock. The short simulation is an option of the complete check, off
by default.

## Outside the check

| Step | What AI adds | Bounds | Where |
| --- | --- | --- | --- |
| Running the app | How to start an unfamiliar app when detection fails | Proposals are tried in an isolated copy and refused when unsafe | `eaos/live/app/setup.py`, MCP `run_try` |
| Fixes and builds | Writing the change a card asks for | Every gate and the behaviour lock judge each change; it reaches the project only as a branch | `eaos/journeys/agent_tools/`, `eaos/journeys/build_from_plan/` |
| Fix review | Each card of a batch: accept, retry or ask, after reading the diff and the checks (deep tier) | A card the gates failed is never accepted; "accept" is a recommendation, the person still decides | `eaos/ai/nodes/fix_reviewer.py` |
| AI nodes on demand | The nodes above run again on the latest check | Same citation check and rules fallback per node; started by the person | MCP `run_nodes`, `eaos/ai/nodes/` |

## Where AI adds nothing

Facts, measurements, probes, load, the plan's waves and the reports stay deterministic. Their value is that they are
reproducible; a model would only make them less so.

## What the person sees

- On the live check map, AI stages carry a small "AI" mark; their panel shows the assistant, model and calls the stage
  reported, or the reason it was skipped.
- In the Studio, the planned ideal is shown with its provenance (assistant, model, time, departures from the rules,
  open questions). Without a plan, every view says plainly that it shows the rules' target.
- `eaos usage` (MCP `history op=usage`) shows the tokens and cost of each stage and run. Measured costs are in
  [METRICS.md](METRICS.md).
