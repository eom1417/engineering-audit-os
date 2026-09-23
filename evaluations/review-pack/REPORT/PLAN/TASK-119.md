# TASK-119 — 2 symbols share the same structure up to identifier names (internal/extractors/dartextractor/grammar/src/tree_sitter/par

> claim: CLM-113 · pattern: canonicalize · priority: 0.0031

> investigate · needs_review

No data for this section in this snapshot.

## The problem

2 symbols share the same structure up to identifier names (internal/extractors/dartextractor/grammar/src/tree_sitter/par

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-fa1173f0f20f58e3
- probes: PRB-123
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/extractors/dartextractor/grammar/src/tree_sitter/parser.h, internal/extractors/swiftextractor/grammar/src/tree_sitter/parser.h
- مستوردون مباشرون (2): internal/extractors/dartextractor/grammar/src/scanner.c, internal/extractors/swiftextractor/grammar/src/scanner.c
- غير مباشرين (2): internal/extractors/dartextractor/grammar/cgo_scanner.c, internal/extractors/swiftextractor/grammar/cgo_scanner.c
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
| human review / مراجعة هندسية | CLM-113: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
