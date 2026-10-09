# Task-runner scripts traced to the program they run: what was adopted

Checked on 2026-10-08 against PyPI and the virtual environment EAOS already ships, for the entry point detector of
manifests (`eaos/facts/frameworks/manifests.py`): a package.json script or a Makefile target is followed to the
repository file it runs (`node scripts/ship.mjs`, `python -m pkg.tool`, through `npm run x` and make prerequisites),
and a script that only runs an external tool (`vite build`, `tsc`, `pytest`) becomes a `tool_command` fact.

## Reading a script's command line

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| Python's `shlex` (standard library) | PSF | Python 3.12 | maintained with Python | POSIX word splitting with quotes; no operators, so `&&`, `\|\|`, `;`, `\|` and `&` are split first by one expression |
| `bashlex` | GPL-3.0-or-later | 0.18 (2023-01-18) | no release since 2023 | A full bash AST (lists, pipelines, substitutions); the licence is outside `docs/TOOLCHAIN.md` §2 for code EAOS runs in-process, and it has not been released for almost three years |
| `tree-sitter-bash` through `tree-sitter-language-pack` | MIT | 0.25.1 (2025-12-02); the pack 1.20.0 is already in `.venv` | active | A real bash grammar, already installed for the syntax extractor; it would split operators inside quotes correctly, but it answers only the syntax: which word is a program and which is a tool's argument is the same rule either way |

**Decision**: use the standard library, no package. The hard part of the task is not parsing a one-line script but
deciding which word is the program a runner executes (`node`, `tsx`, `python`, `bash`, a `$(PYTHON)` variable, a path
to a file of the repository) and which is only a file handed to a tool (`eslint src/a.ts` reads the file, it does not
run it); no candidate answers that, and the rule is about thirty lines. `shlex` already handles the quoting a script
uses. The known limit, an operator inside a quoted string (`echo "a && b"`), only splits a command that runs no
repository program anyway; tree-sitter-bash stays the candidate if scripts with subshells or substitutions ever need
to be followed, and it is already installed.

**Pinned**: none
