# NS46.T9: the command centre's action API and assistant launcher

Scouting record for the command centre (docs/STUDIO.md D8, `docs/studio-actions.json`): how the Studio starts the
person's assistant and reads what it does, what holds a run and its events, and how the actions are served and
protected. Written 2026-10-08, before the code of `eaos/studio/actions/`. The assistant versions were read on this
computer (`claude --version`, `codex --version`); the libraries' versions were not re-checked online, so none is
pinned. No new package enters EAOS for this task.

## Driving the assistant headless

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| Claude Code print mode, `claude -p --output-format stream-json --verbose` (with `--resume <session>`) | the person's own CLI | 2026-10-08, Claude Code 2.1.285 on this computer | released weekly | already drives EAOS in `tools/mcp_trial.py` and `tools/handover_trial.py`; one JSON object per line (`system`/`init` with the session, `assistant` with `tool_use` and `text`, `user` with `tool_result`, `result`); MCP config by `--mcp-config` and tool limits by `--allowedTools`/`--disallowedTools` |
| Codex `codex exec --json` (and `codex exec resume <session>`) | Apache-2.0, the person's own CLI | 2026-10-08, codex-cli 0.159.2 on this computer | released weekly | already drives EAOS in `tools/handover_trial.py`; JSONL `thread.started`, `item.started`/`item.completed` (`agent_message`, `mcp_tool_call`, `command_execution`, `file_change`), `turn.completed`; MCP server by `-c mcp_servers.eaos=...` |
| Claude Agent SDK (Python) | Anthropic commercial terms | not re-checked | active | the same engine as a library; it would need an API key or the CLI underneath, and a second way to configure tools |
| Agent Client Protocol (ACP, Zed) with `claude-code-acp` / `codex-acp` | Apache-2.0 | not re-checked | young, active | one JSON-RPC protocol for both assistants with permission requests; one more adapter process to install per assistant, which a non-developer on a Mac would have to get right |

**Decision**

Adopt the assistants' own headless modes. They are what the person already installed and logged into, what EAOS's
trials already drive, and they need nothing new. Each is wrapped by one small adapter
(`eaos/studio/actions/adapters.py`): detect installed and logged in, build the argv with the EAOS MCP server and the
tool limits, and turn each stream line into the contract's events. The adapter interface is the seam where ACP can be
added later without touching the run manager. Real recorded streams from the handover trial are kept, shortened and
without paths or signatures, under `tests/fixtures/studio/actions/` and parsed by the tests.

**Pinned**

none

## The run, its queue and its event log

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| `eaos/jobs.py` (in EAOS) | EAOS | 2026-10-08, in the repository | used by every long MCP tool | a detached job with a record on disk; the right model for EAOS's own long work, which the runs reuse through the tools; it has no events, questions or queue |
| `eaos/handover.py` journal and `HANDOVER.md` (in EAOS) | EAOS | 2026-10-08 | used by every MCP call | every tool call already lands there, from the assistant's MCP server; the runs leave it as it is, so an assistant in chat continues a Studio run |
| The event envelope of D-platform 2.5 (NS39, not built yet) | n/a (design) | 2026-10-08, `eaos-dev/planning/studio-v2/D-platform.md` | planned | `seq`, `id`, `at`, `kind`, `data`, `prev`, `hash`; a run's `events.jsonl` uses this envelope and hash chain so NS39's project event log can absorb it |
| huey, RQ, Celery, Dramatiq | MIT / BSD | not re-checked | active | task queues with workers; they need Redis or a broker, or a second process to manage, for a queue of a few runs per project |
| SQLite (stdlib) | public domain | in Python | n/a | would hold runs well; the rest of EAOS's local state is JSON files a person can open, and the store is NS39's to introduce |

**Decision**

Build a small run manager on the patterns EAOS already has: a run is a folder in the project's EAOS workspace
(`~/.eaos/projects/<project>/runs/<run>/`) with `run.json` written atomically (as `jobs.py` writes its records) and an
append-only `events.jsonl` in the D-platform envelope; the queue order is `runs/queue.json`; one dispatcher per project,
held by a file lock, so two servers never start the same run. EAOS's long work stays in `jobs.py`, called through the
tools as before. A brokered task queue is rejected: it adds a service to install and run for a handful of runs.

**Pinned**

none

## Serving and protecting the actions

**Candidates**

| Candidate | Licence | Checked | Maintenance | Fit |
|---|---|---|---|---|
| FastAPI / Starlette with sse-starlette | MIT / BSD-3 / BSD-3 | not re-checked | active | NS37.T2's choice for the read server (docs/north-star.json NS37 tools); the actions mount on it |
| starlette-csrf, itsdangerous | MIT / BSD-3 | not re-checked | active | CSRF tokens and signed values; both a few lines over `secrets` and `hmac` here, where there is one user and one launch |
| Python stdlib `secrets`, `hmac.compare_digest` | PSF | in Python | n/a | random tokens and constant-time compares |

**Decision**

Build the handlers framework-agnostic: one `Actions.handle(method, path, headers, body)` returning `(status, dict)`
and an SSE frame iterator, with the security checks inside, so the server of NS37.T2 mounts them with a few lines
(`eaos.studio.actions.mount`, a Starlette router when Starlette is installed) and the tests need no server. The
tokens, the CSRF check and the confirm tokens use the stdlib only. Adopting starlette-csrf would tie the checks to one
framework and add a dependency for twenty lines.

**Pinned**

none
