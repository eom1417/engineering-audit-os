# TASK-009 — walkForCalls in internal/extractors/rubyextractor/ruby_ast.go carries 102 branches over 380 lines, in a file ranked 15 f

> claim: CLM-010 · pattern: hotspot · priority: 0.0

> investigate · needs_review

No data for this section in this snapshot.

## The problem

walkForCalls in internal/extractors/rubyextractor/ruby_ast.go carries 102 branches over 380 lines, in a file ranked 15 f

Every change to this path passes through one dense function; it is the most concentrated maintenance risk in the module. It is among the most branching functions in the project.

## Evidence

- facts: FACT-fed46b1da3e7665c
- probes: PRB-010
- falsifier: A measurement showing the branching is below the declared threshold, or evidence that the complexity is inherent to the problem and isolated behind a tested contract.

## Blast radius

- files: internal/extractors/rubyextractor/ruby_ast.go
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
| human review / مراجعة هندسية | CLM-010: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. A measurement showing the branching is below the declared threshold, or evidence that the complexity is inherent to the problem and isolated behind a tested contract. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
