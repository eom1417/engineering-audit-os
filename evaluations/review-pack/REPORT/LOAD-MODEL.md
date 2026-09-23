# Load Model

> A structural projection of how each entry point scales. This is not a performance test; the numbers are a stated heuristic that ranks entries and names bottlenecks. Every figure below carries the fact IDs that justify it.

## Method

multiplier=1000; cost per data_access_call, ×100 per n+1, ×1000 per unbounded query, ×10 per shared-state mutation, ×50 per missing rate limit

## Entry points ranked by load risk

| Rank | Entry | Surface | Path | Cost | Incomplete | Bottlenecks |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | / | http | `pkg/dashboard/dashboard.go` | 50000.00 | yes | no_rate_limit |
| 2 | /orders | http | `examples/cross-repo/api/server.go` | 50000.00 | yes | no_rate_limit |
| 3 | /orders/{id} | http | `examples/cross-repo/api/server.go` | 50000.00 | yes | no_rate_limit |
| 4 | baseline | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 5 | blame | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 6 | build_wheel | cli | `packaging/pypi/build_wheel.py` | 0.00 | yes | — |
| 7 | build_wheel | cli | `packaging/pypi/build_wheel.py` | 0.00 | yes | — |
| 8 | check | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 9 | cluster | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 10 | constraints | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 11 | coverage | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 12 | dashboard | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 13 | diff | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 14 | doctor | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 15 | endpoint | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 16 | gc | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 17 | history | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 18 | hook | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 19 | install | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 20 | log | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 21 | main | cli | `cmd/enola/main.go` | 0.00 | yes | — |
| 22 | plan | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 23 | providers | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 24 | server | cli | `examples/cross-repo/api/server.go` | 0.00 | yes | — |
| 25 | show | cli | `pkg/command/command.go` | 0.00 | yes | — |
| 26 | uninstall | cli | `pkg/command/command.go` | 0.00 | yes | — |

## Worst five in detail

### FACT-2dded790a385b007 — `pkg/dashboard/dashboard.go`

projected ceiling of 50000.0 cost units at 1000x traffic (data_access_calls=False, n_plus_one=False, unbounded=False, shared_state=False, rate_limited=False)

**This entry's projection is incomplete.** Unanswered questions: complexity_class, result_is_bounded

| Question | Status | Value | Evidence |
| --- | --- | --- | --- |
| data_access_calls | answered | False | FACT-2dded790a385b007 |
| repeats_per_iteration | answered | False | FACT-2dded790a385b007 |
| result_is_bounded | undetectable | None | FACT-203690207df7a08d |
| complexity_class | undetectable | None | — |
| shared_mutable_state | answered | False | FACT-2dded790a385b007 |
| outbound_calls_protected | answered | False | FACT-2dded790a385b007 |
| cached | answered | False | FACT-2dded790a385b007 |
| rate_limited | answered | False | FACT-2dded790a385b007 |

### FACT-40f0e2171ef948e4 — `examples/cross-repo/api/server.go`

projected ceiling of 50000.0 cost units at 1000x traffic (data_access_calls=False, n_plus_one=False, unbounded=False, shared_state=False, rate_limited=False)

**This entry's projection is incomplete.** Unanswered questions: complexity_class, result_is_bounded

| Question | Status | Value | Evidence |
| --- | --- | --- | --- |
| data_access_calls | answered | False | FACT-40f0e2171ef948e4 |
| repeats_per_iteration | answered | False | FACT-40f0e2171ef948e4 |
| result_is_bounded | undetectable | None | FACT-840eef306261bb74 |
| complexity_class | undetectable | None | — |
| shared_mutable_state | answered | False | FACT-40f0e2171ef948e4 |
| outbound_calls_protected | answered | False | FACT-40f0e2171ef948e4 |
| cached | answered | False | FACT-40f0e2171ef948e4 |
| rate_limited | answered | False | FACT-40f0e2171ef948e4 |

### FACT-b26941a671e075b9 — `examples/cross-repo/api/server.go`

projected ceiling of 50000.0 cost units at 1000x traffic (data_access_calls=False, n_plus_one=False, unbounded=False, shared_state=False, rate_limited=False)

**This entry's projection is incomplete.** Unanswered questions: complexity_class, result_is_bounded

| Question | Status | Value | Evidence |
| --- | --- | --- | --- |
| data_access_calls | answered | False | FACT-b26941a671e075b9 |
| repeats_per_iteration | answered | False | FACT-b26941a671e075b9 |
| result_is_bounded | undetectable | None | FACT-840eef306261bb74 |
| complexity_class | undetectable | None | — |
| shared_mutable_state | answered | False | FACT-b26941a671e075b9 |
| outbound_calls_protected | answered | False | FACT-b26941a671e075b9 |
| cached | answered | False | FACT-b26941a671e075b9 |
| rate_limited | answered | False | FACT-b26941a671e075b9 |

### FACT-d144a2fb6c5db267 — `pkg/command/command.go`

projected ceiling of 0.0 cost units at 1000x traffic (data_access_calls=False, n_plus_one=False, unbounded=False, shared_state=False, rate_limited=True)

**This entry's projection is incomplete.** Unanswered questions: complexity_class, result_is_bounded

| Question | Status | Value | Evidence |
| --- | --- | --- | --- |
| data_access_calls | answered | False | FACT-d144a2fb6c5db267 |
| repeats_per_iteration | answered | False | FACT-d144a2fb6c5db267 |
| result_is_bounded | undetectable | None | FACT-7161923731948bdd |
| complexity_class | undetectable | None | — |
| shared_mutable_state | answered | False | FACT-d144a2fb6c5db267 |
| outbound_calls_protected | answered | False | FACT-d144a2fb6c5db267 |
| cached | answered | False | FACT-d144a2fb6c5db267 |
| rate_limited | not_applicable | None | FACT-d144a2fb6c5db267 |

### FACT-2c0b2441fccfc229 — `pkg/command/command.go`

projected ceiling of 0.0 cost units at 1000x traffic (data_access_calls=False, n_plus_one=False, unbounded=False, shared_state=False, rate_limited=True)

**This entry's projection is incomplete.** Unanswered questions: complexity_class, result_is_bounded

| Question | Status | Value | Evidence |
| --- | --- | --- | --- |
| data_access_calls | answered | False | FACT-2c0b2441fccfc229 |
| repeats_per_iteration | answered | False | FACT-2c0b2441fccfc229 |
| result_is_bounded | undetectable | None | FACT-7161923731948bdd |
| complexity_class | undetectable | None | — |
| shared_mutable_state | answered | False | FACT-2c0b2441fccfc229 |
| outbound_calls_protected | answered | False | FACT-2c0b2441fccfc229 |
| cached | answered | False | FACT-2c0b2441fccfc229 |
| rate_limited | not_applicable | None | FACT-2c0b2441fccfc229 |

## What we could not measure and why

| Question | Reason | Entry points |
| --- | --- | --- |
| complexity_class | no engine performance observation on this path | 26: FACT-2dded790a385b007, FACT-40f0e2171ef948e4, FACT-b26941a671e075b9 and 23 more |
| result_is_bounded | some queries are bounded, others are not; mixed result | 26: FACT-2dded790a385b007, FACT-40f0e2171ef948e4, FACT-b26941a671e075b9 and 23 more |
| rate_limited | a cli entry point has no inbound request rate to bound | 23: FACT-d144a2fb6c5db267, FACT-2c0b2441fccfc229, FACT-4ab7f1d5c5c9fbd9 and 20 more |

Every entry point and every reason is in `load-model.json`.

