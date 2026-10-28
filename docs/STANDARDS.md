# EAOS engineering standards

The laws every line of EAOS obeys, each beside **what guards it**: `tools/quality.sh` (about a minute), a named test of
the suite, a git hook, or "review" where no machine guards it yet (each of those is a candidate for a guard; a guard
added moves the law out of review). Numbers only ever get stricter: a change that worsens one is refused by
`tools/quality.sh`. Where a new file goes: `docs/ARCHITECTURE.md` §4.

## 1. Code

| Law | Today (enforced) | Target | Enforced by |
|---|---|---|---|
| Module size | ≤ 400 lines, no exception in Python (M3, 0.0.75); the Studio's JavaScript under it since M4.6 (0.0.76), no exception | same, no exception | `tools/code_limits.py` (`tests/guards/test_code_limits.py`) |
| Function complexity | ≤ 10, no exception in Python (M3, 0.0.75), one count for the laws and the hotspots (`core/contracts/code_laws.py` `complexity`, a nested function counted alone); the Studio's JavaScript since M4.6, no exception; a split of its code proved by `console/tools/same.cjs` (every screen and sheet drawn the same before and after) | same, no exception | same |
| Function length | ≤ 50 lines, no exception (M8.4) | same | same |
| Function parameters | ≤ 5 (self, cls aside), none listed (M8.4): one whose parameters cannot be grouped (a tool mirroring its command's options, a record's constructor) says why on its `def` line, `# limits: parameters -- <why>`, as a justified pyflakes or Semgrep line does | same | same |
| One source of truth | no function written twice | no duplicated block | `test_code_limits` |
| One source per pattern (M15) | four numbers, each recorded in `tools/quality.json` and only ever lower: (a) **near copies** of code, clusters of pairs jscpd finds renamed, one or two lines apart or 85% alike (its similarity), of 40 tokens or more; (b) **the look**: every colour, font size, spacing, radius, shadow and z-index written outside the tokens file (`console/src/css/tokens.css`), in a stylesheet, a style attribute, a JSX style or a Tailwind arbitrary value; (c) **UI patterns**: an element tree written three times or more, 80% alike, is one component; (d) **idioms**: a way of working (reading a JSON file, a date, money, a request with its loading and error, a pop-up, drag and drop, validation, paging, an endpoint's guard) written three times or more is one helper. A near copy or a screen pattern counts, and is a card, only with all three conditions (owner, 2026-10-28): its copies carry one responsibility (the rules propose it: one part of the system, changed together, or fixed apart; the judge rules), keeping them costs upkeep or risks drift, and one source is simpler with no new coupling; otherwise it is a likeness said in the report, never a card nor a breach (`analysis/assessments/one_source_evidence.py`); those conditions are signs to sort by, not proof of one contract, and today the history decides no card (a known limit, M17). A change is refused for code copied word for word (a copy kept on purpose inside jscpd's ignore markers aside); the four detectors refuse only once their refusals are measured safe, none yet, and never while under their measured bar (`analysis/repair/one_source_gate.py` `REFUSES`). The same numbers hold every project EAOS checks or builds (`core/contracts/code_laws.py` `NEAR_COPY`, `PATTERN_REPEATS`, `UI_SIMILARITY`, `LOOK`) | zero, or one reason each where the copy is on purpose | `tools/quality.sh` (`eaos/analysis/assessments/one_source.py`) |
| No dead code | no unused import or variable (pyflakes); EAOS's own dead-code detector (the Python) and `knip` (the Studio) not more than recorded | no unused function, module or JS export | `test_code_limits`, `tools/quality.sh` (not `enola`: its count moves with the documents' words) |
| Repository craft | no crowded folder, vague name, family of files, document naming a path that is gone, machine detail in a published file, or assistant's context too heavy or said twice (M8.8, 0.0.80; the limits in `eaos/rules/repository-craft.json`, the same rules EAOS reads any project with) | same | `tools/quality.sh` |
| Layers | each layer imports only the layers under it, directly or not (`docs/ARCHITECTURE.md` §2; one layers contract in `pyproject.toml`, no exception since M3.1) | same | `import-linter` in `tools/quality.sh` |

What exceeds a limit is listed in `tools/code_limits.json` and may only shrink (today the list is empty): after
shrinking one, run `python tools/code_limits.py --tighten`. Every engine's number (findings per engine and rule) is recorded in
`tools/quality.json` and may only go down: after it went down, run `tools/quality.sh --record`. The engines are EAOS's
own adapters (`eaos/engines/`), over what EAOS ships (without the tests, the developer tools, the built Studio and the
rule examples); `knip` reads the Studio's entries from `console/knip.json`, and ESLint checks the Studio's JavaScript
for undefined names and unused imports (`console/eslint.config.js`).

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
| EAOS's own code carries **no finding** from `bandit`, `semgrep`, `gitleaks`, `osv-scanner` (`osv-scanner` reads the Studio's `package-lock.json` and the Python dependencies' `uv.lock`); a justified line says why, `# nosemgrep: <rule> -- <why>` | `tools/quality.sh`: `tools/quality.json` records none since M8.4; a new finding fails |

## 3. Safety

| Law | Guarded by |
|---|---|
| `main` is never committed to; every change goes through a `dev/<topic>` branch from `develop` (directly on `develop` only when the maintainers say so) | `main`'s branch protection and its gate (`.github/workflows/main-gate.yml`); the maintainers' local `pre-commit` and `pre-push` hooks refuse `main` |
| A project's app runs only in its isolated copy (`eaos/live/isolation/sandbox.py`, `eaos/live/app/run.py`): its own database, port and scratch home; never the owner's real data | `test_sandbox` |
| A project's state is read and written only through `core/project/state.py` | `test_consistency` |
| Never one machine's path in code | `test_platforms` |
| A simulated user acts only in the isolated copy: external services stubbed, dummy data only, within step, time and cost budgets; what needs a real service is reported as not covered | `test_experience_data` (services stubbed or not covered), `test_experience_seed` (data only in the run's own database), `test_experience_actor` (budgets; the app's text kept as data) |
| Fixes of EAOS are proved on trial apps and on the compatibility corpus, never on a person's real project | review |
| Nothing destructive or outward-facing (push to `main`, delete a remote branch, publish) without the maintainers | `main`'s protection; review for the rest |

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
- Guards that always stay: every test of `tests/guards/` (`test_code_limits`, `test_studio_assets`, `test_golden_facts`,
  `test_consistency`, `test_artifact_contract`, `test_named_paths` (every path EAOS names exists), `test_public_tree`,
  `test_platforms`, `test_single_source`, `test_packaging`, `test_journey` (the fast end-to-end proof)), `test_layers`
  (every planted boundary defect found) and the golden trial (`tools/golden_trial.sh`).
- **Detection baseline** (M0.2): `tests/fixtures/baseline-app` carries 35 planted problems, listed in
  `tests/fixtures/baseline-problems.json` with how far EAOS reaches each (card, finding, missed): eight from M0.2 (a
  command injection, a secret, a dead function, a dead module, duplication, a broken screen, a sign-in, a logic flaw)
  and, since M6, one defect per boundary of the layers; since M12-M14 real data in the code, old engines and how the
  data is saved; since M15 one source per pattern (a near copy one line changed, JSON read three ways, a pop-up on three
  screens, a colour a shade off, sizes off the scale, a date three ways, a route repeating its guard). Its clean twin `tests/fixtures/baseline-clean` (the same app
  done right) must show no layer finding. The golden trial checks both and `tools/detection_baseline.py` refuses a
  check that reaches any problem less; `--record` after reaching more. Today 16 of 16 (0.0.83; `docs/METRICS.md`).
- **Compatibility corpus** (M0.3): 15 real open-source apps pinned in `tools/corpus.json` (React/Vite with and without
  hash routes, Next.js, Vue, SvelteKit, Expo web, Flask, Django, Streamlit, one behind a sign-in, one with a welcome
  flow, a static site; and, since M6, three of the stacks the layers matter for, whose layer findings are recorded and
  judged by hand). `tools/corpus.py` checks each as a person would (`--path look --run-app`, no assistant; about
  50 minutes, a background job), records whether it ran and which expected screens were pictured, and refuses when an
  app that passed now fails; `--record` writes the results. A change to running apps or finding screens never lowers
  its pass rate. Today 15 of 15 (0.0.83; `docs/METRICS.md` measures it at each milestone end).

## 6. Language

- **Everything programmed is English**: code, comments, file and symbol names, commit messages, technical docs.
- What EAOS shows its users is bilingual (Arabic and English) from one words catalog.

## 7. Definition of Done

**A card is done when, on its own `dev/<topic>` branch:**
1. `tools/quality.sh` passes.
2. The full suite and `tools/validate.py` pass; the Studio is built when `console/` changed.
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
