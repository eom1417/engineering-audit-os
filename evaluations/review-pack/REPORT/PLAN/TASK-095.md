# TASK-095 — 8 symbols share the same structure up to identifier names (internal/extractors/hclextractor/hcl.go:44 .method_declaratio

> claim: CLM-526 · pattern: canonicalize · priority: 0.0172

> investigate · needs_review

No data for this section in this snapshot.

## The problem

8 symbols share the same structure up to identifier names (internal/extractors/hclextractor/hcl.go:44 .method_declaratio

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-f7f02e31f37eb6cc
- probes: PRB-095
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/extractors/hclextractor/hcl.go, internal/extractors/javaextractor/java.go, internal/extractors/kotlinextractor/kotlin.go, internal/extractors/phpextractor/php.go, internal/extractors/pythonextractor/python.go, internal/extractors/rustextractor/rust.go, internal/extractors/scalaextractor/scala.go, internal/extractors/swiftextractor/swift.go
- مستوردون مباشرون (1): pkg/bootstrap/bootstrap.go
- غير مباشرين (10): cmd/enola/main.go, internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go … (+2)
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
| human review / مراجعة هندسية | CLM-526: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
