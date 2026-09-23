# TASK-121 — 2 symbols share the same structure up to identifier names (internal/history/blobs.go:179 .function_declaration, internal

> claim: CLM-278 · pattern: canonicalize · priority: 0.0018

> investigate · needs_review

No data for this section in this snapshot.

## The problem

2 symbols share the same structure up to identifier names (internal/history/blobs.go:179 .function_declaration, internal

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-406d4f77c05cb11c
- probes: PRB-125
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/history/blobs.go, internal/history/blobs_test.go
- مستوردون مباشرون (4): internal/engine/history.go, pkg/command/backfill.go, pkg/command/gc.go, pkg/command/history.go
- غير مباشرين (1): cmd/enola/main.go
- تدفقات مارّة: —
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
| human review / مراجعة هندسية | CLM-278: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
