<!-- EAOS guide: begin (written by EAOS from the project itself; what you write below the end line stays) -->
# Extending shop

**Adding anything starts here.** Read the recipe of what you add, then its example; read further only if the recipe leaves a question. It is taken from how this project really grew.

## The layers

| Layer | Where | Files | May use |
|---|---|---|---|
| domain | `app` | 6 | - |

## Features today

| Feature | Where it starts | Its data |
|---|---|---|
| cli:shop | `pyproject.toml` | - |

## The checks

Before merging: it declares none.
Tests: this project has none yet.

## Recipes

### A dependency
- **Last real example:** `pyproject.toml` (b4a70c4, 2026-01-01).
- **Read only:** `pyproject.toml`, `app/__init__.py`, `app/main.py`, `app/old_export.py`, `app/old_mail.py`.
- **Touch, in order:** (1) `pyproject.toml`; (2) `app/__init__.py`; (3) `app/main.py`; (4) `app/old_export.py`; (5) `app/old_mail.py`; (6) `app/old_report.py`; (7) `app/prices.py`.

## Not in this project yet

A page; An endpoint; A data model and its migration; A background job; A value of the look (a token); A component; A format (a date, a number, a currency); A test; A setting or a secret (by name only, its value never written here); A translation. Keep the layers above when adding the first one.

## Known departures

Where the project breaks its own structure today. Follow the tables for new code, not these.

- Inputs and outputs in documented formats with versions: not found (typed schema source: none)
- Tests on every push, on every supported Python: not found (0 CI step(s) in the repository)
- Unit tests plus approval tests of command output: not found (0 test file(s))
- Exit codes that mean something, and --verbose logging: not found (0 observability signal(s))
- Layers with no test: domain.

<!-- EAOS guide: end -->
