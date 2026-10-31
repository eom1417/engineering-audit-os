# Index and reading order

> {{PROJECT}} · eaos 0.0.90 · 2026-10-31 10:40 UTC · model calls 0
> Coverage: 6/6 · claims 3 (0 semantic)
> tasks 3 · waves 1

## Read in this order

| If you are… | Start with | Time |
|---|---|---|
| wanting the whole picture: the four reports; every other document is an appendix to them | [CURRENT-STATE.md](CURRENT-STATE.md) → [TARGET-STATE.md](TARGET-STATE.md) → [GAP-AND-STRATEGY.md](GAP-AND-STRATEGY.md) → [EXECUTION-PLAN.md](EXECUTION-PLAN.md) | 20 min |
| deciding where effort goes | [START-HERE.md](START-HERE.md) → [PLAN/STEPS.md](PLAN/STEPS.md) → [PLAN/WAVES.md](PLAN/WAVES.md) | 5 min |
| reviewing the architecture | [TARGET-ARCHITECTURE.md](TARGET-ARCHITECTURE.md) → [GAP-AND-STRATEGY.md](GAP-AND-STRATEGY.md) | 30 min |
| checking how this check ran | [RUN.md](RUN.md) | 2 min |
| about to change one file | the assistant's `impact` tool (/eaos) | 1 min |

## Not examined

- unparsed source files: 0
- unresolved or ambiguous imports: 0
- invocation surfaces with no detector: 0 files
- runtime behaviour: no execution evidence in this run
- semantic review: not performed in this run (facts only)

## Every file

| # | File | Why |
|---|---|---|
| 1 | [README.md](README.md) | What this report holds and in what order to read it |
| 2 | [START-HERE.md](START-HERE.md) | The first page in plain words: what was found, what EAOS fixes alone |
| 3 | [CURRENT-STATE.md](CURRENT-STATE.md) | What the program is today: features, data, measured risk |
| 4 | [EXECUTION-PLAN.md](EXECUTION-PLAN.md) | Milestones, sections and the first cards a team starts with |
| 5 | [GAP-AND-STRATEGY.md](GAP-AND-STRATEGY.md) | The distance component by component, and the order to close it |
| 6 | [TARGET-STATE.md](TARGET-STATE.md) | The same features on the reference type, with its infrastructure |
| 7 | [EXPERIENCE.md](EXPERIENCE.md) | The users' story: who tried the app, what each reached, the difficulties confirmed with their steps and pictures, the replays — absent when: the person did not choose to try the experience |
| 8 | [TARGET-ARCHITECTURE.md](TARGET-ARCHITECTURE.md) | The structure the evidence argues for, and who decided each part |
| 9 | [PLAN/STEPS.md](PLAN/STEPS.md) | The plan's order: the assistant's steps with why, or the rules' waves |

## Reproduce

- eaos audit {{PROJECT}} --out <dir> --engines
- eaos audit {{PROJECT}} --out <dir> --resume
