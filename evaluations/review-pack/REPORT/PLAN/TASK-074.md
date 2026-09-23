# TASK-074 — 236 functions perform the same ordered sequence of calls (internal/config/output_dir_test.go:None, internal/diff/attribu

> claim: CLM-567 · pattern: canonicalize · priority: 0.0197

> investigate · needs_review

No data for this section in this snapshot.

## The problem

236 functions perform the same ordered sequence of calls (internal/config/output_dir_test.go:None, internal/diff/attribu

The same orchestration is maintained in several places at once.

## Evidence

- facts: FACT-93c30188b414942d
- probes: PRB-074
- falsifier: Evidence that the shared order is coincidental rather than one orchestration copied.

## Blast radius

- files: internal/config/output_dir_test.go, internal/diff/attribution_test.go, internal/diff/changedprops_test.go, internal/diff/constraintattribution_test.go, internal/diff/constraintcredit_test.go, internal/diff/counts_test.go, internal/diff/diff_test.go, internal/engine/cache_build_test.go … (+97)
- مستوردون مباشرون (3): internal/server/server.go, pkg/bootstrap/bootstrap.go, pkg/command/plan.go
- غير مباشرين (10): cmd/enola/main.go, internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go … (+2)
- تدفقات مارّة: —
- اختبارات مغطية: internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go, internal/explainers/messagingcoverage/integration_test.go … (+8)
- executed coverage: —
- شركاء التغيير: —

## Options

| Option | Cost | Verdict |
|---|---|---|
| Investigate the requirement | unknown | Determine repair or retain |
| Keep current design | unknown | Valid outcome if no violation is established |

## Proposed change

Establish or refute this observation before changing code: Evidence that the shared order is coincidental rather than one orchestration copied.

## Acceptance criterion

| Command | Expected |
|---|---|
| human review / مراجعة هندسية | CLM-567: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the shared order is coincidental rather than one orchestration copied. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
