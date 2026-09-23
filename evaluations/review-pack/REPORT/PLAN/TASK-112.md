# TASK-112 — 2 symbols share the same structure up to identifier names (pkg/command/log.go:508 .function_declaration, pkg/history/his

> claim: CLM-347 · pattern: canonicalize · priority: 0.0052

> investigate · needs_review

No data for this section in this snapshot.

## The problem

2 symbols share the same structure up to identifier names (pkg/command/log.go:508 .function_declaration, pkg/history/his

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-9a05a755f114edf2
- probes: PRB-114
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: pkg/command/log.go, pkg/history/history.go
- مستوردون مباشرون (0): —
- غير مباشرين (0): —
- تدفقات مارّة: FLOW-005 blame, FLOW-013 diff, FLOW-016 gc, FLOW-020 log, FLOW-025 show
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
| human review / مراجعة هندسية | CLM-347: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
