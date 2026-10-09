# NS46.T15: AI nodes in the EAOS pipeline

Task: NS46.T15

Scouting record for the AI nodes (docs/STUDIO.md D11): stages of EAOS's own pipeline whose input is a deterministic
output and whose output is a structured decision, routed on by declared branches, with guards (evidence, critique,
rules-only fallback, budget, run log, cache). Written 2026-10-08, before the code of `eaos/studio/nodes/`. The
assistant versions were read on this computer (`claude --version` 2.1.285, `codex --version` 0.159.2, and their
`--help`: Claude Code has `--max-budget-usd`, Codex has no cost option); the libraries below were not re-checked
online, so none is pinned. No new package enters EAOS for this task, and no service or API key.

The rule of the brief: reuse the command centre's launcher (NS46.T9) and the planned ideal's prompt, evidence check and
provenance (NS46.T14), and generalise them into one AI-node module instead of copying them.

## Running a node: the model, and how it is asked

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| `eaos/studio/actions/adapters.py` `ask` (in EAOS, NS46.T9/T14): the person's own Claude Code or Codex, one question on standard input, the answer held to a JSON Schema by the CLI itself, its own process group, timeout and cancel | the person's own CLIs | 2026-10-08, in the repository and both `--help` | used by the planned ideal's real run on FleetManageWeb | exactly what a node needs; it lacks only a cost limit and the cost read back, both of which Claude Code offers (`--max-budget-usd`, `total_cost_usd` in its result line) |
| `eaos/studio/ideal.py` `AdapterLauncher` and `_pick` | EAOS | 2026-10-08 | NS46.T14 | the launcher shape `launcher(pass, prompt, schema) -> dict` and the choice of the first available assistant; generalised into the node module, and the ideal imports them from there |
| LangGraph (graph of LLM nodes with conditional edges) | MIT | not re-checked | active | its nodes call a model through an API client (a key the owner ruled out) and it brings its own runtime, state store and checkpointer; EAOS needs none of it to call one CLI per node |
| Burr (Apache), Prefect (Apache-2.0), PydanticAI graphs (MIT), DSPy (MIT) | as listed | not re-checked | active | workflow or agent frameworks: each would replace a 30-line driver with a service or a dependency tree, and none runs the person's own CLI assistant |

**Decision**

Build the thin layer only: `eaos/studio/nodes/core.py` runs one node through the launcher of `ideal.py`, moved there and
shared; `ask` gains an optional cost limit (passed to Claude Code as `--max-budget-usd`) and returns the cost the stream
reports. Every framework above was rejected for the same two reasons: they call models through keyed API clients, and
they add a runtime for what is a loop over a declared list.

**Pinned**

none

## The shared decision and its evidence check

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| `tools/make_contracts.py` + `eaos/artifact_contracts.validate` (in EAOS) | EAOS | 2026-10-08 | every artifact | the decision becomes a contract (`ai-node`) like every other artifact: one source, a packaged copy, validated in tests and at run time |
| `eaos/studio/ideal.py` `check`, `known_ids`, `share` and `RULES_OF_THE_ANSWER` (NS46.T14), from `eaos/semantic.py`'s rules | EAOS | 2026-10-08 | NS46.T14 | the citation rules, the ids a citation may resolve to (FACT, CLM, TASK, RULE), the untrusted-project-data rule and the share with evidence; the node module applies them decision by decision |
| Pydantic models | MIT | not re-checked | active | a second way to say what the JSON Schema already says; EAOS's contracts are JSON Schema |
| Guardrails, Instructor, Outlines | Apache-2.0 / MIT | not re-checked | active | rejected in ns46-t14-ideal-planner.md; the CLIs already hold the answer to the schema |

**Decision**

Reuse. The decision's shape is written once, in the contract `ai-node` (`subject, decision, options, evidence,
confidence, why, open_questions, source, detail`); the module reads it from the packaged contract, so a node cannot
drift from it. The evidence check is deterministic: a decision keeps only the ids that resolve, a decision with none
left, an unknown subject, a choice the node does not have, or a repeated subject is dropped and listed. A subject the
model did not decide keeps the rules' decision, marked `source: rules`.

**Pinned**

none

## Routers, fallback, budget, run log and cache

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| Declared data read by EAOS's own pipeline detector (`eaos/facts/pipeline_code.py`, NS46.T12) | EAOS | 2026-10-08 | NS46.T12 | the nodes as a declared list with `requires` and `routes=(Route(decision, to, when), ...)`: the detector already reads declared DAGs, so it only learns `kind='ai'` and `routes`, and EAOS's own map then draws the nodes and their branches from the code, as any project's would be |
| LangGraph conditional edges, Airflow branch operators | MIT / Apache-2.0 | not re-checked | active | the same idea inside a runtime EAOS does not have; the detector already reads both in other projects |
| `joblib.Memory` (BSD-3), `diskcache` (Apache-2.0) | as listed | not re-checked | active | a cache keyed by function arguments; the key here is a digest of the node, its version, the prompt and the schema, and the value is a small JSON file beside the report, which needs neither |
| MLflow / Langfuse / OpenTelemetry GenAI tracing | Apache-2.0 / MIT | not re-checked | active | run logs for model calls, each a service or an exporter to one; the command centre's runs already keep `events.jsonl` locally, and a node's log line (prompt digest, model, inputs digest, output) is one JSON line in the report |
| LiteLLM budgets | MIT | not re-checked | active | cost limits for API keys; the person's CLI is not called through it |

**Decision**

Build the glue in EAOS. Each node's router is its declared `routes`, with exactly one `rules only` route that the
deterministic fallback takes when no assistant is available, when the node is over its time budget (the framework waits
on the launcher for the budget's seconds, so even a launcher that hangs is cut off), when the answer cost more than
the budget (Claude Code is also given the limit itself), or when the answer fails. The run log is
`<report>/nodes/runs.jsonl` (append-only; the prompt and inputs as sha256 digests, the full output); the cache is
`<report>/nodes/<node>/cache/<key>.json`, keyed by the digests of the node, its version, the prompt and the schema,
so the same inputs give the same result without a new call, and a changed input asks again.

**Pinned**

none

## Where each node's work goes next

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| `eaos/probes.py` probe records (in EAOS) | EAOS | 2026-10-08 | the probe stage | a doubtful card becomes a probe request (`probe(...)`, status `not_run`) on its claim, for the probe stage to settle; nothing is run by the node |
| `docs/engine-precision.json` / `tools/precision.py` (in EAOS) | EAOS | 2026-10-08 | the labelled precision set | the triage's verdicts per detector are read beside the hand labels as their own column (the model's opinion, never a label) |
| `studio/decisions.json` and the Decisions inbox (in EAOS, NS46.T10) | EAOS | 2026-10-08 | the command centre | a node's open questions become inbox rows, as the planned ideal's do |
| `eaos/waves.py` batch records (`wave.json`, the patches) | EAOS | 2026-10-08 | the fix flow | what the fix reviewer reads: the kept and failed cards with the reason, and the diff; accept is only ever a recommendation, the person still accepts |

**Decision**

Reuse all four. The nodes write proposals beside the report (`nodes/<node>/`); they never change the plan, a card's
state or the person's branch by themselves.

**Pinned**

none
