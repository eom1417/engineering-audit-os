# Decision brief

> /workspace/upstream-src/enola  ·  2026-09-22 14:15 UTC  ·  eaos 3.0.0
> Coverage: 1021/1021 (100%) · internal imports resolved 6% (4261 external) · entry points 13 (+24 in tests) · runtime-confirmed 0
> ⬤ 10 · ◐ 0 · ○ 0 · ؟ 2
> model calls: 0

## What this system is

⬤ 1021 source files, 10495 symbols, languages: go (985), c (12), bash (9), unknown (8). Invocation surfaces: cli (2), http (35). ○ Responsibilities and contracts are not assessed in a facts-only run.

## Observations for review

| # | Claim | Confidence | Impact | Detail |
|---|---|---|---|---|
| CLM-007 | 421 functions perform the same ordered sequence of calls (cmd/enola/flags_documented_test.go:None, cmd/enola/main.go:None… | ⬤ CONFIRMED | The orchestration is maintained in several places at once. | [SUSTAINABILITY.md](SUSTAINABILITY.md) |
| CLM-004 | 236 functions perform the same ordered sequence of calls (internal/config/output_dir_test.go:None, internal/diff/attribution_test.go:None… | ⬤ CONFIRMED | The orchestration is maintained in several places at once. | [SUSTAINABILITY.md](SUSTAINABILITY.md) |
| CLM-001 | packaging/pypi/build_wheel.py: ينادي خدمة خارجية بلا مهلة أو إعادة محاولة — load blocker (unprotected_dependency) | ⬤ CONFIRMED | بطء الخدمة الأخرى يصير توقفًا عندك؛ الطلبات تتراكم حتى ينفد التجمّع. | [LOAD-MODEL.md](LOAD-MODEL.md) |
| CLM-002 | packaging/pypi/build_wheel.py: ينادي خدمة خارجية بلا مهلة أو إعادة محاولة — load blocker (unprotected_dependency) | ⬤ CONFIRMED | بطء الخدمة الأخرى يصير توقفًا عندك؛ الطلبات تتراكم حتى ينفد التجمّع. | [LOAD-MODEL.md](LOAD-MODEL.md) |
| CLM-006 | 328 functions perform the same ordered sequence of calls (internal/clientspec/clientspec.go:None, internal/conformance/conformance.go:None… | ⬤ CONFIRMED | The orchestration is maintained in several places at once. | [SUSTAINABILITY.md](SUSTAINABILITY.md) |

- Decisions: repair: 0, investigate: 9, retain: 1

## Do now

- TASK-001 — investigate: 421 functions perform the same ordered sequence of calls (cmd/enola/flags_documented_test.go:None, cmd/enola/main.go:Non
- TASK-002 — investigate: 236 functions perform the same ordered sequence of calls (internal/config/output_dir_test.go:None, internal/diff/attribu
- TASK-003 — investigate: packaging/pypi/build_wheel.py: ينادي خدمة خارجية بلا مهلة أو إعادة محاولة

## Do not do (yet)

- Do not treat this as a security review or a production-readiness certificate.
- Do not read the attention order as a severity order; it is a declared reading convention.
- Do not read an absent finding as safety; absence means unexamined unless an absence search is declared.

## Open questions

| # | Question | Source |
|---|---|---|
| Q-001 | History is too shallow (1 commits in scope) for co-change coupling to mean anything; no coupling claim was made from it. | facts |
| Q-002 | No semantic review was run: responsibilities, contracts and root causes are unassessed. | facts |

## Not examined

- unparsed source files: 0
- unresolved or ambiguous imports: 1345
- invocation surfaces with no detector: 18 files
- runtime behaviour: no execution evidence in this run
- semantic review: not performed in this run (facts only)
