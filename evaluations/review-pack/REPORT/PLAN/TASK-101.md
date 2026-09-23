# TASK-101 — 3 symbols share the same structure up to identifier names (pkg/cli/help.go:184 .function_declaration, pkg/cli/help.go:24

> claim: CLM-456 · pattern: canonicalize · priority: 0.0118

> investigate · needs_review

No data for this section in this snapshot.

## The problem

3 symbols share the same structure up to identifier names (pkg/cli/help.go:184 .function_declaration, pkg/cli/help.go:24

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-3c1fe1ffcd44dc95
- probes: PRB-101
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: pkg/cli/help.go
- مستوردون مباشرون (13): cmd/enola/dashboard_hint.go, cmd/enola/main.go, internal/docslint/commands_test.go, internal/docslint/inventory.go, internal/server/e2e_test.go, pkg/command/check.go, pkg/command/check_fatal_test.go, pkg/command/command.go … (+5)
- غير مباشرين (0): —
- تدفقات مارّة: FLOW-021 main
- اختبارات مغطية: internal/docslint/commands_test.go, internal/server/e2e_test.go, pkg/command/check_fatal_test.go, pkg/command/doctor_update_test.go, pkg/command/help_consistency_test.go, pkg/command/helpers_test.go, pkg/command/install_test.go, pkg/command/runner_test.go
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
| human review / مراجعة هندسية | CLM-456: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
