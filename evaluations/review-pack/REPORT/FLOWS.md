# Traced flows

> Static trace: every step has a real location, and an unresolved step means the trace stopped, not execution.

## Coverage

| Traced flows | steps | unresolved | stop at first boundary |
|---|---|---|---|
| 23 | 889 | 27 | 2 |

These entry points reach no further code in the project (dynamic dispatch or library calls only): examples/cross-repo/api/server.go:12, examples/cross-repo/api/server.go:12

## FLOW-010 — cli  constraints

- Entry point: pkg/command/command.go:147 [go_dispatch_case]
- Handler: Constraints
- Files touched: pkg/bootstrap/bootstrap.go, pkg/command/check.go, pkg/command/command.go, pkg/command/constraints.go, pkg/command/constraints_explain.go, pkg/command/constraints_init.go, pkg/command/constraints_ledger.go, pkg/command/install.go, pkg/command/mine.go
- Environment reads on the path: PATH

| Step | Call | Location | Resolution |
|---|---|---|---|
| Constraints | ConstraintsMine | pkg/command/mine.go:40 | imported |

Showing 1 of 16; the rest stays in the fact records.

+24 library or method calls on this path (in the fact records)

## FLOW-014 — cli  doctor

- Entry point: pkg/command/command.go:166 [go_dispatch_case]
- Handler: Doctor
- Files touched: internal/hookstate/hookstate.go, internal/updatecheck/updatecheck.go, pkg/command/check.go, pkg/command/command.go, pkg/command/doctor.go, pkg/command/install.go, pkg/command/providers.go
- Environment reads on the path: CI

| Step | Call | Location | Resolution |
|---|---|---|---|
| Doctor | Fprint | internal/updatecheck/updatecheck.go:40 | imported |
| Doctor | name | pkg/command/command.go:41 | imported |
| Doctor | cmdFatal | pkg/command/check.go:54 | imported |
| Doctor | isDirectory | pkg/command/command.go:57 | imported |
| Doctor | cmdFatal | pkg/command/check.go:58 | imported |
| Doctor | hookOutputDir | pkg/command/install.go:67 | imported |
| Doctor | Load | internal/hookstate/hookstate.go:68 | imported |
| Doctor | hooksConfigured | pkg/command/doctor.go:69 | local |
| Doctor | baselineUsability | pkg/command/doctor.go:70 | local |
| Doctor | selfUpgrades | pkg/command/command.go:77 | imported |
| Doctor | For | internal/updatecheck/updatecheck.go:78 | imported |
| Doctor | name | pkg/command/command.go:97 | imported |

Showing 12 of 15; the rest stays in the fact records.

+25 library or method calls on this path (in the fact records)

## FLOW-021 — cli  main

- Entry point: cmd/enola/main.go:29 [go_main]
- Handler: main
- Files touched: cmd/enola/autocluster.go, cmd/enola/main.go, internal/updatecheck/updatecheck.go, pkg/bootstrap/bootstrap.go, pkg/cli/help.go, pkg/status/aggregate.go
- Environment reads on the path: CI, PATH

| Step | Call | Location | Resolution |
|---|---|---|---|
| main | startMemWatch | cmd/enola/main.go:44 | local |
| main | binary | cmd/enola/main.go:60 | local |
| main | RenderHelp | pkg/cli/help.go:109 | imported |
| main | helpSpec | cmd/enola/main.go:109 | local |
| main | Fprint | internal/updatecheck/updatecheck.go:112 | imported |
| main | PrintStatusAll | pkg/status/aggregate.go:161 | imported |
| main | NewEngine | pkg/bootstrap/bootstrap.go:168 | imported |
| main | foldedRepos | cmd/enola/autocluster.go:196 | imported |

+32 library or method calls on this path (in the fact records)

## FLOW-001 — http ANY /

- Entry point: pkg/dashboard/dashboard.go:52 [go_http]
- Handler: s.handleIndex
- Files touched: pkg/dashboard/dashboard.go, pkg/dashboard/edgediagram.go, pkg/dashboard/format.go, pkg/dashboard/graphdetail.go, pkg/dashboard/insights.go

| Step | Call | Location | Resolution |
|---|---|---|---|
| handleIndex | buildPageForModule | pkg/dashboard/dashboard.go:252 | local |
| buildPageForModule | formatDuration | pkg/dashboard/format.go:479 | imported |
| buildPageForModule | toolRows | pkg/dashboard/dashboard.go:481 | local |
| buildPageForModule | toolRows | pkg/dashboard/dashboard.go:497 | local |
| buildPageForModule | valueRows | pkg/dashboard/dashboard.go:498 | local |
| buildPageForModule | instanceRows | pkg/dashboard/dashboard.go:500 | local |
| buildPageForModule | instanceRows | pkg/dashboard/dashboard.go:503 | local |
| buildPageForModule | currentReceipt | pkg/dashboard/dashboard.go:508 | local |
| buildPageForModule | summarizeSnapshot | pkg/dashboard/dashboard.go:511 | local |
| buildPageForModule | assessQuality | pkg/dashboard/dashboard.go:515 | local |
| buildPageForModule | graphDetails | pkg/dashboard/graphdetail.go:536 | imported |
| buildPageForModule | buildEdgeDiagram | pkg/dashboard/edgediagram.go:537 | imported |

Showing 12 of 16; the rest stays in the fact records.

+24 library or method calls on this path (in the fact records)

## FLOW-004 — cli  baseline

- Entry point: pkg/command/command.go:175 [go_dispatch_case]
- Handler: Baseline
- Files touched: internal/engine/baseline.go, pkg/bootstrap/bootstrap.go, pkg/command/check.go, pkg/command/command.go, pkg/command/pinreuse.go
- Environment reads on the path: PATH

| Step | Call | Location | Resolution |
|---|---|---|---|
| Baseline | name | pkg/command/command.go:440 | imported |
| Baseline | resolveTarget | pkg/command/check.go:459 | local |
| Baseline | ResolveBaselineDir | internal/engine/baseline.go:463 | imported |
| Baseline | name | pkg/command/command.go:475 | imported |
| Baseline | snapshotIsCurrent | pkg/command/pinreuse.go:481 | imported |
| Baseline | name | pkg/command/command.go:482 | imported |
| Baseline | name | pkg/command/command.go:484 | imported |
| Baseline | SetDeferLinking | pkg/bootstrap/bootstrap.go:486 | imported |
| Baseline | GenerateSnapshot | pkg/bootstrap/bootstrap.go:487 | imported |
| Baseline | checkFatal | pkg/command/check.go:488 | local |
| Baseline | WriteArtifacts | pkg/bootstrap/bootstrap.go:492 | imported |
| Baseline | checkFatal | pkg/command/check.go:493 | local |

Showing 12 of 15; the rest stays in the fact records.

+25 library or method calls on this path (in the fact records)

## FLOW-005 — cli  blame

- Entry point: pkg/command/command.go:186 [go_dispatch_case]
- Handler: Blame
- Files touched: pkg/command/blame.go, pkg/command/check.go, pkg/command/command.go, pkg/command/log.go, pkg/history/blame.go

| Step | Call | Location | Resolution |
|---|---|---|---|
| Blame | name | pkg/command/command.go:41 | imported |
| Blame | splitPatternAndRepo | pkg/command/blame.go:58 | local |
| Blame | blameFatal | pkg/command/blame.go:60 | local |
| Blame | name | pkg/command/command.go:60 | imported |
| Blame | historyWithStore | pkg/command/blame.go:63 | local |
| Blame | onlyCommitted | pkg/command/log.go:65 | imported |
| Blame | blameFatal | pkg/command/blame.go:70 | local |
| Blame | onlyCommittedUnion | pkg/command/blame.go:74 | local |
| Blame | BlameUnion | pkg/history/blame.go:77 | imported |
| Blame | blameFatal | pkg/command/blame.go:82 | local |
| Blame | blameFatal | pkg/command/blame.go:88 | local |
| Blame | renderBlame | pkg/command/blame.go:93 | local |

Showing 12 of 16; the rest stays in the fact records.

+24 library or method calls on this path (in the fact records)

## FLOW-011 — cli  coverage

- Entry point: pkg/command/command.go:159 [go_dispatch_case]
- Handler: Coverage
- Files touched: internal/clientspec/clientspec.go, pkg/command/check.go, pkg/command/command.go, pkg/command/coverage.go, pkg/coverage/clients.go

| Step | Call | Location | Resolution |
|---|---|---|---|
| Coverage | name | pkg/command/command.go:36 | imported |
| Coverage | resolveTarget | pkg/command/check.go:52 | imported |
| Coverage | name | pkg/command/command.go:53 | imported |
| Coverage | coverageFatal | pkg/command/coverage.go:59 | local |
| Coverage | coverageFatal | pkg/command/coverage.go:65 | local |
| Coverage | onlyUnresolved | pkg/command/coverage.go:68 | local |
| Coverage | coverageFatal | pkg/command/coverage.go:74 | local |
| Coverage | BuildClients | pkg/coverage/clients.go:83 | imported |
| Coverage | RenderClientsText | pkg/coverage/clients.go:83 | imported |
| Coverage | UnsupportedNotice | internal/clientspec/clientspec.go:84 | imported |
| resolveTarget | isDirectory | pkg/command/command.go:58 | imported |
| resolveTarget | checkFatal | pkg/command/check.go:61 | local |

+28 library or method calls on this path (in the fact records)

## FLOW-012 — cli  dashboard

- Entry point: pkg/command/command.go:172 [go_dispatch_case]
- Handler: Dashboard
- Files touched: pkg/bootstrap/bootstrap.go, pkg/command/check.go, pkg/command/command.go, pkg/command/dashboard.go, pkg/dashboard/dashboard.go
- Environment reads on the path: PATH

| Step | Call | Location | Resolution |
|---|---|---|---|
| Dashboard | name | pkg/command/command.go:29 | imported |
| Dashboard | name | pkg/command/command.go:37 | imported |
| Dashboard | dashboardFatal | pkg/command/dashboard.go:44 | local |
| Dashboard | dashboardFatal | pkg/command/dashboard.go:47 | local |
| Dashboard | dashboardFatal | pkg/command/dashboard.go:53 | local |
| Dashboard | resolveTarget | pkg/command/check.go:59 | imported |
| Dashboard | Config | pkg/bootstrap/bootstrap.go:62 | imported |
| Dashboard | LoadDashboardSnapshot | pkg/bootstrap/bootstrap.go:62 | imported |
| Dashboard | name | pkg/command/command.go:71 | imported |
| Dashboard | buildVersion | pkg/command/command.go:72 | imported |
| Dashboard | GraphStateFunc | pkg/bootstrap/bootstrap.go:76 | imported |
| Dashboard | Config | pkg/bootstrap/bootstrap.go:79 | imported |

Showing 12 of 13; the rest stays in the fact records.

+27 library or method calls on this path (in the fact records)

## FLOW-016 — cli  gc

- Entry point: pkg/command/command.go:189 [go_dispatch_case]
- Handler: GC
- Files touched: internal/config/config.go, pkg/command/check.go, pkg/command/command.go, pkg/command/gc.go, pkg/command/log.go

| Step | Call | Location | Resolution |
|---|---|---|---|
| GC | name | pkg/command/command.go:35 | imported |
| GC | logTarget | pkg/command/log.go:54 | imported |
| GC | gcFatal | pkg/command/gc.go:57 | local |
| GC | parseAge | pkg/command/gc.go:62 | local |
| GC | gcFatal | pkg/command/gc.go:64 | local |
| GC | GC | pkg/command/gc.go:69 | local |
| GC | gcFatal | pkg/command/gc.go:71 | local |
| GC | renderGC | pkg/command/gc.go:73 | local |
| logTarget | isDirectory | pkg/command/command.go:182 | imported |
| logTarget | logFatal | pkg/command/log.go:185 | local |
| logTarget | fileExists | pkg/command/command.go:188 | imported |
| logTarget | Load | internal/config/config.go:195 | imported |

Showing 12 of 18; the rest stays in the fact records.

+22 library or method calls on this path (in the fact records)

## FLOW-013 — cli  diff

- Entry point: pkg/command/command.go:183 [go_dispatch_case]
- Handler: Diff
- Files touched: pkg/command/blame.go, pkg/command/command.go, pkg/command/log.go, pkg/command/show.go

| Step | Call | Location | Resolution |
|---|---|---|---|
| Diff | name | pkg/command/command.go:88 | imported |
| Diff | splitRevAndRepo | pkg/command/show.go:102 | local |
| Diff | diffFatal | pkg/command/show.go:104 | local |
| Diff | name | pkg/command/command.go:104 | imported |
| Diff | diffFatal | pkg/command/show.go:108 | local |
| Diff | historyWithStore | pkg/command/blame.go:111 | imported |
| Diff | diffFatal | pkg/command/show.go:114 | local |
| Diff | diffFatal | pkg/command/show.go:119 | local |
| Diff | diffFatal | pkg/command/show.go:127 | local |
| Diff | diffFatal | pkg/command/show.go:131 | local |
| Diff | reconstructUnion | pkg/command/show.go:134 | local |
| Diff | reconstructUnion | pkg/command/show.go:135 | local |

Showing 12 of 14; the rest stays in the fact records.

+26 library or method calls on this path (in the fact records)

## FLOW-018 — cli  hook

- Entry point: pkg/command/command.go:195 [go_dispatch_case]
- Handler: Hook
- Files touched: internal/hookstate/hookstate.go, internal/updatecheck/updatecheck.go, pkg/command/command.go, pkg/command/hook.go
- Environment reads on the path: CI

| Step | Call | Location | Resolution |
|---|---|---|---|
| Hook | runStopHook | pkg/command/hook.go:69 | local |
| Hook | runSessionStartHook | pkg/command/hook.go:71 | local |
| Hook | Refresh | internal/updatecheck/updatecheck.go:76 | imported |
| runStopHook | readHookInput | pkg/command/hook.go:87 | local |
| runStopHook | RecordSuppressed | internal/hookstate/hookstate.go:104 | imported |
| runStopHook | outputDirFor | pkg/command/hook.go:104 | local |
| runStopHook | gradeQuietly | pkg/command/hook.go:111 | local |
| runStopHook | name | pkg/command/command.go:134 | imported |
| runStopHook | unenforcedReport | pkg/command/hook.go:134 | local |
| runStopHook | name | pkg/command/command.go:147 | imported |
| runStopHook | name | pkg/command/command.go:147 | imported |
| runStopHook | ShouldReport | internal/hookstate/hookstate.go:159 | imported |

Showing 12 of 20; the rest stays in the fact records.

+20 library or method calls on this path (in the fact records)

## FLOW-022 — cli  plan

- Entry point: pkg/command/command.go:158 [go_dispatch_case]
- Handler: Plan
- Files touched: pkg/bootstrap/bootstrap.go, pkg/command/check.go, pkg/command/command.go, pkg/command/plan.go
- Environment reads on the path: PATH

| Step | Call | Location | Resolution |
|---|---|---|---|
| Plan | name | pkg/command/command.go:28 | imported |
| Plan | splitPlanPositionals | pkg/command/plan.go:48 | local |
| Plan | splitList | pkg/command/check.go:49 | imported |
| Plan | splitList | pkg/command/check.go:50 | imported |
| Plan | planFatal | pkg/command/plan.go:57 | local |
| Plan | resolveTarget | pkg/command/check.go:65 | imported |
| Plan | name | pkg/command/command.go:66 | imported |
| Plan | SetPersistCache | pkg/bootstrap/bootstrap.go:68 | imported |
| Plan | OutputDir | pkg/bootstrap/bootstrap.go:71 | imported |
| Plan | LoadSnapshotDir | pkg/bootstrap/bootstrap.go:75 | imported |
| Plan | name | pkg/command/command.go:78 | imported |
| Plan | planFatal | pkg/command/plan.go:78 | local |

Showing 12 of 14; the rest stays in the fact records.

+26 library or method calls on this path (in the fact records)
