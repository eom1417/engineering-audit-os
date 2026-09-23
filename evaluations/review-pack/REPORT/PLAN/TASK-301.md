# TASK-301 — 7 symbols share the same structure up to identifier names (internal/extractors/dotnetextractor/csharp_ast.go:156 .method

> claim: CLM-520 · pattern: canonicalize · priority: 0.0

> investigate · needs_review

No data for this section in this snapshot.

## The problem

7 symbols share the same structure up to identifier names (internal/extractors/dotnetextractor/csharp_ast.go:156 .method

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-d0b7ef2dd5c1db23
- probes: PRB-557
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/extractors/dotnetextractor/csharp_ast.go, internal/extractors/javaextractor/java_ast.go, internal/extractors/kotlinextractor/kotlin_ast.go, internal/extractors/pythonextractor/python_ast.go, internal/extractors/rubyextractor/ruby_ast.go, internal/extractors/swiftextractor/swift_ast.go
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
| human review / مراجعة هندسية | CLM-520: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
