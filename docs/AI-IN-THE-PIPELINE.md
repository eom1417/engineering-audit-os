# AI in the pipeline

Where the person's own assistant (Claude Code or Codex, `eaos/ai/__init__.py`) makes EAOS's outcome better,
and how each use is bounded. The rules stay the baseline everywhere: the assistant adds to them and never replaces
them.

## The bounds every AI step keeps

1. **Citations.** Every output cites ids of this report: facts (`FACT-`), claims (`CLM-`), cards (`TASK-`) or rules
   (`RULE-`). A deterministic check drops an output whose citations do not resolve, and lists it.
2. **Hypotheses.** What the assistant says never reaches CONFIRMED by itself. Only a probe can raise it.
3. **A fallback.** No assistant, a "no" to the consent question, a stuck assistant, a failure, or an answer outside
   the schema: the step is recorded as unavailable with its reason, the rules' result stands, and the check never
   fails because of AI.
4. **Time to do it well, never a cut-off** (owner, 2026-10-10). An AI step takes the time and the money the work
   needs; both are recorded and shown as facts, never used to stop it. Only the person's stop ends it, or a hang:
   an assistant that gives no output at all for 20 minutes is ended as stuck (`eaos/ai/assistant/command.py` `STUCK`,
   reason `ai_stuck`). A check stopped during an AI step resumes at that step; the finished ones are not asked
   again. Speed comes from clear prompts (goal, the exact evidence packet, the output schema, the criteria of a good
   answer, what not to do), not from limits. The project's text is untrusted data, never instructions.
5. **On by default, and never silently off** (owner, 2026-10-11). The check uses the person's assistant unless they
   said no (question `use_assistant`, kept in the project's state; `eaos start --yes` answers it, the MCP `audit`
   passes it as `use_assistant`). Before a check starts, the assistant is asked for one word
   (`eaos/ai/assistant/readiness.py`: installed, signed in, answering). When it does not answer, the check does not start:
   the reason and its fix are said (in the Studio as a question: "I fixed it: check again" or "Start this check
   without AI", `without_ai`, which changes no choice), and an assistant that stops answering during the check gives
   its own reason on the live map and in the report. `EAOS_ASSISTANT=none` turns every assistant off on a computer.

## Where the assistant decides in the check

The check gathers the evidence first, lets the tools propose, lets the assistant decide with them, derives the gaps
and the plan from that joint decision, and writes the reports last (eaos/pipeline/stages.py):

| Order | Stage | Kind | What it decides or reads | What changes downstream |
|---|---|---|---|---|
| 1 | `facts` … `probe` | rules | The evidence and the measures, static (`engines`) and live once the person agreed to run the app (`setup`, `record`, `crawl`, `screens`, `baseline`) | The current state |
| 2 | `semantic` | AI | Responsibilities, boundaries, root causes, as hypotheses | Investigation cards; the ideal reads them |
| 3 | `plan`, `target` | rules | The candidate cards; the target proposal (`target-proposal.json`) | Nothing is final yet |
| 4 | `proposals` | rules | The Studio's records of the proposals, which the assistant reads | |
| 5 | `triage` | AI | Each candidate card confirmed, doubted or rejected on its own evidence | |
| 5b | `visual` | AI | The assistant opens the screen pictures, and only them, and names what a person would notice; each finding names its picture and a region inside it | Design cards |
| 6 | `cards` | guard | The verdicts applied once, before ranking, the plan and the reports: a rejected card leaves the plan and the gaps and its claim is refuted; a doubted one (judged again on all its facts) needs a person's review and is never fixed automatically; a prerequisite on a rejected card is dropped with why; each visual finding becomes a design card (`cards.json`) | plan.json, dossier.json, PLAN/ |
| 7 | `ideal` | AI | Each proposal of the target accepted (same operation), modified (another operation) or rejected (delete), with why and evidence | |
| 8 | `pipeline_gaps` | AI | How each broken pipeline rule is closed | The order reads its steps |
| 9 | `reconcile` | guard | The final target: the assistant's decision where it passes the guards (a component that exists, an operation it can take, no deletion of what the owner protects: critical features, the intake's answer, the architecture policy's layers), the rule's elsewhere; every component says who decided it: `agreed`, `ai_modified`, `rule_only`, `disagreement` (the guard kept the rule), `ai_added`; the gap matrix is drawn again from it | target-architecture.json, TARGET-ARCHITECTURE.md, ADRs |
| 10 | `order` | AI | The confirmed cards ordered and grouped into steps with why | |
| 11 | `steps` | guard | The assistant's steps when every card is placed once and no prerequisite is broken, else the rules' waves (`plan.json` `order`, PLAN/STEPS.md) | EXECUTION-PLAN.md follows them |
| 12 | `reports` | rules | The four reports and the C4 diagrams, written from the final records; REPORT.html and the Studio's data follow | |

When the rule and the assistant differ, the assistant decides if it cites evidence and passes the guards; the rule's
view is kept beside it (`decided_by.rule`, `disagreements`). A record an earlier check left on disk is never read as
this check's decision: the guards read an AI stage's output only when that stage ended ok in this run.

Without an assistant the path is the same: the AI stages say `no_provider`, the guards keep every card and every
proposal (`rule_only`), and the findings, cards and plan are those of the rules alone.

## The steps, ranked by value

| Rank | Step | What AI adds | Bounds | Where |
|---|---|---|---|---|
| 1 | Target decision (check stage `ideal`) | Each of the tools' proposals for the target judged, and the other views planned, then critiqued (what was missed, risks, order). The rules alone give a generic target. | Plan + critique passes; elements without a resolving citation are dropped; the reconcile guards decide what reaches the target; cached on the same inputs. | `eaos/ai/ideal/planner.py`, node `ideal_planner`, `eaos/report/target_architecture/picture.py` `reconcile` |
| 2 | Semantic reading (check stage `semantic`) | Responsibilities, boundaries, contracts and root causes, which no rule can read from facts. | At most 3 rounds, one call of up to 600 s each; invented fact ids are sent back and the answer is rejected if they stay; every claim is a HYPOTHESIS with a falsifier. | `eaos/ai/semantic.py` |
| 3 | Card triage (check stage `triage`) | Each candidate card confirmed, doubted or rejected as a false alarm on its own evidence and the code at it, with why in the person's words. The engines cannot judge their own findings. | A verdict that does not cite the card or one of its facts falls back to the rules; every card is read, in batches of 40; cached. | `eaos/ai/nodes/triage.py`, node `card_triage`, `eaos/analysis/planning/cards.py` `confirm` |
| 4 | Plan order (check stage `order`) | The cards ordered and grouped into steps with why, reading the triage, the ideal and the pipeline steps. The rules order by milestone and wave only. | Plan + critique passes; an order that breaks a prerequisite, names a card twice or one outside the plan is dropped; cached. | `eaos/ai/nodes/plan_orderer.py`, node `plan_orderer`, `eaos/analysis/planning/cards.py` `sequence` |
| 4b | Visual review (check stage `visual`) | What a person would notice on each screen: crowding, hierarchy, consistency, clarity, accessibility, behaviour. No rule sees a picture. | The assistant may open exactly the listed pictures (Claude Code: `--tools Read --allowedTools "Read(<file>)"`, every other read refused; Codex: `-i <file>`); a finding without a region inside its picture drops the decision; batches of 6 pictures. | `eaos/ai/nodes/visual_reviewer.py`, node `visual_reviewer`, `eaos/analysis/planning/cards.py` `design_card` |
| 5 | Pipeline gaps (check stage `pipeline_gaps`) | How each broken pipeline rule is closed, as a step the order places. | Plan + critique passes; a decision must cite its gap or its rule. | `eaos/ai/nodes/pipeline_gap_planner.py` |
| 6 | Setup (`eaos next`, step `ready`) | How to start an unfamiliar app when detection fails. | Proposals are tried in an isolated copy and refused when unsafe. | `eaos/live/app/setup.py` |
| 7 | Fixes | Writing the change a card asks for. | The gates and the behaviour lock judge every change; it reaches the project only as a branch. | `eaos/journeys/agent_tools/` `fix_*` |
| 8 | AI nodes from the Studio (`run_nodes`) | Fix review, and the nodes above again on demand. | Same citation check and rules fallback per node; started by the person. | `eaos/ai/nodes/` |

Ranks 1 to 5 run inside every check once the person said yes (the visual review once the app was run and pictured). Ranks 6 to 8 already used the assistant before. Each AI
stage reports its calls, seconds, assistant and model to the live map; a node's record keeps its `calls`.

## Measured on a small project

Corpus project RendaPerene (45 cards, 5 milestones), Claude Code `claude-opus-5-5`, 2026-10-10:

| Stage | Calls | Seconds | Rules alone | With the assistant |
|---|---|---|---|---|
| `semantic` | 2 | 139 | No reading of responsibilities or causes | 8 hypotheses, 5 questions for the person |
| `ideal` | 2 | 820 | The rules' generic target | 60 cited elements over 7 views, 3 departures, 9 questions |
| `triage` | 2 | 114 | 45 cards, all shown as the engines wrote them | 28 confirmed, 16 doubted with what their evidence fails to show, 1 rejected |
| `order` | 2 | 104 | 5 groups, one per milestone, no reason | 17 steps with reasons: cards on the same file together, doubted cards after their probe, the rejected card set aside |

Limit seen: the triage reads the first 4 facts of a card. A hotspot card whose first facts were simple functions was
rejected although the same file is the subject of a confirmed complexity card.

Not built: the executive summary in plain words and choosing the screens and journeys to record. Neither was measured
yet, so neither is claimed.

## Where AI adds nothing

Facts, measurements, probes, load, plan waves and reports stay deterministic. Their value
is that they are reproducible, and a model would only make them less so.

## What the person sees

- In the live check map, the AI stages carry a small "AI" mark. Their panel shows that the person's assistant did the
  work, with the assistant, model and calls the stage reported, or the reason it was skipped.
- In the Studio, the planned ideal is shown with its provenance (assistant, model, time, departures from the rules,
  open questions). Without a plan, every view says plainly that it shows the rules' target.
