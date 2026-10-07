# Developing EAOS: what every assistant working on this repository must know

This file is for the assistant developing EAOS itself (Codex reads it; CLAUDE.md points Claude Code here).
It is not what EAOS tells the assistants of the projects it audits; that lives in `eaos/data/`.

## The owner

- The owner writes Gulf Arabic and is not a developer. **Every message to them is in Arabic, always**:
  replies, the short progress updates between steps, questions, summaries and the notification summary;
  plain words, no jargon; tables are welcome. **Everything programmed is in English**: code, code
  comments, file and symbol names, commit messages and the technical docs. A command or a file name
  inside an Arabic sentence stays as it is.
- They judge EAOS by what a non-developer feels when using it on a Mac with Codex and Claude Code.
  Fix the cause, not the symptom; prove it with a real assistant trial, not only unit tests; keep the
  progress numbers honest.
- **`main` is the owner's mother copy and is never touched**: no commit, push or merge into it; only the
  owner decides about it. All work happens on `develop`: once a change is done and verified clean (full
  suite, gates), commit and push to `origin/develop` (standing instruction since 2026-10-07).

## Versions

`0.0.1`, `0.0.2`, … (`pyproject.toml`, `CHANGELOG.md`). Bump the patch number with each published
update. `1.0.0` is reserved for the first official release, which only the owner declares: after
progress reaches 100%, everything is fixed, and EAOS has audited its own structure with itself.

## Setting up a computer

```bash
bash tools/dev_setup.sh
```

It builds `.venv`, installs every external tool at its pinned version in `~/.eaos/tools`
(`$EAOS_ENGINE_TOOLS`), and fetches the development material into `~/.eaos/dev` (`$EAOS_DEV_HOME`):
the pinned sample corpus and the engines' source checkouts. `python tools/dev_paths.py` shows where
each part is. Never write a path of one machine in code: `tests/test_platforms.py` fails if you do.

## The plan and progress

- The product's plan is `docs/north-star.json` (steps NS*, weights sum to 100; capabilities with
  indicators). `docs/NORTH-STAR.md` is generated from it: `python tools/north_star.py`, then
  `python tools/north_star.py --check`.
- A new request from the owner becomes a new step, its weight taken from done steps (the owner
  accepts progress dropping). A task closes only when its acceptance command passes
  (`tools/north_star.py measure --only X --min 1.0` or `tools/acceptance.py`), never on its own
  unit tests alone. `python tools/north_star.py --no-regression` must hold.
- `acceptance/` is locked by `acceptance/LOCK.json`: change an acceptance test only as the planner,
  never to make a failing task pass, then `python tools/acceptance.py lock`.

## Tests and gates

The checks in `CONTRIBUTING.md` before every commit. The tests are `unittest`, about 1500 of them,
about 25 minutes: run the affected modules while working (`.venv/bin/python -m unittest tests.test_x`),
the full suite before pushing, as a background job.

## Real trials

`tools/mcp_trial.py`, `tools/build_trial.py`, `tools/handover_trial.py`, `tools/branch_trial.py`,
`tools/ux_trial.py` drive the real Codex and Claude Code on real projects and write
`$EAOS_MEASURE/<kind>/<project>/trial.json` (default `~/.eaos/dev/measure`), which the plan's
indicators read. Run long trials from a frozen copy of the repository: a code edit changes the tool
digest and forces a new audit. They need the assistants installed and logged in, and the owner's
projects cloned from their GitHub (`eom1417/*`); only run their code with the owner's authorization,
recorded in `docs/north-star.json` (`live_corpus`).
