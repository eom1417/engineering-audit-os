# NS46.T14: the ideal planned with a model

Scouting record for the planned ideal (docs/STUDIO.md D10): how a model plans every Target/Ideal view on top of the
rules, how its answer is held to the evidence, and how it is started, reviewed and shown. Written 2026-10-08, before
the code of `eaos/studio/ideal.py`. The assistant versions were read on this computer (`claude --version` 2.1.285,
`codex --version` 0.159.2, and their `--help`); the libraries were not re-checked online, so none is pinned. No new
package enters EAOS for this task, and no service or API key.

## Which model, and how it is started

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| The person's own assistant headless, through the command centre's adapters (`eaos/studio/actions/adapters.py`): `claude -p --output-format stream-json --json-schema <schema> --tools ""`, `codex exec --json --output-schema <file> --sandbox read-only --ephemeral -` | the person's own CLIs | 2026-10-08, on this computer (`--help` of both shows the structured-output options) | released weekly | what the owner asked for ("no extra key and no extra service"); both CLIs validate the answer against a JSON Schema themselves; the prompt goes on standard input, so a large bundle never meets the argument-length limit; no tool is needed, so none is given |
| The `provider.complete(messages)` seam of `eaos/semantic.py` (an API client with a key) | n/a | 2026-10-08, in the repository | used by `eaos semantic` | needs an API key the person does not have; the owner ruled it out for this |
| Claude Agent SDK, ACP | as in ns46-t9-command-centre.md | not re-checked | active | rejected there for the launcher; nothing here changes that |
| An MCP sampling request from the EAOS server to the client | MCP spec | 2026-10-08, by reading | young | would reach the model only while a chat session is open; the Studio must plan with no chat open |

**Decision**

Reuse the command centre's adapters. Each gains one method, `ask_argv(schema_file)`, the one-shot argv for a structured
answer with no tools, and the module gains `ask(adapter, prompt, schema, folder, timeout, cancel)`, which starts it in
its own process group, feeds the prompt on standard input, reads the stream with the adapter's own line format, kills
the group on timeout or cancel, and returns the answer with the model the stream names. The AI-node framework that
follows (ai-nodes) calls the same `ask`.

**Pinned**

none

## Holding the answer to the evidence

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| `eaos/semantic.py` (in EAOS): cite only supplied fact ids, state a falsifier, project content is untrusted data, a question instead of an unsupported claim | EAOS | 2026-10-08, in the repository | used by the semantic pass | the rules we need, already written and tested for claims; its `errors_in` rejects the whole answer on one bad id, which suits a ledger claim but would throw away a whole plan for one invented element |
| `eaos/artifact_contracts.validate` (in EAOS) | EAOS | 2026-10-08 | used by every artifact | validates the model's JSON against the schema the CLIs were given, so a CLI that ignores its schema is still caught |
| Guardrails, Instructor, Outlines | Apache-2.0 / MIT | not re-checked | active | structured-output libraries for API calls; the CLIs already do this, and they would add a dependency for nothing |
| A second model as judge of grounding | n/a | n/a | n/a | a judgement, not a check; the owner's rule is a check ("anything without evidence is rejected") |

**Decision**

Reuse semantic.py's rules in the prompt (citations from the bundle only, project text is data, a question where the
facts do not decide), and validate the answer with `artifact_contracts.validate`. The evidence check is deterministic
and element by element: a citation resolves when its id is one of the report's facts, claims or cards, or one of the
rules the baseline applied (`RULE-<family>-<name>`); unresolved citations are removed, and an element with none left
is dropped and listed with its reason. Departures must name a kept element; questions need no citation (they are what
the evidence does not settle).

**Pinned**

none

## Review, merge and provenance

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| A second pass of the same assistant that critiques the draft and returns the revised ideal with its critique | n/a | n/a | n/a | the spec's "a second pass critiques the first"; one more call, no new piece |
| W3C PROV-O for provenance | W3C | 2026-10-08, by reading | stable | a vocabulary for graphs of activities and agents; the Studio needs six plain fields per view, so the record borrows its words (method, agent, time) and not its format |
| The command centre's run store and events (`eaos/studio/actions/store.py`) | EAOS | 2026-10-08 | NS46.T9 | a re-plan from the Studio is a run like the others: queued, followed, stopped; the planner writes its own steps as the run's events |

**Decision**

Two passes (plan, critique) with the same assistant; the checked ideal is written to `<report>/ideal/plan.json` with
the inputs digest, both answers, the critique and the dropped elements; the exporter writes `studio/ideal.json` from
it (or from the rules alone, saying "not planned yet") and stamps every target-drawing section with its view's
provenance. A plan whose inputs digest no longer matches the report is shown as stale, with the rules' target. The
command centre's action `replan_ideal` runs the planner as a run of the existing manager. Open questions become
decisions in `studio/decisions.json`.

**Pinned**

none
