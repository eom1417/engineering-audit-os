# Risk register

> priority = (reach_normalised × confidence × origin) ÷ cost
> A declared ordering with visible inputs, not a severity classification.

| # | Priority | Claim | Reach | Cost | Origin | Disposition |
|---|---|---|---|---|---|---|
| CLM-271 | 0.5 | 2 symbols share the same structure up to identifier names (internal/facts/accessors.go:81… | 638 | medium | source | investigate |
| CLM-012 | 0.3265 | 16 symbols share the same structure up to identifier names (internal/explainers/deadmethods/deadmethods.go:349… | 625 | large | source | investigate |
| CLM-569 | 0.1818 | 328 functions perform the same ordered sequence of calls (internal/clientspec/clientspec.go:None… | 497 | large | test_and_source | investigate |
| CLM-477 | 0.1348 | 4 symbols share the same structure up to identifier names (internal/factpath/factpath.go:46… | 86 | small | source | investigate |
| CLM-531 | 0.0729 | Flow FLOW-004 (cli baseline) stops at 4 unresolvable calls | 93 | medium | source | investigate |
| CLM-532 | 0.0729 | Flow FLOW-005 (cli blame) stops at 3 unresolvable calls | 93 | medium | source | investigate |
| CLM-533 | 0.0729 | Flow FLOW-008 (cli check) stops at 3 unresolvable calls | 93 | medium | source | investigate |
| CLM-544 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-545 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-546 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-547 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-548 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-549 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-550 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-551 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-552 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-553 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-554 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-555 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-556 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-557 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-558 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-559 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-560 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-561 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-562 | 0.0729 | pkg/command/command.go: calls an external service with no timeout or retry — load blocker… | 93 | medium | source | investigate |
| CLM-054 | 0.0721 | 2 symbols share the same structure up to identifier names (internal/explainers/constraints/basis.go:36… | 46 | small | source | investigate |
| CLM-082 | 0.0627 | 2 symbols share the same structure up to identifier names (internal/explainers/queryloops/queryloops.go:329… | 120 | large | source | investigate |
| CLM-450 | 0.0543 | 3 symbols share the same structure up to identifier names (internal/linkers/vocab/overlay.go:44… | 104 | large | source | investigate |
| CLM-004 | 0.053 | 11 symbols share the same structure up to identifier names (internal/extractors/goextractor/storage.go:129… | 145 | large | test_and_source | investigate |

Showing 30 of 573; the rest stays in the fact records.

## How to read the priority

- confidence: CONFIRMED 1.0 · LIKELY 0.7 · HYPOTHESIS 0.4
- cost: lines of the code the change would touch: small 1 · medium 2 · large 3
- origin: product code 1.0 · mixed 0.7 · test code 0.3
- reach: dependents + flows + entry-point exposure
