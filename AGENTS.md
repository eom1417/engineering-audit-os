> **أول قاعدة قبل أي شي: كل كلام للمالك بالعربي فقط، بدون أي استثناء**: الردود، والسطر القصير بين خطوة وخطوة، والأسئلة، والجداول وعناوينها، والملخصات، وملخص الإشعار؛ وتقارير المساعدين الفرعيين تُترجم قبل ما تُنقل. بكلام بسيط بلا مصطلحات، واللهجة الخليجية مقبولة. الكود والتعليقات وأسماء الملفات ورسائل commit والوثائق التقنية فقط بالإنجليزي.
> **مواضع الزلل المعروفة (تكررت):** بعد ما تنقطع الجلسة وترجع، وبعد شغل برمجي طويل، ولما تشرح تصميم أو تقترح حل، وفي عناوين الجداول. اكتب أول كلمة بالعربي، وراجع الرسالة كلها قبل الإرسال، ولا تكتب بالإنجليزي ثم تترجم.
> **First rule: every word to the owner is Arabic, no exception; everything programmed is English.** Slip points: after a resume, after long coding, when explaining a design, in table headers.

# Developing EAOS

The one manual for the assistant developing EAOS itself (Codex reads this file; `CLAUDE.md` imports it for Claude
Code). What EAOS tells the assistants of the projects it checks lives in `eaos/data/`, not here.

## Start of every session (any assistant, any account, any model)

1. In the development container: read `/workspace/AGENTS.md` (the workspace map) and `/workspace/HANDOFF.md` (the state
   now); run `bash /workspace/eaos-dev/workers/disk-budget.sh` and say any folder over its budget.
2. Read `ROADMAP.md`: where the work stands and the cards of the milestone the owner names.
3. Read only the reference the card needs:

| Reference | What it holds |
|---|---|
| `docs/NORTH-STAR.md` | what EAOS is for, the three journeys, the principles |
| `docs/STANDARDS.md` | the laws (code, security, safety, disk, tests, language), what guards each, the Definition of Done |
| `docs/ARCHITECTURE.md` | the layout, the layers, the loops, where a new file goes |
| `docs/DECISIONS.md` | the owner's decisions that bind, by topic |
| `docs/METRICS.md` | the numbers, baseline and after each milestone |
| `CHANGELOG.md` | what each version changed and why |
| `/workspace/RUNBOOK.md` | how to run a verify, the beta update, a trial, the corpus, the metrics in this container |

   `docs/archive/` (the done cards, the reasoning of done milestones) is read only when a question needs that history.
4. "Execute Mx" means every card of Mx, in order, to the Definition of Done, without asking again except for a
   decision only the owner can take.

## Keep the context current

After every finished card or new decision, in the same change, as `docs/STANDARDS.md` §8 lists. Nothing about the work
is kept in an account's or assistant's folders: a plan made in a provider's plan mode is copied into `ROADMAP.md` or
`docs/DECISIONS.md` before the turn ends.

## The owner

- Writes Gulf Arabic and is not a developer: plain words, no jargon, the visible result first, short answers, honest
  about what is not done or not proven; no loops, no long waits.
- Judges EAOS by what a non-developer feels using it. **Least change, best result**: the smallest root fix, the cause
  not the symptom; state the regression risks and how they are avoided; never break what exists; prove it with a real
  trial, not only unit tests.
- **Time and tokens are the owner's** (2026-10-24): plan the shortest path first; the affected tests while working, the
  full verify **once** at the end of a batch of changes; no checks beyond what proves the change; finish what is in
  hand before opening new work; real, not padded, estimates.
- The owner's own projects (chief-ops, HungerLab, …) live in other containers and are never checked from here: fixes
  are proved on trial apps in `/workspace/eaos-work/<task>/` and on the compatibility corpus.
- **`main` is the owner's mother copy and is never touched** (git hooks refuse it).

## The laws (in full: `docs/STANDARDS.md`)

- Least code, best result; one source of truth; clear and clean; nothing replaced is left behind.
- EAOS itself: module ≤ 400 lines and function complexity ≤ 10 with no exception (M3) in Python; the Studio's
  JavaScript under the same laws, no exception (M4.6; `console/tools/same.cjs` proves a split left every screen as it was); functions ≤ 50 lines and ≤ 5
  parameters (today's exceptions listed). The laws EAOS holds every project to stay 600 / 15 (`eaos/core/code_laws.py`,
  the owner's to change). No dead code, no duplication, no medium or high security finding; layers per
  `docs/ARCHITECTURE.md`.
- **`tools/quality.sh`** checks every law in about a minute and refuses any number worse than recorded
  (`tools/code_limits.json`, `tools/quality.json`, the layer contracts in `pyproject.toml`); `--record` after a number
  went down, `python tools/code_limits.py --tighten` after a listed function or module shrank.

## The development flow: EAOS develops EAOS

`beta-trial` is the working EAOS (code, tools, Studio); `develop` is the project under check, as anyone else's.
0. **Build on a new branch** `dev/<topic>` from `develop`, without asking (directly on `develop` only when the owner
   says so).
1. **Develop and verify** there: affected tests while working, then before merging:
   ```bash
   tools/quality.sh && .venv/bin/python -m unittest discover -s tests -q && .venv/bin/python tools/validate.py
   (cd console && npm run build)     # only when console/ or docs/studio-actions.json changed
   ```
   The full suite (~7 min) runs as a background job; one heavy job at a time. In this container
   `/workspace/eaos-dev/workers/verify.sh <commit>` runs all three in a throwaway worktree and stamps the commit in
   git when they pass; the beta update then skips its own suite and code laws for it (the golden trial still runs).
2. **Merge into `develop`** (`--no-ff`), push `origin/develop`, delete the branch.
3. **`develop` into `beta-trial`** with `bash /workspace/eaos-beta-trial/update.sh --approved` (as a systemd unit:
   `/workspace/RUNBOOK.md`): at each milestone end, approved in advance; otherwise only when the owner approves.
   It stops at the first failure, runs the suite, `tools/quality.py` and the golden trial, restarts the Studio, and deletes merged
   `dev/` branches.
4. **Then the check**: of `develop`, from the Studio that runs `beta-trial`.

For everyone else EAOS lets the person choose the branch and when to merge; it never decides that for them.

## Versions

`0.0.x`: one version per milestone (M-1, documents only, has none) (`pyproject.toml`, `eaos/__init__.py`, the badges in `README.md` and `README.ar.md`, a `CHANGELOG.md` entry:
why, from the real incident, then what changed). `1.0.0` only when the owner declares it.

## Tests

`unittest`, one test per real behaviour, a fix adds a test only when it reproduces a real failure. Guards that always
stay: `test_code_limits`, `test_studio_assets`, `test_golden_facts`, `test_consistency`, `test_artifact_contract`,
the golden trial (`tools/golden_trial.sh`, with the detection baseline of `tests/fixtures/baseline-app` and no layer
finding on its clean twin `tests/fixtures/baseline-clean`), `test_layers` (every planted boundary defect found).
`tests/test_journey.py` is the fast end-to-end proof. A change to running apps or finding screens also runs the
compatibility corpus (`tools/corpus.py`, a background job of about an hour: `/workspace/RUNBOOK.md`); a milestone end
measures `docs/METRICS.md` with `tools/metrics.py`.

## Setting up a computer

`bash tools/dev_setup.sh` builds `.venv`, installs every external tool at its pinned version in `~/.eaos/tools`
(`$EAOS_ENGINE_TOOLS`) and the development material in `~/.eaos/dev`; `python tools/dev_paths.py` shows where each
part is. Never write one machine's path in code (`tests/test_platforms.py`).

## The disk: a helping tool never weighs on the machine (owner, 2026-10-17)

- Scratch of a task lives in `/workspace/eaos-work/<task>/` and is removed when the task ends; never a copy of a
  project, report or measurement kept past its task.
- One copy of the tools: `~/.eaos/tools` is the working EAOS's (`/workspace/eaos-beta-trial/tools`).
- What EAOS makes, EAOS removes: a new kind of file comes with the rule that removes or bounds it, and its test.
- The disk budget (`/workspace/eaos-dev/workers/disk-budget.sh`) is said at the start of every session; the beta
  update stops while a folder is over it.
