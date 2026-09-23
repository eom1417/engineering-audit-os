# TASK-067 — 7 symbols share the same structure up to identifier names (internal/diff/diff.go:978 .function_declaration, internal/ext

> claim: CLM-515 · pattern: canonicalize · priority: 0.0209

> investigate · needs_review

No data for this section in this snapshot.

## The problem

7 symbols share the same structure up to identifier names (internal/diff/diff.go:978 .function_declaration, internal/ext

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-c2e719d960bf3c71
- probes: PRB-067
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/diff/diff.go, internal/extractors/goextractor/testrefs.go, internal/extractors/rubyextractor/resolve.go, internal/linkers/binders/frameworkroots/frameworkroots.go, internal/linkers/crossrepo/signals/sharedcode/sharedcode.go, internal/orphans/orphans.go, internal/providers/rubydex/provider.go
- مستوردون مباشرون (7): internal/engine/engine_test.go, internal/explainers/deadmethods/deadmethods.go, internal/explainers/entrypoints/entrypoints.go, internal/explainers/entrypoints/entrypoints_test.go, internal/linkers/crossrepo/contract_test.go, internal/linkers/crossrepo/crossrepo_test.go, pkg/bootstrap/bootstrap.go
- غير مباشرين (10): cmd/enola/main.go, internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go … (+2)
- تدفقات مارّة: —
- اختبارات مغطية: internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/engine_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go … (+14)
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
| human review / مراجعة هندسية | CLM-515: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
