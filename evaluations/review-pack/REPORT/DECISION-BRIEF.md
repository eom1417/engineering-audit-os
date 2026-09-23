# Decision brief

> /workspace/upstream-src/enola  ·  2026-09-23 15:44 UTC  ·  eaos 3.0.0
> Coverage: 1021/1021 (100%) · internal imports resolved 98% (4261 external) · entry points 26 (+24 in tests) · runtime-confirmed 0
> ⬤ 573 · ◐ 0 · ○ 0 · ؟ 2
> model calls: 0

## What this system is

⬤ 1021 source files, 10495 symbols, languages: go (985), c (12), bash (9), unknown (8). Invocation surfaces: cli (23), http (27). ○ Responsibilities and contracts are not assessed in a facts-only run.

## Observations for review

| # | Claim | Confidence | Impact | Detail |
|---|---|---|---|---|
| CLM-271 | 2 symbols share the same structure up to identifier names (internal/facts/accessors.go:81 .method_declaration, internal/facts/accessors.go:98… | ⬤ CONFIRMED | Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them. | [SUSTAINABILITY.md](SUSTAINABILITY.md) |
| CLM-012 | 16 symbols share the same structure up to identifier names (internal/explainers/deadmethods/deadmethods.go:349 .function_declaration… | ⬤ CONFIRMED | Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them. | [SUSTAINABILITY.md](SUSTAINABILITY.md) |
| CLM-569 | 328 functions perform the same ordered sequence of calls (internal/clientspec/clientspec.go:None, internal/conformance/conformance.go:None… | ⬤ CONFIRMED | The same orchestration is maintained in several places at once. | [SUSTAINABILITY.md](SUSTAINABILITY.md) |
| CLM-477 | 4 symbols share the same structure up to identifier names (internal/factpath/factpath.go:46 .function_declaration, internal/factpath/factpath.go:50… | ⬤ CONFIRMED | Editing the rule in one copy and not the other makes the paths disagree, and nothing in the code links them. | [SUSTAINABILITY.md](SUSTAINABILITY.md) |
| CLM-531 | Flow FLOW-004 (cli baseline) stops at 4 unresolvable calls | ⬤ CONFIRMED | The behavior of this entry point is not fully visible from source alone. | [FLOWS.md](FLOWS.md) |

- Decisions: repair: 0, investigate: 308, retain: 265

## Do now

- TASK-001 — investigate: 2 symbols share the same structure up to identifier names (internal/facts/accessors.go:81 .method_declaration, internal/
- TASK-002 — investigate: 16 symbols share the same structure up to identifier names (internal/explainers/deadmethods/deadmethods.go:349 .function
- TASK-003 — investigate: 328 functions perform the same ordered sequence of calls (internal/clientspec/clientspec.go:None, internal/conformance/c

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
- unresolved or ambiguous imports: 33
- invocation surfaces with no detector: 18 files
- runtime behaviour: no execution evidence in this run
- semantic review: not performed in this run (facts only)
