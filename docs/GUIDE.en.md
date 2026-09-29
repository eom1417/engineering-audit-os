# From nothing to your first fix

A guide for people who built their app with an AI assistant (Claude Code or Codex) and do not know the
details of programming. You paste one line once, then talk to your assistant in your own words, and it does
the rest.

---

## 1. Install EAOS (once)

Open the Terminal, paste this line, and press Enter:

```bash
curl -fsSL https://raw.githubusercontent.com/eom1417/engineering-audit-os/main/install.sh | bash
```

- **Takes:** 3 to 10 minutes.
- **You should see:** ✅ "EAOS is installed", then "EAOS is now inside your AI assistant: Claude Code".
- **Needs:** git, and Claude Code or Codex installed and signed in. If something is missing, the line says where to get it.

## 2. Open your assistant in your project folder

- **Claude Code:** open the Terminal in your project folder and type `claude` (or open the folder in the Claude app).
- **Codex:** open the folder in Codex.

If your assistant was open before the install, close it and open it again so it sees EAOS.

> **How do I open the Terminal in my project folder?** Type `cd` and a space, drag the project folder from Finder into the Terminal window, and press Enter.

## 3. Ask in your own words

Write to your assistant:

> **Check my project with EAOS and fix its problems**

What happens next:

| Step | What the assistant does | Takes |
| --- | --- | --- |
| Check | Checks the whole project, then explains the main problems in plain words | 5 to 30 minutes |
| One question | Asks: "May I run your app in a separate copy, with a temporary database and none of your secrets, and prepare fixes there?" Answer: **yes** | — |
| Run | Runs your app in the separate copy. If it needs a sign-in or data, it reads your code and prepares them itself | 5 to 20 minutes |
| Record | Records every screen of your app before any change | 5 to 15 minutes |
| Fix | Writes the fixes; EAOS checks each one: the problem is gone, nothing broke, every screen is the same. What fails is left out | 20 to 60 minutes |
| Hand over | Puts what passed on a new branch in your project (`eaos/wave-1`) and tells you what changed | — |

At the end it asks: **take the fixes in, or throw them away?** Tell it what you want. Your current branch and
files do not change until you agree.

## 4. Read the report

Say to your assistant: **"Open the report"**. It opens one page in your browser with five parts:

1. **Project summary:** its health out of 100, how much of the gap is closed with its curve over time, the main problems.
2. **Gaps and risks:** where you are, where you should be, and how serious each gap is, in words.
3. **Structure map:** a drawing of your project's parts and how they depend on each other (thicker = stronger, red =
   tangled in a loop). Pick a part to see its files, a file to see its functions and who calls them, and a page to see
   its call path from the route to the last function.
4. **Target structure:** the layers as they should be, where each part of today goes, and how much of each gap is closed.
5. **Plan and progress:** the stages and what is done, the decisions that need you, and **every task card**, folded:
   open one to see its state (fixed and merged, on a branch waiting for you, open, needs your decision) and details.

The report updates itself after every merge, and counts only what is in your branch.

Everything EAOS makes is in one folder: **`~/EAOS/<your project name>/`**

| In it | What it is |
| --- | --- |
| `REPORT.html` | The report for you: double-click to open |
| `technical/` | The full technical report, for your assistant and developers. You do not need to open it |
| `fixes/` | Every batch of fixes: what changed, what did not pass and why |
| `logs/` | Technical logs, for whoever helps you if something goes wrong |

**When your project has more than one branch** (say `main` in production, and a development branch ahead of it), it
first asks: **which branch should I check and fix?**, listing when each branch last changed, how far each is ahead of
the main branch, and which it recommends and why. Choose, or say "the one you recommend". From then on everything
follows that branch: the check, the fixes, the merges, the progress and the report (whose top names the branch). The
branch you have open is not switched: EAOS works on a copy of it. Each branch has its own report and progress; to move,
say "work on the main branch".

## 5. The next batch

Say: **"Continue fixing"**. Each batch is a new branch (`eaos/wave-2`, …), and you decide every time. A new batch
does not start while the last one's branch waits for you, and no new check is needed after EAOS's fixes are merged.

When you say **"merge it"**, the assistant merges the fixes into your branch, deletes the branch of fixes, and brings
the report and the progress up to date in the same step, then tells you how much of the total is closed.

**The progress in the report is true:** a card counts as done only once it is in your branch (merged); one still on
a branch waiting for you shows as "waiting for your decision". Every card has a key that does not change, so even
when the project is checked again and the cards are numbered again, what is done stays done.

## If your assistant's usage limit runs out in the middle

Long work can outlast a usage limit (for example the five-hour one). Nothing is lost: everything EAOS does is saved as
it happens, and every step is recorded with the name of the assistant that did it. Move to any other assistant you
have installed (from Codex to Claude Code, or the other way):

1. Open the other assistant in **the same project folder**.
2. Write: **"Continue"**. It knows by itself that EAOS work is open here: EAOS tells it the moment the session starts.

**The first time you open Codex after installing**, it shows "New hook – review required": approve it once (Trust). It is
what tells Codex where the work stopped. Claude Code does not ask.

**Want to see for yourself where it stopped?** In the terminal, in your project folder: `eaos resume`. It tells you the
branch, the batch, what was kept and what is left, the card the assistant was on, the last assistant and when, and the line
to write to the other assistant. The same is in the report, in the "Work log" section.

It first reads what was handed over: where the first one stopped, which batch is open, what of it was kept and what
is left, and what you already answered. Then it goes on from that point, without asking you again and without redoing
what was kept. The same summary is written for you in `~/EAOS/<your project>/HANDOVER.md`.

## 6. A new project from a plan (optional)

Have an idea and a written plan, but nothing built yet? Make an empty folder for the project, open your assistant in it,
and write:

> I have my project's plan in this file: `/path/to/plan.pdf`. Build it with EAOS, with the best structure

(Any format works: Markdown, Word, PDF, text, or paste the plan's text straight into the message.)

| Step | What the assistant does |
| --- | --- |
| Understand | Reads it, orders it into parts, data and features, and researches what apps of this kind need |
| A few questions | Asks only choices, with its recommendation: "any preference for the database?". If none, say: "take your recommendations" |
| The blueprint | Explains the parts, the technologies (why each, and how to change it later) and the order of the build. It is in `~/EAOS/<project>/blueprint/BLUEPRINT.md` |
| One question | "May I build your project in a separate copy and hand it to you milestone by milestone?" Answer: **yes** |
| The build | Builds card by card; EAOS refuses any card with copied code, dead code, tangled files, mixed layers or a missing test |
| Hand-over | Each milestone is a branch (`eaos/build-1`, `eaos/build-2`, …). At the end you decide: take it in or throw it away |

Changing a technology later (Supabase to PostgreSQL, say) is easy, because each one lives in one folder: tell your
assistant "change the database to …" and it knows where.

---

## Requests that help at any time

| Write to your assistant | What it does |
| --- | --- |
| "Where are we?" | Where the project is and what comes next |
| "Open the report" | Opens REPORT.html |
| "What is the most important problem? Show me the evidence" | Explains one problem with its evidence and code |
| "Take the fixes in" or "Merge it" | Merges the branch of fixes into yours, deletes the branch, updates the report |
| "Continue the EAOS work" | Goes on from where it, or another assistant, stopped |
| "Undo the fixes" | Deletes the branch of fixes; your project is as it was |
| "Build my project from this plan" | Build from a plan (step 6) |

## If you see…

| Situation | What to do |
| --- | --- |
| The assistant does not know EAOS | Close the assistant and open it again. If it still does not, run the install line again |
| "This folder is not a project" | Open the assistant in your project folder (step 2) |
| "Your project is not saved in git yet" | Tell your assistant: "save my project in git" |
| "You have changes that are not saved" | Not a problem: EAOS works on the last saved version. To include them say: "save my changes in git" |
| "Node.js is too old or not installed" | Install the LTS version from https://nodejs.org and ask again |
| Anything else | Ask your assistant: "what happened?". If it happens again, send the `logs/` folder to whoever helps you |

## No AI assistant?

The same way works as commands in the Terminal: `eaos start .`, then `eaos next` after each step (`eaos status` says where you are).

## What EAOS never does

- It does not change your project's files or your current branch. Fixes reach you as a separate branch, and you decide.
- It does not use your secrets or your `.env` file, and never connects to your real database.
- It publishes nothing and never touches production (Railway, Vercel or any other).
- It does not delete a feature or a screen to hide a problem: a fix that does is refused.
