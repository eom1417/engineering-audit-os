# TASK-077 — 6 symbols share the same structure up to identifier names (internal/explainers/crossrepo/crossrepo.go:156 .function_decl

> claim: CLM-505 · pattern: canonicalize · priority: 0.0193

> investigate · needs_review

No data for this section in this snapshot.

## The problem

6 symbols share the same structure up to identifier names (internal/explainers/crossrepo/crossrepo.go:156 .function_decl

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-fe607c04c89ec780
- probes: PRB-077
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/explainers/crossrepo/crossrepo.go, internal/explainers/deadmethods/deadmethods.go, internal/explainers/queryloops/queryloops.go, internal/extractors/tsextractor/ember.go, internal/linkers/binders/clientseam/clientseam.go, internal/linkers/binders/emberresolver/emberresolver.go
- مستوردون مباشرون (5): internal/orphans/deference_test.go, internal/orphans/orphans.go, internal/perf/deference_test.go, internal/perf/perf.go, pkg/bootstrap/bootstrap.go
- غير مباشرين (10): cmd/enola/main.go, internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go … (+2)
- تدفقات مارّة: —
- اختبارات مغطية: internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go, internal/explainers/messagingcoverage/integration_test.go … (+11)
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
| human review / مراجعة هندسية | CLM-505: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
