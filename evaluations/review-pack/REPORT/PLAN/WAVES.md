# Execution waves

> Two tasks touching the same file never share a wave; an investigation precedes the change it informs.

- entry: Required predecessor decisions accepted; file conflicts serialized.
- exit: Record check outcomes or an evidenced investigation decision.

## Wave 1

| # | Task | Kind | Priority |
|---|---|---|---|
| TASK-001 | 421 functions perform the same ordered sequence of calls (cmd/enola/flags_documented_test. | investigate | 0.2333 |
| TASK-003 | packaging/pypi/build_wheel.py: ينادي خدمة خارجية بلا مهلة أو إعادة محاولة — load blocker ( | investigate | 0.0784 |
| TASK-007 | handleCall in internal/extractors/rubyextractor/routes_ast.go carries 109 branches over 54 | investigate | 0.0 |
| TASK-008 | registerTools in internal/server/server.go carries 189 branches over 1117 lines, in a file | investigate | 0.0 |
| TASK-009 | walkForCalls in internal/extractors/rubyextractor/ruby_ast.go carries 102 branches over 38 | investigate | 0.0 |

## Wave 2

| # | Task | Kind | Priority |
|---|---|---|---|
| TASK-002 | 236 functions perform the same ordered sequence of calls (internal/config/output_dir_test. | investigate | 0.0961 |
| TASK-004 | packaging/pypi/build_wheel.py: ينادي خدمة خارجية بلا مهلة أو إعادة محاولة — load blocker ( | investigate | 0.0784 |

## Wave 3

| # | Task | Kind | Priority |
|---|---|---|---|
| TASK-005 | 328 functions perform the same ordered sequence of calls (internal/clientspec/clientspec.g | investigate | 0.0458 |

## Wave 4

| # | Task | Kind | Priority |
|---|---|---|---|
| TASK-006 | 149 functions perform the same ordered sequence of calls (cmd/enola/main_test.go:None, int | investigate | 0.0 |
