# TASK-304 — rows in examples/policy-as-code/legacy/cardstore.go is module-level state changed at runtime (assignment, line 12)

> claim: CLM-564 · pattern: mutable_state · priority: 0.0

> investigate · needs_review

No data for this section in this snapshot.

## The problem

rows in examples/policy-as-code/legacy/cardstore.go is module-level state changed at runtime (assignment, line 12)

Two callers may see different values depending on order, and tests can pass alone and fail together.

## Evidence

- facts: FACT-daf647c7956b5aee
- probes: PRB-568
- falsifier: The value becoming immutable, or the mutation moving behind an owner that serialises access.

## Blast radius

- files: examples/policy-as-code/legacy/cardstore.go
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

Establish or refute this observation before changing code: The value becoming immutable, or the mutation moving behind an owner that serialises access.

## Acceptance criterion

| Command | Expected |
|---|---|
| human review / مراجعة هندسية | CLM-564: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. The value becoming immutable, or the mutation moving behind an owner that serialises access. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
