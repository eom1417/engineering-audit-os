# TASK-002 — 16 symbols share the same structure up to identifier names (internal/explainers/deadmethods/deadmethods.go:349 .function

> claim: CLM-012 · pattern: canonicalize · priority: 0.3265

> investigate · needs_review

No data for this section in this snapshot.

## The problem

16 symbols share the same structure up to identifier names (internal/explainers/deadmethods/deadmethods.go:349 .function

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-42e17f53dc6e7e5c
- probes: PRB-002
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/explainers/deadmethods/deadmethods.go, internal/explainers/queryloops/queryloops.go, internal/extractors/detectnames/detectnames.go, internal/extractors/dotnetextractor/razor.go, internal/extractors/goextractor/grpcclient.go, internal/extractors/javaextractor/java_ast.go, internal/extractors/pythonextractor/python.go, internal/extractors/rubyextractor/resolve.go … (+7)
- مستوردون مباشرون (565): cmd/enola/main.go, internal/config/config_test.go, internal/config/scalaglobs_test.go, internal/conformance/conformance.go, internal/conformance/conformance_test.go, internal/diff/attribution_test.go, internal/diff/changedprops_test.go, internal/diff/constraintattribution_test.go … (+557)
- غير مباشرين (10): internal/docslint/inventory.go, internal/drift/drift.go, internal/engine/append_version_test.go, internal/engine/defer_linking_test.go, internal/engine/detect_test.go, internal/engine/freeze_publication_test.go, internal/engine/history_e2e_test.go, internal/engine/intent_test.go … (+2)
- تدفقات مارّة: —
- اختبارات مغطية: internal/config/config_test.go, internal/config/scalaglobs_test.go, internal/conformance/conformance_test.go, internal/diff/attribution_test.go, internal/diff/changedprops_test.go, internal/diff/constraintattribution_test.go, internal/diff/constraintcredit_test.go, internal/diff/counts_test.go … (+349)
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
| human review / مراجعة هندسية | CLM-012: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
