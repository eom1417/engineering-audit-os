# TASK-096 — 11 symbols share the same structure up to identifier names (pkg/command/blame.go:259 .method_declaration, pkg/command/ch

> claim: CLM-005 · pattern: canonicalize · priority: 0.0157

> investigate · needs_review

No data for this section in this snapshot.

## The problem

11 symbols share the same structure up to identifier names (pkg/command/blame.go:259 .method_declaration, pkg/command/ch

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-e11b20e346f28d7d
- probes: PRB-096
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: pkg/command/blame.go, pkg/command/check.go, pkg/command/constraints.go, pkg/command/coverage.go, pkg/command/dashboard.go, pkg/command/gc.go, pkg/command/history.go, pkg/command/log.go … (+2)
- مستوردون مباشرون (0): —
- غير مباشرين (0): —
- تدفقات مارّة: FLOW-004 baseline, FLOW-005 blame, FLOW-008 check, FLOW-010 constraints, FLOW-011 coverage, FLOW-012 dashboard, FLOW-013 diff, FLOW-014 doctor … (+7)
- اختبارات مغطية: —
- executed coverage: —
- شركاء التغيير: —

## Options

| Option | Cost | Verdict |
|---|---|---|
| Investigate the requirement | unknown | Determine repair or retain |
| Keep current design | unknown | Valid outcome if no violation is established |

## Proposed change

Establish or refute this observation before changing code: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Acceptance criterion

| Command | Expected |
|---|---|
| human review / مراجعة هندسية | CLM-005: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
