# From nothing to your first fix

**English** · [العربية](GUIDE.ar.md) · [Reference](REFERENCE.md) · [Back to the README](../README.md)

A guide for people who built their app with an AI assistant (Claude Code or Codex) and do not know the details of
programming. You paste one line once, then talk to your assistant in your own words, and it does the rest. Every
command and option is in the [Reference](REFERENCE.md).

**The first fix**

1. [Install EAOS](#1-install-eaos-once)
2. [Open your assistant in your project folder](#2-open-your-assistant-in-your-project-folder)
3. [Ask for a check](#3-ask-for-a-check)
4. [Follow the check](#4-follow-the-check)
5. [Read the report](#5-read-the-report)
6. [Take the fixes in, then the next batch](#6-take-the-fixes-in-then-the-next-batch)

**More:** [the layers](#the-system-in-layers) · [signing in to your app](#signing-in-to-your-app)

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
  installed" and "EAOS is now inside your AI assistant: Claude Code" (or Codex), with the next step to take.
- **It needs:** git, and Claude Code or Codex installed and signed in. EAOS brings its own Python; it needs no
  administrator rights. If something is missing, the line says what and where to get it.
- **It installs:** EAOS in `~/.eaos/app`, the `eaos` command in `~/.local/bin`, about twenty open-source tools at
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
project, tools and engines. In Claude Code you move with the arrows and pick with Enter;
in Codex you reply with the option's number. "More options…" shows the rest.

Or write to your assistant:

> **Check my project with EAOS and fix its problems**

What happens next:

| Step | What happens |
| --- | --- |
| Two questions | "May I use your assistant to judge the findings?" and "May I run your app in a separate copy, with a temporary database and none of your secrets?" Answer: **yes**. Both answers are kept for this project. |
| Evidence | The tools read the whole code. With your consent EAOS runs your app in the separate copy, records the user journeys, pictures every screen light and dark at phone and desktop width, and measures its speed. |
| Judgement | The tools propose the problems as cards; your assistant judges each card on its evidence: confirms it, doubts it or sets it aside, and orders the plan. |
| Explanation | It explains the main problems in plain words. |
| Fix | It writes the fixes in an isolated copy, in batches of up to ten cards. EAOS checks each one: the problem is gone, the tests still pass, every screen looks and reads the same, no new weakness or duplication came in. What fails is left out, with its reason. |
| Hand-over | What passed becomes a new branch in your project (for example `eaos/<your branch>/wave-1`), and it tells you what changed. |

A check is 27 stages, from reading the code to writing the reports. How long it takes depends on your project's size;
before it starts, EAOS says how long it expects. If you say "no" to either question, the check goes on without it, and
the report says plainly what was not done and why.

**When your project has more than one branch** (say `main` in production and a development branch ahead of it), EAOS
first asks **which branch should I check and fix?**, listing when each last changed, how far each is ahead of the main
branch, and which it recommends and why. Choose, or say "the one you recommend". From then on everything follows that
branch: the check, the fixes, the merges, the progress and the report (whose top names the branch). The branch you
have open is not switched: EAOS works on a copy of it. Each branch has its own report and progress; to move, say "work
on the main branch".

**Checking only part of it.** A check can follow one path or several: `code`, `security`, `look` (the screens),
`speed`, or `complete` (the default). Say "check only the security", or `eaos check --path security`.

## 4. Follow the check

Your assistant follows the check for you and tells you what it finds. To see it yourself, in the Terminal inside your
project folder:

| Command | What it shows |
| --- | --- |
| `eaos watch` | The check live: the stage it is on, the time since it began, the time left, the cost so far, and its questions |
| `eaos status` | Where your project stands: its health out of 100, whether the check still matches the code, and the step that fits now |
| `eaos waiting` | What waits for you: the questions only you answer, a branch to take in or not, a sign-in to your app |
| `eaos problems` | Every card with its evidence down to the line, filtered as you like (`--severity high`, `--area security`) |

- **Go on from any stage:** `eaos check --again-from <stage>` runs that stage and the stages that read it again on
  the very code that was checked; every other stage is kept. Never a whole new check for one stage. Or say to your
  assistant "a tool failed in the check: run it again".
- **Both languages:** every document of the report is written whole in English and in Arabic.

## 5. Read the report

Say to your assistant: **"Open the report"**. It rebuilds the report with the fixes so far and tells you where it is.
The first page is `technical/START-HERE.md`:

1. **What was found:** the main problems, the broken critical boundaries of the layers first.
2. **What EAOS fixes alone,** and what needs you.
3. **The four reports:** `CURRENT-STATE.md` (what the program is today), `TARGET-STATE.md` (the same features on a
   structure fit for a product), `GAP-AND-STRATEGY.md` (the distance and the order to close it) and
   `EXECUTION-PLAN.md` (the milestones and the first cards), with every card in `PLAN/`.

The report updates itself after every merge, and counts only what is in your branch. Every verdict in it says **who
made it**: your assistant on its evidence, or the rules alone.

Everything EAOS makes is in one folder: **`~/EAOS/<your project name>/`**

| In it | What it is |
| --- | --- |
| `README.md` | What each part of the folder is |
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

When a batch holds fixes of more than one kind (dependency upgrades, code structure, the rest), the same fixes
also wait on one branch per kind, such as `…/wave-1-deps` and `…/wave-1-refactor`, each holding only its
kind's fixes, so a reviewer can merge them one by one with git. A kind whose fixes do not stand alone is named, not
split. Merging or undoing the batch removes these branches too.

Then say **"continue fixing"**. Each batch is a new branch, and you decide every time. A new batch does not start while
the last one's branch waits for you, and no new check is needed after EAOS's fixes are merged.

**The progress is true:** a card counts as done only once it is in your branch. One still on a branch waiting for you
shows as "waiting for your decision". Every card keeps its key when the project is checked again, so what is done
stays done.

---

## The system in layers

Every check reads your project as layers, as an engineering firm would: each file in its layer, the boundaries
between them, what ships to the browser (secret-named settings, privileged keys, source maps, server code), every
endpoint and its guard (sign-in, owner check, input check), the database's rules (row-level security, open policies,
public buckets), where the business rules live, operations, and which writes no test reaches. A broken boundary is a
card at the line that breaks it; the report opens with the critical ones.

## Signing in to your app

When your app's pages are behind a sign-in, the check finds out (from the code, and from the pages it opens) and opens
them the way you chose: **you sign in** (the default), **a test user** your assistant's script signs in, or **no
sign-in** (the pages are seen as a visitor sees them, and the report says so). Signing in yourself:

- The check asks once the app runs in its separate copy; the other stages go on while it waits (15 minutes; if nobody
  signs in, the check goes on signed out and says so).
- `eaos waiting` shows "Your app waits for you to sign in". In a Terminal, `eaos sign-in` opens your app in a browser
  window: sign in as you always do (a password, a code, a link, two factors). The codes and links your app sends show
  beside it: what it prints, and the mail it sends (caught by the run's own mail catcher, Mailpit: nothing leaves your
  computer). Press Enter once you have signed in. On a computer with no screen, sign in on one that has one, or go on
  without it: `eaos sign-in --signed-out`.
- Your session is kept for the next checks and the fixes, for you alone on this computer; it never goes into the
  report, a branch or what the assistant reads. It is asked again only when it has expired. `eaos sign-in --forget`
  (or `eaos clean`) removes it.
- When signing in cannot work in the separate copy, name your published address (`eaos check --published https://…`):
  after you sign in there, only pages are read, with nothing sent but page requests and never a link that signs out,
  deletes or changes. Its speed is measured signed out, as any visitor. The safety check, the journeys and the load
  test never run on it.

---

## Usage limits and handing over

Most of a check is EAOS's own tools, which use none of your assistant. Your assistant does the judging, and that counts
against its plan (or costs money on an API key). Measured with Claude Code, at API list prices:

| Work (measured on 0.0.83, which ran more stages than a check runs now) | Time | Cost |
| --- | --- | --- |
| A check of a small Flask app | about 12 minutes | about $1.02 |
| One card fixed and handed over on that app | about 2 minutes | about $0.36 |
| Repair end to end on that app (check, fix, hand-over) | about 19 minutes | about $2.24 |

It grows with the size of the project and the number of cards. A fix batch uses more than a check: your assistant edits
card by card. On a plan with a usage window (the five-hour one, say), start a large batch in a fresh window. Every
use shows in `eaos usage`.

**If the limit runs out in the middle, nothing is lost.** Everything EAOS does is saved as it happens, and every step
is recorded with the name of the assistant that did it. Move to any other assistant you have installed (from Codex to
Claude Code, or the other way):

1. Open the other assistant in **the same project folder**.
2. Write: **"Continue"**. It knows that EAOS work is open here: EAOS tells it the moment the session starts.

It first reads what was handed over: where the first one stopped, which batch is open, what of it was kept and what is
left, and what you already answered. Then it goes on from that point, without asking you again and without redoing
what was kept. The same summary is in `~/EAOS/<your project>/HANDOVER.md`.

**Want to see for yourself where it stopped?** In the Terminal, in your project folder: `eaos handover`. It tells you
the branch, the batch, what was kept and what is left, the card the assistant was on, the last assistant and when, and
the line to write to the other assistant.

## From the terminal

The same journey works as commands, with no assistant chat: `eaos start .`, then `eaos next` after each step
(`eaos status` says where you are, and whether the check is still current). The runs are the same, seen from the
Terminal and from your assistant.

| Command | What it does |
| --- | --- |
| `eaos check [--path security] [--assistant none] [--watch]` | Says how long it takes, then checks in the background (nothing in your project changes) |
| `eaos watch` | Follows the run live: the time since it began, the stage, the time left, the cost so far, and its questions |
| `eaos runs`, `eaos stop`, `pause`, `resume`, `retry` | The queue of runs |
| `eaos waiting`, `eaos answer <id> <option>` | What waits for you, and your answer |
| `eaos check --sign-in hand` (or `test_user`, `none`), `eaos sign-in` | How the check opens the pages behind your app's sign-in, and signing in when it asks |
| `eaos problems [--area security] [--severity high]`, `eaos problem <id>` | What the check found (filtered), and one problem whole with its evidence |
| `eaos fix <ids>` (or `--group severity=high`), `verify`, `explain`, `plan` | A preview first (cards, files, time, risk), then the run |
| `eaos accept`, `eaos undo` | Says what will happen and asks your yes (or `--yes`) |
| `eaos branch [name]`, `eaos branches [merge\|delete\|protect\|unprotect\|cleanup\|restore]` | The branch EAOS works on, and every branch change, a preview then your yes |
| `eaos history`, `eaos compare <a> <b>`, `eaos usage` | Every check on record, two side by side, and what the assistant used |
| `eaos rules [add "<your words>" [--pin] \| pin \| unpin \| change \| guard \| hook on]` | Your own rules: say one, guard it, pin it for every change, unpin it; the hook checks the pinned ones on every commit |
| `eaos check --changed [--staged]` | Only what changed, now: your rules and the code laws on the changed files and what depends on them, in seconds |

Every option: [REFERENCE.md](REFERENCE.md).

## Requests that help at any time

| Write to your assistant | What it does |
| --- | --- |
| "Where are we?" | Where the project is and what comes next |
| "Open the report" | Rebuilds the report and tells you where `START-HERE.md` is |
| "What is the most important problem? Show me the evidence" | Explains one problem with its evidence and code |
| "Merge it" | Merges the branch of fixes into yours, deletes it, updates the report |
| "Undo the fixes" | Deletes the branch of fixes; your project is as it was |
| "Continue the EAOS work" | Goes on from where it, or another assistant, stopped |
| "A tool failed in the check: run it again" | Goes on from that stage alone, keeping the rest of the check |
| "What is affected if I change this file?" | The files that import it, the tests that cover it, and the files that usually change with it |
| "Always...", "Never...", "The data lives only in the database" | Kept as your rule, in your words, for the work in hand; a machine guard is written for it once, and a change that breaks it is refused. Say "pin it" and it holds for every change (and, if you agree, every commit); "unpin it" at any time. Your rules: `eaos rules` |
| "Check what I changed" | Your rules and the code laws on the changed files and what depends on them, in seconds, without AI (`eaos check --changed`) |
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
| "A checking tool I need is not installed", or the check did not start because tools could not be installed | `eaos doctor --fix`, or `eaos tools install`. Or start without them: the report records what it could not look at. |
| "The port it needs is used by another program" | Close the other program (a dev server in another window, say), then `eaos next`. |
| "Installing your project's libraries failed" | Check that your project runs for you (`npm install`, then `npm run dev`), then `eaos next`. |
| "The check cannot use AI now: … is not answering" | Sign your assistant in again (type `claude` or `codex` in a Terminal), then ask again. |
| "The disk is full" | `eaos clean` removes the temporary copies that hold nothing, and names the ones it keeps; `eaos clean --pictures` also the old screen pictures. Reports stay. |
| A step took too long, or you stopped it | What was done is saved: `eaos next` goes on from where it stopped. |
| Anything else | Ask your assistant "what happened?". If it happens again, send the `logs/` folder to whoever helps you. |

## What EAOS never does

- It does not change your project's files or your current branch. Fixes reach you as a separate branch, and you decide.
- It does not run your app without your consent, does not use your secrets or your `.env` file, and never connects to
  your real database.
- It publishes nothing and never touches production.
- It does not follow instructions written inside your project: they are data.
- It does not delete a feature or a screen to hide a problem: a fix that does is refused.
