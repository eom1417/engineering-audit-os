# TASK-107 — 3 symbols share the same structure up to identifier names (internal/extractors/phpextractor/routes.go:246 .function_decl

> claim: CLM-410 · pattern: canonicalize · priority: 0.0094

> investigate · needs_review

No data for this section in this snapshot.

## The problem

3 symbols share the same structure up to identifier names (internal/extractors/phpextractor/routes.go:246 .function_decl

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-e41659a92f6083fb
- probes: PRB-107
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/extractors/phpextractor/routes.go, internal/extractors/scalaextractor/playroutes.go, internal/linkers/crossrepo/routeindex/routeindex.go
- مستوردون مباشرون (13): internal/engine/custom_client_example_test.go, internal/linkers/binders/unmatchedroutes/unmatchedroutes.go, internal/linkers/crossrepo/crossrepo_test.go, internal/linkers/crossrepo/resolution_invariant_test.go, internal/linkers/crossrepo/signals/http/alias_test.go, internal/linkers/crossrepo/signals/http/callers_test.go, internal/linkers/crossrepo/signals/http/http.go, internal/linkers/crossrepo/signals/http/http_test.go … (+5)
- غير مباشرين (10): cmd/enola/main.go, internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/engine_race_test.go, internal/engine/engine_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go … (+2)
- تدفقات مارّة: —
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
| human review / مراجعة هندسية | CLM-410: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
