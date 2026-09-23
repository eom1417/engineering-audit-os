# TASK-115 — pkg/dashboard/dashboard.go: calls an external service with no timeout or retry — load blocker (unprotected_dependency)

> claim: CLM-563 · pattern: load_blocker · priority: 0.0047

> investigate · needs_review

No data for this section in this snapshot.

## The problem

pkg/dashboard/dashboard.go: calls an external service with no timeout or retry — load blocker (unprotected_dependency)

Cost grows with traffic or data at this entry point; current behavior may not survive higher load.

## Evidence

- facts: FACT-2dded790a385b007
- probes: PRB-117
- falsifier: A timeout, retry policy or circuit breaker on the call, or evidence the call is local.

## Blast radius

- files: pkg/dashboard/dashboard.go
- مستوردون مباشرون (2): cmd/enola/main.go, pkg/command/dashboard.go
- غير مباشرين (0): —
- تدفقات مارّة: FLOW-001 /, FLOW-012 dashboard
- اختبارات مغطية: —
- executed coverage: —
- شركاء التغيير: —

## Options

| Option | Cost | Verdict |
|---|---|---|
| Investigate the requirement | unknown | Determine repair or retain |
| Keep current design | unknown | Valid outcome if no violation is established |

## Proposed change

Establish or refute this observation before changing code: A timeout, retry policy or circuit breaker on the call, or evidence the call is local.

## Acceptance criterion

| Command | Expected |
|---|---|
| human review / مراجعة هندسية | CLM-563: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. A timeout, retry policy or circuit breaker on the call, or evidence the call is local. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
