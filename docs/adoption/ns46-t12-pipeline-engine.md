# The pipeline map's engine: what was adopted

Task: NS46.T12

Checked on 2026-10-08 against PyPI, GitHub releases and the projects' repositories, for the pipeline map
(STUDIO-COMPLETE.md, "The pipeline map"; `docs/STUDIO.md` D9): find whether a project, or a part of it, is a pipeline,
its stages, the data flow between them, its routers and branches, fan-out and fan-in, failure routes and hidden side
channels, all from the code and never by running it. What EAOS already has was looked at first: the stdlib `ast`
reading of `eaos/facts/syntax.py` and `eaos/facts/sequences.py`, the call edges of `facts/syntax.json` and the
resolver of `facts/resolve.json`, the flows of `eaos/facts/flows.py`, the CI reading of `eaos/facts/runtime.py`, and
the layered ordering of `eaos/arch_map.py`.

## Value flow and stages in Python code

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| pyan3 | GPL-2.0 | 2.9.0 (2026-10-06) | active again | A static call graph; no value flow (which return feeds which argument), and GPL, which EAOS does not embed |
| PyCG | Apache-2.0 | 0.0.8 (2023-11-26) | archived by its authors | A precise call graph (ICSE 2021); no data flow, and no longer maintained |
| code2flow | MIT | 2.5.1 (2023-01-08) | no release for almost three years | Draws call graphs; by name only, no value flow |
| LibCST | MIT | 1.9.0 (2026-07-29) | active (Meta) | A concrete syntax tree with scope analysis; the same information `ast` gives for what we read, as a new dependency |
| astroid | LGPL-2.1 | 4.3.4 (2026-10-08) | active (pylint) | Inference of what a name holds; heavy, and inference is not needed to follow `x = f(); g(x)` |
| EAOS's own reading: stdlib `ast` (as `facts/syntax.py` and `facts/sequences.py` read Python) plus `facts/syntax.json` call edges | ours | — | in EAOS | Assignments and arguments give the value flow directly; the call edges and symbols already in the facts give who calls which stage and which stage nothing reaches |

**Decision**: build on what EAOS has, no package. `eaos/facts/pipeline.py` reads Python with the standard `ast`, the
parser `facts/syntax.py` already uses, and follows values only where the code shows them: a name assigned from a
stage's call and passed to a later stage's call, an accumulator keyed by a stage's name, a declared `requires`. It
runs inside the facts stage as one more extractor, so its facts sit beside the others and the cards can cite them. A
dead stage is one a registry holds that the declared stage list never names; joining the `call_edge` facts of
`facts/syntax.json` for reachability is left for a later step (amended 2026-10-08: the first version of this record
said the call facts were used for it, which the code does not do). A call EAOS cannot follow (a name looked up at run
time) is written as an unresolved step, never as an edge. None of the candidates follows values between calls, which
is the fact the map needs; the call-graph ones repeat what the facts hold.

**Pinned**: none

## Declared DAG frameworks (Airflow, Prefect, Dagster, Luigi, Celery, LangGraph, Temporal, Step Functions, n8n, Node-RED)

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| Airflow's `DagBag` (apache-airflow) | Apache-2.0 | 3.3.2 (2026-09-17) | active (ASF) | Parses DAGs by importing the DAG files: it runs the project's code, which EAOS never does without consent, and needs Airflow installed |
| Prefect / Dagster / Luigi / Celery loaders | Apache-2.0 / Apache-2.0 / Apache-2.0 / BSD-3 | current | active | The same: their graphs exist only after importing the user's modules |
| Static reading of the frameworks' own syntax (operators and `>>`, `@task`/`@flow` calls, `chain`/`group`/`chord`, `add_node`/`add_edge`/`add_conditional_edges`) | ours | — | — | What the frameworks document as the way a graph is declared, read without running it |
| JSON exports (n8n `nodes`/`connections`, Node-RED flows, Step Functions ASL `States`/`Next`/`Choices`) | — | — | — | Plain JSON: `json` reads them |

**Decision**: read the declarations statically, no package. Importing a project's DAG files runs its code (and its
imports), which the evidence-first rule forbids for an audit. The frameworks' declaration syntax is small and
documented; each kind found is recorded with its file and line, and a graph built at run time (a loop creating tasks
from data EAOS cannot see) is a counted unresolved step.

**Pinned**: none

## GitHub Actions, Makefile and justfile, npm scripts

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| PyYAML | MIT | 6.0.3 (2025-09-25) | active | A full YAML reader; loses the line numbers the evidence needs, and is not an EAOS dependency |
| actionlint | MIT | 1.7.12 (2026-03-30) | active | Checks workflows (Go binary); its job graph is internal, not an output |
| `eaos/facts/runtime.py` `yaml_load` | ours | — | in EAOS | Refuses block scalars (`run: |`), which every workflow has |
| A line reader for `jobs:` and `needs:` | ours | — | — | `needs` is a scalar, a flow list or a block list under each job: a few lines, with the line of each job and need |

**Decision**: build the small line reader for `jobs`/`needs` (with lines, for the evidence), read Make and just
targets with their prerequisites by line, and npm script chains (`npm run a && npm run b`) from `package.json` with
`json`. No package.

**Pinned**: none

## Layout of the stages

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| ELK (`elkjs`) | EPL-2.0 | 0.12.0 (2026-07-17) | active (Eclipse) | The layered layout the spec names for the page; a 1.4 MB bundle or a worker in the reader's browser |
| EAOS's layered ordering (`eaos/arch_map.py`: `feedback_edges`, `layer_of`, `order_columns`) | ours | — | in EAOS | Layers by longest path after setting cycle edges aside, then barycentre sweeps: what a left-to-right pipeline needs |

**Decision**: reuse `arch_map` in the exporter, as the System, Paths and Data maps do: `studio/pipeline.json` carries
each stage's layer and order, so positions are stable between views and runs and the Studio only draws. Whether the
page adds ELK for routing the edges is the page task's (NS46.T13) own record.

**Pinned**: none
