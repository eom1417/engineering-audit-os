# Release validation — 1.0.0

Date: 2026-09-17.

- Framework registry: 26 modules, 151 controls, 37 source records (including the two seed videos). No duplicate control IDs, unresolved source references or mismatched packaged copies detected.
- `python -m unittest discover -s tests -v`: 22 tests passed. Tests cover false completion, unresolved gateway knowledge, evidence requirements, required applicability, stale source/record detection, bounded packets, sensitive filenames, traversal/symlinks, read-only target behavior, and record consistency.
- Local wheel built with `pip wheel --no-deps --no-build-isolation .` and installed into an isolated virtual environment. Installed entry point and packaged controls were exercised from outside the repository.
- The complete-record test uses explicitly synthetic records. It validates record contracts; it does not demonstrate the accuracy or completeness of a real software audit.
- No live cloud account, original video repository, production load test, penetration test or multi-project field calibration was performed.
- Both video transcripts were read in full. Continuous visual review and independent verification of on-screen performance tables remain incomplete.
- Runtime CLI has no third-party dependencies. The installer/build uses setuptools; package publication and hosted Git repository are not part of this release.

Remaining integration work, if desired: provider-specific read-only cloud adapters, AST/call-graph adapters, actual tokenizer budgets and model-provider orchestration. These are explicitly not implemented features of this release.
