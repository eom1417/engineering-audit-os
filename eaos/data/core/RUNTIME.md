# Executable architecture audit and remediation runtime

This is the runnable path. The existing `audit/next` commands remain available for a host coding agent that performs the reasoning itself. `run` invokes a configured model through every stage; it does not stop after creating templates.

## Quick start

Install the included wheel or `python -m pip install .` from the repository. Python 3.10+ is declared; release tests were executed on Linux/Python 3.12.

Create a provider config OUTSIDE the target repository using the model you have access to:

```json
{
  "kind": "chat_completions",
  "endpoint": "https://api.openai.com/v1/chat/completions",
  "model": "YOUR_MODEL_ID",
  "api_key_env": "OPENAI_API_KEY",
  "timeout_seconds": 120,
  "max_calls": 400,
  "max_response_bytes": 2000000
}
```

The environment variable must already contain your API key. Keys are not stored in the config or reports. Choose a model/endpoint that supports Chat Completions JSON output. An HTTPS-compatible provider can use a different endpoint; a local model can use loopback HTTP and `"api_key_env": ""`.

```bash
eaos run /absolute/project --out /absolute/audit --provider /absolute/provider.json
```

The provider is the model doing the reasoning. EAOS controls its read access, stage sequence, contracts, records, context and completion checks. The configured endpoint receives eligible, redacted source excerpts. Only configure an endpoint authorized to receive this repository. Redaction is heuristic, not a guarantee of removing every secret or personal datum.

After interruption:

```bash
eaos continue /absolute/audit --provider /absolute/provider.json
```

Completed jobs are reused only when input identity, result checksum, references and record dependencies remain valid. Source changes require a fresh run. Transport timeout and max_calls can be increased without changing semantic model identity. Budget exhaustion preserves work; it does not become a false completed audit. Engine lock files prevent overlapping runs; remove a stale lock only after confirming its process is gone.

## What the engine executes

1. Inventory all surfaces, hash eligible files and record exclusions.
2. Stream every eligible text range into bounded inspection batches. Keep original briefs addressable; do not silently sample a large repository.
3. Synthesize briefs hierarchically, then reconstruct responsibilities, contracts, dependency direction, business-rule ownership, flows and change scenarios.
4. For each of the 27 domains, decide applicability. For applicable domains declare component × flow × environment coverage BEFORE executing the checks. Core architecture domains cannot be excluded.
5. Execute domain reviews with retrieval of actual source. Record evidence, counter-evidence, hypotheses and full findings. Source-only reviews cannot certify unobserved production configuration.
6. Challenge the root-cause diagnosis, including alternative explanations, missing structural causes and duplicated findings. Reconcile challenged results and recheck them, with up to two correction passes.
7. Design concrete target components, dependencies, contracts, ownership, architecture decisions and a staged migration. Each remediation task links to a finding, invariant, existing change scenario, decision, files, tests, dependency order and rollback.
8. Challenge the proposed migration and revise it if needed, with up to two correction passes.
9. Carry uncertainty across stages. Every question needs an evidence-backed resolution or remains open. Missing source and unresolved challenge blockers cannot disappear through summarization.
10. Validate and render the deliverables. Remaining blockers are included in the result; an agent cannot get COMPLETE by omitting them from a summary.

These are model-assisted engineering judgments. The challenge passes are separate requests to the same configured provider; they are not independent human reviews or a guarantee against correlated model mistakes.

## Deliverables

| Artifact | Content |
|---|---|
| EXECUTIVE.md | Main findings, causes and priorities |
| ARCHITECTURE.md + architecture.mmd | Observed components, responsibilities, contracts, rules and graph |
| architecture.json + flows.json | Machine-readable current model and journeys |
| TARGET-ARCHITECTURE.md + target-architecture.mmd | Concrete target structure, decisions, alternatives, tradeoffs and migration |
| IMPLEMENTATION-PLAN.md + roadmap.json | Ordered work packages with invariants, costs, risks, tests and rollback |
| findings.json + evidence.json | Full findings and reproducible source references |
| coverage.json + surface-review.json | Domain/flow checks and per-file accounting |
| diagnosis-challenge.json + plan-challenge.json | Adversarial review results |
| uncertainty-resolutions.json | Question resolutions when unresolved questions were raised |
| report.md | Full combined report including limits and exclusions |
| usage.json | Calls, request characters and provider-reported token usage if supplied |
| engine-state.json | Computed engine completion and current blockers |
| jobs/ | Checksummed results for resumable work |

`COMPLETE` applies only to the declared audited scope and evidence. It does not mean every possible defect has been found, the plan has been implemented, or deployment is authorized. Exit 0 means the requested deliverable passed its gates; exit 2 means blocked, partial or invalid work. Partial reports and completed job records remain available.

## Implement a task

First inspect the actual roadmap and choose the real task ID. Define verification commands for its predeclared gate IDs:

```json
{
  "checks": [
    {
      "id": "ACTUAL_GATE_ID_FROM_ROADMAP",
      "argv": ["python", "-m", "unittest", "discover", "-s", "tests"],
      "cwd": ".",
      "timeout_seconds": 120
    }
  ],
  "inherit_env": []
}
```

This Python command is an example, not a universal test strategy. Use the target's real build, typecheck, lint, integration, migration and regression commands as appropriate. Do not map every gate to an unrelated trivial check. Passing tests is insufficient unless the tests protect the stated invariant.

```bash
eaos implement /absolute/audit --task ACTUAL_TASK_ID \
  --out /absolute/candidate --checks /absolute/checks.json \
  --provider /absolute/provider.json
```

This explicit command authorizes the listed check commands and model-proposed edits within the task's planned paths, in a NEW COPY. It:

1. Validates the plan, confirmed findings and prerequisite tasks.
2. Copies eligible source into `candidate/project`, excluding sensitive files and dependency/build directories.
3. Runs baseline commands. A failed baseline or source mutation stops the change.
4. Asks the model for concrete edits, requiring it to read complete existing files before replacing them. Rejects traversal, symlinks, sensitive paths and changes outside the task.
5. Runs the configured checks and verifies they did not mutate prepared source or files outside the plan. Failed candidates can receive up to two repair retries.
6. Re-audits the changed invariant against the changed source snapshot and actual test results.
7. Produces `changes.patch`, `RESULT.md` and `verification/` evidence. The original repository and its historical findings are not relabeled as repaired.

The copy is not an OS sandbox. Configured commands are trusted user-selected code; they can have effects outside their working directory. Use a container/VM for untrusted projects. Dependency installation is not automatic: configure a prepared environment or an explicit appropriate check; never assume a test passed because dependencies were absent. Project secrets are not copied automatically, and only explicitly inherited environment variables are passed to checks, beyond minimal process environment.

## Execute a sequence of improvements

```bash
eaos improve /absolute/audit --out /absolute/campaign \
  --checks /absolute/checks.json --provider /absolute/provider.json --max-steps 10
```

The campaign chooses a dependency-ready remediation task, implements and verifies it, then runs a NEW full audit on the changed copy before choosing the next task. Unchanged source-inspection jobs may be reused by content identity; global architecture and findings are reassessed. It never changes revision strings on old evidence to pretend a repair was verified.

`campaign.json` identifies every input audit, task, candidate and result. A campaign ends COMPLETE only when the latest audited scope is complete and no unresolved findings remain. Investigations, accepted/deferred risks, failing checks and step limits remain explicit. The checks file must cover the actual gate IDs in each generated plan; missing verification is not guessed. Deployment/merging into the original project remains separate from producing reviewed changes.

## Existing coding agent adapter

A user-selected command can adapt an already installed agent/model:

```json
{
  "kind": "command",
  "argv": ["/absolute/path/to/your-model-adapter"],
  "timeout_seconds": 120,
  "max_calls": 400
}
```

The adapter receives one JSON object `{"messages":[...]}` on stdin and must emit one JSON object on stdout:

```json
{"action":"final","result":{"fields":"according to the supplied stage contract"}}
```

Or it requests bounded source/record reads using the supplied protocol. It is invoked without a shell, from an empty working directory. No brand-specific coding-agent CLI is falsely advertised as compatible without an adapter. The host-driven `audit/next` workflow is available without an API adapter and uses the agent you are already running.

## Context and failure behavior

Default request budget: 96,000 characters; this is NOT a token measurement. Default per-job bound: 8 model rounds. Model response size, network/command timeouts, run max_calls and campaign max_steps are explicit. Whole-repository text is streamed, not kept in one prompt. Large briefs are reduced into an index while originals remain retrievable. Oversized single source lines, binary/sensitive content and inventory truncation are reported rather than silently counted reviewed.

Commands/providers may fail. Jobs persist before subsequent work; a malformed response receives contract feedback, while transport failure preserves the run for `continue`. Raising a budget does not make missing evidence pass. Provider error bodies and stderr are withheld to avoid printing credentials.

## Verification evidence for this delivery

The test suite exercises the full engine, real subprocess transport, a local HTTP protocol server, source retrieval, corrupt/missing output, cache resumption, source drift, design revision, actual baseline/post-change checks, an isolated root-cause repair fixture and a multi-snapshot campaign. Model judgments in those automated integration tests are SCRIPTED fixtures, not live external-model evaluations.

Separately, the host coding agent applied EAOS to its own source, discovered defects, wrote failing regressions, fixed the implementations and recorded before/after evidence. That is a substantive self-review, not an independent security certification. Current measurements and remaining limits are in docs/CAPABILITY-SCORE.md and evaluations/release-evidence.json.

Provider protocol reference: [OpenAI Chat Completions API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create). The adapter uses model/messages/JSON response format and optional max_completion_tokens; it does not hardcode model availability or pricing.
