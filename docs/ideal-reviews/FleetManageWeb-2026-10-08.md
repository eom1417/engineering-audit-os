# FleetManageWeb: the planned ideal against the rules-only target (2026-10-08)

The first real planning run of NS46.T14 (docs/STUDIO.md D10). The run was made by `tools/ideal_trial.py` from a frozen
copy of `418f40a`, on a copy of the check of FleetManageWeb at `e0e2576` that the integration had exported. It used
Claude Code 2.1.285 headless with the model `claude-opus-5-5`, in two passes: a plan, then a critique that returns the
revised ideal. The bundle was 193 KB. Both passes took 18 minutes in all. None of the project's code ran; its README
was read as untrusted data. The record is `$EAOS_MEASURE/ideal/FleetManageWeb/run.json`, and the table view by view is
`comparison.md` beside it.

## Numbers

| View | Rules elements | Planned | Same op | Changed op | Added | Departures | Questions |
|---|---|---|---|---|---|---|---|
| system | 76 | 24 | 19 | 4 | 1 | 5 | 2 |
| change | 35 | 9 | 3 | 4 | 2 | 2 | 0 |
| journeys | 46 | 12 | 7 | 5 | 0 | 0 | 3 |
| paths | 44 | 16 | 16 | 0 | 0 | 0 | 0 |
| data_paths | 37 | 17 | 1 | 16 | 0 | 0 | 2 |
| infra | 9 | 10 | 8 | 1 | 1 | 1 | 5 |
| pipeline | 0 | 0 (the summary says it is not a pipeline) | | | | | |
| plan_order | 7 | 15 | 12 | 0 | 3 | 3 | 1 |

- **Elements and evidence.** The plan kept 103 elements, and the share with evidence is **1.0**. It was 1.0 before the
  check and 1.0 in the draft too: the evidence check dropped nothing, and no citation was unresolved.
- **The citations.** There are 590 in all: 294 facts, 263 cards, 25 rules and 8 claims.
- **The critique.** It found 9 misses, 11 risks and 6 order issues, and the revised ideal acts on them. One example: a
  delete batch must not take `SubscriptionGate` while the owner has not answered about it.
- **Questions.** 13 open questions went to the Decisions inbox.

## What the plan adds over the rules

1. **It plans what the rules cannot.**
   - *Journeys.* The rules give screens no target. The plan groups the 46 routes into 12 user journeys and names the
     duplicates (`/` and `/ai-chat` declared twice, `/fuel` with `/operations/fuel`, `/reset` with
     `/reset-password`). It refuses to pick a winner before behaviour-lock tests exist, and asks the owner instead.
   - *Data.* The rules list the 37 stores with no target. The plan gives each store one owner module in `api-client`,
     marks the stores that only dead code reaches for deletion, and raises two questions: whether `/trucks` is the same
     resource as `/equipment`, and whether the Supabase tables are still live.
2. **Its departures are grounded.** There are 11, and each says what the rule says, what the plan chose, and why.
   - The rules kept `dashboard` and `sidebar` as they are. The plan removes their unreachable files (deadcode facts).
   - The rules wanted six new feature components. The plan merges `operations` into `fuel` and `home` into `dashboard`,
     because the routes show they are the same page.
   - The rules rebuild `src/hooks`. The plan keeps `use-toast` (57 importers) and moves the rest to their features.
3. **It caught a mistake in the rules.**
   - *What the rules said.* The infrastructure baseline said "CI present: keep GitHub Actions (5 steps)".
   - *What the facts show.* The 5 "CI steps" are npm scripts in `package.json`. No workflow runs on a push, and none
     runs tests.
   - *What the plan did.* It introduces a workflow and records why. This is an engine defect in `runtime` `ci_step`
     facts: npm scripts are read as CI. It is worth a card of its own.
4. **It orders the work better.**
   - It adds a re-measure step after the deletions, and an owner-decision gate between M02 and M03, since M03 needs
     answers on Supabase, `/`, Motive and the API contract.
   - It moves monitoring before the rebuilds.
   - It closes TASK-113 and TASK-114 together with TASK-078, which breaks the same cycle, instead of leaving them in M07.

## Where it is weaker, or not yet proven

- **Coarser than the rules.** There are 103 elements against 254 in the rules. The plan restates what it changes, not
  every unchanged component, and some elements group several stores or files ("the stores with one owner stay"). The
  Studio keeps both layers, so nothing of the rules is hidden, but an element-by-element "same/changed" count only
  covers what the plan names.
- **The check proves that a citation exists, not that it fits.** I read 8 elements at random against their facts. Seven
  cite exactly what they claim (the route facts for the duplicate routes, the deadcode findings for the deletions, the
  data-access sites for each store). One is weak: "Playwright and Vitest" cites flows whose trace stops, which is
  related but indirect.
- **The check had nothing to drop here.** Its dropping is proven by the unit tests and by the acceptance test (an
  injected invented element is dropped), not by this run.
- **Some semantic merges need a person or a probe.** One example is `http:operators` with `http:drivers`. The plan
  marks the risky ones as questions or as "if it proves so". It does not claim them.
- **One project, one assistant.** Codex, the other three projects and EAOS's own roadmap are the re-plan task's
  (replan-targets).
