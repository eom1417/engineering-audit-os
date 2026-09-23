# Sustainability dashboard

> Six measurable properties. Values come from deterministic facts; targets from the engagement contract. The gap is the distance to the target; a proposed move closes it.

## Indicators

| Indicator | Current | Target | Gap |
| --- | --- | --- | --- |
| P1 Single source | 0.111 | 0.0 | 0.111 |
| P2 Minimal path | not measured | 0.0 | — |
| P3 Single owner per field | 0 | 0 | 0 |
| P4 Honest boundaries | 0 | 0 | 0 |
| P5 Verifiable paths | 0.08 | 0.0 | 0.08 |
| P6 Understandable units | 242 | 0 | 242 |

## Proposed moves

### Move 1: canonicalize
- indicator: single_source
- cluster: 1ed6eb31a6e326f1
- sites:
  - internal/engine/detect_test.go:132 .method_declaration
  - internal/explainers/complexity/complexity.go:37 .method_declaration
  - internal/explainers/constraints/constraints.go:178 .method_declaration
  - internal/explainers/coverage/coverage.go:102 .method_declaration
  - internal/explainers/crossrepo/crossrepo.go:23 .method_declaration
  - internal/explainers/cycles/cycles.go:40 .method_declaration
  - … 53 more in `sustainability.json`
- predicted single_source: 0.111
- falsifier: Demonstrate the two occurrences compute a different rule (different units, ranges, or business meanings).

### Move 2: canonicalize
- indicator: single_source
- cluster: 60b811cb8c6c83e3
- sites:
  - internal/explainers/complexity/complexity.go:33 .function_declaration
  - internal/explainers/constraints/constraints.go:174 .function_declaration
  - internal/explainers/coverage/coverage.go:24 .function_declaration
  - internal/explainers/crossrepo/crossrepo.go:19 .function_declaration
  - internal/explainers/cycles/cycles.go:36 .function_declaration
  - internal/explainers/deadmethods/deadmethods.go:47 .function_declaration
  - … 53 more in `sustainability.json`
- predicted single_source: 0.111
- falsifier: Demonstrate the two occurrences compute a different rule (different units, ranges, or business meanings).

### Move 3: canonicalize
- indicator: single_source
- cluster: 1e84767c4e77eaf4
- sites:
  - internal/extractors/rustextractor/rust_ast_test.go:225 .function_declaration
  - internal/extractors/rustextractor/rust_ast_test.go:241 .function_declaration
  - internal/extractors/rustextractor/rust_ast_test.go:257 .function_declaration
  - internal/extractors/rustextractor/rust_ast_test.go:346 .function_declaration
  - internal/extractors/rustextractor/rust_ast_test.go:365 .function_declaration
  - internal/extractors/rustextractor/rust_ast_test.go:384 .function_declaration
  - … 19 more in `sustainability.json`
- predicted single_source: 0.111
- falsifier: Demonstrate the two occurrences compute a different rule (different units, ranges, or business meanings).

### Move 4: canonicalize
- indicator: single_source
- cluster: 1a831c5a7e381b04
- sites:
  - internal/config/config.go:779 .function_declaration
  - internal/engine/output_dir_test.go:96 .function_declaration
  - internal/extractors/cppextractor/complexity_test.go:47 .function_declaration
  - internal/extractors/cppextractor/cppmacro_test.go:23 .function_declaration
  - internal/extractors/dotnetextractor/testrefs_test.go:34 .function_declaration
  - internal/extractors/goextractor/complexity_test.go:47 .function_declaration
  - … 18 more in `sustainability.json`
- predicted single_source: 0.111
- falsifier: Demonstrate the two occurrences compute a different rule (different units, ranges, or business meanings).

### Move 5: canonicalize
- indicator: single_source
- cluster: 3ddb0a9b89784830
- sites:
  - internal/linkers/binders/clientseam/clientseam.go:47 .method_declaration
  - internal/linkers/binders/emberresolver/emberresolver.go:44 .method_declaration
  - internal/linkers/binders/frameworkroots/frameworkroots.go:145 .method_declaration
  - internal/linkers/binders/grpcclientfqn/grpcclientfqn.go:49 .method_declaration
  - internal/linkers/binders/grpcimpl/grpcimpl.go:77 .method_declaration
  - internal/linkers/binders/httphandler/httphandler.go:66 .method_declaration
  - … 11 more in `sustainability.json`
- predicted single_source: 0.111
- falsifier: Demonstrate the two occurrences compute a different rule (different units, ranges, or business meanings).

### Move 6: canonicalize
- indicator: single_source
- cluster: 0aae4afd1bf6080b
- sites:
  - internal/explainers/deadmethods/deadmethods.go:349 .function_declaration
  - internal/explainers/queryloops/queryloops.go:649 .function_declaration
  - internal/extractors/detectnames/detectnames.go:97 .function_declaration
  - internal/extractors/dotnetextractor/razor.go:262 .function_declaration
  - internal/extractors/goextractor/grpcclient.go:324 .function_declaration
  - internal/extractors/goextractor/grpcclient.go:334 .function_declaration
  - … 10 more in `sustainability.json`
- predicted single_source: 0.111
- falsifier: Demonstrate the two occurrences compute a different rule (different units, ranges, or business meanings).

Showing 6 of 530 moves; the rest are in `sustainability.json`.

## Details

The full measurement behind every indicator — inputs, thresholds and sites — is in `sustainability.json`.

- **P1 Single source** — duplicates=1170, measured=True, symbols=10495
- **P2 Minimal path** — files_analysed=1, files_blocked=1020, measured=False, reason=redundancy detection analysed 1 of 1021 file(s) (0.1%), below the declared floor of 20%; this is a statement about coverage, not a clean result
- **P3 Single owner per field** — no detail
- **P4 Honest boundaries** — cycles=0, measured=True, policy_declared=False, policy_violations=0
- **P5 Verifiable paths** — flows=25, measured=True, stopping_at_first_boundary=2
- **P6 Understandable units** — oversized=242

## Limits

- Every indicator is a function of structural facts only; runtime behaviour is out of scope.
- Targets are taken from the engagement contract or the declared policy; no target is invented.
- A transformation is a proposal; its predicted delta is computed from the structural reduction, not from runtime measurements.
- A falsifier is a hint at the kind of evidence that would reject the move; it is not a guard.
