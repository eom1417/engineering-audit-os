# TASK-028 — 2 symbols share the same structure up to identifier names (internal/explainers/queryloops/queryloops.go:329 .function_de

> claim: CLM-082 · pattern: canonicalize · priority: 0.0627

> investigate · needs_review

No data for this section in this snapshot.

## The problem

2 symbols share the same structure up to identifier names (internal/explainers/queryloops/queryloops.go:329 .function_de

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-81b7d891490294a4
- probes: PRB-028
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/explainers/queryloops/queryloops.go, internal/intent/constraints.go
- مستوردون مباشرون (46): internal/config/config.go, internal/diff/constraintattribution_test.go, internal/diff/constraintcredit_test.go, internal/docslint/inventory.go, internal/engine/conceptcensusreach_test.go, internal/engine/conceptedgematrix_test.go, internal/engine/conceptownsmethods_test.go, internal/engine/conceptrolesides_test.go … (+38)
- غير مباشرين (10): cmd/enola/autocluster.go, cmd/enola/autocluster_test.go, cmd/enola/main.go, internal/engine/append_version_test.go, internal/engine/baseline_e2e_test.go, internal/engine/clientspec_cache_test.go, internal/engine/clientspec_test.go, internal/engine/cluster_receipts_test.go … (+2)
- تدفقات مارّة: —
- اختبارات مغطية: cmd/enola/autocluster_test.go, internal/diff/constraintattribution_test.go, internal/diff/constraintcredit_test.go, internal/engine/append_version_test.go, internal/engine/baseline_e2e_test.go, internal/engine/clientspec_cache_test.go, internal/engine/clientspec_test.go, internal/engine/cluster_receipts_test.go … (+66)
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
| human review / مراجعة هندسية | CLM-082: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
