# Risk register

> priority = (reach_normalised × confidence × origin) ÷ cost
> A declared ordering with visible inputs, not a severity classification.

| # | Priority | Claim | Reach | Cost | Origin | Disposition |
|---|---|---|---|---|---|---|
| CLM-007 | 0.2333 | 421 functions perform the same ordered sequence of calls (cmd/enola/flags_documented_test.go:None… | 51 | large | test_and_source | investigate |
| CLM-004 | 0.0961 | 236 functions perform the same ordered sequence of calls (internal/config/output_dir_test.go:None… | 21 | large | test_and_source | investigate |
| CLM-001 | 0.0784 | packaging/pypi/build_wheel.py: ينادي خدمة خارجية بلا مهلة أو إعادة محاولة | 8 | medium | source | investigate |
| CLM-002 | 0.0784 | packaging/pypi/build_wheel.py: ينادي خدمة خارجية بلا مهلة أو إعادة محاولة | 8 | medium | source | investigate |
| CLM-006 | 0.0458 | 328 functions perform the same ordered sequence of calls (internal/clientspec/clientspec.go:None… | 10 | large | test_and_source | investigate |
| CLM-003 | 0.0 | 149 functions perform the same ordered sequence of calls (cmd/enola/main_test.go:None… | 0 | large | test_and_source | investigate |
| CLM-005 | 0.0 | 270 functions perform the same ordered sequence of calls (internal/engine/conceptedgematrix_test.go:None… | 0 | large | test | investigate |
| CLM-008 | 0.0 | handleCall in internal/extractors/rubyextractor/routes_ast.go carries 109 branches over 541 lines, in a file… | 0 | large | source | investigate |
| CLM-009 | 0.0 | registerTools in internal/server/server.go carries 189 branches over 1117 lines, in a file ranked 12 for… | 0 | large | source | investigate |
| CLM-010 | 0.0 | walkForCalls in internal/extractors/rubyextractor/ruby_ast.go carries 102 branches over 380 lines, in a file… | 0 | large | source | investigate |

## How to read the priority

- confidence: CONFIRMED 1.0 · LIKELY 0.7 · HYPOTHESIS 0.4
- cost: lines of the code the change would touch: small 1 · medium 2 · large 3
- origin: product code 1.0 · mixed 0.7 · test code 0.3
- reach: dependents + flows + entry-point exposure
