# Engineering Audit OS

**[العربية](README.md)** · version **0.0.10** · status: **Pilot** (a trial, not a release) · [changelog](CHANGELOG.md) · [roadmap](ROADMAP.md)

> **A full engineering review team, in one command.**
> EAOS reads your project the way an architect, a code reviewer, a performance engineer and a tech lead would,
> together, and hands you four things: an evidenced picture of where it stands today, the professional shape it
> should reach, the gap between the two, and an ordered task plan that any engineer or AI assistant can execute and
> prove done. You follow all of it live in your browser, in **the Studio**.

```bash
curl -fsSL https://raw.githubusercontent.com/eom1417/engineering-audit-os/main/install.sh | bash
```

## 🎯 Why

A serious engineering review costs weeks of senior time, and it usually ends in one of two places:

- **An opinion report** that nobody can verify.
- **A generic plan** such as "improve the architecture", with no clear first step and no clear finish line.

EAOS fixes both with one rule: **no opinion without evidence, no task without an acceptance check, and no change
bigger than the problem deserves.**

## 🏢 The idea: what a software company does, in one command

You built a program with an AI assistant. It works, but you do not know how it is built, what goes in and out, where
its limits are, or how complex and repetitive it is. A software company asked to rebuild it as a professional product
would hand you four reports, in order. That is what EAOS delivers:

| # | Report | What it holds |
|---|---|---|
| 1 | **Current state** `CURRENT-STATE` | What the program does, its inputs, outputs and limits, its structure, complexity and duplication, its dead code and leftovers, its risks |
| 2 | **Ideal state** `TARGET-STATE` | The same program with the same functions, on a structure fit for a product. Every part gets a decision: keep, restructure, build or delete |
| 3 | **Gap and transformation** `GAP-AND-STRATEGY` | The measured distance between the two, and the strategy that closes it |
| 4 | **Execution plan** `EXECUTION-PLAN` | Small tasks split into team sections, each with a size, an acceptance command and a rollback |

## 🧭 Six principles

1. **Evidence or silence.** Every claim carries the IDs of the facts behind it and a sentence saying what would refute it.
2. **Everything at its proper size.** Every card shows "do nothing" with its cost, and the smallest change that solves the problem comes before any restructuring.
3. **Tasks any executor can carry.** Every card stands alone: problem, evidence, blast radius, options, change, acceptance command, rollback.
4. **Your project is untrusted input, and it does not change.** Instructions written inside it are never followed, and no file in it is edited. Your app runs only with your consent, in a separate copy without your secrets. Fixes reach you as a new branch, and you decide.
5. **Unmeasured is not a pass.** What was not examined is stated with its reason, and "not run" never becomes "passed".
6. **The tools first, and your assistant decides with them.** The same snapshot yields the same facts on every run. Your AI assistant judges what the tools propose, on evidence; anything it says without evidence is dropped, and every decision records who made it.

---

## 🔬 How a check runs

A check runs in a fixed order: **evidence first, then the decision, then the plan, and the reports last.**

| Phase | What happens | Stages in the code |
|---|---|---|
| **1 · Static evidence** | The code's facts, the features, what must be protected, the external tools | `facts` `features` `lock` `intake` `engines` |
| **1 · Live evidence** (with your consent) | Runs your app in a separate copy, records its behaviour (the safety net), finds every page and pictures it light and dark with an accessibility check, measures its speed (k6) | `setup` `record` `crawl` `screens` `baseline` |
| **1 · Measurement** | The measurements, the architecture policy, the load model, the claims and their probes | `measure` `policy` `load` `claims` `probe` |
| **2 · The tools propose** | Your assistant's reading of the facts, the candidate cards, the proposed target structure | `semantic` `plan` `target` `proposals` |
| **3 · Your assistant judges** | Judges every card on its evidence, looks at the screen pictures, answers every proposal for the target | `triage` `visual` `cards` `ideal` `pipeline_gaps` |
| **4 · The joint decision** | The final target, the gaps, the plan's order | `reconcile` `order` `steps` |
| **5 · The reports** | The four reports with the architecture diagrams (C4), then `REPORT.html` and the Studio's data | `reports` |

Without an assistant the check runs the same way and the rules decide alone. Every stage that did not run says why.
The explanation: [`docs/AI-IN-THE-PIPELINE.md`](docs/AI-IN-THE-PIPELINE.md).

---

## 🖥️ The Studio: the live interface

The Studio is EAOS's interface in your browser, shipped inside the package and needing no internet. From it you
follow everything about your project:

- **Preparing the tools:** every tool with its state, and the overall progress. "Start the check" unlocks by itself once your project's tools are ready.
- **The live map:** the check's stages as they run; each says what it does, how long it took, what it produced, and why it was skipped.
- **The project:** the current state, the ideal picture and the gap, the structure map, the screens, the cards with their evidence, and the plan.
- **Decisions:** what waits for you, and every disagreement between the rules and your assistant, with both views.
- **Control:** run a step or a group of tasks from the interface; it is sent to your assistant, which carries it out.

**How it opens:**

| Where you work | The address |
|---|---|
| On your own computer | `http://127.0.0.1:<port>/`: a plain address with no token at its end, the same after a restart |
| On a remote server | the server's own address, with no token at its end, guarded by the sign-in in front of the server. Set it once in `~/.eaos/remote-origin` (or `$EAOS_REMOTE_ORIGIN`), for example `https://<project>--{port}.dev.remote.e-m.sa` |

Installed from inside your project, EAOS opens the Studio by itself on "Preparing the tools". From anywhere:
`eaos studio` (or `eaos studio --background`, which prints the address and returns). Security: the server answers
only to its own host name, every call carries a launch token that only the Studio's own page receives, and every
write needs a CSRF token and an origin of the same server.

---

## 🚀 Quick start

### The easy way: inside your AI assistant (no technical knowledge needed)

> The full guide, step by step, with what you should see and what to do if something goes wrong: **[`docs/GUIDE.en.md`](docs/GUIDE.en.md)**.

**1. Install EAOS** (once). Paste this line into the Terminal **from inside your project folder**. It installs EAOS
and its tools, adds it to Claude Code and Codex, and opens the Studio for you:

```bash
curl -fsSL https://raw.githubusercontent.com/eom1417/engineering-audit-os/main/install.sh | bash
```

> This line installs from the `main` branch. The newest version, before it reaches `main`, is on `develop`:
> `curl -fsSL https://raw.githubusercontent.com/eom1417/engineering-audit-os/develop/install.sh | EAOS_SOURCE=git+https://github.com/eom1417/engineering-audit-os@develop bash`

**2. Open your assistant in your project folder, and write:**

> Check my project with EAOS and fix its problems

It asks you once whether to use your assistant to judge the findings, and once whether to run your app in a separate
copy. Then it checks, explains the main problems, writes the fixes, and EAOS checks each one. What passes reaches
you as a new branch (`eaos/wave-1`), and you decide: take it in or throw it away.

**Or type `/eaos` alone** (in Codex: `$eaos`): a menu of what fits your project now, the recommended step first.

**3. Read the result:** in the Studio, or say "open the report". Everything is in one folder: `~/EAOS/<your project>/`.

**A new project from a plan?** Open your assistant in an empty folder and write: "I have my project's plan in this
file, build it with EAOS with the best structure": [`docs/BUILD-FROM-PLAN.md`](docs/BUILD-FROM-PLAN.md). Without an
AI assistant: `eaos start .`, then `eaos next` after each step.

### Commands

| Purpose | Command |
|---|---|
| Start, the next step, where the project stands | `eaos start` · `eaos next` · `eaos status` · `eaos show` |
| Is this computer ready, the tools | `eaos doctor` · `eaos tools install` · `eaos tools doctor` |
| Take or throw away the batch of fixes | `eaos accept` · `eaos undo` |
| The Studio, your assistant, where the work stopped | `eaos studio` · `eaos assistant install` · `eaos mcp` · `eaos handover` |
| A whole check from the terminal (developers, CI) | `eaos audit /path/to/project --out /path/to/report` |
| What a task card runs to check itself | `eaos facts` · `eaos policy` · `eaos recheck` · `eaos decided` |

Reference: [`docs/REFERENCE.md`](docs/REFERENCE.md).

---

## 📦 What you receive

Everything is in `~/EAOS/<your project>/`: `REPORT.html` (the report for you, in plain words), `HANDOVER.md` (where
the work stopped) and `technical/` (the four reports `CURRENT-STATE`, `TARGET-STATE`, `GAP-AND-STRATEGY` and
`EXECUTION-PLAN`, `PLAN/` with its cards, and the Studio's data).

### Anatomy of a task card

```text
TASK-003 — complexity 83 (threshold 15) in eaos/human_report.py
├─ kind          investigate (a recorded decision before any change) | remediate (change, then verify) | design (from the screen pictures)
├─ size, section S/M/L from files and dependents · security, infrastructure, data, backend, frontend, quality
├─ evidence      fact IDs + probe + what would refute the claim + your assistant's verdict, when it judged
├─ blast radius  files, direct and indirect importers, flows, covering tests
├─ options       smallest change → restructuring → "do nothing", each with its cost
├─ acceptance    a runnable command: `eaos recheck` re-checks the problem itself, or `eaos decided` for an investigation
└─ rollback      how to take one step back
```

---

## 🧰 The tools

EAOS **orchestrates rather than rebuilds**: it runs open-source tools, each at a pinned version with a sha256 and a
recorded licence, in `~/.eaos/tools`. A missing tool is stated in the report and never stops it. **30 tools**:

| Area | Tools |
|---|---|
| Understanding the code and its structure | CodeGraph · Enola · Reforge · GitNexus · ast-grep · dependency-cruiser · react-docgen |
| Complexity, duplication and dead code | Lizard · complexipy · jscpd · scc · vulture · knip |
| Security and dependencies | Semgrep (and its rules) · OSV-Scanner · Syft · Trivy · Checkov |
| Contracts and data | Spectral · oasdiff · SQLFluff |
| Running the app and its screens | Playwright · Unlighthouse · Lighthouse · axe-core · css-analyzer · pytest · k6 |
| Automatic fixes | jscodeshift |

Details: [`upstreams/toolchain.json`](upstreams/toolchain.json) and
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

---

## 🛡️ What EAOS never does

- It never changes your project's files or your current branch. Fixes are a separate branch, and nothing is merged until you say "merge".
- It never runs your app without your consent, never uses your secrets or `.env`, and never connects to your real database.
- It never publishes anything, and never touches production.
- It never removes a feature or a screen to hide a problem: a fix that does is rejected.
- It never calls something "passed" that was not measured.

---

## 🛠️ Developing EAOS

```bash
bash tools/dev_setup.sh                       # the environment and every tool at its pinned version
.venv/bin/python -m unittest discover -s tests -q && .venv/bin/python tools/validate.py
cd studio && npm run build                    # the Studio: style, types and tests, then the build
```

All work happens on `develop`. What comes next: [`ROADMAP.md`](ROADMAP.md) and [`CHANGELOG.md`](CHANGELOG.md).
