# Adopt before build: scouting records

The owner's rule (EAOS v2, 2026-10-08): before any code is written for a new capability, a scouting record says
which existing projects could do it, under which licence, how alive they are, and what was decided. EAOS writes code
only where the record shows nothing adequate exists, or for the thin glue that wires an adopted project in.

The source of the candidates is `eaos-dev/planning/studio-v2/E-adopt-before-build.md` (lens E of the v2 plan); a
record here narrows it to one task and pins what is adopted.

## The format of a record

One file per task, `docs/adoption/<task>.md`. Each capability is a `## ` section that holds, in this order:

- `**Candidates**`: a table with every candidate looked at, its licence, the version and date it was checked at,
  and its maintenance (last release, open source health).
- `**Decision**`: adopt, build (with the reason no candidate fits) or reject, in one paragraph.
- `**Pinned**`: the packages adopted, each as `` `name@version` ``, or `none`.

The licence policy is `docs/TOOLCHAIN.md` §2: a library bundled into the Studio is embedded, so only MIT, BSD, ISC,
Apache-2.0, CC0, OFL (fonts) and file-level copyleft left unmodified (MPL-2.0, EPL-2.0) are accepted.

## How the plan measures it (indicator W2)

`python tools/north_star.py measure --only W2` reads every record here. W2 is the share of the plan's tasks that ask
for a record (a step naming `docs/adoption/`) and have begun (done, or code committed for them) whose record is
complete (candidates, licence, maintenance, decision) and was committed no later than the task's first code. A record
names its tasks on a `Task:` line, or by its file name (`ns37-t1-…` is NS37.T1). A task that writes Studio code
(`studio/`) also needs every package of `studio/package.json` pinned by a complete section of a record committed no
later than the commit that first added that package to `studio/package.json`: a package added without a record, or a
record written after the package came in, fails that task. When several records name one task, the earliest complete
one is its record.

## Records

| Task | Record |
|---|---|
| NS37.T1 design system and shell | [ns37-t1-studio-shell.md](ns37-t1-studio-shell.md) |
| NS37.T1 finishing: bundle locales, one screen gate | [ns37-t1-finish.md](ns37-t1-finish.md) |
| NS37.T2 local read server and live stream | [ns37-t2-live-server.md](ns37-t2-live-server.md) |
| NS38.T1 labelled precision set | [NS38.T1-precision-harness.md](NS38.T1-precision-harness.md) |
| NS46.T1 contract v2 and its fixtures | [ns46-t1-contract-v2.md](ns46-t1-contract-v2.md) |
| The System maps (territory, change, target) | [studio-maps.md](studio-maps.md) |
| Code paths, sequences and the plan timeline | [studio-map-paths.md](studio-map-paths.md) |
| NS46.T6 user journeys, visible and hidden | [studio-journeys.md](studio-journeys.md) |
| The data paths map and the infrastructure lens | [studio-map-data.md](studio-map-data.md) |
| NS46.T9 command centre: action API and assistant launcher | [ns46-t9-command-centre.md](ns46-t9-command-centre.md) |
| The pipeline map's engine (stages, value flow, routers, declared DAGs, CI and build chains) | [ns46-t12-pipeline-engine.md](ns46-t12-pipeline-engine.md) |
| NS46.T9 command centre: action API and assistant launcher | [ns46-t9-command-centre.md](ns46-t9-command-centre.md) |
| NS46.T14 the ideal planned with a model | [ns46-t14-ideal-planner.md](ns46-t14-ideal-planner.md) |
| NS46.T14 the ideal planned with a model | [ns46-t14-ideal-planner.md](ns46-t14-ideal-planner.md) |
| NS46.T15 AI nodes in the EAOS pipeline | [ns46-t15-ai-nodes.md](ns46-t15-ai-nodes.md) |

| NS46.T4 Library reader, History and EAOS quality | [ns46-t4-library-history-quality.md](ns46-t4-library-history-quality.md) |
| Task-runner scripts traced to the program they run | [script-handlers.md](script-handlers.md) |
