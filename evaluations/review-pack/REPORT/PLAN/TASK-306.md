# TASK-306 — handleCall in internal/extractors/rubyextractor/routes_ast.go carries 109 branches over 541 lines, in a file ranked 129 

> claim: CLM-571 · pattern: hotspot · priority: 0.0

> investigate · needs_review

No data for this section in this snapshot.

## The problem

handleCall in internal/extractors/rubyextractor/routes_ast.go carries 109 branches over 541 lines, in a file ranked 129 

Every change on this path runs through one dense function, concentrating maintenance risk in a single unit.

## Evidence

- facts: FACT-e8bc1411229b1465
- probes: PRB-571
- falsifier: A measurement showing the branching is below the declared threshold, or evidence that the complexity is inherent to the problem and isolated behind a tested contract.

## Blast radius

- files: internal/extractors/rubyextractor/routes_ast.go
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
| human review / مراجعة هندسية | CLM-571: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. A measurement showing the branching is below the declared threshold, or evidence that the complexity is inherent to the problem and isolated behind a tested contract. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
