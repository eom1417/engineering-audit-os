# TASK-058 — 3 symbols share the same structure up to identifier names (internal/extractors/tsextractor/ts.go:3548 .function_declarat

> claim: CLM-441 · pattern: canonicalize · priority: 0.023

> investigate · needs_review

No data for this section in this snapshot.

## The problem

3 symbols share the same structure up to identifier names (internal/extractors/tsextractor/ts.go:3548 .function_declarat

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-ef7afbeac1dc121f
- probes: PRB-058
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/extractors/tsextractor/ts.go, pkg/command/install.go, pkg/status/aggregate.go
- مستوردون مباشرون (9): cmd/enola/main.go, internal/server/autocluster.go, internal/server/middleware_wire_test.go, internal/server/server.go, internal/server/usage_e2e_test.go, pkg/bootstrap/bootstrap.go, pkg/command/dashboard.go, pkg/dashboard/dashboard.go … (+1)
- غير مباشرين (10): internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go, internal/explainers/messagingcoverage/integration_test.go … (+2)
- تدفقات مارّة: FLOW-010 constraints, FLOW-014 doctor, FLOW-019 install, FLOW-021 main
- اختبارات مغطية: internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go, internal/explainers/messagingcoverage/integration_test.go … (+10)
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
| human review / مراجعة هندسية | CLM-441: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
