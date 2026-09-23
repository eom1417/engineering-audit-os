# TASK-056 — examples/cross-repo/api/server.go: calls an external service with no timeout or retry — load blocker (unprotected_depend

> claim: CLM-539 · pattern: load_blocker · priority: 0.0235

> investigate · needs_review

No data for this section in this snapshot.

## The problem

examples/cross-repo/api/server.go: calls an external service with no timeout or retry — load blocker (unprotected_depend

Cost grows with traffic or data at this entry point; current behavior may not survive higher load.

## Evidence

- facts: FACT-785173267564ee2c
- probes: PRB-056
- falsifier: A timeout, retry policy or circuit breaker on the call, or evidence the call is local.

## Blast radius

- files: examples/cross-repo/api/server.go
- مستوردون مباشرون (0): —
- غير مباشرين (0): —
- تدفقات مارّة: FLOW-002 /orders, FLOW-003 /orders/{id}, FLOW-024 server
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
| human review / مراجعة هندسية | CLM-539: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. A timeout, retry policy or circuit breaker on the call, or evidence the call is local. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
