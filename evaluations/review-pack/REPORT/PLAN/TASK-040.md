# TASK-040 — 2 symbols share the same structure up to identifier names (internal/diff/counts.go:417 .method_declaration, internal/dif

> claim: CLM-020 · pattern: canonicalize · priority: 0.0282

> investigate · needs_review

No data for this section in this snapshot.

## The problem

2 symbols share the same structure up to identifier names (internal/diff/counts.go:417 .method_declaration, internal/dif

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-ba9f86a076a9f725
- probes: PRB-040
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/diff/counts.go
- مستوردون مباشرون (34): internal/conformance/conformance.go, internal/conformance/conformance_test.go, internal/drift/drift.go, internal/engine/baseline_e2e_test.go, internal/engine/history.go, internal/engine/history_summarize_once_test.go, internal/engine/layergate_e2e_test.go, internal/server/server.go … (+26)
- غير مباشرين (3): cmd/enola/main.go, pkg/command/dashboard.go, pkg/dashboard/dashboard.go
- تدفقات مارّة: —
- اختبارات مغطية: internal/conformance/conformance_test.go, internal/engine/baseline_e2e_test.go, internal/engine/history_summarize_once_test.go, internal/engine/layergate_e2e_test.go, pkg/check/advisorynote_test.go, pkg/check/census_test.go, pkg/check/check_test.go, pkg/check/e2e_test.go … (+10)
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
| human review / مراجعة هندسية | CLM-020: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
