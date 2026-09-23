# TASK-082 — 13 symbols share the same structure up to identifier names (internal/extractors/ansibleextractor/ansible.go:40 .method_d

> claim: CLM-010 · pattern: canonicalize · priority: 0.0178

> investigate · needs_review

No data for this section in this snapshot.

## The problem

13 symbols share the same structure up to identifier names (internal/extractors/ansibleextractor/ansible.go:40 .method_d

Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them.

## Evidence

- facts: FACT-3274bc6e262e2d1a
- probes: PRB-082
- falsifier: Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing.

## Blast radius

- files: internal/extractors/ansibleextractor/ansible.go, internal/extractors/cppextractor/cpp.go, internal/extractors/dartextractor/dart.go, internal/extractors/dotnetextractor/csharp.go, internal/extractors/goextractor/go.go, internal/extractors/hclextractor/hcl.go, internal/extractors/kotlinextractor/kotlin.go, internal/extractors/manifestextractor/manifest.go … (+5)
- مستوردون مباشرون (2): internal/engine/detect_test.go, pkg/bootstrap/bootstrap.go
- غير مباشرين (10): cmd/enola/main.go, internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go … (+2)
- تدفقات مارّة: —
- اختبارات مغطية: internal/engine/clientspec_cache_test.go, internal/engine/crossrepo_php_test.go, internal/engine/custom_client_example_test.go, internal/engine/detect_test.go, internal/engine/engine_race_test.go, internal/engine/golden_test.go, internal/engine/provider_cache_test.go, internal/engine/receipt_test.go … (+10)
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
| human review / مراجعة هندسية | CLM-010: CONFIRMED or REFUTED concerns the observation only; record requirement evidence and decide repair, retain, or blocked_missing_requirement. Evidence that the occurrences encode different rules that evolve for different reasons, which would make a single definition wrong rather than missing. |

## Rollback

No code changes during investigation.

## Effort

unknown · estimate confidence: Not measured / لم يُقَس
