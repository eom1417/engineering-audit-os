# EAOS reference

**English** · [Guide](GUIDE.md) · [Back to the README](../README.md)

Every command and option, the check paths and stages, the environment variables, and where EAOS keeps things. For a
walk-through from nothing to the first fix, read the [Guide](GUIDE.md). For the tools EAOS gives your AI assistant,
read [MCP.md](MCP.md).

- [Conventions](#conventions)
- [Commands at a glance](#commands-at-a-glance)
- [Getting started](#getting-started) · [Checking](#checking) · [Following a run](#following-a-run) ·
  [Reading the results](#reading-the-results) · [Fixing and branches](#fixing-and-branches) ·
  [The assistant](#the-assistant) · [Maintenance](#maintenance) · [Advanced: card acceptance](#advanced-card-acceptance)
- [Check paths](#check-paths) · [The stages of a check](#the-stages-of-a-check) · [Model tiers](#model-tiers)
- [Environment variables](#environment-variables) · [Where EAOS keeps things](#where-eaos-keeps-things)

## Conventions

| Option | Meaning, wherever it appears |
|---|---|
| `[project]` | The project folder. Defaults to the current folder (`.`). |
| `--project PROJECT` | The same, as an option. Defaults to `.`. |
| `--lang {ar,en}` | The language of the answer. Defaults to the language kept for the project. |
| `--yes` | Answer yes to the question the step asks (a preview, a merge, a cost). Without it, EAOS asks. |
| `run` | A run's id (see `eaos runs`). Defaults to the newest run the command applies to. |
| `--assistant claude\|codex\|handoff` | On `fix`, `verify`, `explain`, `plan` and `answer`: who does the work. `handoff` leaves it to the assistant you are talking to. |
| `--group by=value` | On `fix`, `verify`, `explain`, `plan`: pick cards by `area=`, `severity=`, `component=`, `gap=` or `operation=` instead of listing ids. |

`eaos --version` prints the version. `eaos <command> --help` prints the options below.

## Commands at a glance

| Group | Commands |
|---|---|
| Getting started | `start` `next` `status` `show` `do` `studio` |
| Checking | `check` `audit` `logic-flaws` `experience` |
| Following a run | `watch` `runs` `stop` `pause` `resume` `retry` `waiting` `answer` `sign-in` |
| Reading the results | `problems` `problem` `history` `compare` `usage` `projects` |
| Fixing and branches | `fix` `verify` `explain` `plan` `accept` `undo` `branch` `branches` |
| Your rules | `rules` `check --changed` |
| The assistant | `assistant` `mcp` `handover` |
| Maintenance | `doctor` `tools` `clean` `govern` |
| Advanced: card acceptance | `facts` `policy` `recheck` `decided` |

43 commands in all. Everything the Studio does can also be done from these commands and from the MCP tools.

## Getting started

| Command | Options | What it does |
|---|---|---|
| `eaos start [project]` | `--path PATH…` `--assistant {claude,codex,none}` `--mode {normal,speed}` `--no-watch` `--lang` `--yes` | Start here: check the project and get a plain report (nothing in it changes). Asks once whether to use your assistant and whether to run your app. `--assistant` and `--mode` are kept for the project. `--no-watch`: do not open the live map in a running Studio. |
| `eaos next [project]` | `--lang` `--yes` | Do the next step for the project in this folder. |
| `eaos status [project]` | `--lang` `--yes` | Where the project stands, whether the check is still current, and what comes next. |
| `eaos show [project]` | `--lang` `--yes` | Print what the check found, in plain words. |
| `eaos do "<request>"` | `--project` `--lang` `--yes` | Ask in your own words, for example `eaos do "check my project"`. |
| `eaos studio [project]` | `--port PORT` `--no-open` `--background` `--remote-origin URL` | Open the project's Studio in your browser. It listens on 127.0.0.1 only, on a free port unless `--port` is given. `--no-open`: print the address only. `--background`: start it, print the address and return. `--remote-origin`: on a remote server, the one exact `https://<project>--<port>.<domain>` address it is reached at (token and CSRF checks stay on). |

## Checking

| Command | Options | What it does |
|---|---|---|
| `eaos check` | `--path PATH…` `--assistant {claude,codex,none}` `--mode {normal,speed}` `--run-app` `--sign-in {hand,test_user,none}` `--published URL` `--again-from STAGE` `--watch` `--project` `--lang` | Says how long the check will take, then checks in the background. Nothing in the project changes. |
| `eaos audit <target> --out OUT` | `--engines [ENGINE…]` `--run-app FOLDER` `--intake FILE` `--only STAGE` `--skip STAGE` `--resume` `--exclude GLOB` `--goal {onboarding,debugging,evolution,architecture}` `--lang` (default `ar`) | The whole pipeline in the foreground, writing the report to `OUT` and saying what each stage did. For scripts and development. |
| `eaos logic-flaws <target> --out OUT` | `--assistant {claude,codex}` `--minutes N` (default 40) `--max-calls N` (default 4) `--yes` | An optional deep check after a check: your assistant hunts logic flaws (skipped steps, races, wrong checks). Each candidate is read twice and grounded on a real line of code. Says its time and cost and asks first. The check then goes on from its claims, so the flaws become cards. |
| `eaos experience <step> <target> --out OUT` | `--base URL` `--sessions DIR` `--runtime DIR` `--apart SUFFIX` `--database FILE` `--assistant {claude,codex}` `--max-calls N` (default 400) `--lang` (default `ar`) `--yes` | The simulated users, one step at a time, after a check. Steps: `plan` (personas and their data), `run` (drive the app), `judge` (a fresh persona meets each difficulty again, then one strict ruling; confirmed ones become cards), `replay` (saved journeys, no AI), `report` (writes `EXPERIENCE.md`). `run`, `judge` and `replay` need `--base`, the address of the app's isolated copy already running on this computer. Most people use `eaos check --path experience` instead. |

**`eaos check` options**

| Option | Meaning |
|---|---|
| `--path PATH…` | Check only these [paths](#check-paths). Default: `complete`. Add `layers` or `experience` beside `complete` to switch on those optional parts of the full check. |
| `--assistant {claude,codex,none}` | The AI the check uses. `none`: the rules decide alone. |
| `--mode {normal,speed}` | `speed`: several assistant calls at once and lighter models for the standard tier; faster, more tokens. Kept for the project. |
| `--run-app` | Run your app in an isolated copy (its pages, sign-in and speed). Your consent, kept for the project. |
| `--sign-in {hand,test_user,none}` | For an app behind a sign-in: you sign in when the check asks, a test user signs in, or no sign-in. Kept. |
| `--published URL` | The published address, read signed in and read only, for this check. |
| `--again-from STAGE` | Go on from this [stage](#the-stages-of-a-check) of the last check: it and the stages that read it run again on the same code; the rest is kept. |
| `--watch` | Follow the run in the terminal until it ends. |
| `--changed` | Check only what changed, now, instead: your rules and the code laws on the changed files and the files that import them, in seconds and without AI. With `--base REF` (what the change is measured from, default `HEAD`), `--staged` (what is staged for a commit), `--hook` (as the commit hook runs it: only your pinned rules refuse). Exit 1 when a rule is broken. |

**`eaos audit` options**

| Option | Meaning |
|---|---|
| `--out OUT` | The report folder (required). |
| `--engines [ENGINE…]` | Run the pinned external tools: name a subset, or pass the flag alone for all. Without it, the `engines` stage is skipped. |
| `--run-app FOLDER` | Run the app in an isolated copy under `FOLDER` (your consent): setup, lock, screens, speed. |
| `--intake FILE` | The owner's answers to the intake questions, as JSON `{question id: answer}`. |
| `--only STAGE` · `--skip STAGE` | Run only, or leave out, a stage. Repeatable. |
| `--resume` | Go on with the last run in `OUT`. Refused when the code changed since. |
| `--exclude GLOB` | Leave paths out. Repeatable. |
| `--goal` | The questions the reading of the project's meaning starts from. Default `evolution`. |

## Following a run

| Command | Options | What it does |
|---|---|---|
| `eaos watch [run]` | `--project` `--lang` | Follow a run live: the time since it began, the stage, the time left, the cost so far, and its questions. |
| `eaos runs` | `--all` `--project` `--lang` | The runs: running, queued and ended. `--all`: also those already read. |
| `eaos stop [run]` | `--project` `--lang` | Stop a run. |
| `eaos pause [run]` | `--project` `--lang` | Pause a run. |
| `eaos resume [run]` | `--project` `--lang` | Resume a paused run. |
| `eaos retry [run]` | `--project` `--lang` | Run a failed, stopped or unchanged run again. |
| `eaos waiting` | `--project` `--lang` | What waits for you: the questions of the runs and of the report, a branch to accept or undo, a sign-in. |
| `eaos answer <id> [option]` | `--text TEXT` `--assistant ASSISTANT` `--project` `--lang` | Answer what waits for you. `--text`: your own answer instead of an option. `--assistant`: for a report question, who reviews your answer (`claude`, `codex` or `handoff`). |
| `eaos sign-in` | `--signed-out` `--forget` `--project` `--lang` | Sign in to your app while a check asks for it: a browser window, or on a server with no screen a page of its own. `--signed-out`: go on without signing in. `--forget`: forget your saved sign-ins. |

## Reading the results

| Command | Options | What it does |
|---|---|---|
| `eaos problems` | `--area {security,structure,quality,performance,ux,maintainability}` `--severity {critical,high,medium,low}` `--kind KIND` `--where TEXT` `--text TEXT` `--fixable` `--limit N` (default 30) `--offset N` `--project` `--lang` | What the check found, most important first, filtered as in the Studio. `--kind`: a card pattern such as `dead_code` or `security_weakness`. `--where`: only paths containing this text. `--fixable`: only what EAOS can fix. |
| `eaos problem <id>` | `--project` `--lang` | One problem whole: what, why, the evidence with its code, and the change. |
| `eaos history` | `--project` `--lang` | Every check on record: the score, the open problems, closed of total. |
| `eaos compare <first> <second>` | `--project` `--lang` | Two checks of the history side by side. |
| `eaos usage` | `--project` `--lang` | What the assistant used: tokens and cost, per stage and per run. |
| `eaos projects` | `--project` `--lang` | Every project EAOS knows on this computer. |

## Fixing and branches

| Command | Options | What it does |
|---|---|---|
| `eaos fix [ids…]` | `--group by=value` `--assistant` `--auto-accept` `--yes` `--project` `--lang` | Fix these cards. A preview first (cards, files, time, risk), then the run in an isolated copy. What passes every gate is handed over as a branch. `--auto-accept`: merge it by itself when its checks pass. |
| `eaos verify [ids…]` | `--group` `--assistant` `--yes` `--project` `--lang` | Your assistant reads the code each card points at and records whether the problem is still there, already gone, or a false alarm. Changes nothing. A preview first. |
| `eaos explain [ids…]` | `--group` `--assistant` `--yes` `--project` `--lang` | Your assistant explains each card in plain words: what is wrong, why it matters, what fixing it would change. Changes nothing. A preview first. |
| `eaos plan [ids…]` | `--group` `--assistant` `--yes` `--project` `--lang` | Your assistant proposes an order of batches, what waits for what, and each batch's risk. Changes nothing. A preview first. |
| `eaos accept [project]` | `--lang` `--yes` | Take the latest batch of fixes into your branch (merge its branch). Says what will happen and asks first. |
| `eaos undo [project]` | `--lang` `--yes` | Throw the latest batch of fixes away (delete its branch). Asks first. |
| `eaos branch [name]` | `--yes` `--project` `--lang` | The branch EAOS checks and fixes: the list, or move to one. Each branch has its own report and progress. |
| `eaos branches [op] [name]` | `--into BRANCH` `--yes` `--project` `--lang` | Every branch, and one change to it, a preview then your yes. `op`: `list` (default), `merge` (`--into`: the branch to merge into), `delete`, `protect` (nothing from EAOS is merged into it), `unprotect`, `cleanup` (remove merged branches and old worktrees; each branch stays recoverable), `restore` (bring a deleted branch back). |

## Your rules

| Command | Options | What it does |
|---|---|---|
| `eaos rules` | `--project` `--lang` | Every rule you stated: for which work (a card, the batch now, or pinned), held or broken where, how often it came back, its guard, its last changes. |
| `eaos rules add "<your words>"` | `--card ID` `--pin` | Keep a rule in your words: for that card, or for the batch of fixes now, or pinned for every change. The same rule said again is counted, and pinning is offered. |
| `eaos rules pin ID` · `unpin ID` | | Pin a rule for every change (written for your assistant between EAOS's lines in `CLAUDE.md` / `AGENTS.md`), or end it (its lines, and with the last pinned rule the hook's, go; your project's own tests stay). What it touches is shown first. |
| `eaos rules change ID "<words>"` | `--yes` | New words for a rule, what it touches shown first; its history keeps the old ones. |
| `eaos rules guard ID` | `--write` · `--pattern JSON --language L --broken CODE --kept CODE [--message] [--files GLOB…]` · `--test "CMD"` · `--detectors NAME…` · `--none WHY` | The rule's machine guard, proved on its examples before it is kept: an ast-grep pattern, a test of your project's, EAOS's detectors, or none with why. `--write`: your assistant writes it, once. |
| `eaos rules hook on` · `off` | `--yes` | Your pinned rules on every commit (git's pre-commit hook, a few lines between EAOS's markers). A commit that breaks one is refused with the place; EAOS failing to run never stops a commit. |

## The assistant

| Command | Options | What it does |
|---|---|---|
| `eaos assistant [install]` | `--project` `--lang` `--yes` | Teach Claude Code and Codex to use EAOS: the MCP server, the `/eaos` skill (`$eaos` in Codex), and a session-start hook that tells a new session where EAOS work stopped. Running it again replaces only EAOS's own part. The install line runs it for you. |
| `eaos mcp` | | The MCP server on stdio (what `assistant install` registers). See [MCP.md](MCP.md). |
| `eaos handover [project]` | `--hook` `--lang` | Where the work stopped (branch, batch, what was kept and what is left, the last assistant and when) and the line to write to another assistant. `--hook`: the form the session-start hook uses (JSON on stdin). |

## Maintenance

| Command | Options | What it does |
|---|---|---|
| `eaos doctor [project]` | `--fix` `--lang` `--yes` | Is this computer ready? Python 3.10+, git, Node.js 22+ (for JavaScript projects and some tools), the project saved in git, the checking tools, the tools that run and fix your app, a temporary PostgreSQL, an AI assistant, and 5 GB free. Every missing piece with its fix. `--fix`: install what is missing. |
| `eaos tools {install,doctor}` | `--stage {assessment,execution}` `--project PROJECT` `--only NAMES` `--skip NAMES` `--json` | Install the external tools at their pinned versions (each download checked against its pinned checksum, no administrator rights), or report what is installed. `--project`: first what this project's check needs. `--only` and `--skip` take comma-separated names. |
| `eaos clean [project]` | `--pictures` `--lang` `--yes` | Remove the temporary copies, caches and saved app sign-ins EAOS made; reports and state stay. `--pictures`: also the reports' screen pictures and the assistant's raw runs (a new check takes them again). |
| `eaos govern <project>` | `--answer ID` `--option OPTION` `--text TEXT` | The headless host that starts a project's runs while no Studio runs. The other commands start it themselves; you do not need to run it. |

## Advanced: card acceptance

A card's acceptance check runs one of these on a changed copy of the project. You rarely run them by hand.

| Command | Options | What it does |
|---|---|---|
| `eaos facts <target> --out OUT` | `--history` `--max-commits N` (default 2000) `--exclude GLOB` `--engines [ENGINE…]` | Deterministic facts only; no model is used. `--history`: read the git history too. `--engines`: also run the pinned external tools (a subset, or all when the flag is alone). |
| `eaos policy {check,init} <target> --out OUT` | `--policy FILE` | Check the declared architecture policy (`eaos.policy.json`), or scaffold one. |
| `eaos recheck [root] --spec JSON` | | Collect facts on a changed copy and let one claim's probe decide: `{"probe_type": …, "specification": {…}}`. Exit 0 when the problem is gone. |
| `eaos decided <report> <uid>` | | Exit 0 once an observation carries a recorded decision (the acceptance of an investigation card). |

## Check paths

`eaos check --path`, `eaos start --path`, the Studio and the MCP `audit` tool all take these. Every path also runs the
required stages and the assistant's review of its cards.

| Path | What it looks at |
|---|---|
| `complete` (default) | Every path below except the two optional ones, together: the whole check. |
| `code` | Structure and layers, cycles and coupling, complexity, duplication, dead code, the tests, how easily it grows. |
| `security` | Exposed secrets, vulnerabilities, dependencies and their licences, dangerous settings, access gaps. |
| `look` | The app's screens, their accessibility and speed, the design review, users' journeys. Needs the app running. |
| `speed` | The app under load, the cost of each entry at 1000 times the use, the hot paths, production readiness. |
| `layers` | Optional. On an isolated copy: the production build (secrets in what ships), the data rules tried as different users (pgTAP), the endpoints with two test accounts (Schemathesis). Adds up to 15 minutes. |
| `experience` | Optional. Simulated users try the running app. Alone: several personas with their data, hand-offs and a support desk, up to an hour. Beside `complete`: one persona doing the main task, up to 5 minutes, 12 light assistant calls and one ruling. |

`layers` and `experience` run only when chosen: alone, or beside `complete` (`--path complete layers experience`).
The paths that look at the running app need your consent to run it (`--run-app`, asked once and kept).

## The stages of a check

A check is 41 declared stages (`eaos/pipeline/stages.py`), grouped in loops. A stage runs as soon as what it reads is
ready; a stage that did not run says why, and a tool that failed is named. Any of them can be given to
`--again-from`, `--only` and `--skip`.

| Loop | Stages |
|---|---|
| Understand | `facts` `features` `roles` `intake` `engines` `policy` `rules` |
| Run and see the app | `setup` `verify` `session` `crawl` `lock` `record` `journeys` `screens` `baseline` `layers` |
| Try the layers (optional) | `layers_trial` |
| Try the experience (optional) | `experience` |
| Judge | `measure` `architecture` `load` `readiness` `claims` `probe` `sustainability` `transform` `semantic` `plan` `target` `proposals` `triage` `visual` `cards` |
| Envision the target | `ideal` `pipeline_gaps` `reconcile` |
| Plan | `order` `steps` |
| Hand over | `reports` `translate` |

The stages that ask your assistant, and the guards on what it says: [AI-IN-THE-PIPELINE.md](AI-IN-THE-PIPELINE.md).

## Model tiers

Each assistant step asks on a tier, so a cheaper model does the routine work. A tier that fails is asked again one tier
up, and a cheaper model never closes anything alone: setting a card aside, calling a gap no gap or a screen clean is
asked again on the deep tier.

| Tier | Claude Code | Codex | Used for |
|---|---|---|---|
| light | haiku | low effort | a card's first triage, translation, a simulated user's steps |
| standard | sonnet | medium effort | the screen review, the gap planner, the plan's order, the support desk |
| deep | your own model | high effort | the ideal target, the fix review, the simulated users' scenario, data and ruling |

The check's `speed` mode lowers standard to light. The variables below change a tier or a model.

## Environment variables

None is needed. Set them only to change where EAOS keeps things or how it calls your assistant.

| Variable | Default | What it does |
|---|---|---|
| `EAOS_HOME` | `~/.eaos` | EAOS's own state: each project's workspace (`projects/`), the Studio's keys, the remote address. When set and `EAOS_OUTPUT` is not, the outputs go to `EAOS/` beside it. |
| `EAOS_OUTPUT` | `~/EAOS` | Where the reports and fixes for you are written, one folder per project. |
| `EAOS_ENGINE_TOOLS` | `~/.eaos/tools` | Where the external tools are installed (one copy for every project). |
| `EAOS_ASSISTANT` | the first installed: Claude Code, then Codex | The assistant EAOS uses: `claude`, `codex`, or `none` to turn every assistant off. A project's own choice (`--assistant`) is kept separately. |
| `EAOS_CLAUDE_MODEL` | your own model | The Claude model of the deep tier. |
| `EAOS_CLAUDE_MODEL_<TIER>` | `haiku`, `sonnet` | The Claude model of one tier, for example `EAOS_CLAUDE_MODEL_STANDARD=opus`. |
| `EAOS_CODEX_MODEL` | Codex's own | The Codex model. |
| `EAOS_TIER_<STEP>` | per step | The tier (`light`, `standard`, `deep`) of one assistant step, for example `EAOS_TIER_CARD_TRIAGE=deep`. Steps: `CARD_TRIAGE`, `TRANSLATION`, `VISUAL_REVIEWER`, `PIPELINE_GAP_PLANNER`, `PLAN_ORDERER`, `IDEAL_PLANNER`, `FIX_REVIEWER`, and the `EXPERIENCE_*` steps. |
| `EAOS_SIGN_IN_WAIT` | `900` | Seconds a check waits for you to sign in to your app before it goes on signed out. |
| `EAOS_REMOTE_ORIGIN` | none | On a remote server: the Studio's address pattern with `{port}`, for example `https://<project>--{port}.dev.example.com`. Overrides the file `~/.eaos/remote-origin`. |
| `EAOS_STUDIO_TRUST_REMOTE_LOGIN` | off | `1`: a Studio started with `--remote-origin` trusts the sign-in in front of the server instead of its own token. |

The install line also reads these:

| Variable | Default | What it does |
|---|---|---|
| `EAOS_SOURCE` | the `main` branch on GitHub | Install from another git URL or a local folder, for example `git+https://github.com/eom1417/engineering-audit-os@develop`. |
| `EAOS_APP` | `~/.eaos/app` | Where EAOS itself is installed (its own Python environment). |
| `EAOS_SKIP_TOOLS` | off | `1`: do not install the checking tools now (`eaos tools install` later). |
| `EAOS_NO_STUDIO` | off | `1`: do not open the Studio at the end. |
| `EAOS_LANG` | from `LANG` | `ar` or `en`: the installer's language. |

## Where EAOS keeps things

**What you read**, one folder per project: `~/EAOS/<project>/` (`EAOS_OUTPUT`). A branch other than the first one
checked has its own part in `branches/<name>/`.

| In it | What it is |
|---|---|
| `REPORT.html` | The report for people: summary, gaps and risks, the system in layers, the structure and system maps, the target, the plan and progress with the work log |
| `HANDOVER.md` | Where the work stopped and what is left, for any assistant |
| `technical/` | The full technical report; the folder `--out` names for `logic-flaws` and `experience` |
| `fixes/` | Every batch of fixes: what changed, what did not pass and why |
| `blueprint/` | A project built from its plan: `BLUEPRINT.md` and the chosen look, `DESIGN.md` |
| `extend/` | A feature added to a checked project: its source plan, spec and cards |
| `logs/` | Technical logs, for whoever helps you if something goes wrong |

In `technical/`:

| In it | What it is |
|---|---|
| `START-HERE.md` | Where to begin: the broken critical boundaries first, then the rest |
| `CURRENT-STATE.md` · `TARGET-STATE.md` · `GAP-AND-STRATEGY.md` · `EXECUTION-PLAN.md` | The four reports |
| `TARGET-ARCHITECTURE.md` | The final target structure |
| `EXPERIENCE.md` | The simulated users' story, when they ran |
| `PLAN/` | `STEPS.md` and one file per task card |
| `i18n/en/` · `i18n/ar/` | Every document, whole, in English and in Arabic |
| `run-manifest.json` | Every stage's status, time and reason |
| `cards.json`, `plan.json`, `facts/`, `live/`, … | The records the Studio, the MCP tools and the fixes read |

**EAOS's own state**: `~/.eaos/` (`EAOS_HOME`): `app/` (EAOS itself), `tools/` (the external tools), `projects/<name>-<id>/`
(each project's workspace: state, runs, isolated copies, your rules in `rules.json`; never inside your project), `remote-origin` (the Studio's
address on a remote server). `eaos clean` removes the temporary copies there.

## The code

How EAOS itself is laid out, its layers and where a new file goes: [ARCHITECTURE.md](ARCHITECTURE.md). The laws every
change follows: [STANDARDS.md](STANDARDS.md).
