# EAOS inside your AI assistant (MCP)

EAOS runs as an MCP server, so Claude Code or Codex can check, fix, build and extend a project for a person who
just asks in their own words: "check my project and fix the most important problems". The assistant calls EAOS's
tools, reads the code itself and writes the changes; EAOS gives the evidence, keeps every change in an isolated copy,
checks it, and hands it over as a git branch.

| The assistant (Claude Code or Codex) | EAOS |
| --- | --- |
| Understands the request and chooses the steps | Exact evidence: the problems and where they are, the structure, the plan |
| Reads the code and writes the fix | An isolated copy of the project, with a temporary local database |
| Proposes how to run the app when detection is not enough | Refuses what is unsafe, runs the rest, reports the result as it is |
| Explains the outcome to the person in plain words | The gates (the problem is gone, nothing broke, every screen as before, no endpoint gone), then a branch of its own |

On this path the brain is the person's own assistant, with everything it sees of the project. The safety rules live in
EAOS, not in the instructions: nothing leaves this computer, no command outside the package managers and the
runtimes, and the person's checked-out branch and files are never touched.

The assistant comes back to the person only for what is theirs to decide: which branch to work on (when there are
several), one agreement before their app runs and fixes are prepared, and at the end whether to take the branch in
(`accept`) or throw it away (`undo`).

## Setup

`install.sh` runs `eaos assistant install` for every assistant it finds on the computer. Run it again at any time; it
replaces only EAOS's own part of each file.

| Assistant | What `eaos assistant install` writes |
| --- | --- |
| Claude Code | The MCP server for the user (`claude mcp add --scope user eaos -- eaos mcp`), the skill `~/.claude/skills/eaos/SKILL.md`, and a SessionStart hook in `~/.claude/settings.json` |
| Codex | The MCP server in `~/.codex/config.toml`, the guide between marker lines in `~/.codex/AGENTS.md`, the skill `~/.codex/skills/eaos/SKILL.md`, and a SessionStart hook in `~/.codex/hooks.json` (Codex asks the person once to trust it) |

The server itself is `eaos mcp`, speaking MCP over stdio. Any MCP client can start it the same way. Its `initialize`
answer carries instructions that tell the assistant the whole way, in order, and what to ask the person.

**The menu.** Typing `/eaos` alone in Claude Code (or `$eaos` in Codex) shows the `menu` tool's options: only those that
make sense for the project now, the recommended one first, in pages of four (`eaos/interfaces/menu.py`). Claude Code
shows them as a choice like `/model`; Codex as a numbered list. The server also offers prompts, which Claude Code lists
as `/mcp__eaos__<name>`: `build`, `audit`, `fix`, `status`, `continue`, `report`, `tasks`, `ask` (takes the question)
and `tools`.

## The tools

`eaos mcp` exposes 66 tools. Every tool takes `project`, the project folder (by default, the folder the assistant was
opened in). Long work returns a job, followed with `wait`. `status` always names the next tool to call.

**An open exception: `status` is declared read-only and is not always.** On a settled project it writes only its journal line. Its first
call makes the project's state and settles its branch, it records that the branch question was asked, it brings the state up to what
git says, and it rebuilds a report an older EAOS made. An assistant or client must not take its `readOnlyHint` as a promise that
nothing is written. Every other tool that acts says so.

### Orient and continue

| Tool | What it does |
| --- | --- |
| `status` | Where the project is in the EAOS way, the next tool to call, the progress, and the hand-over (what the last assistant did and noted, and how to continue without asking the person again). Call it first, every session |
| `menu` | What to offer a person who typed `/eaos` alone: the options that make sense now, the recommended one first, each described from the project's own numbers |
| `note` | A note for whoever continues the work: what was found, decided, and about to be done. Every call is already recorded; the note adds the why |
| `projects` | Every project EAOS knows on this computer: name, folder, score, when it was checked, whether its Studio runs |
| `tools_check` | This EAOS (version, commit) and every external tool: installed or not, at which version, whether this project needs it, and the one command that installs what is missing |
| `assistant_check` | Each AI assistant on the computer, really asked for one word: ready, or the exact reason (not installed, not signed in, sign-in expired, usage limit, no answer) and its fix |

### Branches

| Tool | What it does |
| --- | --- |
| `branches` | The person's branches (bots' and EAOS's left out): when each last changed, how far ahead of and behind the main branch, and the recommendation |
| `choose_branch` | Work on this branch from now on; the check, the run, the fixes and the progress follow it. Takes `person_said`, the person's own reply. Their checkout is not switched |
| `branch_view` | The branches as the Studio's branch screens show them: `inventory`, `detail` (commits, files, diff, checks, runs), `freshness`, `context` |
| `branch_change` | Merge, delete, protect, unprotect, clean up, restore, fetch, or propose a conflict's resolution. A preview and its confirm token first; then `person_agreed=true` with the token |

### Check

| Tool | What it does |
| --- | --- |
| `audit` | Check the whole project (40 stages). Returns a job; a project already checked at this commit returns its overview at once. Options: `paths` (security, look, code, speed, experience; complete by default), `mode=speed`, `use_assistant` and `assistant`, `sign_in` (hand, test_user, none), `published` (a live address the person names, read only), `run_app`, `again_from=<stage>`, `fresh` |
| `wait` | Follow a job for up to `seconds` (default 50): its progress, or its result once done |
| `run_nodes` | Run the AI nodes again on the latest check: `card_triage`, `visual_reviewer`, `ideal_planner`, `pipeline_gap_planner`, `plan_orderer`, `fix_reviewer` |
| `replan_ideal` | Re-plan the ideal structure of the latest check with the person's assistant, as the Studio does |

### Read the findings

| Tool | What it does |
| --- | --- |
| `overview` | The project's health: counts, kinds of problems with plain titles, the plan's milestones, what did not complete |
| `findings` | The problems, most important first, filtered by kind, path, text, or only those EAOS can fix; paged |
| `finding` | One problem whole, by card (`TASK-…`) or claim (`CLM-…`): the evidence with the code around it, the rule it breaks, the suggested change, how it is proven gone |
| `structure` | The architecture: current and target components, forbidden and target dependencies, decisions, gaps, import cycles |
| `plan` | The plan of fixes: milestones in order and their cards; pass a milestone id for all of its cards |
| `impact` | What changing a file or symbol touches: the files that import it, the flows and entry points through it, the tests that cover it, the files that change with it |
| `ask` | Search the check's records for a question, each answer with its place; `NOT_IN_RECORDS` when none answers it |
| `report_file` | A file of the technical report (for example `START-HERE.md`, `TARGET-ARCHITECTURE.md`); with no name, the list |
| `open_report` | Open the report for people (`REPORT.html`) in the person's browser, rebuilt with the fixes so far |
| `open_studio` | Open the project's live EAOS Studio in the person's browser |

### Deep checks (optional)

| Tool | What it does |
| --- | --- |
| `logic_flaws` | Hunt logic flaws after a check (skipped steps, races, wrong checks): the assistant reads the code twice on its deep tier, then the check goes on from its claims so the cards include them. It spends: without `person_agreed` it answers with what it costs. Returns a job |
| `experience` | How the app's simulated users fared in the last experience run: each persona's goals and results, the difficulties ranked, the tickets, the replays that broke. The full story is `EXPERIENCE.md` |

### The look

| Tool | What it does |
| --- | --- |
| `design_brief` | The look at almost no tokens: the EAOS design standard, the Arabic font catalogue, the pinned design libraries, the design system UI UX Pro Max suggests for the product, and the project's look today |
| `design_choose` | Save the look the person chose as one `DESIGN.md`; the screen review then judges every page against it |

### External tools

| Tool | What it does |
| --- | --- |
| `tools_find` | GitHub candidates for a tool a stage lacks: stars, license, latest release assets |
| `tools_add` | Add a pinned tool (version, sha256 or commit, license) after the person agreed, then install it |

### Run the app

| Tool | What it does |
| --- | --- |
| `run_setup` | Run the app in an isolated copy (a temporary local database, no secrets, nothing reaches the internet). Needs the person's agreement once. Returns a job |
| `run_try` | Try the assistant's proposal to make the app run (environment, commands, a seed script that signs in); unsafe proposals are refused with the reason. Returns a job |
| `safety_net` | Record every screen of the running app, and its speed under load on the production build: what every fix is compared with. Returns a job |
| `sign_in_forget` | Forget the sign-ins to the app EAOS kept for this project. The person's decision |

### Fix a batch

| Tool | What it does |
| --- | --- |
| `context_propose`, `context_make` | The assistants' context trimmed on a branch of its own, every instruction kept, with the project's extension guide (`docs/EXTENDING.md`, drawn from its layers and how it grew) and one line in the context files pointing at it |
| `project_map` | GitNexus's map of the project for its assistant, with the person's yes: the index outside the project, its area skills where git does not take them, its MCP registered |
| `design` | What the project's screens are really made of: how many looks each part has, values per kind, near colours, formats, two libraries for one job |
| `design_propose`, `design_make` | The look's raw values named as tokens on a branch of their own, no assistant asked, kept only when proved that nothing looks different but what the person agreed to merge |
| `fix_start` | Open a batch in an isolated copy: the next cards EAOS can fix (or the ids passed), with their automatic fixes (codemods) applied and checked. Options set in the fix preview: `base`, `deliver_as`, `merge_into`, `base_commit`, `assistants` |
| `fix_read` | Read a file (or list a folder) in the batch's copy, with line numbers |
| `fix_edit` | Make one card's change, then check it at once: the problem is gone, no new broken code, no endpoint gone. A change that fails is taken back with the reason. Returns a job |
| `fix_skip` | Leave a card out, with the reason |
| `fix_finish` | Run the project's own checks and every recorded screen on all kept changes together, then hand over the branch `eaos/<branch>/wave-N`. Returns a job |
| `fix_abandon` | Close a batch that cannot be checked, handing nothing over; its cards can be picked again |
| `accept` | Merge the waiting branch, delete it, and bring the report and progress up to date in one call. Only after the person's yes (`person_agreed=true`) |
| `undo` | Throw the waiting branch away. Only after the person's yes |

### Your rules (M16)

| Tool | What it does |
| --- | --- |
| `rules` | The person's own rules (read, answered at once): op=list (each in scope, pinned, held or broken where, how often it came back; the commit hook), op=touches (what changing or unpinning one touches) |
| `rule` | Keep or change one: op=add (the person's words, for the card or batch in hand; said again, it is counted), op=guard (a pattern with its examples, a test, EAOS's detectors, or none with why; `write=true` asks your assistant once), and the person's own decisions op=pin, unpin, change, hook, approve (a test command you propose never runs before the person approves it; new words wait for a guard written for them) (`person_agreed=true` after their yes; refused inside a Studio run) |
| `check_changed` | Only what changed, now: each rule on what the change brought and the code laws over the changed files and those importing them, in seconds and without AI (`base`, or `staged` for a commit) |

### Build from a plan

| Tool | What it does |
| --- | --- |
| `blueprint_start` | Read a plan (Markdown, text, PDF, Word, HTML, or pasted text) and return it with the spec format and the technology catalogue |
| `blueprint_spec` | Check the product spec the assistant wrote: what is missing, and the questions for the person with a recommendation |
| `blueprint_design` | Draw the target from the checked spec: the technologies (each in one adapter folder), the layers and rules, and the build plan as milestones of cards |
| `build_start` | Open the next milestone in an isolated copy (the first time, after the person's agreement). Returns the cards to build |
| `build_read` | Read a file (or list a folder) in the build's copy |
| `build_edit` | Write one build card; kept only if every gate passes, otherwise taken back with the reasons. Returns a job |
| `build_skip` | Leave a build card out, with the reason |
| `build_finish` | Close the milestone through every gate and hand it over as `eaos/build-N`, stacked on the one before. Returns a job |

See [BUILD-FROM-PLAN.md](BUILD-FROM-PLAN.md).

### Extend a checked project

| Tool | What it does |
| --- | --- |
| `extend_start` | Read the plan of a feature, page or part, and return it with the project as its check read it: its parts, layers and rules, the functions to reuse, its look |
| `extend_plan` | Check the feature's spec against itself and the project, then add its cards to the plan as one milestone that `fix_start` builds through every gate of a fix |

### Follow and govern runs

| Tool | What it does |
| --- | --- |
| `runs` | The Studio's queue: `list`, `show` (stage, minutes left, cost so far, last events, its question), `estimate`, `check` (a new check in the background), `stop`, `pause`, `resume`, `retry` |
| `waiting` | What waits for the person: the runs' and the report's questions, a branch waiting for a decision, a sign-in a check waits for. `op=answer` takes `person_said`, their own reply |
| `act` | A verb (`fix`, `verify`, `explain`, `plan`) on cards or a group (`severity=high`): `op=preview` first (cards, files, batches, estimate, risk, confirm token), then `op=start` |
| `history` | The project over time: `list` every check, `compare` two, `usage` (tokens and cost per stage and per run) |
| `reorder` | Put the queued runs in a given order, as dragging the Studio's queue does |

## Governance

`runs`, `waiting`, `act`, `history` and `branch_change` give an assistant the Studio's governance without the Studio
(`eaos/interfaces/mcp_server/govern.py`). They and the terminal's commands (`eaos check`, `eaos runs`, `eaos waiting`,
...) call the same core as the Studio (`eaos/interfaces/govern.py`), so no rule is written twice and a run is the
same run in the terminal, the assistant and the Studio. When the Studio is not running, a host without HTTP
(`eaos govern`) starts on demand and leaves two minutes after the queue is empty.

What only the person decides needs their word: `accept`, `undo`, `choose_branch`, answers to questions, merging,
deleting, protecting, cleaning up or restoring branches, a fix that accepts itself (`auto_accept`), `sign_in_forget`,
and `logic_flaws` (it spends). These take `person_agreed=true` (with the preview's confirm token where there is one)
or `person_said`, given at least 30 seconds after the question was shown. They are always refused inside a run the
Studio started; there the person decides in the Studio. The assistant asks the person only these, and does the rest
on its own. Signing in to the app is the person's alone, in the Studio or with `eaos sign-in`; never the assistant's.

## Parity with the Studio

Everything the Studio does has an MCP tool, and the whole journey runs from the terminal alone. The table lives in the
code: `PARITY` in [`eaos/interfaces/mcp_server/studio_parity.py`](../eaos/interfaces/mcp_server/studio_parity.py)
covers the Studio's 62 routes: 50 with a tool, 12 without one on purpose (`NO_TOOL`).
`tests/interfaces/test_parity.py` derives the routes from the code (the read server and the action contract
[`docs/studio-actions.json`](studio-actions.json)), so a new route without a row, or a row naming a tool that does not
exist, fails the tests. It also walks the journey with the `eaos` command alone.

| Studio action | MCP tool | Command |
| --- | --- | --- |
| Sections, progress, events, report files | `overview`, `findings`, `finding`, `structure`, `plan`, `report_file`; `status`, `runs`, `wait` | `eaos problems`, `eaos status`, `eaos watch` |
| The report page, its pictures and screens | `open_report` | none |
| Projects and switching between them | `projects`, `open_studio` | `eaos projects`, `eaos studio <folder>` |
| Sign-in: its state, going on without it, forgetting it | `waiting`, `status`, `sign_in_forget` | `eaos waiting`, `eaos sign-in --signed-out`, `eaos sign-in --forget` |
| Start or preview any action | `act`, `runs` (`check`, `estimate`), `replan_ideal` | `eaos check`, `eaos fix`, `eaos verify`, `eaos explain`, `eaos plan` |
| The queue: show, stop, pause, resume, retry, reorder | `runs`, `reorder` | `eaos runs`, `eaos watch`, `eaos stop`, `eaos pause`, `eaos resume`, `eaos retry`; reorder has no command |
| Questions and the report's decisions | `waiting` | `eaos waiting`, `eaos answer` |
| Accept or undo a branch | `accept`, `undo` | `eaos accept`, `eaos undo` |
| Branches: inventory, detail, freshness, context | `branch_view`, `branches`, `status` | `eaos branches`, `eaos branch`, `eaos status`; detail has no command |
| The analysis branch; merge, delete, protect, clean up, restore | `choose_branch`; `branch_change` | `eaos branch <name>`; `eaos branches …` |
| Fetch a remote, propose a conflict's resolution | `branch_change` (`op=fetch`, `op=conflict`) | none |
| A new project's plan | `blueprint_start` | none |
| Usage, the assistants | `history` (`op=usage`), `assistant_check` | `eaos usage`, `eaos doctor` |
| **No tool on purpose:** the Studio's chat (the assistant is the chat), the person signing in to their app by hand (theirs alone), the page's own plumbing (words, session, schemas) | none | none |

The governance tools and the tools added for parity are registered only by `eaos mcp`, not among the Studio's own
direct actions, and they call the Studio's own core, never a second implementation.

## The outputs: one folder per project

Everything EAOS makes for the person is in one visible folder, `~/EAOS/<project>/`, never inside their project:

| Part | What is in it |
| --- | --- |
| `README.md` | What each part is |
| `REPORT.html` | The report for people in one page: project summary, gaps and risks, structure map, plan and progress. Rebuilt after every batch |
| `technical/` | The full technical report, for the assistant and developers (`EXPERIENCE.md` among it after an experience run) |
| `fixes/wave-N/` | Each batch: `SUMMARY.md` in plain words, its `.patch` files and `wave.json` |
| `blueprint/` | For a project built from its plan: the plan as read, the spec, the stack, the policy, the build plan, `BLUEPRINT.md` |
| `logs/` | Technical logs |
| `HANDOVER.md` | Where the work is, what the last assistant did, and how another continues it; rewritten after every call |
| `branches/<name>/` | The same parts for each further branch EAOS worked on |

What is not an output (the state, the isolated copies, the jobs) stays in the hidden `~/.eaos/`.

## The gates every change passes

A fix reaches the person only as a branch, and only through its gates:

1. **At each edit** (`fix_edit`): the card's problem is gone; no endpoint gone; no new forbidden import, import cycle,
   broken reference or broken layer boundary; nothing added against the code laws (copies, dead code, complexity,
   size, security, the repository's tidiness); the app's own quick checks still pass when its files changed
   (`eaos/analysis/repair/gates.py`); and no rule of the person's that holds for the card is broken by what the edit
   brought (`eaos/analysis/rules/held.py`). A failing edit is taken back with its reason, in the person's words for a rule.
2. **At the batch** (`fix_finish`): every kept change together through the project's own checks (tests, typecheck,
   lint), Semgrep once over the kept changes (Bandit and Gitleaks already read each edit), and the behaviour lock,
   which compares every recorded screen, its picture and its words. A batch that fails
   asks for a repair on top, or `leave_out=true` finds the changes responsible and leaves them out.
3. **At the hand-over**: a branch `eaos/<branch>/wave-N`; the person's checkout is untouched until they `accept`.

A build card passes the same gates against the blueprint ([BUILD-FROM-PLAN.md](BUILD-FROM-PLAN.md#the-gates-after-every-card)).

## Continuity: honest progress, merges that close the loop, hand-over between assistants

- **The ledger** (`eaos/core/project/ledger.py`): each card has a stable key (its kind, files and words, without
  numbers), because every check numbers its cards again. Every EAOS commit carries `EAOS-Card: <key>`, so what was
  merged is read from the person's branch itself, whoever merged it and however. A card is open, in a batch, on a
  branch waiting for a decision, done (merged), gone in a later check, or needs a decision. The report reads the
  progress from the ledger alone and never counts a waiting branch as done.
- **Merging** (`eaos/journeys/guided/batches.py`, `merge` and `reconcile`): `accept` merges (fast-forward, else a clean
  merge; a conflict is aborted, so nothing changes), deletes the branch and rebuilds the report. `status` reconciles
  with git on every call: a branch merged by hand is recorded and deleted, a branch deleted unmerged counts as undone.
  After merging EAOS's own fixes, no new check or run is needed.
- **Hand-over** (`eaos/journeys/handover.py`): the MCP server writes every call to `journal.jsonl` (when, which
  assistant, which tool, which card, the result), `note` adds the reason, and `HANDOVER.md` is rewritten after every
  step. The next assistant calls `status` and finds `handover`: the open work and what is left of it, what the person
  answered, the last steps and notes, and how to continue.
- **Session start** (`eaos handover --hook`): the hook `eaos assistant install` adds means that when EAOS has work
  open in the folder (or the repository it is in), a new session starts already knowing the last step and who did
  it, the batch and what is kept and left, and the card in progress. "Continue" alone is enough. The person sees the
  same with `eaos handover` and in the report's work log.
- **Branches** (`eaos/core/project/branches.py`): when the project has several of the person's branches with
  different code, `status` asks which one first (recommending the one furthest ahead of the main branch) and no check
  starts before the answer. The check, the run and the isolated copies read EAOS's own copy of that branch when it is
  not the one checked out, so the person's checkout never switches. Each branch keeps its own check, ledger, batches
  and report.
- **A report that never hides a failure** (`eaos/journeys/guided/project.py`, `publish`): a part that could not be
  built is named with its reason at the top of the page, in `.report.json` and in `logs/`; every page is stamped with
  the EAOS version, commit and build time (`eaos/core/system/version_info.py`), and `status` rebuilds at once a page an
  older EAOS made.
