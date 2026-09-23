# TASK-086 — 4 symbols share the same structure up to identifier names (internal/extractors/cppextractor/cpp.go:799 .function_declara

> claim: CLM-466 · pattern: canonicalize · priority: 0.0178

> investigate · needs_review

No data for this section in this snapshot.

## The problem

4 symbols share the same structure up to identifier names (internal/extractors/cppextractor/cpp.go:799 .function_declara

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-af8cef5796ce4ae8
- probes: PRB-086
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/extractors/cppextractor/cpp.go, internal/extractors/tsextractor/ember.go, internal/extractors/tsextractor/svelte.go, internal/extractors/tsextractor/vue.go
- مستوردون مباشرون (2): internal/engine/detect_test.go, pkg/bootstrap/bootstrap.go
- غير مباشرين (10): cmd/enola/main.go, internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go … (+2)
- تدفقات مارّة: —
- اختبارات مغطية: internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/detect_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go … (+10)
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
| human review / مراجعة هندسية | CLM-466: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
