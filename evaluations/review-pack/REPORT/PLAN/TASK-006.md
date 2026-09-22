# TASK-006 — 149 functions perform the same ordered sequence of calls (cmd/enola/main_test.go:None, internal/config/clients_test.go:N

> claim: CLM-003 · pattern: canonicalize · priority: 0.0

> investigate · needs_review

No data for this section in this snapshot.

## The problem

149 functions perform the same ordered sequence of calls (cmd/enola/main_test.go:None, internal/config/clients_test.go:N

The orchestration is maintained in several places at once.

## Evidence

- facts: FACT-94be405a6d87ef17
- probes: PRB-006
- falsifier: Evidence that the shared order is coincidental rather than one orchestration copied.

## Blast radius

- files: cmd/enola/main_test.go, internal/config/clients_test.go, internal/docslint/links_test.go, internal/engine/coverage_summary_test.go, internal/engine/filecensus_test.go, internal/engine/global_receipt_test.go, internal/explainers/common/cap_test.go, internal/explainers/constraints/constraints_test.go … (+87)
- مستوردون مباشرون (0): —
- غير مباشرين (0): —
- تدفقات مارّة: —
- اختبارات مغطية: —
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
| human review / مراجعة هندسية | CLM-003: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the shared order is coincidental rather than one orchestration copied. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
