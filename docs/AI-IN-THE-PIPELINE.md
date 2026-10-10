# AI in the pipeline

Where the person's own assistant (Claude Code or Codex, `eaos/runtime/assistants.py`) makes EAOS's outcome better,
and how each use is bounded. The rules stay the baseline everywhere: the assistant adds to them and never replaces
them.

## The bounds every AI step keeps

1. **Citations.** Every output cites ids of this report: facts (`FACT-`), claims (`CLM-`), cards (`TASK-`) or rules
   (`RULE-`). A deterministic check drops an output whose citations do not resolve, and lists it.
2. **Hypotheses.** What the assistant says never reaches CONFIRMED by itself. Only a probe can raise it.
3. **A fallback.** No assistant, a "no" to the consent question, a timeout, a failure, or an answer outside the
   schema: the step is recorded as unavailable with its reason, the rules' result stands, and the check never fails
   because of AI.
4. **A budget.** Calls and seconds are capped per step (below). The project's text is untrusted data, never
   instructions.
5. **Consent.** The person is asked once whether the check may use their assistant (question `use_assistant`, kept
   in the project's state; `eaos start --yes` answers it, and the MCP `audit` passes the person's answer as
   `use_assistant`).

## The steps, ranked by value

| Rank | Step | What AI adds | Bounds | Where |
|---|---|---|---|---|
| 1 | Ideal planning (check stage `ideal`) | The target of every view, planned on top of the rules' target and then critiqued (what was missed, risks, order). The rules alone give a generic target. | Plan + critique passes; elements without a resolving citation are dropped; node budget 2400 s and 10 USD; the result is cached on the same inputs. | `eaos/studio/ideal.py`, node `ideal_planner` |
| 2 | Semantic reading (check stage `semantic`) | Responsibilities, boundaries, contracts and root causes, which no rule can read from facts. | At most 3 rounds, one call of up to 600 s each; invented fact ids are sent back and the answer is rejected if they stay; every claim is a HYPOTHESIS with a falsifier. | `eaos/semantic.py` |
| 3 | Setup (`eaos next`, step `ready`) | How to start an unfamiliar app when detection fails. | Proposals are tried in an isolated copy and refused when unsafe. | `eaos/live_setup.py` |
| 4 | Fixes | Writing the change a card asks for. | The gates and the behaviour lock judge every change; it reaches the project only as a branch. | `eaos/agent_tools.py` `fix_*` |
| 5 | AI nodes from the Studio (`run_nodes`) | Card triage, pipeline gaps, plan order and fix review. | Same citation check, rules fallback and budget per node; started by the person. | `eaos/studio/nodes/` |

Ranks 1 and 2 run inside every check once the person said yes. Ranks 3 to 5 already used the assistant before this
change.

## Where AI adds nothing

Facts, measurements, probes, load, sustainability, plan waves, reports and validation stay deterministic. Their value
is that they are reproducible, and a model would only make them less so.

## What the person sees

- In the live check map, the AI stages carry a small "AI" mark. Their panel shows that the person's assistant did the
  work, with the assistant, model and calls the stage reported, or the reason it was skipped.
- In the Studio, the planned ideal is shown with its provenance (assistant, model, time, departures from the rules,
  open questions). Without a plan, every view says plainly that it shows the rules' target.
