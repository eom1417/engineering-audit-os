# Developing EAOS

The manual for anyone, person or AI assistant, who changes EAOS itself (Codex reads this file; `CLAUDE.md` imports it
for Claude Code). What EAOS tells the assistants of the projects it checks lives in `eaos/data/`, not here.

**A maintainer's own notes come first:** when `../eaos-private/DEVELOPING.md` exists beside this checkout, read it
before anything else; it binds over this file.

## Start

1. Read `ROADMAP.md` (where EAOS is going) and `docs/NORTH-STAR.md` (what it is for).
2. Read only the reference the change needs:

| Reference | What it holds |
|---|---|
| `docs/NORTH-STAR.md` | what EAOS is for, the three journeys, the principles |
| `docs/STANDARDS.md` | the laws (code, security, safety, disk, tests, language), what guards each, the Definition of Done |
| `docs/ARCHITECTURE.md` | the layout, the layers, the loops, where a new file goes |
| `docs/METRICS.md` | the numbers, baseline and after each milestone |
| `CHANGELOG.md` | what each version changed and why |
| `CONTRIBUTING.md` | how a change is proposed |

## The laws (in full: `docs/STANDARDS.md`)

- Least code, best result; one source of truth; clear and clean; nothing replaced is left behind; fix the cause, not
  the symptom, and never break what exists.
- EAOS itself: module ≤ 400 lines and function complexity ≤ 10 with no exception in Python; the Studio's JavaScript
  under the same laws, no exception (`console/tools/same.cjs` proves a split left every screen as it was); functions
  ≤ 50 lines and ≤ 5 parameters (today's exceptions listed). The laws EAOS holds every project to stay 600 / 15
  (`eaos/core/contracts/code_laws.py`). No dead code, no duplication, no medium or high security finding; layers per
  `docs/ARCHITECTURE.md`.
- **`tools/quality.sh`** checks every law in about a minute and refuses any number worse than recorded
  (`tools/code_limits.json`, `tools/quality.json`, the layer contracts in `pyproject.toml`); `--record` after a number
  went down, `python tools/code_limits.py --tighten` after a listed function or module shrank.
- **The published tree holds only the product.** No machine detail (cores, memory, load, host names, internal
  addresses), no absolute path of a development machine, no personal e-mail, no name of a private project: a real
  incident is told by what it was, not by whose it was (`tests/guards/test_public_tree.py`). Secrets come from the
  environment by name only (`gitleaks`).

## The flow

`main` is the release line and is never committed to directly (git hooks refuse it); `develop` is where work lands.
1. **Build on a new branch** `dev/<topic>` from `develop`.
2. **Verify** there: the affected tests while working, then once before merging:
   ```bash
   tools/quality.sh && .venv/bin/python -m unittest discover -s tests -q && .venv/bin/python tools/validate.py
   (cd console && npm run build)     # only when console/ or docs/studio-actions.json changed
   ```
   The full suite (several minutes) runs as a background job; one heavy job at a time.
3. **Merge into `develop`** (`--no-ff`), push, delete the branch.

EAOS checks itself like any other project: the working copy of EAOS checks `develop`. For everyone else EAOS lets the
person choose the branch and when to merge; it never decides that for them.

## Versions

`0.0.x`: one version per milestone (`pyproject.toml`, `eaos/__init__.py`, the badges in `README.md` and
`README.ar.md`, a `CHANGELOG.md` entry: why, from the real incident, then what changed). `1.0.0` only when the
maintainers declare it.

## Tests

`unittest`, one test per real behaviour, a fix adds a test only when it reproduces a real failure. Guards that always
stay: `test_code_limits`, `test_studio_assets`, `test_golden_facts`, `test_consistency`, `test_artifact_contract`,
`test_public_tree`, the golden trial (`tools/golden_trial.sh`, with the detection baseline of
`tests/fixtures/baseline-app` and no layer finding on its clean twin `tests/fixtures/baseline-clean`), `test_layers`
(every planted boundary defect found). `tests/guards/test_journey.py` is the fast end-to-end proof. A change to running
apps or finding screens also runs the compatibility corpus (`tools/corpus.py`, a background job of about an hour); a
milestone end measures `docs/METRICS.md` with `tools/metrics.py`.

## Setting up a computer

`bash tools/dev_setup.sh` builds `.venv`, installs every external tool at its pinned version in `~/.eaos/tools`
(`$EAOS_ENGINE_TOOLS`) and the development material in `~/.eaos/dev`; `python tools/dev_paths.py` shows where each
part is. Never write one machine's path in code (`tests/guards/test_platforms.py`).

## The disk: a helping tool never weighs on the machine

- Scratch of a task lives outside the repository and is removed when the task ends; never a copy of a project, report
  or measurement kept past its task.
- One copy of the tools: `~/.eaos/tools`.
- What EAOS makes, EAOS removes: a new kind of file comes with the rule that removes or bounds it, and its test.
