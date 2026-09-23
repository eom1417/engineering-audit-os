# TASK-001 — 2 symbols share the same structure up to identifier names (internal/facts/accessors.go:81 .method_declaration, internal/

> claim: CLM-271 · pattern: canonicalize · priority: 0.5

> investigate · needs_review

No data for this section in this snapshot.

## The problem

2 symbols share the same structure up to identifier names (internal/facts/accessors.go:81 .method_declaration, internal/

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-60c213f8b1486d6c
- probes: PRB-001
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/facts/accessors.go
- مستوردون مباشرون (578): cmd/enola/main.go, internal/config/config_test.go, internal/config/scalaglobs_test.go, internal/conformance/conformance.go, internal/conformance/conformance_test.go, internal/diff/attribution_test.go, internal/diff/changedprops_test.go, internal/diff/constraintattribution_test.go … (+570)
- غير مباشرين (10): internal/docslint/inventory.go, internal/drift/drift.go, internal/engine/append_version_test.go, internal/engine/defer_linking_test.go, internal/engine/detect_test.go, internal/engine/freeze_publication_test.go, internal/engine/history_e2e_test.go, internal/engine/intent_test.go … (+2)
- تدفقات مارّة: —
- اختبارات مغطية: internal/config/config_test.go, internal/config/scalaglobs_test.go, internal/conformance/conformance_test.go, internal/diff/attribution_test.go, internal/diff/changedprops_test.go, internal/diff/constraintattribution_test.go, internal/diff/constraintcredit_test.go, internal/diff/counts_test.go … (+349)
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
| human review / مراجعة هندسية | CLM-271: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
