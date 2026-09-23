# TASK-106 — 2 symbols share the same structure up to identifier names (internal/filelock/filelock_unix.go:75 .function_declaration, 

> claim: CLM-277 · pattern: canonicalize · priority: 0.0094

> investigate · needs_review

No data for this section in this snapshot.

## The problem

2 symbols share the same structure up to identifier names (internal/filelock/filelock_unix.go:75 .function_declaration, 

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-86139567352f92fa
- probes: PRB-106
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/filelock/filelock_unix.go, internal/filelock/filelock_windows.go
- مستوردون مباشرون (5): internal/history/share.go, internal/history/write.go, internal/updatecheck/updatecheck.go, pkg/command/hook.go, pkg/status/status.go
- غير مباشرين (7): cmd/enola/main.go, internal/server/server.go, internal/server/update_middleware_test.go, pkg/command/command.go, pkg/command/doctor.go, pkg/command/doctor_update_test.go, pkg/command/update.go
- تدفقات مارّة: —
- اختبارات مغطية: internal/server/update_middleware_test.go, pkg/command/doctor_update_test.go
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
| human review / مراجعة هندسية | CLM-277: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
