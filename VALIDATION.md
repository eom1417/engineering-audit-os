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
