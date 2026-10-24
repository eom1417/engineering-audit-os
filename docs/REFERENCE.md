# EAOS reference

The home page is [README.md](../README.md). This page lists the commands, the check's stages, the report folder and
the code layout.

## Commands

| Command | What it does |
|---|---|
| `eaos start [project]` | Start here: check the project (asks once about the assistant and about running the app) |
| `eaos next [project]` | The next step of the journey; fixing points to the assistant (`/eaos`) or the Studio |
| `eaos status` · `eaos show` | Where the project stands · what the check found, in plain words |
| `eaos doctor [--fix]` | Is this computer ready: every missing piece, with its fix |
| `eaos tools install\|doctor` | The external tools at their pinned versions, in `~/.eaos/tools` |
| `eaos accept` · `eaos undo` | Take the waiting branch of fixes into your branch · throw it away |
| `eaos clean` | Remove the temporary copies EAOS made; reports stay |
| `eaos do "<request>"` | Ask in your own words |
| `eaos assistant install` | Register EAOS with Claude Code and Codex (the MCP server, the `/eaos` skill, the session hook) |
| `eaos mcp` | The MCP server on stdio (what `assistant install` registers) |
| `eaos handover` | Where the work stopped, and what to tell another assistant |
| `eaos studio [project] [--background]` | The Studio of the project, on 127.0.0.1 |
| `eaos audit <project> --out <report>` | The whole check from the terminal: `--only/--skip STAGE`, `--resume`, `--engines`, `--run-app FOLDER`, `--intake FILE`, `--lang ar\|en` |
| `eaos facts <project> --out <dir>` | Deterministic facts only; a card's acceptance runs it on a changed copy |
| `eaos policy check\|init <project> --out <dir>` | The declared architecture policy (`eaos.policy.json`) |
| `eaos recheck --spec '<probe>' [root]` | A mechanical card's acceptance: exit 0 when its problem is gone |
| `eaos decided <report> <uid>` | An investigation card's acceptance: exit 0 once a decision is recorded |

## The check

`eaos/pipeline/stages.py` declares the 28 stages, what each needs and produces, and when an optional one may be
absent: `facts features lock intake engines setup record crawl screens baseline measure policy load claims probe
semantic plan target proposals triage visual cards ideal pipeline_gaps reconcile order steps reports`.
The AI stages and their guards: [AI-IN-THE-PIPELINE.md](AI-IN-THE-PIPELINE.md).

## The report folder

`~/EAOS/<project>/technical/` holds the four reports (`CURRENT-STATE.md`, `TARGET-STATE.md`, `GAP-AND-STRATEGY.md`,
`EXECUTION-PLAN.md`), `PLAN/`, the records the Studio and the fix tools read (`facts/`, `dossier.json`, `plan.json`,
`cards.json`, `target-architecture.json`, `live/`, `nodes/`, `studio/`), and `run-manifest.json` (every stage's
status, time and reason). `REPORT.html` and `HANDOVER.md` sit one level up.

## The code

| Folder | What it holds |
|---|---|
| `eaos/facts/`, `eaos/engines/` | The facts EAOS reads itself, and the external tools normalised into facts |
| `eaos/pipeline/` | The stages, their runners and the run driver |
| `eaos/compose/` | The four reports and their labels |
| `eaos/assistants/` | Running the person's assistant (Claude Code, Codex) and checking it is ready |
| `eaos/studio/`, `eaos/api/` | The Studio's data, actions and server |
| `eaos/agent_tools.py`, `eaos/mcp_server.py` | The MCP tools, including the fix journey (`fix_start` … `fix_finish`, `accept`, `undo`) |
| `eaos/waves.py`, `eaos/execute.py`, `eaos/sandbox.py` | A batch of fixes in an isolated copy, its gates, and the branch handed over |
| `eaos/guided.py` | The guided commands (`start`, `next`, …) |
| `studio/` | The Studio's source (React); `npm run build` ships it to `eaos/data/studio` |
| `tests/` | The test suite (`python -m unittest discover -s tests`) |
| `tools/` | Development helpers: `validate.py`, `make_contracts.py`, `dev_setup.sh` |
