# TASK-102 — 4 symbols share the same structure up to identifier names (internal/explainers/common/common.go:39 .function_declaration

> claim: CLM-460 · pattern: canonicalize · priority: 0.0117

> investigate · needs_review

No data for this section in this snapshot.

## The problem

4 symbols share the same structure up to identifier names (internal/explainers/common/common.go:39 .function_declaration

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-a1f2cecc2a76f848
- probes: PRB-102
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/explainers/common/common.go, internal/extractors/rubyextractor/resolve_test.go, internal/renderers/llmcontext/llm.go, pkg/explain/explain.go
- مستوردون مباشرون (2): cmd/enola/main.go, pkg/bootstrap/bootstrap.go
- غير مباشرين (10): internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go, internal/explainers/messagingcoverage/integration_test.go … (+2)
- تدفقات مارّة: —
- اختبارات مغطية: internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go, internal/explainers/messagingcoverage/integration_test.go … (+9)
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
| human review / مراجعة هندسية | CLM-460: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
