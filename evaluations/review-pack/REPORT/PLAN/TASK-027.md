# TASK-027 — 2 symbols share the same structure up to identifier names (internal/explainers/constraints/basis.go:36 .method_declarati

> claim: CLM-054 · pattern: canonicalize · priority: 0.0721

> investigate · needs_review

No data for this section in this snapshot.

## The problem

2 symbols share the same structure up to identifier names (internal/explainers/constraints/basis.go:36 .method_declarati

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-5f6c411e7c5d10d4
- probes: PRB-027
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/explainers/constraints/basis.go
- مستوردون مباشرون (16): internal/diff/diff.go, internal/diff/silencing.go, internal/engine/conceptedgematrix_test.go, internal/mining/roundtrip_test.go, internal/server/server.go, pkg/bootstrap/bootstrap.go, pkg/check/check.go, pkg/check/guidance.go … (+8)
- غير مباشرين (10): cmd/enola/main.go, internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go … (+2)
- تدفقات مارّة: —
- اختبارات مغطية: internal/engine/clientspec_cache_test.go, internal/engine/conceptedgematrix_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go … (+13)
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
| human review / مراجعة هندسية | CLM-054: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
