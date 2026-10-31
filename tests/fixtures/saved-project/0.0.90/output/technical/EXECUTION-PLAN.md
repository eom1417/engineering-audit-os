# Execution plan

## Summary

Decision asked for: staff the first milestone (stabilize).

### The numbers that matter

- 3 cards (plan.json → tasks)
- 3 ready, with an acceptance command that decides (plan.json →
  tasks[].decision.readiness)
- S 3 (plan.json → tasks[].effort)
- 0 cards your assistant rejected left the plan; 0 design cards came from the
  screens (cards.json → set\_aside, cards.json → design)
- Order: the rules' waves (plan.json → order.source, PLAN/STEPS.md)

### The largest risks

- 0 investigation cards wait for a recorded decision (eaos decision-review).

## Milestones

### M01 · stabilize

No known-vulnerable version, broken reference, dead code or open access gap
remains. Exit: Every card here passes its acceptance command, and the next audit
raises none of these claims.

- TASK-001 [S/backend] unreachable module `app/old_export.py`: no production
  entry point imports it
- TASK-002 [S/backend] unreachable module `app/old_mail.py`: no production entry
  point imports it
- TASK-003 [S/backend] unreachable module `app/old_report.py`: no production
  entry point imports it

## Sections

- backend: 3 cards

## Recommendation

Run each card in an isolated copy, run its acceptance command, then audit again;
each card states its rollback.

## Not examined

- No card has run against the project yet; execution needs the owner's
  authorization.json.

## Appendices

- [PLAN/STEPS.md](PLAN/STEPS.md)
- [PLAN/WAVES.md](PLAN/WAVES.md)
