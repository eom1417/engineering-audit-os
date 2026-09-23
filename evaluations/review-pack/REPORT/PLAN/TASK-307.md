# TASK-307 — registerTools in internal/server/server.go carries 189 branches over 1117 lines, in a file ranked 11 for attention

> claim: CLM-572 · pattern: hotspot · priority: 0.0

> investigate · needs_review

No data for this section in this snapshot.

## The problem

registerTools in internal/server/server.go carries 189 branches over 1117 lines, in a file ranked 11 for attention

Every change on this path runs through one dense function, concentrating maintenance risk in a single unit.

## Evidence

- facts: FACT-315aae552043ef54
- probes: PRB-572
- falsifier: A measurement showing the branching is below the declared threshold, or evidence that the complexity is inherent to the problem and isolated behind a tested contract.

## Blast radius

- files: internal/server/server.go
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

Establish or refute this observation before changing code: A measurement showing the branching is below the declared threshold, or evidence that the complexity is inherent to the problem and isolated behind a tested contract.

## Acceptance criterion

| Command | Expected |
|---|---|
| human review / مراجعة هندسية | CLM-572: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. A measurement showing the branching is below the declared threshold, or evidence that the complexity is inherent to the problem and isolated behind a tested contract. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
