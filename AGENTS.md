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
| `docs/EXTENDING.md` | **adding anything starts here**: per kind of addition, the files to read and touch, the test, the gates |
| `docs/METRICS.md` | the numbers, baseline and after each milestone |
| `CHANGELOG.md` | what each version changed and why |
| `CONTRIBUTING.md` | how a change is proposed |

## The laws (in full: `docs/STANDARDS.md`)

- Least code, best result; one source of truth; clear and clean; nothing replaced is left behind; fix the cause, not
  the symptom, and never break what exists.
- EAOS itself: modules ≤ 400 lines and function complexity ≤ 10, no exception, in Python and in the Studio's
  JavaScript (`console/tools/same.cjs` proves a split left every screen as it was); functions ≤ 50 lines and ≤ 5
  parameters, none listed: a function whose parameters cannot be grouped (a tool mirroring its command, a record's
  constructor) says why on its `def` line, `# limits: parameters -- <why>`. The laws EAOS holds every project to stay
  600 / 15 (`eaos/core/contracts/code_laws.py`). No dead code, no duplication, no security finding; layers per
  `docs/ARCHITECTURE.md`. **One source per pattern**: no near copy of one responsibility (alike shapes of two stay
  apart), no value of the look outside the Studio's `tokens.css`, no screen pattern or way of working written three
  times (`core/system/files.py` reads JSON, `core/system/clock.py` tells the time); a copy kept on purpose says why,
  `# jscpd:ignore-start -- <why>` (a way of working: `// ast-grep-ignore: <rule> -- <why>`).
- **`tools/quality.sh`** checks every law in about a minute and refuses any number worse than recorded
  (`tools/code_limits.json`, `tools/quality.json`, the layers contract in `pyproject.toml`, EAOS's own repository
  rules, ESLint on the Studio); `--record` after a number went down, `python tools/code_limits.py --tighten` after a
  listed function or module shrank.
- **The published tree holds only the product.** No machine detail (cores, memory, load, host names, internal
  addresses), no absolute path of a development machine, no personal e-mail, no name of a private project: a real
  incident is told by what it was, not by whose it was (`tests/guards/test_public_tree.py`). Secrets come from the
  environment by name only (`gitleaks`).

## The flow

`main` is the release line and is never committed to directly (its branch protection and gate,
`.github/workflows/main-gate.yml`, and the maintainers' git hooks refuse it); `develop` is where work lands.
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
stay: every test of `tests/guards/` (`tests/guards/test_journey.py` is the fast end-to-end proof), `test_layers`
(every planted boundary defect found) and the golden trial (`tools/golden_trial.sh`, with the detection baseline of
`tests/fixtures/baseline-app` and no layer finding on its clean twin `tests/fixtures/baseline-clean`). A change to running
apps or finding screens also runs the compatibility corpus (`tools/corpus.py`, a background job of about an hour); a
milestone end measures `docs/METRICS.md` with `tools/metrics.py`. The proofs with the real assistant, each spending money:
`tools/fix_proof.py` (in the golden trial), `tools/journeys_proof.py` (the three journeys), `tools/tidy_proof.py`
(moves and context, ten questions per app), `tools/experience_proof.py` (the simulated users). A tool's new pin:
`tools/platform_assets.py` fills its asset for every computer EAOS supports.

## Setting up a computer

`bash tools/dev_setup.sh` builds `.venv`, installs every external tool at its pinned version in `~/.eaos/tools`
(`$EAOS_ENGINE_TOOLS`) and the development material in `~/.eaos/dev`; `python tools/dev_paths.py` shows where each
part is. Never write one machine's path in code (`tests/guards/test_platforms.py`).

## The disk: a helping tool never weighs on the machine

- Scratch of a task lives outside the repository and is removed when the task ends; never a copy of a project, report
  or measurement kept past its task.
- One copy of the tools: `~/.eaos/tools`.
- What EAOS makes, EAOS removes: a new kind of file comes with the rule that removes or bounds it, and its test.

<!-- EAOS rules: begin (your pinned rules, written by EAOS from its rule registry; change them with eaos rules) -->
Rules the person pinned for this project. Keep every one of them in every change; EAOS refuses a change that breaks one.

- Nothing private is ever published: no machine detail, no path of this container, no name of the owner's own projects, no personal e-mail (R1, guarded by a test)
- One source per pattern: no code copied word for word (R2, guarded by EAOS's detectors)
- The code laws: modules of 400 lines at most, functions of complexity 10, 50 lines and 5 parameters at most (R3, guarded by a test)
<!-- EAOS rules: end -->
