# TASK-004 — 4 symbols share the same structure up to identifier names (internal/factpath/factpath.go:46 .function_declaration, inter

> claim: CLM-477 · pattern: canonicalize · priority: 0.1348

> investigate · needs_review

No data for this section in this snapshot.

## The problem

4 symbols share the same structure up to identifier names (internal/factpath/factpath.go:46 .function_declaration, inter

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-3322c65ce5def288
- probes: PRB-004
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/factpath/factpath.go
- مستوردون مباشرون (79): internal/explainers/layers/declared.go, internal/extractors/ansibleextractor/ansible.go, internal/extractors/asyncapiextractor/asyncapi.go, internal/extractors/asyncapiextractor/schema.go, internal/extractors/cppextractor/cpp.go, internal/extractors/cppextractor/cpp_ast.go, internal/extractors/dartextractor/dart.go, internal/extractors/dartextractor/dart_ast.go … (+71)
- غير مباشرين (10): cmd/enola/main.go, internal/engine/clientspec_cache_test.go, internal/engine/conceptedgematrix_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/detect_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go … (+2)
- تدفقات مارّة: —
- اختبارات مغطية: internal/engine/conceptedgematrix_test.go, internal/engine/detect_test.go, internal/engine/intent_test.go, internal/engine/layergate_e2e_test.go, internal/engine/method_ownership_test.go, pkg/check/intersection_test.go
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
| human review / مراجعة هندسية | CLM-477: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
