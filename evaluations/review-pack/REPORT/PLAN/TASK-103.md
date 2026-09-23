# TASK-103 — 2 symbols share the same structure up to identifier names (internal/extractors/dartextractor/grammar/binding.go:34 .func

> claim: CLM-103 · pattern: canonicalize · priority: 0.011

> investigate · needs_review

No data for this section in this snapshot.

## The problem

2 symbols share the same structure up to identifier names (internal/extractors/dartextractor/grammar/binding.go:34 .func

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-c9e09617b9ca6494
- probes: PRB-103
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/extractors/dartextractor/grammar/binding.go, internal/extractors/swiftextractor/grammar/binding.go
- مستوردون مباشرون (7): internal/extractors/dartextractor/dart_ast.go, internal/extractors/dartextractor/kinds.go, internal/extractors/dartextractor/probe_test.go, internal/extractors/swiftextractor/kinds.go, internal/extractors/swiftextractor/probe_test.go, internal/extractors/swiftextractor/swift_ast.go, internal/extractors/swiftextractor/swift_manifest.go
- غير مباشرين (0): —
- تدفقات مارّة: —
- اختبارات مغطية: internal/extractors/dartextractor/probe_test.go, internal/extractors/swiftextractor/probe_test.go
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
| human review / مراجعة هندسية | CLM-103: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
