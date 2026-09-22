# Index and reading order

> /workspace/upstream-src/enola · eaos 3.0.0 · 2026-09-22 14:15 UTC · model calls 0
> Coverage: 1021/1021 · claims 10 (0 semantic)
> tasks 9 · waves 4

## Read in this order

| If you are… | Start with | Time |
|---|---|---|
| deciding where effort goes | [DECISION-BRIEF.md](DECISION-BRIEF.md) → [RISK-REGISTER.md](RISK-REGISTER.md) → [PLAN/WAVES.md](PLAN/WAVES.md) | 5 min |
| joining the project today | [ONBOARDING.md](ONBOARDING.md) → [SYSTEM-MAP.md](SYSTEM-MAP.md) → [FLOWS.md](FLOWS.md) | 45 min |
| reviewing the architecture | [POLICY.md](POLICY.md) → [COUPLING-ATLAS.md](COUPLING-ATLAS.md) → [CONTRACTS.md](CONTRACTS.md) | 30 min |
| about to change one file | `eaos impact-of <path> --out .` | 1 min |

## How well each section is sourced

| Section | Source | Grade | Note |
|---|---|---|---|
| SYSTEM-MAP.md | deterministic extractors | ⬤ | reproducible byte for byte from the same snapshot |
| CONTRACTS.md | resolved imports and entry points | ⬤ |  |
| FLOWS.md | static trace | ◐ | 0 unresolved steps declared |
| DOMAIN-AND-DATA.md | parsed definitions | ⬤ |  |
| COUPLING-ATLAS.md | graph and metrics | ⬤ | attention order is a declared convention, not a measured predictor |
| EVOLUTION.md | git history | ◐ | 1 commits in scope |
| VERIFICATION-MAP.md | not executed | ○ | run eaos verify --execute |
| responsibilities, boundaries, internal contracts | — | ○ | not assessed: needs the model path |

## Not examined

- unparsed source files: 0
- unresolved or ambiguous imports: 1345
- invocation surfaces with no detector: 18 files
- runtime behaviour: no execution evidence in this run
- semantic review: not performed in this run (facts only)

## Every file

| # | File | Why |
|---|---|---|
| 1 | [README.md](README.md) | What this report holds and in what order to read it |
| 2 | [RUN.md](RUN.md) | What this run examined, and what it could not |
| 3 | [EXECUTIVE.md](EXECUTIVE.md) | The decision a sponsor has to make, and on what evidence |
| 4 | [DECISION-BRIEF.md](DECISION-BRIEF.md) | Every live claim with its confidence and its falsifier |
| 5 | [PRODUCT-REPORT.md](PRODUCT-REPORT.md) | The reviewed project in one narrative |
| 6 | [BLOCKERS.md](BLOCKERS.md) | What stops the plan from being executable today |
| 7 | [SYSTEM-MAP.md](SYSTEM-MAP.md) | Modules and their dependency directions |
| 8 | [COUPLING-ATLAS.md](COUPLING-ATLAS.md) | Where change spreads and why |
| 9 | [FLOWS.md](FLOWS.md) | Traced end-to-end paths from each entry point |
| 10 | [DOMAIN-AND-DATA.md](DOMAIN-AND-DATA.md) | Domain concepts and the state they own |
| 11 | [CONTRACTS.md](CONTRACTS.md) | The public surface other code depends on |
| 12 | [EVOLUTION.md](EVOLUTION.md) | How the code changed over its recorded history |
| 13 | [DATA-MODEL.md](DATA-MODEL.md) | Persisted shapes and their migrations |
| 14 | [DEPLOYMENT.md](DEPLOYMENT.md) | Where the system is declared to run |
| 15 | [OBSERVABILITY.md](OBSERVABILITY.md) | What the system reports about itself |
| 16 | [SECURITY-SURFACE.md](SECURITY-SURFACE.md) | Reachable surfaces and declared secrets |
| 17 | [INTEGRATIONS.md](INTEGRATIONS.md) | Outbound calls to systems outside this repository |
| 18 | [ENGINES.md](ENGINES.md) | What each external engine saw, and where they disagree — absent when: external engines were not requested or are not installed |
| 19 | [POLICY.md](POLICY.md) | The declared architecture contract and its breaches — absent when: the project declares no policy |
| 20 | [VERIFICATION-MAP.md](VERIFICATION-MAP.md) | What the tests actually executed |
| 21 | [RISK-REGISTER.md](RISK-REGISTER.md) | Live risks with their dispositions |
| 22 | [ONBOARDING.md](ONBOARDING.md) | The shortest path to understanding this system |
| 23 | [SUSTAINABILITY.md](SUSTAINABILITY.md) | The six indicators and the moves that would close them |
| 24 | [CANONICAL-HOMES.md](CANONICAL-HOMES.md) | Where each repeated definition should live |
| 25 | [TARGET-ARCHITECTURE.md](TARGET-ARCHITECTURE.md) | The structure the evidence argues for |
| 26 | [transform-plan.md](transform-plan.md) | The staged route from here to there |
| 27 | [STAGES.md](STAGES.md) | Each transform stage with its acceptance check |
| 28 | [WAVES.md](WAVES.md) | Execution waves over the task cards |
| 29 | [KPI.md](KPI.md) | What to measure to know the transformation worked |
| 30 | [BASELINE.md](BASELINE.md) | The debt accepted when the baseline was pinned, and what has closed since — absent when: no baseline is pinned in this report directory |
| 31 | [PROVENANCE.md](PROVENANCE.md) | Which tool, which version, which commit produced this |
| 32 | [SEMANTIC.md](SEMANTIC.md) | Model interpretation, every line still a hypothesis — absent when: no model provider was configured |
| 33 | [LOAD-MODEL.md](LOAD-MODEL.md) | Per-entry-point cost record and 1000x projection, ranked |
| 34 | [index.html](index.html) | The same records, browsable — absent when: the site was turned off |

## Reproduce

- eaos audit /workspace/upstream-src/enola --out <dir> --engines
- eaos audit /workspace/upstream-src/enola --out <dir> --resume
- eaos impact-of <path> --out <dir>
