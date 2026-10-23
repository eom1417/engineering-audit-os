# EAOS engineering standards

The laws every line of EAOS obeys, all checked by one command: **`tools/quality.sh`** (about a minute). Numbers only
ever get stricter: a change that worsens one is refused (by `tools/quality.sh`, and by the beta update, step 5a).

## 1. Code

| Law | Today (enforced) | Target (ratchet, reached by M3) | Enforced by |
|---|---|---|---|
| Module size | ≤ 600 lines | ≤ 400 lines | `tools/code_limits.py` (`tests/test_code_limits.py`) |
| Function complexity | ≤ 15 decisions | ≤ 10 decisions | same |
| Function length | ≤ 50 lines, today's 12 longer ones listed | same | same |
| Function parameters | ≤ 5 (self, cls aside), today's 130 listed | same | same |
| One source of truth | no function written twice; jscpd clones not more than recorded | no duplicated block | `test_code_limits`, `jscpd` |
| No dead code | no unused import or variable (pyflakes); `vulture`, `enola`, `knip` not more than recorded | no unused function, module or JS export | `test_code_limits`, `tools/quality.sh` |
| Layers | today's direct imports between subpackages may not go backwards (5 contracts in `pyproject.toml`) | each layer imports only the layers under it (`docs/ARCHITECTURE.md`) | `import-linter` |

What exceeds a limit today is listed in `tools/code_limits.json` and may only shrink: after shrinking one, run
`python tools/code_limits.py --tighten`. Every engine's number (findings per engine and rule) is recorded in
`tools/quality.json` and may only go down: after it went down, run `tools/quality.sh --record`. The engines are EAOS's
own adapters (`eaos/engines/`), over EAOS's code without the tests, the built Studio and the rule examples; `knip` reads
the Studio's entries from `console/knip.json`.

**How code is written** (owner, 2026-10-13):
1. **Least code, best result**: the shortest, most direct code that does the job best; no needless layer, option or
   abstraction. A change that adds lines must earn them.
2. **One source of truth**: anything needed in two places is written once and called from everywhere else; a change
   then happens in one place.
3. **Clear and clean**: small functions with one job, modules with one responsibility, easy to extend.
4. **Fix the cause, not the symptom**, with the smallest change that solves it; state the regression risks and how
   they are avoided. Something a change replaces is removed in the same change.

## 2. Security

- No secret in code, logs, commits, process arguments or outputs; secrets come from the environment by name only.
- No shell built from strings; subprocesses take argument lists. Paths from outside are resolved and kept inside
  their root.
- Studio and API: launch token, CSRF and Origin checks on every write; bound to the hosts it was started for.
- EAOS's own code carries **no medium or high finding** from `bandit`, `semgrep`, `gitleaks`, `osv-scanner`: today's
  findings are recorded in `tools/quality.json` and may only go down (M2.1 silences `semgrep`'s noisy rule; the rest
  are reviewed in M3). `osv-scanner` reads the Studio's `package-lock.json`; the Python dependencies have no lock file.

## 3. Safety

- `main` is never touched (git hooks refuse it). Every change goes through a `dev/<topic>` branch from `develop`
  (directly on `develop` only when the owner says so).
- A project's app runs only in its isolated copy (`eaos/sandbox.py`, `eaos/live_run.py`): its own database, port and
  scratch home; never the owner's real data.
- The owner's own projects are never checked from the EAOS development container; fixes are proved on trial apps and
  on the compatibility corpus.
- Nothing destructive or outward-facing (push to `main`, delete a remote branch, publish) without the owner.

## 4. Performance and disk

- **What EAOS makes, EAOS removes**: a new kind of file comes with the rule that removes or bounds it, and its test.
- Outputs hold what people or later stages read; caches live in the runtime folder, never in the report.
- A check's output and runtime have size budgets (`docs/METRICS.md`); the disk budget script
  (`/workspace/eaos-dev/workers/disk-budget.sh`) is said at the start of each session.
- Long runs (checks, suites, updates) run as systemd units or background jobs, one heavy job at a time.

## 5. Tests

- `unittest`. One test per real behaviour; a fix adds a test only when it reproduces a real failure. No sleeps where a
  condition can be awaited; no test of exact wording unless the wording is the contract.
- Guards that always stay: `test_code_limits`, `test_studio_assets`, `test_golden_facts`, `test_consistency`,
  `test_artifact_contract`, the golden trial (`tools/golden_trial.sh`).
- **Detection baseline** (M0.2): `tests/fixtures/baseline-app` carries eight planted problems (a command injection, a
  secret, a dead function, a dead module, duplication, a broken screen, a sign-in, a logic flaw), listed in
  `tests/fixtures/baseline-problems.json` with how far EAOS reaches each (card, finding, missed). The golden trial checks
  the app and `tools/detection_baseline.py` refuses a check that reaches any of them less; `--record` after reaching
  more. Today 5 of 8 (the three missed say why).
- **Compatibility corpus** (M0.3): pinned real open-source apps; a change to running apps or screens never lowers its
  pass rate.

## 6. Language

- **Everything said to the owner is Arabic**: replies, the one-line updates between steps, questions, tables (headers
  too), summaries, the notification summary. Plain words, no jargon.
- **Everything programmed is English**: code, comments, file and symbol names, commit messages, technical docs.
- What EAOS shows its users is bilingual (Arabic and English) from one words catalog.

## 7. Definition of Done

**A card is done when, on its own `dev/<topic>` branch:**
1. `tools/quality.sh` passes.
2. The full suite and `tools/validate.py` pass; the Studio is built when `console/` changed.
3. The golden trial passes; the detection baseline finds the same problems or more; the compatibility corpus does not
   get worse (once they exist).
4. It is merged into `develop` (`--no-ff`), pushed, and the branch deleted.
5. **The context is updated in the same change** (section 8).

**A milestone is done when** all its cards are done, then: one version (`pyproject.toml`, `eaos/__init__.py`, the
README badges, a `CHANGELOG.md` entry), `beta-trial` updated (`update.sh --approved`, approved in advance for each
milestone end), `docs/METRICS.md` measured again, and a short Arabic summary to the owner.

## 8. The context is always current

After **every** finished card or decision, before the turn ends, the assistant updates:
- `ROADMAP.md`: the card's status, version and date.
- `docs/DECISIONS.md`: any new decision of the owner.
- `docs/ARCHITECTURE.md`: any change to the layout, layers or pipeline.
- `docs/STANDARDS.md`: any law that changed or became enforced.
- `docs/METRICS.md`: the numbers, at each milestone end.
- `AGENTS.md` (this repository) and `/workspace/AGENTS.md`, `/workspace/HANDOFF.md`: whatever they say that is no
  longer true.

Nothing about the work is kept in an assistant's or account's own folders (`~/.claude`, run-accounts, plan files,
provider memory, `~/.codex`): a plan written in any provider's plan mode is copied into `ROADMAP.md` or
`docs/DECISIONS.md` before the turn ends.
