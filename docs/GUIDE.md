# From nothing to your first fix

**English** · [العربية](GUIDE.ar.md) · [Reference](REFERENCE.md) · [Back to the README](../README.md)

A guide for people who built their app with an AI assistant (Claude Code or Codex) and do not know the details of
programming. You paste one line once, then talk to your assistant in your own words, and it does the rest. Every
command and option is in the [Reference](REFERENCE.md).

**The first fix**

1. [Install EAOS](#1-install-eaos-once)
2. [Open your assistant in your project folder](#2-open-your-assistant-in-your-project-folder)
3. [Ask for a check](#3-ask-for-a-check)
4. [Follow it in the Studio](#4-follow-it-in-the-studio)
5. [Read the report](#5-read-the-report)
6. [Take the fixes in, then the next batch](#6-take-the-fixes-in-then-the-next-batch)

**More journeys:** [build from a plan](#build-a-new-project-from-its-plan) ·
[add a feature](#add-a-feature-to-your-project) · [simulated users](#try-the-experience-with-simulated-users) ·
[the layers](#the-system-in-layers) · [logic flaws](#hunt-logic-flaws) · [signing in to your app](#signing-in-to-your-app)

**When you need it:** [usage limits and handing over](#usage-limits-and-handing-over) ·
[from the terminal](#from-the-terminal) · [requests that help](#requests-that-help-at-any-time) ·
[troubleshooting](#troubleshooting) · [what EAOS never does](#what-eaos-never-does)

---

## 1. Install EAOS (once)

Open the Terminal **in your project folder**, paste this line, and press Enter:

```bash
curl -fsSL https://raw.githubusercontent.com/eom1417/engineering-audit-os/main/install.sh | bash
```

- **You should see:** three steps (EAOS's own environment, EAOS, the checking tools), then "✅ What happened: EAOS is
  installed" and "EAOS is now inside your AI assistant: Claude Code" (or Codex). Then **the Studio** opens in your
  browser on "Preparing the tools" (see [step 4](#4-follow-it-in-the-studio)).
- **It needs:** git, and Claude Code or Codex installed and signed in. EAOS brings its own Python; it needs no
  administrator rights. If something is missing, the line says what and where to get it.
- **It installs:** EAOS in `~/.eaos/app`, the `eaos` command in `~/.local/bin`, about forty open-source tools at
  pinned versions in `~/.eaos/tools`, and EAOS inside your assistant (its tools, the `/eaos` skill, and a session hook).
- **To update:** run the same line again.
- **The newest version:** the line installs from the `main` branch. To try what is coming before it reaches `main`:
  `curl -fsSL https://raw.githubusercontent.com/eom1417/engineering-audit-os/develop/install.sh | EAOS_SOURCE=git+https://github.com/eom1417/engineering-audit-os@develop bash`

If it says "Open a new terminal window first", do so before typing `eaos`.

## 2. Open your assistant in your project folder

- **Claude Code:** open the Terminal in your project folder and type `claude` (or open the folder in the Claude app).
- **Codex:** open the folder in Codex.

If your assistant was open before the install, close it and open it again so it sees EAOS.

> **How do I open the Terminal in my project folder?** Type `cd` and a space, drag the project folder from Finder into
> the Terminal window, and press Enter.

**The first time you open Codex after installing**, it shows "New hook – review required": approve it once (Trust).
It is what tells Codex where EAOS work stopped. Claude Code does not ask.

## 3. Ask for a check

**Not sure where to start?** Type `/eaos` alone and press Enter (in Codex: `$eaos`). A menu shows what EAOS can do for
your project now, the fitting step first and marked "recommended": check the project, continue where we stopped,
review the ready fixes, fix the next batch, where are we, open the report, done and coming next, ask about your
project, build a project from a plan, tools and engines. In Claude Code you move with the arrows and pick with Enter;
in Codex you reply with the option's number. "More options…" shows the rest.

Or write to your assistant:

> **Check my project with EAOS and fix its problems**

What happens next:

| Step | What happens |
| --- | --- |
| Two questions | "May I use your assistant to judge the findings?" and "May I run your app in a separate copy, with a temporary database and none of your secrets?" Answer: **yes**. Both answers are kept for this project. |
| Evidence | The tools read the whole code. With your consent EAOS runs your app in the separate copy, records the user journeys, pictures every screen light and dark at phone and desktop width, and measures its speed. |
| Judgement | The tools propose the problems, the cards and the target structure; your assistant judges each proposal on its evidence: accepts, changes or rejects it. It also looks at the screen pictures and notes what a person would notice. |
| Explanation | It explains the main problems in plain words. |
| Fix | It writes the fixes in an isolated copy, in batches of up to ten cards. EAOS checks each one: the problem is gone, the tests still pass, every screen looks and reads the same, no new weakness or duplication came in. What fails is left out, with its reason. |
| Hand-over | What passed becomes a new branch in your project (for example `eaos/<your branch>/wave-1`), and it tells you what changed. |

A check is 40 stages, from reading the code to writing the reports. How long it takes depends on your project's size;
before it starts, EAOS says how long it expects. If you say "no" to either question, the check goes on without it, and
the report says plainly what was not done and why.

**When your project has more than one branch** (say `main` in production and a development branch ahead of it), EAOS
first asks **which branch should I check and fix?**, listing when each last changed, how far each is ahead of the main
branch, and which it recommends and why. Choose, or say "the one you recommend". From then on everything follows that
branch: the check, the fixes, the merges, the progress and the report (whose top names the branch). The branch you
have open is not switched: EAOS works on a copy of it. Each branch has its own report and progress; to move, say "work
on the main branch".

**Checking only part of it.** A check can follow one path or several: `code`, `security`, `look` (the screens),
`speed`, or `complete` (the default). Say "check only the security", or choose the paths in the Studio. Two more paths
are off unless you choose them: `layers` and `experience` (below).

## 4. Follow it in the Studio

The Studio is a page in your browser that shows everything about your project, updated as it happens. It is shipped
inside EAOS, needs no internet, and works in English and Arabic, light and dark, on a computer and a phone.

| Place | What it shows |
| --- | --- |
| **Status** | Where your project stands: its health out of 100, whether the check still matches the code, your journey, and the step that fits now. "Everything EAOS can do…" lists every action, the recommended ones first. |
| **Waiting for you** | The questions only you answer, the decisions where the rules and your assistant disagree (both views shown, for you to settle), a branch to take in or not, a sign-in to your app. |
| **Problems** | Every card with its evidence down to the line, filtered and grouped as you like. Pick some and press Fix, Verify, Explain or Plan: a free preview first (the files, the time, the risk), then the run. Its **Plan** view shows the fix plan (or, for a project built from its plan, the build plan): the steps, what waits for what, and the progress. |
| **Activity** | The live map: the stages of the journey as they run (check and fix, build from a plan, or extend the project), what each does, how long it took, what it produced, and why it was skipped if it was. Before the first check it shows "Preparing the tools": the check starts by itself once your project's tools are ready. |
| **Report** | The report itself, the pictures of your app's screens, the report's files, and the simulated users' experience when it ran. |

The project's name at the top opens **Project and settings**: the branches, the language and theme, the tools, the
assistants, and how your app runs.

- **Go on from any stage:** in Activity, open a stage and press **"Redo from here…"**: that stage and the stages that
  read it run again on the very code that was checked; every other stage is kept. If a tool failed in it, **"Run its
  failed tools again…"** runs only those tools. Never a whole new check for one stage.
- **Search or ask:** press Ctrl K anywhere to find a place, a problem or an action, or to ask your assistant a question
  in your own words; what it would do comes back as a card you confirm.
- **Both languages:** the Studio and every document of the report, switched with one button.

**How to open it:** it opens by itself after the install. To open it any time, say "open the Studio" to your
assistant, or type `eaos studio` in the Terminal inside your project folder.

| Where you work | The address |
| --- | --- |
| On your own computer | `http://127.0.0.1:<number>/#token=…`. The address carries its key and stays the same after a restart, so bookmark it. No other program on the computer can ask the Studio for it. |
| On a remote server | The server's own address, with no token, guarded by the sign-in in front of the server. Write its pattern once in the file `~/.eaos/remote-origin` (for example `https://<project>--{port}.dev.example.com`). |

## 5. Read the report

Say to your assistant: **"Open the report"**. It opens one page in your browser:

1. **Project summary:** its health out of 100, how much of the gap is closed, and the main problems.
2. **Gaps and risks:** where you are, where you should be, and how serious each gap is, in words.
3. **The system in layers:** the broken critical boundaries first, in red, then each boundary with its state.
4. **Structure map:** your project's parts and how they depend on each other (thicker is stronger, red is tangled in
   a loop). Pick a part to see its files, a file to see its functions and who calls them.
5. **System map:** the regions, the components and the links between them.
6. **Target:** the structure your project should reach, where each part of today goes, and how much of each gap is closed.
7. **Plan and progress:** the work log (where the work stopped), what is done, the decisions that need you, and every
   task card, folded: open one to see its state and details.

The report updates itself after every merge, and counts only what is in your branch. Every decision in it says **who
made it**: the tools and your assistant agreed, your assistant changed it with evidence, the rules alone, or a
disagreement where the rules' view was kept.

Everything EAOS makes is in one folder: **`~/EAOS/<your project name>/`**

| In it | What it is |
| --- | --- |
| `REPORT.html` | The report for you: double-click to open, or send it to anyone |
| `HANDOVER.md` | Where the work stopped and what is left, to carry on with any assistant |
| `technical/` | The full technical report, for your assistant and developers (start with `START-HERE.md`) |
| `fixes/` | Every batch of fixes: what changed, what did not pass and why |
| `logs/` | Technical logs, for whoever helps you if something goes wrong |

## 6. Take the fixes in, then the next batch

At the end of a batch your assistant asks: **take the fixes in, or throw them away?** Your current branch and files do
not change until you agree.

- Say **"merge it"**: the assistant merges the fixes into your branch, deletes the branch of fixes, and brings the
  report and the progress up to date in the same step, then tells you how much of the total is closed.
- Say **"undo the fixes"**: the branch of fixes is deleted, and your project is as it was.

Then say **"continue fixing"**. Each batch is a new branch, and you decide every time. A new batch does not start while
the last one's branch waits for you, and no new check is needed after EAOS's fixes are merged.

**The progress is true:** a card counts as done only once it is in your branch. One still on a branch waiting for you
shows as "waiting for your decision". Every card keeps its key when the project is checked again, so what is done
stays done.

---

## Build a new project from its plan

Have an idea and a written plan, but nothing built yet? Make an empty folder for the project, open your assistant in
it, and write:

> I have my project's plan in this file: `/path/to/plan.pdf`. Build it with EAOS, with the best structure

Any format works: Markdown, Word, PDF, HTML, text, pictures of the screens, or the plan pasted into the message. In the
Studio, choose "Build from a plan" among the actions.

| Step | What happens |
| --- | --- |
| Understand | Your assistant reads the plan and looks at every picture, orders it into parts, data and features, and notes what apps of this kind need. |
| A few questions | Only choices, each with its recommendation ("any preference for the database?"). If you have none, say "take your recommendations". |
| The blueprint | The parts, the technologies (why each, and how to change it later), the look (one theme, its colours, fonts and screens) and the order of the build, in `~/EAOS/<project>/blueprint/BLUEPRINT.md`; the look in `DESIGN.md`. |
| One question | "May I build your project in a separate copy and hand it to you milestone by milestone?" Answer: **yes**. |
| The build | Card by card. EAOS refuses any card with copied code, dead code, tangled files, mixed layers, a security weakness or a missing test. |
| The look | After each milestone with screens, EAOS pictures them and your assistant compares them with `DESIGN.md`; what departs is fixed first in the next milestone. |
| Hand-over | Each milestone is a branch (`eaos/build-1`, `eaos/build-2`, …). You decide: take it in or throw it away. A milestone refused three times in a row is handed over with what stays unproven, said plainly. |
| Acceptance | A whole check of the built project; from then on it is checked and fixed like any project. |

Changing a technology later (Supabase to PostgreSQL, say) is easy, because each lives in one folder: tell your
assistant "change the database to …". More in [BUILD-FROM-PLAN.md](BUILD-FROM-PLAN.md).

## Add a feature to your project

A new page, a feature or a whole part, in a project EAOS has checked. Write to your assistant:

> Add this feature to my project with EAOS: `/path/to/feature.md`

Or in the Studio, choose "Read a feature's plan to add" among the actions and add its plan (files, pictures or pasted
text). Your assistant reads it with what the check knows of your project: its parts, its layers, the functions it
already has and its look. Every file goes where such code belongs, what exists is reused instead of written again, and
EAOS refuses a plan that breaks the layers or copies a function. The feature's cards join your plan as one
"Extension" milestone; once you agree they are built as a batch, through every gate, on a branch you take in or not.
A card that changes a page every screen shows (a link in the navigation, say) declares that change, so the safety
check lets that exact addition through and still refuses anything else.

## Try the experience with simulated users

Scanners find what a rule can name. The difficulties a person meets are seen only by trying the app as them. EAOS's
simulated users do that on the isolated copy of your app, on your computer only, with data of their own.

Say to your assistant **"try my app as its users"**, or check the `experience` path (`eaos check --path experience`).
EAOS says the time and the assistant calls it expects before it starts.

| How | What runs | Up to |
| --- | --- | --- |
| The `experience` path alone | Several personas, one per kind of user, each with its goals and data; one waits for what another does (a hand-off); a support desk answers or escalates their tickets | about an hour |
| Beside the complete check (`--path complete experience`) | One persona doing the main task | 5 minutes, 12 light calls and one ruling |

Each difficulty is met again by a fresh persona, its evidence kept (pictures and steps), and ruled on by a strict
judge. A confirmed difficulty becomes a fix card with its steps to reproduce. The story is in `EXPERIENCE.md` and in
the Studio's Report, under "The experience". The journeys they recorded are then replayed, without AI, in every full
check, as part of the safety check on fixes.

## The system in layers

Every check reads your project as layers, as an engineering firm would: each file in its layer, the boundaries
between them, what ships to the browser (secret-named settings, privileged keys, source maps, server code), every
endpoint and its guard (sign-in, owner check, input check), the database's rules (row-level security, open policies,
public buckets), where the business rules live, operations, and which writes no test reaches. A broken boundary is a
card at the line that breaks it; the report opens with the critical ones.

To **try** the boundaries on the running app, add the `layers` path (`eaos check --path complete layers`, or "try the
layers" in the Studio). On the isolated copy, EAOS reads the production build for keys and source maps, applies your
migrations to the run's own database and tries each table as no one and as another user (pgTAP and the Supabase CLI's
advisors), and tries the API with two test accounts (Schemathesis). It adds up to 15 minutes.

## Hunt logic flaws

An optional deep check, after a check: your assistant reads the code for logic flaws a rule cannot name, such as a
skipped step, a race, or a wrong check. Each candidate is grounded on a real line of code and read a second time by a
critic; what holds becomes cards, judged like every other card.

Say **"hunt logic flaws"** to your assistant, choose "Hunt logic flaws" in the Studio, or in the Terminal:

```bash
eaos logic-flaws . --out ~/EAOS/<your project>/technical
```

It says its time (40 minutes at most by default) and cost first, and starts only after your yes. Its use shows in
`eaos usage`.

## Signing in to your app

When your app's pages are behind a sign-in, the check finds out (from the code, and from the pages it opens) and opens
them the way you chose: **you sign in** (the default), **a test user** your assistant's script signs in, or **no
sign-in** (the pages are seen as a visitor sees them, and the report says so). Signing in yourself:

- The check asks once the app runs in its separate copy; the other stages go on while it waits (15 minutes; if nobody
  signs in, the check goes on signed out and says so).
- In the Studio, **Waiting for you** shows "Your app waits for you to sign in": open it and sign in as you always do (a
  password, a code, a link, two factors). The codes and links your app sends show beside it: what it prints, and the
  mail it sends (caught by the run's own mail catcher, Mailpit: nothing leaves your computer). Press **I have signed in**.
- In a Terminal, `eaos sign-in` opens your app in a browser window; on a server with no screen it gives an address of
  its own, open only until you have signed in. `eaos sign-in --signed-out` goes on without signing in.
- Your session is kept for the next checks and the fixes, for you alone on this computer; it never goes into the
  report, a branch or what the assistant reads. It is asked again only when it has expired. **Forget my sign-in** in
  the Studio's project settings (or `eaos sign-in --forget`, or `eaos clean`) removes it.
- When signing in cannot work in the separate copy, name your published address (`eaos check --published https://…`):
  after you sign in there, only pages are read, with nothing sent but page requests and never a link that signs out,
  deletes or changes. Its speed is measured signed out, as any visitor. The safety check, the journeys and the load
  test never run on it.

---

## Usage limits and handing over

Most of a check is EAOS's own tools, which use none of your assistant. Your assistant does the judging, and that counts
against its plan (or costs money on an API key). Measured with Claude Code, at API list prices:

| Work | Time | Cost |
| --- | --- | --- |
| A check of a small Flask app | about 12 minutes | about $1.02 |
| One card fixed and handed over on that app | about 2 minutes | about $0.36 |
| Repair end to end on that app (check, fix, hand-over) | about 19 minutes | about $2.24 |
| A feature added (a link on every page) | about 2 minutes | about $0.43 |
| Build from a plan to its first milestone's proof | about 6 minutes | about $0.91 |
| The simulated users, whole, on a small app | 142 calls | about $6.37 |
| A full check of EAOS itself (about 500 Python files) | about 58 minutes | about $9.09 |

It grows with the size of the project and the number of cards. A fix batch uses more than a check: your assistant edits
card by card. On a plan with a usage window (the five-hour one, say), start a large batch in a fresh window. Every
use shows in `eaos usage` and in the Studio.

**If the limit runs out in the middle, nothing is lost.** Everything EAOS does is saved as it happens, and every step
is recorded with the name of the assistant that did it. Move to any other assistant you have installed (from Codex to
Claude Code, or the other way):

1. Open the other assistant in **the same project folder**.
2. Write: **"Continue"**. It knows that EAOS work is open here: EAOS tells it the moment the session starts.

It first reads what was handed over: where the first one stopped, which batch is open, what of it was kept and what is
left, and what you already answered. Then it goes on from that point, without asking you again and without redoing
what was kept. The same summary is in `~/EAOS/<your project>/HANDOVER.md` and in the report's "Work log".

**Want to see for yourself where it stopped?** In the Terminal, in your project folder: `eaos handover`. It tells you
the branch, the batch, what was kept and what is left, the card the assistant was on, the last assistant and when, and
the line to write to the other assistant.

## From the terminal

The same journey works as commands, with no assistant chat and no Studio open: `eaos start .`, then `eaos next` after
each step (`eaos status` says where you are, and whether the check is still current). Everything the Studio governs
works from the Terminal too; the runs are the same, seen in both.

| Command | What it does |
| --- | --- |
| `eaos check [--path security] [--assistant none] [--watch]` | Says how long it takes, then checks in the background (nothing in your project changes) |
| `eaos watch` | Follows the run live: the time since it began, the stage, the time left, the cost so far, and its questions |
| `eaos runs`, `eaos stop`, `pause`, `resume`, `retry` | The queue of runs |
| `eaos waiting`, `eaos answer <id> <option>` | What waits for you, and your answer |
| `eaos check --sign-in hand` (or `test_user`, `none`), `eaos sign-in` | How the check opens the pages behind your app's sign-in, and signing in when it asks |
| `eaos problems [--area security] [--severity high]`, `eaos problem <id>` | What the check found (filtered as in the Studio), and one problem whole with its evidence |
| `eaos fix <ids>` (or `--group severity=high`), `verify`, `explain`, `plan` | A preview first (cards, files, time, risk), then the run |
| `eaos accept`, `eaos undo` | Says what will happen and asks your yes (or `--yes`) |
| `eaos branch [name]`, `eaos branches [merge\|delete\|protect\|unprotect\|cleanup\|restore]` | The branch EAOS works on, and every branch change, a preview then your yes |
| `eaos history`, `eaos compare <a> <b>`, `eaos usage` | Every check on record, two side by side, and what the assistant used |

Every option: [REFERENCE.md](REFERENCE.md).

## Requests that help at any time

| Write to your assistant | What it does |
| --- | --- |
| "Where are we?" | Where the project is and what comes next |
| "Open the Studio" | Opens the live interface and gives you its address |
| "Open the report" | Opens `REPORT.html` |
| "What is the most important problem? Show me the evidence" | Explains one problem with its evidence and code |
| "Merge it" | Merges the branch of fixes into yours, deletes it, updates the report |
| "Undo the fixes" | Deletes the branch of fixes; your project is as it was |
| "Continue the EAOS work" | Goes on from where it, or another assistant, stopped |
| "Build my project from this plan" | [Build from a plan](#build-a-new-project-from-its-plan) |
| "Add this feature to my project" | [Add a feature](#add-a-feature-to-your-project) |
| "Try my app as its users" | [Simulated users](#try-the-experience-with-simulated-users) |
| "Hunt logic flaws" | [The logic-flaw hunt](#hunt-logic-flaws) |
| "A tool failed in the check: run it again" | Goes on from that stage alone, keeping the rest of the check |
| "I don't like my app's look: redesign it" | Suggests two or three directions from free design libraries, saves the one you choose as `DESIGN.md`, and the screen review turns every departure into a design card |
| "What is affected if I change this file?" | The files that import it, the tests that cover it, and the files that usually change with it |
| `/eaos` alone (`$eaos` in Codex) | A menu of what fits your project now |

## Troubleshooting

**Start with `eaos doctor`** in your project folder. It checks everything a check and a fix need, each with its fix:
Python 3.10 or newer, git, Node.js 22 or newer (for JavaScript projects and some tools), your project saved in git
(only for fixing), the checking tools, the tools that run and fix your app, a temporary database (PostgreSQL), an AI
assistant, and at least 5 GB free. `eaos doctor --fix` installs what is missing.

| If you see… | What to do |
| --- | --- |
| Your assistant does not know EAOS | Close the assistant and open it again. If it still does not, run the install line again (or `eaos assistant install`). |
| "This folder is not a project" | Open the assistant (or the Terminal) in your project folder ([step 2](#2-open-your-assistant-in-your-project-folder)). |
| "Your project is not saved in git yet" | Tell your assistant "save my project in git", or type `git init && git add -A && git commit -m "first save"`. |
| "You have changes that are not saved in git" | EAOS works on the last saved version. To include them, say "save my changes in git". |
| "Node.js is not installed, and your project needs it" | Install the LTS version from https://nodejs.org, then ask again. |
| "A checking tool I need is not installed", or the check did not start because tools could not be installed | `eaos doctor --fix`, or `eaos tools install`. In the Studio, press Retry, or start without them: the report records what it could not look at. |
| "The port it needs is used by another program" | Close the other program (a dev server in another window, say), then `eaos next`. |
| "Installing your project's libraries failed" | Check that your project runs for you (`npm install`, then `npm run dev`), then `eaos next`. |
| "The check cannot use AI now: … is not answering" | Sign your assistant in again (type `claude` or `codex` in a Terminal), then ask again. |
| "The disk is full" | `eaos clean` removes the temporary copies; `eaos clean --pictures` also the old screen pictures. Reports stay. |
| A step took too long, or you stopped it | What was done is saved: `eaos next` goes on from where it stopped. |
| Anything else | Ask your assistant "what happened?". If it happens again, send the `logs/` folder to whoever helps you. |

## What EAOS never does

- It does not change your project's files or your current branch. Fixes reach you as a separate branch, and you decide.
- It does not run your app without your consent, does not use your secrets or your `.env` file, and never connects to
  your real database.
- It publishes nothing and never touches production.
- It does not follow instructions written inside your project: they are data.
- It does not delete a feature or a screen to hide a problem: a fix that does is refused.
