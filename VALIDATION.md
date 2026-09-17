# Release validation — 2.1.0

Date: 2026-09-17. Agent-led workflow and evidence-backed development planning.

- 62 tests passed (`python -m unittest discover -s tests`), including 22 new discovery/workflow tests. Existing 40 tests remain passing.
- New checks exercise the read-only single entry point, stage progression, path-specific review evidence, unsupported parsing, explicit parse failures, bounded source-range capture and tamper detection, missing invariants, unresolved findings, task dependency cycles/order, hypothesis/remediation separation, false repair closure, stale source rejection, draft preservation and partial/full report contracts.
- Registry and canonical packaged copies validated: 27 modules, 165 controls, 41 source records. Source/control knowledge was not inflated to simulate increased capability.
- Wheel built with `pip wheel . --no-deps --no-build-isolation`, installed with `--no-index` into a separate venv and exercised outside the source repository: audit → observe → next → partial report. Packaged workflow manual and plan schema confirmed available. Target bytes unchanged; partial report returned exit 2 as specified.
- Environment tested: Linux, Python 3.12. Python 3.10+ is declared, not exhaustively certified across all supported interpreter/platform combinations.
- Python AST gives syntactic observations; JS/TS uses explicitly hypothetical lexical hints; other languages remain visible for agent review. No automatic domain ownership, semantic findings, deployment reconstruction or architecture graph inference is claimed.
- End-to-end ready-plan tests use synthetic records and source fixtures. They prove record contracts, not independent architectural judgment or production readiness.
- Product-level blind repository evaluation and real-project remediation are NOT YET DEMONSTRATED. See ACCEPTANCE.md for the acceptance protocol and the exact boundary of current assurance.
- No model-provider orchestration, cloud adapter, autonomous repair runtime or automatic cross-revision evidence migration is implemented.

Upgrade: start a fresh 2.1 run. Preserve prior runs as history; never relabel old evidence as current without revalidation.

---

## Historical release evidence

# Release validation — 2.0.0

Date: 2026-09-17. Architecture, Structure, Maintainability & Evolvability edition.

- Registry: 27 modules, 165 controls, 41 source records including three illustrative seed videos. IDs, references and packaged canonical copies validated.
- `python -m unittest discover -s tests -v`: 40 tests passed after the architectural module split. Checks include model references, typed dependency cycles, reverse impact direction, explicit depth frontier, hypothesis handling, contract consumers, context budgets, stale models, scenario/evidence completion gates, path boundaries and the original record checks.
- Internal boundary check: architecture graph module imports only collections/pathlib; CLI, source IO and audit gates are separate modules. This is a targeted dependency fitness test, not a claim that all design decisions are optimal.
- Wheel built locally and installed in an isolated environment; CLI entry point and registry exercised outside the repository. Runtime has no third-party dependencies. Python 3.10+ declared; execution tested in the available Linux/Python environment, not an all-platform certification.
- Complete-record and graph tests use explicitly synthetic fixtures. They verify algorithms/contracts and prevent selected false completion modes; they do not prove accuracy of a real product audit.
- All three auto-generated video transcripts were read fully. Continuous visual review and independent source-repository verification remain incomplete.
- No production repository calibration, cloud adapter, universal AST extractor, model-provider orchestration or live security/load test is claimed.

Upgrade: create a fresh 2.0 run. Do not manually bump old run versions or reuse COMPLETE without rebuilding evidence/model/coverage. Version 1.0 remains historical; 2.0 uses architecture as the default profile.
