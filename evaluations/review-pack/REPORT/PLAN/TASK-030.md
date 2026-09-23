# TASK-030 — 11 symbols share the same structure up to identifier names (internal/extractors/goextractor/storage.go:129 .function_dec

> claim: CLM-004 · pattern: canonicalize · priority: 0.053

> investigate · needs_review

No data for this section in this snapshot.

## The problem

11 symbols share the same structure up to identifier names (internal/extractors/goextractor/storage.go:129 .function_dec

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-77cf8720e027f0e2
- probes: PRB-030
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/extractors/goextractor/storage.go, internal/extractors/mdintent/document.go, internal/factpath/factpath.go, internal/facts/intern_test.go, internal/litfold/litfold.go, internal/mining/render.go, internal/orphans/orphans.go, internal/perf/perf.go … (+2)
- مستوردون مباشرون (109): internal/engine/detect_test.go, internal/engine/intent_test.go, internal/explainers/layers/declared.go, internal/extractors/ansibleextractor/ansible.go, internal/extractors/asyncapiextractor/asyncapi.go, internal/extractors/asyncapiextractor/schema.go, internal/extractors/cppextractor/cpp.go, internal/extractors/cppextractor/cpp_ast.go … (+101)
- غير مباشرين (10): cmd/enola/main.go, internal/engine/clientspec_cache_test.go, internal/engine/conceptedgematrix_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/history.go … (+2)
- تدفقات مارّة: —
- اختبارات مغطية: internal/engine/clientspec_cache_test.go, internal/engine/conceptedgematrix_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/detect_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/intent_test.go … (+29)
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
| human review / مراجعة هندسية | CLM-004: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
