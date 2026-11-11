"""The AI nodes of EAOS's pipeline, declared as data.

Each node takes a deterministic output, analyses it, plans and decides, and writes one structured decision per subject
(eaos/features/assistant/analysis/framework.py, contract `ai-node`). After each node a router of declared branches (`routes`) sends every
subject on by its decision, to the next node or out of the pipeline (`SINKS`); each node has exactly one route
"rules only", the one every subject takes when the rules decide alone. `requires` names the nodes whose result a node
reads, in this order.

    run(report, names=None, launcher=None, adapters=None, project=None, lang='en', fresh=False, **inputs)
        runs the named nodes (all by default) whose inputs exist, in order, and returns {name: record}.

The declaration (NODES) and the run: nodes/pipeline.py.
"""
from .pipeline import BY_NAME, NODES, SINKS, TITLES_AR, run, summary  # noqa: F401
