# TASK-029 — 3 symbols share the same structure up to identifier names (internal/linkers/vocab/overlay.go:44 .method_declaration, pkg

> claim: CLM-450 · pattern: canonicalize · priority: 0.0543

> investigate · needs_review

No data for this section in this snapshot.

## The problem

3 symbols share the same structure up to identifier names (internal/linkers/vocab/overlay.go:44 .method_declaration, pkg

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-f6cb84abc0bffb72
- probes: PRB-029
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/linkers/vocab/overlay.go, pkg/check/check.go, pkg/history/patch.go
- مستوردون مباشرون (29): internal/config/config.go, internal/engine/engine.go, internal/engine/engine_test.go, internal/engine/linkvocab_test.go, internal/linkers/binders/registry_test.go, internal/linkers/binders/unmatchedroutes/unmatchedroutes.go, internal/linkers/binders/unmatchedroutes/unmatchedroutes_test.go, internal/linkers/crossrepo/contract_test.go … (+21)
- غير مباشرين (10): cmd/enola/autocluster.go, cmd/enola/autocluster_test.go, cmd/enola/main.go, internal/docslint/inventory.go, internal/engine/append_version_test.go, internal/engine/baseline_e2e_test.go, internal/engine/clientspec_cache_test.go, internal/engine/clientspec_test.go … (+2)
- تدفقات مارّة: —
- اختبارات مغطية: cmd/enola/autocluster_test.go, internal/engine/append_version_test.go, internal/engine/baseline_e2e_test.go, internal/engine/clientspec_cache_test.go, internal/engine/clientspec_test.go, internal/engine/cluster_receipts_test.go, internal/engine/conceptedgematrix_test.go, internal/engine/crossrepo_php_test.go … (+60)
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
| human review / مراجعة هندسية | CLM-450: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
