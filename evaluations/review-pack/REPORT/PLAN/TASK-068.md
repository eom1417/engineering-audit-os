# TASK-068 — 59 symbols share the same structure up to identifier names (internal/engine/detect_test.go:132 .method_declaration, inte

> claim: CLM-500 · pattern: canonicalize · priority: 0.0208

> investigate · needs_review

No data for this section in this snapshot.

## The problem

59 symbols share the same structure up to identifier names (internal/engine/detect_test.go:132 .method_declaration, inte

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-01a8b5c4f8a55f41
- probes: PRB-068
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/engine/detect_test.go, internal/explainers/complexity/complexity.go, internal/explainers/constraints/constraints.go, internal/explainers/coverage/coverage.go, internal/explainers/crossrepo/crossrepo.go, internal/explainers/cycles/cycles.go, internal/explainers/depth/depth.go, internal/explainers/domain/domain.go … (+51)
- مستوردون مباشرون (22): internal/engine/baseline_e2e_test.go, internal/engine/cluster_receipts_test.go, internal/engine/custom_client_example_test.go, internal/engine/defer_linking_test.go, internal/engine/engine_test.go, internal/engine/freeze_publication_test.go, internal/engine/history_e2e_test.go, internal/engine/restore_test.go … (+14)
- غير مباشرين (10): cmd/enola/main.go, internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go, internal/explainers/messagingcoverage/integration_test.go … (+2)
- تدفقات مارّة: FLOW-015 endpoint
- اختبارات مغطية: internal/engine/baseline_e2e_test.go, internal/engine/clientspec_cache_test.go, internal/engine/cluster_receipts_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/defer_linking_test.go, internal/engine/engine_race_test.go, internal/engine/engine_test.go … (+26)
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
| human review / مراجعة هندسية | CLM-500: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
