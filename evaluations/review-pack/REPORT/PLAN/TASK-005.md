# TASK-005 — Flow FLOW-004 (cli baseline) stops at 4 unresolvable calls

> claim: CLM-531 · pattern: trace_gap · priority: 0.0729

> investigate · needs_review

No data for this section in this snapshot.

## The problem

Flow FLOW-004 (cli baseline) stops at 4 unresolvable calls

The behavior of this entry point is not fully visible from source alone.

## Evidence

- facts: FACT-d8348682ea77ab14
- probes: PRB-005
- falsifier: A resolver or runtime trace that follows those calls to their targets.

## Blast radius

- files: pkg/command/command.go
- مستوردون مباشرون (0): —
- غير مباشرين (0): —
- تدفقات مارّة: FLOW-004 baseline, FLOW-005 blame, FLOW-008 check, FLOW-009 cluster, FLOW-010 constraints, FLOW-011 coverage, FLOW-012 dashboard, FLOW-013 diff … (+10)
- اختبارات مغطية: —
- executed coverage: —
- شركاء التغيير: —

## Options

| Option | Cost | Verdict |
|---|---|---|
| Investigate the requirement | unknown | Determine repair or retain |
| Keep current design | unknown | Valid outcome if no violation is established |

## Proposed change

Establish or refute this observation before changing code: A resolver or runtime trace that follows those calls to their targets.

## Acceptance criterion

| Command | Expected |
|---|---|
| human review / مراجعة هندسية | CLM-531: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. A resolver or runtime trace that follows those calls to their targets. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
