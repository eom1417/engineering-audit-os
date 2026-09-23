# TASK-039 — 24 symbols share the same structure up to identifier names (internal/config/config.go:779 .function_declaration, interna

> claim: CLM-360 · pattern: canonicalize · priority: 0.0289

> investigate · needs_review

No data for this section in this snapshot.

## The problem

24 symbols share the same structure up to identifier names (internal/config/config.go:779 .function_declaration, interna

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-fee983ce05e13966
- probes: PRB-039
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/config/config.go, internal/engine/output_dir_test.go, internal/extractors/cppextractor/complexity_test.go, internal/extractors/cppextractor/cppmacro_test.go, internal/extractors/dotnetextractor/testrefs_test.go, internal/extractors/goextractor/complexity_test.go, internal/extractors/goextractor/funcvalues_test.go, internal/extractors/goextractor/go_test.go … (+16)
- مستوردون مباشرون (51): cmd/enola/autocluster.go, cmd/enola/autocluster_test.go, cmd/enola/main.go, internal/docslint/inventory.go, internal/engine/append_version_test.go, internal/engine/baseline_e2e_test.go, internal/engine/clientspec_test.go, internal/engine/cluster_receipts_test.go … (+43)
- غير مباشرين (10): internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go, internal/explainers/messagingcoverage/integration_test.go, internal/server/middleware_wire_test.go … (+2)
- تدفقات مارّة: FLOW-016 gc
- اختبارات مغطية: cmd/enola/autocluster_test.go, internal/engine/append_version_test.go, internal/engine/baseline_e2e_test.go, internal/engine/clientspec_cache_test.go, internal/engine/clientspec_test.go, internal/engine/cluster_receipts_test.go, internal/engine/conceptedgematrix_test.go, internal/engine/crossrepo_php_test.go … (+42)
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
| human review / مراجعة هندسية | CLM-360: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
