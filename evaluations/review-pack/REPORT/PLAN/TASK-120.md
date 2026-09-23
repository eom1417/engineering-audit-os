# TASK-120 — 2 symbols share the same structure up to identifier names (pkg/command/blame.go:252 .function_declaration, pkg/history/p

> claim: CLM-345 · pattern: canonicalize · priority: 0.0031

> investigate · needs_review

No data for this section in this snapshot.

## The problem

2 symbols share the same structure up to identifier names (pkg/command/blame.go:252 .function_declaration, pkg/history/p

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-d41c3b5fe6567077
- probes: PRB-124
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: pkg/command/blame.go, pkg/history/patch.go
- مستوردون مباشرون (0): —
- غير مباشرين (0): —
- تدفقات مارّة: FLOW-005 blame, FLOW-013 diff
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
| human review / مراجعة هندسية | CLM-345: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
