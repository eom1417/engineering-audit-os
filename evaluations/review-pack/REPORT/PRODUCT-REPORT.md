# Project understanding and development plan

> Review goal: evolution
> Deterministic review; semantic interpretation was not run.

## 1. Decision and next action

| # | Kind | Readiness | Details |
|---|---|---|---|
| TASK-001 | investigate | needs_review | [421 functions perform the same ordered sequence of calls (cmd/enola/flags_documented_test.go:None, c](PLAN/TASK-001.md) |
| TASK-002 | investigate | needs_review | [236 functions perform the same ordered sequence of calls (internal/config/output_dir_test.go:None, i](PLAN/TASK-002.md) |
| TASK-003 | investigate | needs_review | [packaging/pypi/build_wheel.py: ينادي خدمة خارجية بلا مهلة أو إعادة محاولة](PLAN/TASK-003.md) |
| TASK-004 | investigate | needs_review | [packaging/pypi/build_wheel.py: ينادي خدمة خارجية بلا مهلة أو إعادة محاولة](PLAN/TASK-004.md) |
| TASK-005 | investigate | needs_review | [328 functions perform the same ordered sequence of calls (internal/clientspec/clientspec.go:None, in](PLAN/TASK-005.md) |
| TASK-006 | investigate | needs_review | [149 functions perform the same ordered sequence of calls (cmd/enola/main_test.go:None, internal/conf](PLAN/TASK-006.md) |
| TASK-007 | investigate | needs_review | [handleCall in internal/extractors/rubyextractor/routes_ast.go carries 109 branches over 541 lines, i](PLAN/TASK-007.md) |
| TASK-008 | investigate | needs_review | [registerTools in internal/server/server.go carries 189 branches over 1117 lines, in a file ranked 12](PLAN/TASK-008.md) |
| TASK-009 | investigate | needs_review | [walkForCalls in internal/extractors/rubyextractor/ruby_ast.go carries 102 branches over 380 lines, i](PLAN/TASK-009.md) |

## 2. How the system works

⬤ 1021 source files, 10495 symbols, languages: go (985), c (12), bash (9), unknown (8). Invocation surfaces: cli (2), http (35). ○ Responsibilities and contracts are not assessed in a facts-only run.

- [SYSTEM-MAP.md](SYSTEM-MAP.md)
- [FLOWS.md](FLOWS.md)
- [CONTRACTS.md](CONTRACTS.md)

## 3. Preserve and investigate

Retain decisions: 1

- [RISK-REGISTER.md](RISK-REGISTER.md)
- [DECISION-BRIEF.md](DECISION-BRIEF.md)

## 4. Work sequence and verification

[PLAN/WAVES.md](PLAN/WAVES.md) · [VERIFICATION-MAP.md](VERIFICATION-MAP.md)

Investigations may conclude no change. Blocked repairs need their evidence and checks completed.

[BLOCKERS.md](BLOCKERS.md): 0

## 5. Confidence limits

- unparsed source files: 0
- unresolved or ambiguous imports: 1345
- invocation surfaces with no detector: 18 files
- runtime behaviour: no execution evidence in this run
- semantic review: not performed in this run (facts only)

[PROVENANCE.md](PROVENANCE.md) · [dossier.json](dossier.json)
