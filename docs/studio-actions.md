# The command centre: the Studio's action contract

The owner's decision of 2026-10-08 (docs/STUDIO.md D8): the Studio is where EAOS is operated, not only read.
`docs/studio-actions.json` is the contract between the Studio pages (NS46.T10), the local server (NS37.T2) and the
action handlers (`eaos/studio/actions/`, NS46.T9). A byte-identical packaged copy is `eaos/data/studio-actions.json`;
`tests/test_studio_actions.py` holds the two equal and every MCP tool present.

## What it defines

| Part | In short |
|---|---|
| `actions` | Every MCP tool of `eaos/mcp_server.py` as an action: `id` (= the tool), label and description in English and Arabic, `inputs` (a JSON schema), `mode` (`direct`: EAOS is called without an assistant; `assistant`: a reasoning step the person's assistant runs), `irreversible` (needs an explicit confirm), `needs_consent` (the one-time run consent), `returns_job`, `changes_code`. One action is not an MCP tool (`tool` null): `replan_ideal`, the planner of the ideal (docs/STUDIO.md D10, `eaos/studio/ideal.py`), which the run manager runs itself with the person's assistant (`adapters.ask`), its steps as `step` events; with no assistant it fails plainly and the rules' target stays. |
| `verbs` | Fix, Verify, Explain and Plan over a selection, each with the EAOS tools the assistant may use and the result the person gets. |
| `selection` | One card, several cards, a group (by area, severity, component, gap or operation) or a plan step, resolved to card ids on the server from the latest check's Studio data. Only open cards run. |
| `lifecycle` | `queued`, `running`, `paused`, `waiting_for_person`, `done`, `failed`, `stopped`, with every transition. One run at a time per project; the rest queue, in an order the person can change. |
| `events` | The run's event log: a gapless `seq` per run (the SSE id), the time, the `kind` (`state`, `step`, `read`, `edit` with its diff, `check` with its result, `screenshot`, `progress`, `question`, `answer`, `result`, `error`, `action`, `say`), a sentence in both languages, the data, and a hash chain (`prev`, `hash`) in the envelope of D-platform 2.5. |
| `preview` | What a run will do before it runs: the cards and the ones left out, the files, the batches, the estimated time, the risk, what happens on failure, the assistant (or the handoff), and a single-use `confirm` token when it changes code or cannot be undone. |
| `endpoints` | `POST /api/actions/<id>/preview`, `POST /api/runs`, `GET /api/runs`, `GET /api/runs/<id>`, `GET /api/runs/<id>/events` (SSE, `Last-Event-ID`), `POST /api/runs/<id>/{pause,resume,stop,retry}`, `POST /api/runs/reorder`, `GET /api/questions`, `POST /api/questions/<id>/answer`, `POST /api/runs/<id>/{accept,undo}` with the confirm token, and `GET /api/session`, `/api/actions`, `/api/assistants`. |
| `security` | 127.0.0.1 only; a launch token on every call; a CSRF token and an Origin and Host check on every POST; constant-time compares; every action logged before it runs; nothing on the network. |
| `assistants` | Claude Code (`claude -p --output-format stream-json --verbose` with the EAOS MCP server), Codex (`codex exec --json`), and the handoff when neither is available: a request the next `status` call returns, and a copyable text. |
| `snapshot` | From a file, with no server, every action button shows how to start the live Studio (`eaos studio`) and the request to copy to an assistant. |

## Guarantees that do not change

- Code changes only in EAOS's isolated copy, handed over as a new branch; the person's branch is never touched.
- Accept, merge and undo need the person's explicit confirmation (the confirm token from their preview).
- Running the project's code still needs the one-time run_setup consent; an assistant never gives it.
- The assistant changes code only through the EAOS tools: no shell, no direct file write.

## Mounting it on the read server (NS37.T2)

The handlers are framework-agnostic (`eaos/studio/actions/__init__.py`): `Actions.handle(method, path, headers, body)`
returns `(status, dict)` for every endpoint, and `Actions.sse(run, last_event_id, follow=True)` yields the event
stream. The read server mounts them next to its own routes, with the same launch token:

```python
from eaos.studio.actions import Actions, mount
actions = Actions(project, port=port, token=launch_token)   # 127.0.0.1:<port>; the CSRF token is actions.csrf
mount(app.router, actions)                                   # /api/session, /api/actions…, /api/runs…, /api/questions…
```

The page gets the CSRF token from `GET /api/session` and sends `X-EAOS-Token` and `X-EAOS-CSRF` on every call; an
`EventSource` passes the token as `?token=` (it cannot set headers) and resumes with `Last-Event-ID`. The read server
keeps its own routes under other paths; both share `127.0.0.1` and the token. Without Starlette,
`eaos.studio.actions.serve.serve(actions)` serves the same API with the standard library (the trial uses it).

## Where a run lives

`~/.eaos/projects/<project>/runs/<run>/`: `run.json`, `events.jsonl` (hash-chained), `stream.jsonl` (the assistant's
raw output) and `stderr.log`; `runs/queue.json` holds the queue's order and `runs/dispatch.lock` the one server that
starts runs. The assistant handoff waits in `~/.eaos/projects/<project>/studio-requests.json`; `status` hands it to the
next assistant and a `note` that starts with `studio-request <run> done` closes it. In a run the Studio started
(`EAOS_STUDIO_RUN` set), `accept`, `undo` and `choose_branch` refuse: the person decides those in the Studio.
