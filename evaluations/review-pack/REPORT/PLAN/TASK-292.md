# TASK-292 — 5 symbols share the same structure up to identifier names (internal/extractors/cppextractor/cpp_ast.go:361 .function_dec

> claim: CLM-485 · pattern: canonicalize · priority: 0.0

> investigate · needs_review

No data for this section in this snapshot.

## The problem

5 symbols share the same structure up to identifier names (internal/extractors/cppextractor/cpp_ast.go:361 .function_dec

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-827959590b49a065
- probes: PRB-532
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/extractors/cppextractor/cpp_ast.go, internal/extractors/javaextractor/java_ast.go, internal/extractors/kotlinextractor/kotlin_ast.go, internal/extractors/swiftextractor/swift_ast.go, internal/extractors/tsextractor/ts.go
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

Establish or refute this observation before changing code: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Acceptance criterion

| Command | Expected |
|---|---|
| human review / مراجعة هندسية | CLM-485: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
