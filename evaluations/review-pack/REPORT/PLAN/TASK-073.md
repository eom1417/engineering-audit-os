# TASK-073 — 7 symbols share the same structure up to identifier names (internal/explainers/importclosure/graph.go:143 .function_decl

> claim: CLM-517 · pattern: canonicalize · priority: 0.0199

> investigate · needs_review

No data for this section in this snapshot.

## The problem

7 symbols share the same structure up to identifier names (internal/explainers/importclosure/graph.go:143 .function_decl

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-accd659dd6648a97
- probes: PRB-073
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/explainers/importclosure/graph.go, internal/explainers/queryloops/queryloops.go, internal/extractors/javaextractor/java.go, internal/extractors/rubyextractor/associations.go, internal/extractors/scalaextractor/resolve.go, internal/metrics/metrics.go, internal/orphans/orphans.go
- مستوردون مباشرون (6): internal/engine/conceptedgematrix_test.go, internal/engine/filecensus_test.go, internal/engine/unseen_test.go, internal/perf/deference_test.go, internal/perf/perf.go, pkg/bootstrap/bootstrap.go
- غير مباشرين (10): cmd/enola/main.go, internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go … (+2)
- تدفقات مارّة: —
- اختبارات مغطية: internal/engine/clientspec_cache_test.go, internal/engine/conceptedgematrix_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/filecensus_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go … (+13)
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
| human review / مراجعة هندسية | CLM-517: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
