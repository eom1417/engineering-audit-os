# EAOS engineering standards

The laws every line of EAOS obeys, each beside **what guards it**: `tools/quality.sh` (about a minute), a named test of
the suite, a git hook, or "review" where no machine guards it yet (each of those is a candidate for a guard; a guard
added moves the law out of review). Numbers only ever get stricter: a change that worsens one is refused (by
`tools/quality.sh`, and by the beta update, step 5a). Where a new file goes: `docs/ARCHITECTURE.md` §4.

## 1. Code

| Law | Today (enforced) | Target | Enforced by |
|---|---|---|---|
| Module size | ≤ 400 lines, no exception in Python (M3, 0.0.75); the Studio's JavaScript under it since M4.6 (0.0.76), no exception | same, no exception | `tools/code_limits.py` (`tests/guards/test_code_limits.py`) |
| Function complexity | ≤ 10, no exception in Python (M3, 0.0.75), one count for the laws and the hotspots (`core/contracts/code_laws.py` `complexity`, a nested function counted alone); the Studio's JavaScript since M4.6, no exception; a split of its code proved by `console/tools/same.cjs` (every screen and sheet drawn the same before and after) | same, no exception | same |
| Function length | ≤ 50 lines, no exception | same | same |
| Function parameters | ≤ 5 (self, cls aside), none listed (M8.4): one whose parameters cannot be grouped (a tool mirroring its command's options, a record's constructor) says why on its `def` line, `# limits: parameters -- <why>`, as a justified pyflakes or Semgrep line does | same | same |
| One source of truth | no function written twice; jscpd clones not more than recorded | no duplicated block | `test_code_limits`, `jscpd` |
| No dead code | no unused import or variable (pyflakes); EAOS's own dead-code detector (the Python) and `knip` (the Studio) not more than recorded | no unused function, module or JS export | `test_code_limits`, `tools/quality.sh` (not `enola`: its count moves with the documents' words) |
| Repository craft | no crowded folder, vague name, family of files, document naming a path that is gone, machine detail in a published file, or assistant's context too heavy or said twice (M8.8, 0.0.80; the limits in `eaos/rules/repository-craft.json`, the same rules EAOS reads any project with) | same | `tools/quality.sh` |
| Layers | each layer imports only the layers under it, directly or not (`docs/ARCHITECTURE.md` §2; one layers contract in `pyproject.toml`, no exception) | same (reached by M3.1) | `import-linter` |

What exceeds a limit today is listed in `tools/code_limits.json` and may only shrink: after shrinking one, run
`python tools/code_limits.py --tighten`. Every engine's number (findings per engine and rule) is recorded in
`tools/quality.json` and may only go down: after it went down, run `tools/quality.sh --record`. The engines are EAOS's
own adapters (`eaos/engines/`), over what EAOS ships (without the tests, the developer tools, the built Studio and the rule examples); `knip` reads
the Studio's entries from `console/knip.json`.

**How code is written** (2026-10-13):
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
| No secret in code, logs, commits, process arguments or outputs; secrets come from the environment by name only | `gitleaks` in `tools/quality.sh`; `test_studio_api` (the token never logged or shown); `test_sandbox` (the isolated copy without env files or secrets) |
| No shell built from strings; subprocesses take argument lists | `bandit` and `semgrep` in `tools/quality.sh` (today's findings recorded, may only go down) |
| Paths from outside are resolved and kept inside their root | review |
| Studio and API: launch token, CSRF and Origin checks on every write; bound to the hosts it was started for | `test_studio_api` (token and host, CSRF and Origin, the routed origin) |
| EAOS's own code carries **no medium or high finding** from `bandit`, `semgrep`, `gitleaks`, `osv-scanner` (`osv-scanner` reads the Studio's `package-lock.json`) | `tools/quality.sh`: today's findings recorded in `tools/quality.json`, may only go down; the rest are fixed or justified in M8.4, which also adds a lock file for the Python dependencies |

## 3. Safety

| Law | Guarded by |
|---|---|
| `main` is never touched; every change goes through a `dev/<topic>` branch from `develop` (directly on `develop` only when the maintainers say so) | the git hooks `pre-commit` and `pre-push` refuse `main` |
| A project's app runs only in its isolated copy (`eaos/live/isolation/sandbox.py`, `eaos/live/app/run.py`): its own database, port and scratch home; never the owner's real data | `test_sandbox` |
| A project's state is read and written only through `core/project/state.py` | `test_consistency` |
| Never one machine's path in code | `test_platforms` |
| A simulated user (M10) acts only in the isolated copy: external services stubbed, dummy data only, within step, time and cost budgets; what needs a real service is reported as not covered | M10's tests, when built |
| Fixes of EAOS are proved on trial apps and on the compatibility corpus, never on a person's real project | review |
| Nothing destructive or outward-facing (push to `main`, delete a remote branch, publish) without the maintainers | the hooks for `main`; review for the rest |

## 4. Performance and disk

| Law | Guarded by |
|---|---|
| **What EAOS makes, EAOS removes**: a new kind of file comes with the rule that removes or bounds it, and its test | `test_artifact_contract` (every artifact one owner, one purpose, one budget); `test_code_limits` (a temporary folder removed by what made it); `test_sandbox` (a killed run's leftovers removed) |
| Outputs hold what people or later stages read; caches live in the runtime folder, never in the report | `test_artifact_contract` |
| A check's output and runtime have size budgets (`docs/METRICS.md`) | `tools/metrics.py` at each milestone end |
| Long runs (checks, suites, updates) run as systemd units or background jobs, one heavy job at a time | review |

## 5. Tests

- `unittest`. One test per real behaviour; a fix adds a test only when it reproduces a real failure. No sleeps where a
  condition can be awaited; no test of exact wording unless the wording is the contract.
- Guards that always stay (`tests/guards/`): `test_code_limits`, `test_studio_assets`, `test_golden_facts`, `test_consistency`,
  `test_artifact_contract`, `test_named_paths` (every path EAOS names exists), the golden trial (`tools/golden_trial.sh`).
- **Detection baseline** (M0.2): `tests/fixtures/baseline-app` carries eight planted problems (a command injection, a
  secret, a dead function, a dead module, duplication, a broken screen, a sign-in, a logic flaw), listed in
  `tests/fixtures/baseline-problems.json` with how far EAOS reaches each (card, finding, missed). The golden trial checks
  the app and `tools/detection_baseline.py` refuses a check that reaches any of them less; `--record` after reaching
  more. M6 planted one defect per boundary of the layers (16 problems in all) and gave the app its clean twin
  `tests/fixtures/baseline-clean` (the same app done right): the golden trial refuses any layer finding on the twin.
  Today 16 of 16 (2026-10-26; `docs/METRICS.md`).
- **Compatibility corpus** (M0.3): 15 real open-source apps pinned in `tools/corpus.json` (React/Vite with and without
  hash routes, Next.js, Vue, SvelteKit, Expo web, Flask, Django, Streamlit, one behind a sign-in, one with a welcome
  flow, a static site; and, since M6, three of the stacks the layers matter for, whose layer findings are recorded and
  judged by hand). `tools/corpus.py` checks each as a person would (`--path look --run-app`, no assistant; about
  50 minutes, a background job), records whether it ran and which expected screens were pictured, and refuses when an
  app that passed now fails; `--record` writes the results. A change to running apps or finding screens never lowers
  its pass rate. Today 15 of 15 (2026-10-26; `docs/METRICS.md` measures it at each milestone end).

## 6. Language

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
