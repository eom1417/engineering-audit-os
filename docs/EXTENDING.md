# Extending EAOS

**Adding anything starts here.** One recipe per kind of addition: the files to read (five at most), the files to touch
in order, the test that proves it, the gates, and its row in `docs/METRICS.md` "The cost of adding a tool". Read the
recipe, not the whole system. Where a file goes in general, and the layers' order, is `docs/ARCHITECTURE.md` §1, §2 and
§4; the laws are `docs/STANDARDS.md`; neither is repeated here. `tests/guards/test_extending.py` keeps every path below
true.

**Gates of every recipe:** the affected tests while working, `tools/quality.sh` (about a minute), then the full verify
once before merging (`AGENTS.md` "The flow"). **Its cost:** a row in the newest "The cost of adding a tool" table of
`docs/METRICS.md`: the files, the lines, whether a core layer had to change (a core change is a defect of EAOS's
structure, fixed in the same milestone), the time.

## The map (before a change that touches code you have not read)

`python tools/dev_paths.py map` builds GitNexus's map of EAOS outside the repository (about 35 s, no token) and copies its
area skills into `.claude/skills` (this command makes it, git ignores it): `gitnexus-area-<area>` names an area's key files and entry points,
about a thousand tokens each; read the one of the area you change. Who calls a symbol and what a change breaks:
`python tools/dev_paths.py map-where` prints the command; write its answer to a file (`> /tmp/impact.json`), since a
piped answer stops at 64 KB, and prefer `impact` or `cypher` to `context`, which lists only the first callers.

## Recipes

### An engine (an external analyzer)
- **Read:** `eaos/engines/code/squawk.py` (the last one added, M14.3), `eaos/engines/contract.py`, `eaos/engines/run.py`,
  `eaos/data/toolchain.json` (Squawk's entry and `jobs`), `tests/engines/test_engine_contracts.py`.
- **Touch, in order:** (1) the registry entry in `eaos/data/toolchain.json`: pinned version, sha256 per platform
  (`python tools/platform_assets.py` fills them), `check: engines`, `applies`, and its `jobs`: the job it is primary
  for, or the part it alone gives beside the primary (`tests/core/test_tool_jobs.py`); (2) the adapter
  `eaos/engines/<security|code|api>/<name>.py` with `NAME`, `PINNED`, `capabilities()` and `analyze()`, its findings in
  the shared kinds of `contract.py`; (3) its line in `_BY_NAME` of `eaos/engines/run.py`; (4) a pinned sample of its real
  output, `tests/contracts/<name>.json`; (5) its licence in `upstreams/licenses/<name>-LICENSE` and its row in
  `THIRD_PARTY_NOTICES.md`. A tool that writes SARIF needs no adapter: its entry declares `engine` and its rules map
  in `eaos/rules/sarif-rules.json` (`eaos/engines/sarif.py`).
- **Test:** `tests/engines/test_engine_contracts.py` and `tests/engines/test_adapters.py`; then the planted case it
  finds in the detection baseline (the recipe below).
- **Before adding:** it earns its place by the five criteria of the maintainers' plan (unique on the planted cases and
  on EAOS, no tokens, under 60 s and 500 MB on a thousand files, safe to pin, precise). Any licence that allows EAOS's
  free, non-commercial use is allowed in full, a non-commercial or non-OSI one included; choose by what the tool gives,
  fewest tools first. A tool another already does better is not added; one that stops earning its place is removed
  (its entry, adapter, sample, licence and row; `toolchain.installers.retire` frees its disk).

### An ast-grep rule
- **Read:** `eaos/rules/ast-grep/rules/saving.yml` (M14.3), its examples `eaos/rules/ast-grep/rule-tests/saving-test.yml`,
  `eaos/engines/code/ast_grep.py`.
- **Touch:** the rule in `eaos/rules/ast-grep/rules/<family>.yml` (a `kind` in its metadata makes it a finding,
  otherwise a record later stages read); its valid and invalid examples in `eaos/rules/ast-grep/rule-tests/`.
- **Test:** `tests/engines/test_code_engines.py` (every rule has its examples, proved by `ast-grep test`); the reader
  of its records, if any.

### A detector and its card
- **Read:** `eaos/analysis/assessments/data_keeping.py` and `eaos/analysis/claims/from_keeping.py` (M14),
  `eaos/analysis/claims/ledger.py`, `eaos/analysis/claims/probe_queries.py`, `eaos/data/detector-verdicts.json`.
- **Touch, in order:** (1) the fact: a `facts/<folder>/` module, an engine, a rule or a live stage that records what is
  there; (2) the assessment `eaos/analysis/assessments/<kind>.py` that sorts it on evidence; (3) the claims module
  `eaos/analysis/claims/from_<kind>.py`, joined in `probe_queries.py`; (4) the words: the kind in `eaos/data/words.json`
  `kinds`, the card's pattern in `eaos/analysis/presentation/model.py` `PATTERNS`; (5) the remediation in
  `eaos/analysis/repair/remediation.py`; (6) the check paths that run it, `eaos/core/contracts/check_paths.py`;
  (7) its planted case and an example that must stay (the recipe below); (8) a detector not yet measured precise stays
  hidden in `eaos/data/detector-verdicts.json` with its reason.
- **Test:** `tests/analysis/test_<kind>.py` (one behaviour each), then the detection baseline.

### A codemod family
- **Read:** `eaos/analysis/repair/codemods.py` (`MECHANICAL`, `card_for`), `eaos/templates/codemods/remove-declaration.cjs`,
  `eaos/journeys/fix/execute.py` (`run_codemod`).
- **Touch:** the transform in `eaos/templates/codemods/<name>.cjs` (jscodeshift); its card in `codemods.py`; the pattern
  in `MECHANICAL` when no assistant is needed.
- **Test:** `tests/analysis/test_codemods.py`: the change lands on the copy only and leaves what it should not touch.

### A stage or a loop, or a change of the stages' order
- **Read:** `eaos/pipeline/stages.py`, `eaos/pipeline/loops.py`, `eaos/pipeline/runners/keeping.py` (the last stage
  added, M14), `eaos/core/contracts/artifacts.py`.
- **Touch, in order:** (1) the `Stage(...)` declaration: what it `requires`, `reads`, `produces`, its necessity and its
  `absent_when`; (2) its loop in `loops.py`; (3) its runner in `eaos/pipeline/runners/` and its line in
  `by_rules.RUNNERS`; (4) its words in `eaos/data/words.json` `stages` (title, does, doing); (5) its artifact in
  `artifacts.py`; (6) the check paths that run it. Changing the order is a change of `requires`/`reads` only; then
  verify the paths and the golden trial (a stage that reads another must wait for it).
- **Test:** `tests/pipeline/test_check_paths.py`, `tests/pipeline/test_run.py`, and a test of the runner writing into a
  report with none of its folders yet.

### A check path
- **Read:** `eaos/core/contracts/check_paths.py`, `eaos/pipeline/path_choice.py`, `docs/ARCHITECTURE.md` §5.
- **Touch:** the path in `check_paths.py` (its stages, kinds, engines, patterns); its words in `eaos/data/words.json`
  `paths`; its row in `docs/ARCHITECTURE.md` §5.
- **Test:** `tests/pipeline/test_check_paths.py`.

### An AI node or a model tier
- **Read:** `eaos/ai/nodes/pipeline.py` (`NODES`), `eaos/ai/nodes/framework.py`, `eaos/ai/nodes/triage.py` (a node),
  `eaos/ai/assistant/tiers.py` (`STAGES`).
- **Touch:** the node module in `eaos/ai/nodes/`, its `Node(...)` in `NODES` (what it consumes and produces), its tier in
  `tiers.py` `STAGES`. The rules decide first; a node judges only what they leave in doubt, and its cost is said.
- **Test:** `tests/ai/test_ai_nodes.py`, `tests/ai/test_tiers.py`, with a fake assistant (no token).

### An interface: a CLI command, an MCP tool, a Studio action
- **Read:** `eaos/interfaces/rules.py` (the last door added to all three, M16), `eaos/interfaces/command_groups.py`,
  `eaos/interfaces/mcp_server/server.py`, `eaos/interfaces/mcp_server/studio_parity.py`, `docs/studio-actions.json`.
- **Touch, in order:** (1) the journey it calls, in `eaos/journeys/` (a door holds no logic); (2) the command in
  `command_groups.py`; (3) the MCP tool in `eaos/interfaces/mcp_server/`; (4) the Studio action in
  `docs/studio-actions.json` and `eaos/interfaces/studio_actions/`; (5) its row in `studio_parity.PARITY`, or in
  `NO_TOOL` with its reason; (6) `docs/MCP.md` when a tool is added; (7) `python tools/public_contract/lock.py --record`, and a writing
  tool's row in `tools/public_contract/capture.py` (`EMPTY_WRITING` or `WRITING_ELSEWHERE`).
- **Test:** `tests/interfaces/test_parity.py`, `tests/guards/test_public_contract.py`, and the door's own test in `tests/interfaces/`.

### A Studio screen
- **Read:** `console/README.md`, `console/src/places/status/index.js` (a place), `console/src/core/router.js`.
- **Touch:** the place `console/src/places/<place>/index.js`; its words in `console/src/words/`; then `npm run build`
  in `console/` (commit `eaos/data/studio`).
- **Test:** `tests/guards/test_studio_assets.py` (built from today's source, within its budgets), ESLint through
  `tools/quality.sh`; a split proved by `console/tools/same.cjs`.

### A kind of value or part of the look
- **Read:** `eaos/data/design-catalog.json`, `eaos/analysis/design/inventory.py`, `eaos/templates/screens/look.cjs`.
- **Touch:** the kind in the catalogue (its words and properties; a part's role, in `roleOf` of `look.cjs` when no tag or ARIA role tells it). A value the codemod names: `eaos/analysis/design/tokens_codemod.py`. A card: `eaos/analysis/design/findings.py`, hidden until judged.
- **Test:** `tests/analysis/test_design_inventory.py`, `tests/analysis/test_tokens_codemod.py`, `tests/live/test_look_oracle.py`; then `tools/judging/tokens_proof.py` on the lab.

### A word
- **Read:** `eaos/data/words.json`, `eaos/core/language/words.py`.
- **Touch:** every form beside the others in `words.json` (Arabic and English); a sentence composed with values stays
  beside its code instead. The Studio's build makes its keys from `words.json`: rebuild it.
- **Test:** `tests/core/test_bilingual.py`, `tests/guards/test_studio_assets.py`.

### A planted case or a corpus app
- **Read:** `tests/fixtures/baseline-problems.json`, `tools/detection_baseline.py`, `tools/golden_trial.sh`,
  `tools/corpus.json`.
- **Touch:** the planted code in `tests/fixtures/baseline-app/` and its row in `baseline-problems.json` (its place,
  line and the words that name it); an example that must stay in `must_stay`; the same app done right stays clean in
  `tests/fixtures/baseline-clean/`. A corpus app: its pinned commit and screens in `tools/corpus.json`.
- **Test:** `tools/golden_trial.sh` (the baseline and its clean twin); `tools/corpus.py <app>` for a corpus app.

### A milestone
- **Read:** `ROADMAP.md`, `CHANGELOG.md`, `docs/METRICS.md`.
- **Touch:** at its end, one version (`pyproject.toml`, `eaos/__init__.py`, the badges of both READMEs), its
  `CHANGELOG.md` entry (why, from the real incident, then what changed), `docs/METRICS.md` measured again
  (`tools/metrics.py`), `ROADMAP.md`.
- **Test:** the full verify and the golden trial, once.
