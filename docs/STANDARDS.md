# EAOS engineering standards

The laws every line of EAOS obeys, each beside **what guards it**: `tools/quality.sh` (about a minute), a named test of
the suite, a git hook, or "review" where no machine guards it yet (each of those is a candidate for a guard; a guard
added moves the law out of review). Numbers only ever get stricter: a change that worsens one is refused by
`tools/quality.sh`. Where a new file goes: `docs/ARCHITECTURE.md` §4.

## 1. Code

| Law | Today (enforced) | Target | Enforced by |
|---|---|---|---|
| Module size | ≤ 400 lines, no exception | same | `tools/code_limits.py` (`tests/guards/test_code_limits.py`) |
| Function complexity | ≤ 10, no exception, one count for the laws and the hotspots (`core/contracts/code_laws.py` `complexity`, a nested function counted alone) | same | same |
| Function length | ≤ 50 lines, no exception | same | same |
| Function parameters | ≤ 5 (self, cls aside), none listed: one whose parameters cannot be grouped (a tool mirroring its command's options, a record's constructor) says why on its `def` line, `# limits: parameters -- <why>`, as a justified pyflakes or Semgrep line does | same | same |
| One source of truth | no function written twice | no duplicated block | `test_code_limits` |
| One source per pattern | two numbers, each recorded in `tools/quality.json` and only ever lower: (a) **near copies** of code, clusters of pairs jscpd finds renamed, one or two lines apart or 85% alike (its similarity), of 40 tokens or more; (b) **idioms**: a way of working (reading a JSON file, a date, money, a request with its loading and error, a pop-up, drag and drop, validation, paging, an endpoint's guard) written three times or more is one helper. A near copy counts, and is a card, only with all three conditions: its copies carry one responsibility (the rules propose it: one part of the system, changed together, or fixed apart; the judge rules), keeping them costs upkeep or risks drift, and one source is simpler with no new coupling; otherwise it is a likeness said in the report, never a card nor a breach (`analysis/assessments/one_source_evidence.py`); those conditions are signs to sort by, not proof of one contract, and the history decides no card yet. A change is refused for code copied word for word (a copy kept on purpose inside jscpd's ignore markers aside); the detectors refuse only once their refusals are measured safe, none yet, and never while under their measured bar (`analysis/repair/one_source_gate.py` `REFUSES`). The same numbers hold every project EAOS checks (`core/contracts/code_laws.py` `NEAR_COPY`, `PATTERN_REPEATS`) | zero, or one reason each where the copy is on purpose | `tools/quality.sh` (`eaos/analysis/assessments/one_source.py`) |
| No dead code | no unused import or variable (pyflakes); EAOS's own dead-code detector not more than recorded | no unused function or module | `test_code_limits`, `tools/quality.sh` |
| Repository craft | no crowded folder, vague name, family of files, document naming a path that is gone, machine detail in a published file, or assistant's context too heavy or said twice (the limits in `eaos/rules/repository-craft.json`, the same rules EAOS reads any project with) | same | `tools/quality.sh` |
| Oldest Python declared | what EAOS ships runs on the `requires-python` of `pyproject.toml` | same | `tests/guards/test_python_floor.py`; a real run on that Python by hand |
| Layers | each layer imports only the layers under it, directly or not (`docs/ARCHITECTURE.md` §2; one layers contract in `pyproject.toml`, no exception) | same | `import-linter` in `tools/quality.sh` |

What exceeds a limit is listed in `tools/code_limits.json` and may only shrink (today the list is empty): after
shrinking one, run `python tools/code_limits.py --tighten`. Every engine's number (findings per engine and rule) is recorded in
`tools/quality.json` and may only go down: after it went down, run `tools/quality.sh --record`. The engines (jscpd,
ast-grep, Semgrep, Gitleaks) are EAOS's own adapters (`eaos/engines/`), over what EAOS ships (without the tests, the
developer tools and the rule examples).

**How code is written:**
1. **Least code, best result**: the shortest, most direct code that does the job best; no needless layer, option or
   abstraction. A change that adds lines must earn them.
2. **One source of truth**: anything needed in two places is written once and called from everywhere else; a change
   then happens in one place.
3. **Clear and clean**: small functions with one job, modules with one responsibility, easy to extend.
4. **Fix the cause, not the symptom**, with the smallest change that solves it; state the regression risks and how
   they are avoided. Something a change replaces is removed in the same change.

## 2. Security

| Law | Guarded by |
|---|---|
| No secret in code, logs, commits, process arguments or outputs; secrets come from the environment by name only | `gitleaks` in `tools/quality.sh`; `test_sandbox` (the isolated copy without env files or secrets) |
| No shell built from strings; subprocesses take argument lists | `semgrep` in `tools/quality.sh` (its findings recorded, may only go down) |
| Paths from outside are resolved and kept inside their root | review |
| EAOS's own code carries **no finding** from `semgrep` or `gitleaks`; a justified line says why, `# nosemgrep: <rule> -- <why>` | `tools/quality.sh`: `tools/quality.json` records none; a new finding fails |

## 3. Safety

| Law | Guarded by |
|---|---|
| `main` is never committed to; every change goes through a `dev/<topic>` branch from `develop` (directly on `develop` only when the maintainers say so) | `main`'s branch protection and its gate (`.github/workflows/main-gate.yml`); the maintainers' local `pre-commit` and `pre-push` hooks refuse `main` |
| A project's app runs only in its isolated copy (`eaos/live/isolation/sandbox.py`, `eaos/live/app/run.py`): its own database, port and scratch home; never the owner's real data | `test_sandbox` |
| A project's state is read and written only through `core/project/state.py` | `test_consistency` |
| Never one machine's path in code | `test_platforms` |
| A file or folder whose name is not valid UTF-8 is never read, renamed or changed, and never stops a check: everything else is read, it is named in red and in `facts/index.json` (`unread_names`), and the check is PARTIAL, never COMPLETE | `tests/facts/test_unreadable_names.py` |
| Fixes of EAOS are proved on trial apps and on the compatibility corpus, never on a person's real project | review |
| Nothing destructive or outward-facing (push to `main`, delete a remote branch, publish) without the maintainers | `main`'s protection; review for the rest |
| A person's own rule holds only for the work it was said for unless they pin it; pinning, unpinning, changing a rule and the commit hook are the person's (never inside a run); a rule's guard is proved on its own examples before it is kept, and a rule EAOS cannot guard is said so; a test command an assistant proposes never runs before the person approves it, and new words never keep an old guard as their protection; a rule and its contradiction are never merged; a commit is judged on what it holds (the index, deletions included), what could not be checked said so; a change is refused only for what it brought; EAOS failing to run never stops a person's commit; unpinning leaves no copy (its context lines, its hook block) and never removes a test of the project's own | `tests/analysis/test_person_rules.py`, `tests/analysis/test_person_rules_closure.py`; `tools/rules_proof.py` on the golden app |

## 4. Performance and disk

| Law | Guarded by |
|---|---|
| **What EAOS makes, EAOS removes**: a new kind of file comes with the rule that removes or bounds it, and its test | `test_artifact_contract` (every artifact one owner, one purpose, one budget); `test_code_limits` (a temporary folder removed by what made it); `test_sandbox` (a killed run's leftovers removed); `test_toolchain` (a tool no longer pinned leaves the tools home at the next install) |
| Outputs hold what people or later stages read; caches live in the runtime folder, never in the report | `test_artifact_contract` |
| A check's output and runtime have size budgets (`docs/METRICS.md`) | `tools/metrics.py` at each milestone end |
| Long runs (checks, suites, updates) run as systemd units or background jobs, one heavy job at a time | review |

## 5. Tests

- `unittest`. One test per real behaviour; a fix adds a test only when it reproduces a real failure. No sleeps where a
  condition can be awaited; no test of exact wording unless the wording is the contract.
- Guards that always stay: every test of `tests/guards/` (`test_code_limits`, `test_golden_facts`, `test_consistency`,
  `test_artifact_contract`, `test_named_paths` (every path EAOS names exists), `test_extending` (the extension guide
  stays true), `test_public_tree`, `test_platforms`, `test_packaging`, `test_journey` (the fast end-to-end proof),
  `test_public_contract` (what the CLI and MCP promise, below)), `test_layers`
  (every planted boundary defect found) and the golden trial (`tools/golden_trial.sh`).
- **The public contract**: `tools/public_contract/lock.py` locks in `tests/fixtures/contract/` every CLI command and argument, every
  MCP tool's input and read-only hints, the exit codes and the form of the answers on an empty project and on a saved one
  (`tests/fixtures/saved-project/<version>/`, frozen, kept for every later version to read). What takes from a caller is refused;
  a break the maintainers agreed to is kept with its reason and who approved it (`--accept-break`, and `CHANGELOG.md`); what
  only adds is recorded (`--record`). Words and values are not held here: the golden trial reads those, and what a writing tool
  answers on real work is held by the tests `tools/public_contract/capture.py` names, or it says it is not locked yet.
  `tools/public_contract/mutations.py` proves the lock on the real code, by hand when its design changes.
- **Detection baseline**: `tests/fixtures/baseline-app` carries planted problems, listed in
  `tests/fixtures/baseline-problems.json` with how far EAOS reaches each (card, finding, missed): a command injection,
  a secret, a dead function, a dead module, duplication, a broken screen, a sign-in, one defect per boundary of the
  layers, real data in the code, old engines, and one source per pattern (a near copy one line changed, JSON read three
  ways, a date three ways, a route repeating its guard). Its clean twin `tests/fixtures/baseline-clean` (the same app
  done right) must show no layer finding. The golden trial checks both and `tools/detection_baseline.py` refuses a
  check that reaches any problem less; `--record` after reaching more. Its numbers: `docs/METRICS.md`.
- **Compatibility corpus**: real open-source apps pinned in `tools/corpus.json` (React/Vite with and without hash
  routes, Next.js, Vue, SvelteKit, Expo web, Flask, Django, Streamlit, one behind a sign-in, one with a welcome flow, a
  static site, and three of the stacks the layers matter for, whose layer findings are recorded and judged by hand).
  `tools/corpus.py` checks each as a person would (`--path look --run-app`, no assistant; about 50 minutes, a
  background job), records whether it ran and which expected screens were pictured, and refuses when an app that
  passed now fails; `--record` writes the results. A change to running apps or finding screens never lowers its pass
  rate. Its numbers: `docs/METRICS.md`, measured at each milestone end.

## 6. Language

- **Everything programmed is English**: code, comments, file and symbol names, commit messages, technical docs.
- What EAOS shows its users is bilingual (Arabic and English) from one words catalog.

## 7. Definition of Done

**A card is done when, on its own `dev/<topic>` branch:**
1. `tools/quality.sh` passes.
2. The full suite and `tools/validate.py` pass.
3. The golden trial passes; the detection baseline finds the same problems or more, and none of the examples planted to
   stay (`must_stay`: a placeholder, the program's own configuration); the compatibility corpus does not
   get worse when the change touches running apps or finding screens.
4. It is merged into `develop` (`--no-ff`), pushed, and the branch deleted.
5. **The context is updated in the same change** (section 8).

**A milestone is done when** all its cards are done, then: one version (`pyproject.toml`, `eaos/__init__.py`, the
README badges, a `CHANGELOG.md` entry), the working copy of EAOS updated to it, `docs/METRICS.md` measured again, and
`ROADMAP.md` updated.

## 8. The context is always current

After **every** finished change, in the same change:
- `docs/ARCHITECTURE.md`: any change to the layout, layers or pipeline.
- `docs/STANDARDS.md`: any law that changed or became enforced.
- `docs/METRICS.md`: the numbers, at each milestone end.
- `CHANGELOG.md` and `ROADMAP.md`: at each milestone end.
- `AGENTS.md`: whatever it says that is no longer true.

Nothing about the work is kept in an assistant's or account's own folders (its memory, its plan files): a plan made in
any assistant's plan mode is written where the work's plan lives before the turn ends. Nothing private is published
(`AGENTS.md`, "The published tree holds only the product").

## Lock integrity and projects without screens

A changed npm lock file is checked against registry integrity metadata for each added hash before its change is kept.
An assistant never invents an integrity hash. A plain directory listing is not an application screen and cannot prove
behaviour preserved. A project with no web interface uses its own runnable checks and build as its safety net; checks
that could not run are named in the handover.
