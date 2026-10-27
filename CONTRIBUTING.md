# Contributing to EAOS

Thank you for helping. EAOS checks other people's code, so its own code is held to the bar it sets for them.

## The workflow

1. **Open an issue first** for anything larger than a small fix, so the approach is agreed before the work.
2. **Branch from `develop`** (`dev/<topic>`); `main` holds released versions only.
3. **Open the pull request into `develop`**, filling in its template.

## Set up

```bash
bash tools/dev_setup.sh          # .venv, every external tool at its pinned version, the development material
(cd console && npm ci)           # the Studio's build and lint tools (esbuild, ESLint)
```

`AGENTS.md` is the full manual for changing EAOS (the flow, the tests, the proofs); this page is the short version.

## Before every commit

```bash
tools/quality.sh                 # every code law, about a minute; refuses any number worse than recorded
.venv/bin/python -m unittest discover -s tests -q && .venv/bin/python tools/validate.py
(cd console && npm run build)    # only when console/ or docs/studio-actions.json changed: the Studio built into
                                 # eaos/data/studio, within its budgets
```

## The code laws

1. **Least code, best performance.** The shortest, most direct code that does the job best; a change that adds lines
   must earn them.
2. **One source of truth.** Anything needed in more than one place is written once and called from everywhere else.
3. **Clear and clean.** No dead code, no unused import, small functions with one job, modules with one responsibility.

`tests/guards/test_code_limits.py` enforces what can be measured in EAOS itself: no module over 400 lines, no function
over cyclomatic complexity 10 or 50 lines, none over 5 parameters unless its `def` line says why
(`# limits: parameters -- <why>`); no function written twice, no pyflakes finding. (600 lines and 15 are the limits
EAOS holds the projects it checks to: `eaos/core/contracts/code_laws.py`.) The laws in full: `docs/STANDARDS.md`.

## The rules of the codebase

- **A new Python module goes in the folder of its job** (`docs/ARCHITECTURE.md` §4); a layer imports only the layers
  under it (`import-linter`, the layers contract in `pyproject.toml`).
- **Every text a person reads exists in English and in Arabic**, added to both at once.
- **A new report document is declared in `eaos/core/contracts/artifacts.py`**, with its owner, purpose and line budget.
- **A test is added only when it reproduces a real failure**, one test per real behaviour.
- **Never write a path of one machine in code**: `tests/guards/test_platforms.py` fails if you do.

## Commits

Commit messages are in English and say what changed and why, in plain sentences. A release bumps the patch version
(`pyproject.toml`, `eaos/__init__.py`, the badges in both READMEs) and adds a `CHANGELOG.md` entry; the maintainers do
this at each milestone's end.

## Licence

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE).
