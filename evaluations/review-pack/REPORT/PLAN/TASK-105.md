# TASK-105 — 2 symbols share the same structure up to identifier names (internal/providers/rubydex/fetch.go:46 .function_declaration,

> claim: CLM-324 · pattern: canonicalize · priority: 0.0104

> investigate · needs_review

No data for this section in this snapshot.

## The problem

2 symbols share the same structure up to identifier names (internal/providers/rubydex/fetch.go:46 .function_declaration,

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-626aad755acbb4f6
- probes: PRB-105
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/providers/rubydex/fetch.go, internal/updatecheck/updatecheck.go
- مستوردون مباشرون (12): cmd/enola/main.go, internal/providers/builtin.go, internal/providers/builtin_test.go, internal/providers/rubydex_index_test.go, internal/server/server.go, internal/server/update_middleware_test.go, pkg/command/command.go, pkg/command/doctor.go … (+4)
- غير مباشرين (0): —
- تدفقات مارّة: FLOW-014 doctor, FLOW-018 hook, FLOW-021 main, FLOW-023 providers
- اختبارات مغطية: internal/providers/builtin_test.go, internal/providers/rubydex_index_test.go, internal/server/update_middleware_test.go, pkg/command/doctor_update_test.go
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
| human review / مراجعة هندسية | CLM-324: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
