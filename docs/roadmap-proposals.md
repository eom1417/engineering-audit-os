# EAOS roadmap: proposals for the owner

A planning pass and a critique pass over EAOS's own roadmap (`docs/north-star.json`) and the Studio master plan, made by `tools/roadmap_review.py` (NS46.T16). **Every proposal is a decision for the owner. None has been applied**; the plan changes only after the owner approves a proposal, as a new planning step.

Planned by Claude Code (claude-opus-5-5) at 2026-10-09T03:26:59+00:00; passes plan, critique; 12 proposals kept, 0 dropped by the evidence check; share with evidence 1.0 (before the check 1.0).

The draft gets the main finding right: most of the roadmap's problems are bookkeeping, not direction. But several proposals need fixing before the owner sees them.

Errors and conflicts with owner decisions:
- P01 asks for E2 to become NS20's goal, but NS20's goal already includes it.
- P01 misses that R6's exit needs E7 and E2, which only NS20 moves, and NS20 is in R7. So R6 can never close as written.
- P02's option to reset F16 to null would lower a measured number. D7 says the share of the Studio not yet measured (F12) may only fall, and NS1 refuses any regression.
- P02 wants NS36.T3 marked done without noticing that its own dependency, NS36.T2, is still todo.
- P04 drops NS37.T1 even though D6 names NS37.T1 as the task that builds the approved design system. That is an owner decision, and NS46 has no task that takes it over.
- P04 also lowers NS37's weight without saying where the 2 points go, and leaves NS37.T2 with no dependency.

Conflicts between proposals:
- P05 enforces Studio-first (D7) through dependencies, while P09, P10 and P12 start other work outside the Studio early, with no shared rule for what counts as engine work.
- P06 adds a quality gate in front of NS46.T8. But the draft never notices that NS46.T8 already waits on NS46.T14, T15 and T16, which are not part of the exit gate the owner defined in D7, D8 and D9.

What the draft missed:
- NS27's goal (B1–B4) is fully met but NS27 is not done: the mirror image of NS9.
- The re-plan evidence has numbers behind it. Elements found only by the rules outnumber matching elements on every project; FleetManageWeb records 0 departures although its critique shows unrecorded ones; and the pipeline view was never planned on FleetManageWeb or chief-ops.

The revision:
- Folds the NS27 fix into P01 and the 10-project corpus point into P07.
- Takes P07's merge of NS31.T2 out: it rests on a master-plan proposal, not an owner decision.
- Points P11 at a weight source other than C8.
- Adds one proposal (P13) that lines NS46.T8 up with the exit gate the owner actually defined.

| Id | Kind | Proposal | Cites | Decision |
|---|---|---|---|---|
| P01 | gate | A done flag must match its goal both ways: NS9 is done with E2 = 0.0, NS27 is open with B1–B4 met | NS9, NS9.T1, E1, E2, NS20 | waiting |
| P02 | gate | Indicators at target while their tasks are todo: settle F10 and F16 without lowering a measured number | F10, NS36.T3, NS36.T2, NS36, F8 | waiting |
| P03 | merge | Contract v2 is defined twice: NS46.T1 owns it, NS39.T3 only fills it | NS46.T1, NS39.T3, NS39.T2, NS39.T1, N1 | waiting |
| P04 | rescope | NS37 overlaps NS46: hand its pages and the design system to NS46, keep the live stream and one source of truth | NS37, NS37.T1, NS37.T2, NS37.T3, NS37.T4 | waiting |
| P05 | gate | Write Studio-first (D7) into the dependencies, and have the owner rule once on what counts as engine work | NS46.T8, NS38.T1, NS38.T2, NS34.T1, NS20.T1 | waiting |
| P06 | gate | The planned ideal needs a completeness and fabrication gate on NS46.T16, and a complete input bundle on NS46.T14 | NS46.T14, NS46.T16, NS42.T1, NS42.T2, I1 | waiting |
| P07 | rescope | NS38.T1's labelled set: add the detector errors the critique found, and fix the holdout projects (NS10.T1) first | NS38.T1, A1, A2, S5, NS10.T1 | waiting |
| P08 | reorder | Split agent_tools (NS32.T1) before the action API (NS46.T9) wires every tool to a button | NS32.T1, NS32.T2, NS43.T2, NS46.T9, NS46.T10 | waiting |
| P09 | reorder | Archive before delete (NS33.T1) should not wait behind the plans chain | NS33, NS33.T1, NS32.T3, D3, D4 | waiting |
| P10 | rescope | NS46.T8 waits on tasks the owner never put in the Studio exit gate | NS46.T8, NS46.T7, NS46.T11, NS46.T12, NS46.T13 | waiting |
| P11 | reweight | Studio indicators are scored inside C12 (weight 5) although Studio milestones carry 17 | C12, C11, C8, F1, F11 | waiting |
| P12 | reorder | Start the proof that a transformation happened (NS20.T1) alongside R6G, if the owner allows | NS20, NS20.T1, NS9.T1, E7, E2 | waiting |

## P01: A done flag must match its goal both ways: NS9 is done with E2 = 0.0, NS27 is open with B1–B4 met

- **Kind:** gate
- **What changes:** (1) NS9's goal is 'E1 = 1.0 and E2 ≥ 0.8', but E2 = 0.0 while NS9 is done. Change NS9's goal to 'E1 = 1.0'. NS20's goal already reads 'E7 = 1 and E2 ≥ 0.8', so nothing needs to be added there. (2) Remove E7 and E2 from R6's exit and keep them in R7's exit. Today R6's exit names indicators that only NS20, an R7 milestone, moves, so R6 can never close. (3) NS27's goal (B1–B4) is fully at target, but NS27 stays open on NS27.T5, whose only open indicator is X7. Split NS27.T5 into a new milestone of weight 2 (the owner trial with both paths, moving X7) and mark NS27 done with weight 4. (4) Add a plan check that fails if a milestone is done while any indicator in its goal is below target, or open while every indicator in its goal is met.
- **Recommendation:** Apply all four. The changes are pure bookkeeping, and done_weight is the number the owner and the Studio read as progress. It goes from 23 to 27, and every point of it is backed by met indicators. Today only NS9 and NS27 would trip the check.
- **Risk:** The new milestone needs an id from the owner, since none can be invented here. Free-text goals in Arabic must be parsed into indicator lists for the check to work. If parsing is unreliable, add an explicit goal_indicators field instead of guessing.
- **Stands on:** NS9, NS9.T1, E1, E2, NS20, NS20.T1, E7, R6, R7, NS27, NS27.T5, B1, B2, B3, B4, X7
- **Decision:** waiting (approve / reject)
- **Applied:** no

## P02: Indicators at target while their tasks are todo: settle F10 and F16 without lowering a measured number

- **Kind:** gate
- **What changes:** F10 = 1.0 is recorded, and the owner approved Instrument on 2026-10-08 (D6), but NS36.T3 is todo and waits on NS36.T2, also todo. Mark NS36.T3 done, citing the owner's approval. Then either remove NS36.T2 from its depends_on (the mockups were drawn on the real report, not on the model) or confirm NS36.T2's real state. Move F8 off NS36.T3, because F8 is measured on the built Studio, not on mockups. F16 = 1.0 while NS46.T12, the engine that produces the map, is todo. Re-run F16's measurement: the map against hand-written truth files, and nothing invented on the app projects (D9). If it holds, record which part of NS46.T12 already shipped and narrow NS46.T12's scope to what remains. If it fails, record it as a regression. Do not reset F16 to null. Add a check that flags any indicator at target while every task that moves it is still todo.
- **Recommendation:** Close NS36.T3 now on the owner's decision, and fix the dependency it contradicts. Never set F16 to null: D7 says the unmeasured share F12 may only fall, and the regression guard (E3, NS1) exists to refuse exactly that.
- **Risk:** If the F16 measurement turns out to compare against a truth file written from the same code that produces the map, a 1.0 says little. The re-measure must use truth files written by reading the code by hand, as D9 requires.
- **Stands on:** F10, NS36.T3, NS36.T2, NS36, F8, NS37.T1, F16, NS46.T12, NS46.T13, F12, E3
- **Decision:** waiting (approve / reject)
- **Applied:** no

## P03: Contract v2 is defined twice: NS46.T1 owns it, NS39.T3 only fills it

- **Kind:** merge
- **What changes:** NS46.T1 ('data contract v2 and its fixtures') and NS39.T3 ('data contract v2') define the same contract. D7 says contract v2 is defined now, as additive sections, so that later engine work only fills data. Make NS46.T1 the only owner of the contract and add F2 to its moves. Rename NS39.T3 to 'fill the contract v2 sections from the store'. It keeps depends_on NS39.T2 and keeps moving N1, and F2 comes off its moves. NS39.T3 may propose new sections, but only additive ones.
- **Recommendation:** Merge. A second definition would drift from the version the Studio pages were tested against, which breaks D7's promise. Adding F2 to NS46.T1 keeps F2 moved by a live task once P04 drops NS37.T3.
- **Risk:** The system graph (NS39.T1) may need node or edge shapes the contract lacks. If a needed change cannot be additive, it must come back to the owner as a decision; it must not silently become contract v3.
- **Stands on:** NS46.T1, NS39.T3, NS39.T2, NS39.T1, N1, F2, F12, NS36.T2
- **Decision:** waiting (approve / reject)
- **Applied:** no

## P04: NS37 overlaps NS46: hand its pages and the design system to NS46, keep the live stream and one source of truth

- **Kind:** rescope
- **What changes:** NS46.T2 to NS46.T6 build every Studio page, and NS37.T3 builds the home, problems and decisions pages again. (1) Drop NS37.T3. (2) Drop NS37.T1, but D6 explicitly names NS37.T1 as the task that builds the blended design-system spec (eaos-dev/planning/studio-v2/directions/studio/DESIGN.md). Hand that job to NS46.T1 by name, or to a new NS46 task in front of NS46.T2–T6. (3) Keep NS37.T2, moving F9, and change its depends_on to [NS46.T8, NS39.T2]. Keep NS37.T4 (F7), depending on NS37.T2. NS45.T1 still depends on NS37.T2. (4) Move F4 to NS46.T7, which already moves F14. (5) Lower NS37 from 4 to 2 and give the 2 to NS46, so total_weight stays 100. (6) Re-point NS40.T3, NS41.T2 and NS42.T3 from NS37.T3 to NS46.T8, and reword each as 'fill the existing page with real data'.
- **Recommendation:** Apply it. It writes D7 into the plan. Say plainly to the owner that it changes D6 (who builds the design system) and the NS37 position in D3 and D5's order, and that D7 is the later decision this follows.
- **Risk:** NS37.T3 needed a human for the 'first real release' (MASTER-PLAN P3). The owner's review moves to NS46.T8. If the owner wanted a separate first-release checkpoint, it is lost.
- **Stands on:** NS37, NS37.T1, NS37.T2, NS37.T3, NS37.T4, NS46, NS46.T1, NS46.T2, NS46.T7, NS46.T8, NS40.T3, NS41.T2, NS42.T3, NS39.T2, NS45.T1, F4, F7, F8, F9, F14, R6G
- **Decision:** waiting (approve / reject)
- **Applied:** no

## P05: Write Studio-first (D7) into the dependencies, and have the owner rule once on what counts as engine work

- **Kind:** gate
- **What changes:** D7 says the engine roadmap resumes from NS38.T2 after the NS46 exit gate, but NS38.T2 depends only on NS38.T1. Add NS46.T8 to NS38.T2's depends_on. NS38.T1 stays free, as 'NS38.T2 onward' implies. Do the same for any engine task that P09 frees from its chain (NS34.T1). Then put one question to the owner: are NS20.T1 (re-auditing a transformation already done), NS33.T1 (archive before delete, a safety measure), NS10.T1 (building the corpus) and NS32.T1 (a refactor that keeps behaviour the same) 'engine work' under D7? The answer decides whether P08, P09, P12 and the NS10.T1 part of P07 may start before NS46.T8.
- **Recommendation:** Add the dependency, and get the single ruling first. Without it, some early work is blocked by a dependency and other early work only by a sentence, and the /eaos menu or status tool can suggest the wrong next step.
- **Risk:** Everything behind NS46.T8 waits on a human review. Combined with P13, the gate is at least limited to what the owner defined.
- **Stands on:** NS46.T8, NS38.T1, NS38.T2, NS34.T1, NS20.T1, NS33.T1, NS10.T1, NS32.T1, R6G, R7
- **Decision:** waiting (approve / reject)
- **Applied:** no

## P06: The planned ideal needs a completeness and fabrication gate on NS46.T16, and a complete input bundle on NS46.T14

- **Kind:** gate
- **What changes:** NS46.T14 and NS46.T16 move only F12. The re-plan results show large omissions. In the system view, elements found only by the rules outnumber matching elements on every project: EAOS 64 vs 22, FleetManageWeb 31 vs 11, chief-ops 57 vs 16, finance-os 51 vs 5. FleetManageWeb records 0 departures even though its critique finds unrecorded ones. The pipeline view fell back to rules on FleetManageWeb and chief-ops. The critiques name missing core parts, such as eaos/engines on EAOS, more than ten screens and five tables on FleetManageWeb, and the movimentacoes journey on finance-os. Proposed changes: (1) Add I2 (the ideal without fabrication) to NS46.T14's moves. (2) Make NS46.T16's acceptance include a new completeness measure, with an id from the owner: the share of baseline components, screens, tables and journeys that each planned view either covers or departs from with a written reason. Unrecorded departures count as failures. (3) Before planning, NS46.T14 checks that the bundle it sends is complete, the way MASTER-PLAN's BC1–BC7 checks would; this is the input side of I1. (4) Rescope NS42.T2 to reuse NS46.T14's planning, critique and evidence-check pipeline, keeping its three independent proposals and the comparison.
- **Recommendation:** Apply it. D10 asks for an ideal that was really thought through, and today's numbers show the planner drops most of the baseline without saying so. Gating on NS46.T16 rather than NS46.T8 keeps this compatible with P13.
- **Risk:** A coverage measure based on the baseline can push the planner to copy the baseline. Reasoned departures must count as covered, and the critique pass must check whether those reasons are real.
- **Stands on:** NS46.T14, NS46.T16, NS42.T1, NS42.T2, I1, I2, F12, W1
- **Decision:** waiting (approve / reject)
- **Applied:** no

## P07: NS38.T1's labelled set: add the detector errors the critique found, and fix the holdout projects (NS10.T1) first

- **Kind:** rescope
- **What changes:** (1) The EAOS critique found errors in EAOS's own detectors: phantom tables (an Arabic word, 'in', and tables from tests and semgrep rules), sqlalchemy models detected in acceptance/test_*.py, and semgrep rule files with hyphenated names reported as dead modules. FleetManageWeb's critique adds api:{dynamic}, a store whose owner cannot be seen. Add 'detector errors found by the critique pass become candidate labelled cases, confirmed by a person' to NS38.T1's scope (D11: a model's opinion is not a label). (2) Move NS10.T1 from R8 to R6G, before NS38.T1 starts labelling. NS10.T1 depends only on NS1.T2, which is done, and V4 = 0.3. Record the 3 holdout projects on day one and have every labelling and tuning step refuse to read them. The draft's merge of NS31.T2 into NS38 is withdrawn: it comes from MASTER-PLAN §8, which the owner has not approved, and D3 and D5 keep NS31 as its own step.
- **Recommendation:** Apply (1) now; it costs little and the errors are real. Apply (2) only if the owner, through P05's ruling, counts corpus building as outside 'engine work'. Its value is choosing the holdout projects before any tuning, not more projects for F13, whose five projects are already named in D7.
- **Risk:** If labelling starts before the holdout list is fixed, V4 means nothing later. If the owner keeps NS10.T1 in R8, NS38.T1 must still exclude whatever projects NS10.T1 will later hold out.
- **Stands on:** NS38.T1, A1, A2, S5, NS10.T1, V4, R8, R6G
- **Decision:** waiting (approve / reject)
- **Applied:** no

## P08: Split agent_tools (NS32.T1) before the action API (NS46.T9) wires every tool to a button

- **Kind:** reorder
- **What changes:** NS32.T1 ('split agent_tools before adding') waits on NS43.T2 (quality models), with which it has nothing to do. Under D8, NS46.T9 turns every MCP tool into a Studio action, building directly on agent_tools. Change NS32.T1's depends_on to [] and add NS32.T1 to NS46.T9's depends_on. Take L9 off NS32.T1's moves, since a refactor that keeps behaviour does not make a plan into a page; NS32.T2 keeps L9. NS32.T2 and NS32.T3 stay where they are.
- **Recommendation:** Move it, if the owner rules (P05) that a refactor that keeps behaviour is not engine work. Splitting before about forty tools are wired to buttons is cheaper than after. It also restores part of D3's order, which put NS32 early.
- **Risk:** It lengthens the critical path to F15. Keep NS32.T1 strictly behaviour-preserving, with the MCP trial as its acceptance check.
- **Stands on:** NS32.T1, NS32.T2, NS43.T2, NS46.T9, NS46.T10, F15, L9
- **Decision:** waiting (approve / reject)
- **Applied:** no

## P09: Archive before delete (NS33.T1) should not wait behind the plans chain

- **Kind:** reorder
- **What changes:** Safe-delete cards already ship (NS5.T4, D3 = 1.0) and real fixes have run (NS9.T1), but D4 (archive before delete) waits behind NS32.T3, which waits behind NS43 and NS42. Change NS33.T1's depends_on to []. It touches only git, is size M and needs a sandbox. Replace NS34.T1's dependency on NS33.T1 with NS46.T8, so that NS34's engine work still respects D7. NS44.T1 keeps NS33.T1.
- **Recommendation:** Move it forward as a safety measure in C4 (weight 10). This changes the owner's order in D5 (NS31 → NS33 → NS34), not only D7, so it needs the owner's explicit approval through P05's ruling.
- **Risk:** It goes against D5's order and possibly D7. MASTER-PLAN §8 instead proposes folding NS33 into the operations phase (P8), so the owner may prefer to keep it there.
- **Stands on:** NS33, NS33.T1, NS32.T3, D3, D4, NS5.T4, NS9.T1, NS34.T1, NS44.T1, NS46.T8, C4
- **Decision:** waiting (approve / reject)
- **Applied:** no

## P10: NS46.T8 waits on tasks the owner never put in the Studio exit gate

- **Kind:** rescope
- **What changes:** D7 defines the exit gate as F11, F13, F14 and the owner's review. D8 adds F15 and D9 adds F16. D10 (NS46.T14) and D11 (NS46.T15) add tasks but do not add them to the gate. D10's own fallback (the rules' target stays and the Studio says plainly that the ideal is not planned yet) is a valid coverage state under D7. NS46's goal lists only F11, F13, F14, F15, F16 and 'F12 measured', and NS46.T14, T15 and T16 move only F12. Remove NS46.T14, NS46.T15 and NS46.T16 from NS46.T8's depends_on. They stay in NS46 and keep their own acceptance, including P06's gate on NS46.T16.
- **Recommendation:** Apply it, so the gate is exactly what the owner defined and engine work (NS38.T2 onward) is not held behind the AI nodes of NS46.T15. Ask the owner to confirm, since NS46.T16 also comes from a later owner instruction (D10 part 2).
- **Risk:** If the owner meant every NS46 task to sit inside the gate, this goes against that intent, so the proposal asks before anything changes. The Studio may pass its gate while the ideal it shows still comes from the rules.
- **Stands on:** NS46.T8, NS46.T7, NS46.T11, NS46.T12, NS46.T13, NS46.T14, NS46.T15, NS46.T16, NS46, NS38.T2, F11, F12, F13, F14, F15, F16
- **Decision:** waiting (approve / reject)
- **Applied:** no

## P11: Studio indicators are scored inside C12 (weight 5) although Studio milestones carry 17

- **Kind:** reweight
- **What changes:** F1–F16 sit in C12, 'Continuity', at weight 5, alongside L1–L11, W1 and W2, 29 indicators in all. NS46 (10), NS36 (3) and NS37 (4) carry 17 milestone weight, so finishing NS46 barely moves any capability score. Add a capability, 'Studio: follow and operate EAOS from one place', holding F1–F16, at weight 6: take 3 from C12, which loses the F indicators, and 3 from C11, whose B1–B4 are all met. The draft's choice of C8 is withdrawn, because C8 is the vision's step 4.
- **Recommendation:** Re-file and version the weights. Tell the owner that moving weight from a capability whose indicators are all met to one that is mostly unmeasured lowers the headline capability score at once. That drop is honest, not a regression.
- **Risk:** Capability score history becomes hard to compare across versions. Keep both weight versions and report against each for a transition period.
- **Stands on:** C12, C11, C8, F1, F11, F12, F13, F14, F15, F16, NS46, NS36, NS37, L7
- **Decision:** waiting (approve / reject)
- **Applied:** no

## P12: Start the proof that a transformation happened (NS20.T1) alongside R6G, if the owner allows

- **Kind:** reorder
- **What changes:** The vision ends with 'every step proven by re-audit', but E7 and E2 are both 0.0. NS20.T1 depends only on NS9.T1, which is done, and NS21, NS22 and NS23 (all of R7) wait on it. Run NS20.T1 on the branch NS9.T1 produced, in parallel with NS46, as verification and not new engine code. NS21 to NS23 stay where they are.
- **Recommendation:** Do it only on the owner's explicit ruling (P05). It goes against D7 if verification counts as engine work. It is the cheapest way to get a first nonzero value for the vision's core proof.
- **Risk:** It competes with NS46 for sandbox time. A poor E7 result may call for engine fixes D7 defers, leaving a known failure unaddressed until after NS46.T8. The bundle does not say which project NS9.T1 ran on, so check that its branch still exists before planning.
- **Stands on:** NS20, NS20.T1, NS9.T1, E7, E2, NS21, NS22, NS23, R7, NS46.T8
- **Decision:** waiting (approve / reject)
- **Applied:** no

## The critique pass

- missed: R6's exit lists E7 and E2, but only NS20 moves them, and NS20 sits in R7. R6 cannot close no matter what happens to NS9. P01 fixed the milestone and left the stage inconsistent.
- missed: NS27 is the reverse of NS9: its goal (B1–B4) is fully at target, yet done = false because NS27.T5 is still open. Of the indicators NS27.T5 moves, only X7 is still open (null); X1, X2, X3 and X9 are already 1.0. A check that a done flag matches its goal has to work both ways.
- missed: NS46.T8 waits on NS46.T14, NS46.T15 and NS46.T16. D7, D8 and D9 define the exit gate as F11, F13, F14, F15, F16 and the owner's review. D10 and D11 add tasks but do not add them to the gate, and D10's fallback (the rules' target plus an honest 'not planned yet' state) is itself a valid coverage state. As written, the plan holds engine work behind AI-planning work the owner never put in the gate.
- missed: The re-plan numbers are stronger evidence than the critique quotes P06 used. Elements found only by the rules outnumber matching elements in the system view on every project (EAOS 64 vs 22, FleetManageWeb 31 vs 11, chief-ops 57 vs 16, finance-os 51 vs 5). FleetManageWeb records 0 departures although its critique shows unrecorded ones (src/components/common moved to ui). The pipeline view fell back to rules on FleetManageWeb and chief-ops.
- missed: The planner's omissions may start upstream, in the bundle the planner receives (I1, NS42.T1), not in the planner. P06 gated the output and not the input.
- missed: P04 left NS37.T2 without a dependency once NS37.T1 is dropped, and lowered NS37's weight without saying where the 2 points go, which would change total_weight (100).
- missed: P03 removes F2 from NS39.T3 and P04 drops NS37.T3, so F2 ends up moved only by NS36.T2. NS46.T1, which owns contract v2, does not move F2.
- missed: P10's reason was weak. F13's five projects are already named in D7 (FleetManageWeb, chief-ops, finance-os, EAOS and a synthetic project), and the 4 projects for NS38.T1 already exist. The real reason to start NS10.T1 early is to fix the holdout list before any labelling or tuning, so they cannot leak into it.
- missed: NS32.T1, a pure refactor, moves L9 ('a registered plan becomes a page'). Moving the task does not move L9, and P08 did not say so.
- risk: P02's option to reset F16 to null raises the share still unmeasured (F12), which D7 says may only fall, and NS1/E3 refuse regressions. Re-measure F16 first. If it really fails, report a recorded regression; do not quietly set it to null.
- risk: Marking NS36.T3 done while NS36.T2 is todo breaks the plan's own dependency order. Either NS36.T2's state is wrong, or the dependency should go because the mockups were drawn on the report and not on the model.
- risk: P04 drops NS37.T1, which D6 (owner, 2026-10-08) names as the task that builds the blended design-system spec. That goes against an owner decision unless the job is explicitly handed to an NS46 task.
- risk: P05 enforces D7 for the NS38 chain only. P09 (NS33.T1), P10 (NS10.T1) and P12 (NS20.T1) start work outside the Studio early. Without one owner ruling on what counts as engine work, the plan is inconsistent: some tasks are gated by a dependency and others only by a note.
- risk: P06 puts a new gate in front of NS46.T8, while P13 removes NS46.T14, T15 and T16 from NS46.T8. Put the completeness gate on NS46.T16's own acceptance so the two do not conflict.
- risk: P07's merge of NS31.T2 into NS38 rested on MASTER-PLAN §8, which is a proposal waiting for the owner, not an approved decision. D3 and D5 keep NS31 as its own step. It is removed from the revision.
- risk: P11 took 5 weight from C8, the vision's step 4 (the execution plan), whose indicators are all met. That lowers the overall score and shrinks a core vision deliverable to fund the Studio. The revision takes the weight from C11, also fully met, and from C12 instead, and says the headline score will drop.
- risk: P12 bundled two unrelated changes (starting NS20.T1 early and splitting NS27). The NS27 split moves to P01. P12 also assumed NS9 ran on FleetManageWeb, which the bundle does not state.
- risk: P09 changes the order the owner set in D5 (NS31 → NS33 → NS34), not only D7. The draft mentioned D7 only.
