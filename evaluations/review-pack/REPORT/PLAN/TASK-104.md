# TASK-104 — 6 symbols share the same structure up to identifier names (internal/extractors/javaextractor/spring.go:316 .function_dec

> claim: CLM-511 · pattern: canonicalize · priority: 0.011

> investigate · needs_review

No data for this section in this snapshot.

## The problem

6 symbols share the same structure up to identifier names (internal/extractors/javaextractor/spring.go:316 .function_dec

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-b99fb87dbf275791
- probes: PRB-104
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/extractors/javaextractor/spring.go, internal/extractors/pythonextractor/resolve.go, internal/extractors/rubyextractor/resolve.go, internal/extractors/tsextractor/ts.go, internal/linkers/crossrepo/routeindex/routeindex.go, pkg/command/backfill.go
- مستوردون مباشرون (14): cmd/enola/main.go, internal/engine/custom_client_example_test.go, internal/linkers/binders/unmatchedroutes/unmatchedroutes.go, internal/linkers/crossrepo/crossrepo_test.go, internal/linkers/crossrepo/resolution_invariant_test.go, internal/linkers/crossrepo/signals/http/alias_test.go, internal/linkers/crossrepo/signals/http/callers_test.go, internal/linkers/crossrepo/signals/http/http.go … (+6)
- غير مباشرين (10): internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/engine_race_test.go, internal/engine/engine_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go, internal/explainers/messagingcoverage/integration_test.go … (+2)
- تدفقات مارّة: FLOW-020 log
- اختبارات مغطية: internal/engine/custom_client_example_test.go, internal/engine/engine_test.go, internal/linkers/binders/registry_test.go, internal/linkers/crossrepo/contract_test.go, internal/linkers/crossrepo/crossrepo_test.go, internal/linkers/crossrepo/resolution_invariant_test.go, internal/linkers/crossrepo/signals/http/alias_test.go, internal/linkers/crossrepo/signals/http/callers_test.go … (+5)
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
| human review / مراجعة هندسية | CLM-511: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
