# From zero to your first fix

For people who built their app with an AI assistant and do not know the details of programming. Copy each
command exactly, paste it into the terminal, and press Enter. Every command ends with a box that says what
happened, and what to type next. Copy the command alone, with nothing before it: `eaos doctor`, not
`bash eaos doctor`.

> **Easiest:** if you use Claude Code or Codex, do step 1 and step 2, then talk to your assistant in your own
> words: "check my project", "what is wrong?", "fix it", "where are we?". It runs the commands and explains.

---

## 1. Install EAOS (once)

```bash
curl -fsSL https://raw.githubusercontent.com/eom1417/engineering-audit-os/main/install.sh | bash
```

- **Takes:** 3 to 10 minutes.
- **You should see:** ✅ "EAOS is installed".
- **If it says "open a new terminal window":** close the terminal and open it again.
- **Needs:** Python 3.10 or newer, and git. If one is missing, the command says where to get it.

## 2. Teach your AI assistant (optional, once)

```bash
eaos assistant install
```

- **You should see:** ✅ "Your assistant now knows EAOS: Claude Code, Codex".
- Then open your assistant in your project folder and ask in your own words.

## 3. Check your project

Open your project folder in the terminal, then:

```bash
eaos start .
```

- **Takes:** 5 to 30 minutes, depending on the project's size. You see each step as it runs: `[3/26] Running the checking tools…`.
- **Nothing in your project changes.** Everything EAOS writes goes to a separate folder: `~/.eaos/projects/`.
- **You should see:** ✅ "Checked your project: 584 problems, 312 of them can be fixed automatically" (your numbers will differ).

To read the result in plain words:

```bash
eaos show
```

## 4. Get ready to fix

```bash
eaos next
```

It asks one question: may it run your app in a separate copy on your computer, with a temporary database and none of your secrets?

- If you agree, type what the box says: `eaos next --yes`
- **Takes:** 5 to 20 minutes. It may ask your AI assistant how your app runs.
- **You should see:** ✅ "Your app runs in the separate copy".

## 5. Record your app before any change

```bash
eaos next
```

- **Takes:** 15 to 30 minutes.
- It records every screen of your app, and measures its speed. After each fix, the screens are compared with these recordings: if anything changed, the fix is refused.
- **You should see:** ✅ "Recorded 28 of 28 screens; the slowest requests take 28 ms".

## 6. Fix a first batch

```bash
eaos next
```

It asks once: may it fix batches of the ready fixes, and put what passes on a new branch in your project? If you agree:
`eaos next --yes`

- **Takes:** 20 to 60 minutes a batch (10 fixes).
- Each fix is tried in the separate copy: your project's checks, the screens, and that the problem is gone. What fails is left out, with its reason written down.
- **You should see:** ✅ "9 of 10 fixes passed; they are on the branch eaos/wave-1 in your project". Your current branch and files are as they were.

## 7. Accept, or undo

```bash
eaos accept    # take the fixes into your project
eaos undo      # throw them away
```

Then `eaos next` for the next batch.

---

## Useful at any time

| Command | What it does |
| --- | --- |
| `eaos status` | Where we are, and what comes next |
| `eaos show` | What the check found, in plain words |
| `eaos do "ask in your words"` | Understands your request and does it, like `eaos do "what is wrong"` |
| `eaos doctor` | Is your computer ready? What is missing, and how to fix it |
| `eaos clean` | Removes the temporary copies, to free space |

## If you see…

| The message | What to do |
| --- | --- |
| "We have not started with this project yet" | Open your project folder and type `eaos start .` |
| "Your project is not saved in git yet" | `git init && git add -A && git commit -m "first save"`, then `eaos next` |
| "You have edits not saved in git" | Not a problem: EAOS works on the last saved version. To include your edits: `git add -A && git commit -m "save"` |
| "The port it needs is used by another program" | Close the dev server running in another window, then `eaos next` |
| "A checking tool I need is not installed" | `eaos doctor --fix` |
| "Node.js is not installed" | Install it from https://nodejs.org (LTS), then `eaos next` |
| "The disk is full" | `eaos clean`, then `eaos next` |
| "I need your AI assistant" | Install Claude Code or Codex and sign in, then `eaos next` |
| Anything else | Type `eaos next`. If it happens again, send the log file named in the box to whoever helps you |

## What EAOS never does

- It does not change your project's files or your current branch. Fixes reach you as a separate branch; you decide.
- It does not use your secrets or your `.env` file, and it never connects to your real database.
- It does not deploy anything, and it never touches production (Railway, Vercel or any other).
