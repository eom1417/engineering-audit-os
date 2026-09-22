# Load Model

> A structural projection of how each entry point scales. This is not a performance test; the numbers are a stated heuristic that ranks entries and names bottlenecks. Every figure below carries the fact IDs that justify it.

## Method

multiplier=1000; cost per data_access_call, ×100 per n+1, ×1000 per unbounded query, ×10 per shared-state mutation, ×50 per missing rate limit

## Entry points ranked by load risk

| Rank | Entry | Path | Cost | Incomplete | Bottlenecks |
| --- | --- | --- | --- | --- | --- |
| 1 | FACT-4ab7f1d5c5c9fbd9 | `packaging/pypi/build_wheel.py` | 0.00 | yes | — |
| 2 | FACT-de174e9b06853330 | `packaging/pypi/build_wheel.py` | 0.00 | yes | — |
| 3 | FACT-d3f797d291f88fc5 | `pkg/dashboard/dashboard.go` | 0.00 | yes | — |
| 4 | FACT-15de3868f6371e28 | `internal/engine/cache.go` | 0.00 | yes | — |
| 5 | FACT-62eceba39cb16dfb | `examples/cross-repo/api/server.go` | 0.00 | yes | — |
| 6 | FACT-6295ade1bd16b6e2 | `examples/cross-repo/api/server.go` | 0.00 | yes | — |
| 7 | FACT-79ccf4edd176820a | `internal/extractors/goextractor/routes.go` | 0.00 | yes | — |
| 8 | FACT-74a86ebe751d1835 | `internal/extractors/goextractor/routes.go` | 0.00 | yes | — |
| 9 | FACT-0f003d5d080ed527 | `internal/extractors/goextractor/routes.go` | 0.00 | yes | — |
| 10 | FACT-69a06621f788fe34 | `internal/extractors/goextractor/routes.go` | 0.00 | yes | — |
| 11 | FACT-9f1dfd15208f4ef8 | `internal/engine/cache.go` | 0.00 | yes | — |
| 12 | FACT-df07f86d5636ae00 | `internal/extractors/goextractor/routes.go` | 0.00 | yes | — |
| 13 | FACT-365733f62015fda1 | `internal/extractors/goextractor/routes.go` | 0.00 | yes | — |

## Worst five in detail

### FACT-4ab7f1d5c5c9fbd9 — `packaging/pypi/build_wheel.py`

projected ceiling of 0.0 cost units at 1000x traffic (data_access_calls=0, n_plus_one=?, unbounded=False, shared_state=False, rate_limited=True)

**This entry's projection is incomplete.** Unanswered questions: cached, complexity_class, data_access_calls, rate_limited, repeats_per_iteration, result_is_bounded, shared_mutable_state

| Question | Status | Value | Evidence |
| --- | --- | --- | --- |
| data_access_calls | undetectable | None | — |
| repeats_per_iteration | undetectable | None | — |
| result_is_bounded | undetectable | None | FACT-d550f2524311b59a |
| complexity_class | undetectable | None | — |
| shared_mutable_state | undetectable | None | — |
| outbound_calls_protected | answered | timeout=False, retry=False, circuit_breaker=False | FACT-d5a64c417a3710df |
| cached | undetectable | None | — |
| rate_limited | undetectable | None | — |

### FACT-de174e9b06853330 — `packaging/pypi/build_wheel.py`

projected ceiling of 0.0 cost units at 1000x traffic (data_access_calls=0, n_plus_one=?, unbounded=False, shared_state=False, rate_limited=True)

**This entry's projection is incomplete.** Unanswered questions: cached, complexity_class, data_access_calls, rate_limited, repeats_per_iteration, result_is_bounded, shared_mutable_state

| Question | Status | Value | Evidence |
| --- | --- | --- | --- |
| data_access_calls | undetectable | None | — |
| repeats_per_iteration | undetectable | None | — |
| result_is_bounded | undetectable | None | FACT-d550f2524311b59a |
| complexity_class | undetectable | None | — |
| shared_mutable_state | undetectable | None | — |
| outbound_calls_protected | answered | timeout=False, retry=False, circuit_breaker=False | FACT-d5a64c417a3710df |
| cached | undetectable | None | — |
| rate_limited | undetectable | None | — |

### FACT-d3f797d291f88fc5 — `pkg/dashboard/dashboard.go`

projected ceiling of 0.0 cost units at 1000x traffic (data_access_calls=0, n_plus_one=?, unbounded=False, shared_state=False, rate_limited=True)

**This entry's projection is incomplete.** Unanswered questions: cached, complexity_class, data_access_calls, outbound_calls_protected, rate_limited, repeats_per_iteration, result_is_bounded, shared_mutable_state

| Question | Status | Value | Evidence |
| --- | --- | --- | --- |
| data_access_calls | undetectable | None | — |
| repeats_per_iteration | undetectable | None | — |
| result_is_bounded | undetectable | None | — |
| complexity_class | undetectable | None | — |
| shared_mutable_state | undetectable | None | — |
| outbound_calls_protected | undetectable | None | — |
| cached | undetectable | None | — |
| rate_limited | undetectable | None | — |

### FACT-15de3868f6371e28 — `internal/engine/cache.go`

projected ceiling of 0.0 cost units at 1000x traffic (data_access_calls=0, n_plus_one=?, unbounded=False, shared_state=False, rate_limited=True)

**This entry's projection is incomplete.** Unanswered questions: cached, complexity_class, data_access_calls, outbound_calls_protected, rate_limited, repeats_per_iteration, result_is_bounded, shared_mutable_state

| Question | Status | Value | Evidence |
| --- | --- | --- | --- |
| data_access_calls | undetectable | None | — |
| repeats_per_iteration | undetectable | None | — |
| result_is_bounded | undetectable | None | — |
| complexity_class | undetectable | None | — |
| shared_mutable_state | undetectable | None | — |
| outbound_calls_protected | undetectable | None | — |
| cached | undetectable | None | — |
| rate_limited | undetectable | None | — |

### FACT-62eceba39cb16dfb — `examples/cross-repo/api/server.go`

projected ceiling of 0.0 cost units at 1000x traffic (data_access_calls=0, n_plus_one=?, unbounded=False, shared_state=False, rate_limited=True)

**This entry's projection is incomplete.** Unanswered questions: cached, complexity_class, data_access_calls, outbound_calls_protected, rate_limited, repeats_per_iteration, result_is_bounded, shared_mutable_state

| Question | Status | Value | Evidence |
| --- | --- | --- | --- |
| data_access_calls | undetectable | None | — |
| repeats_per_iteration | undetectable | None | — |
| result_is_bounded | undetectable | None | — |
| complexity_class | undetectable | None | — |
| shared_mutable_state | undetectable | None | — |
| outbound_calls_protected | undetectable | None | — |
| cached | undetectable | None | — |
| rate_limited | undetectable | None | — |

## What we could not measure and why

| Question | Reason | Entry points |
| --- | --- | --- |
| cached | the flow could not be traced from this entry point | 11: FACT-d3f797d291f88fc5, FACT-15de3868f6371e28, FACT-62eceba39cb16dfb and 8 more |
| complexity_class | the flow could not be traced from this entry point | 11: FACT-d3f797d291f88fc5, FACT-15de3868f6371e28, FACT-62eceba39cb16dfb and 8 more |
| data_access_calls | the flow could not be traced from this entry point | 11: FACT-d3f797d291f88fc5, FACT-15de3868f6371e28, FACT-62eceba39cb16dfb and 8 more |
| outbound_calls_protected | the flow could not be traced from this entry point | 11: FACT-d3f797d291f88fc5, FACT-15de3868f6371e28, FACT-62eceba39cb16dfb and 8 more |
| rate_limited | the flow could not be traced from this entry point | 11: FACT-d3f797d291f88fc5, FACT-15de3868f6371e28, FACT-62eceba39cb16dfb and 8 more |
| repeats_per_iteration | the flow could not be traced from this entry point | 11: FACT-d3f797d291f88fc5, FACT-15de3868f6371e28, FACT-62eceba39cb16dfb and 8 more |
| result_is_bounded | the flow could not be traced from this entry point | 11: FACT-d3f797d291f88fc5, FACT-15de3868f6371e28, FACT-62eceba39cb16dfb and 8 more |
| shared_mutable_state | the flow could not be traced from this entry point | 11: FACT-d3f797d291f88fc5, FACT-15de3868f6371e28, FACT-62eceba39cb16dfb and 8 more |
| cached | no cache site on this path | 2: FACT-4ab7f1d5c5c9fbd9, FACT-de174e9b06853330 |
| complexity_class | no engine performance observation on this path | 2: FACT-4ab7f1d5c5c9fbd9, FACT-de174e9b06853330 |
| data_access_calls | no data-access call sites recorded in this entry path | 2: FACT-4ab7f1d5c5c9fbd9, FACT-de174e9b06853330 |
| rate_limited | no rate-limit or concurrency bound on this path | 2: FACT-4ab7f1d5c5c9fbd9, FACT-de174e9b06853330 |
| repeats_per_iteration | no n+1 redundancy observation in this entry path; cannot confirm or deny | 2: FACT-4ab7f1d5c5c9fbd9, FACT-de174e9b06853330 |
| result_is_bounded | some queries are bounded, others are not; mixed result | 2: FACT-4ab7f1d5c5c9fbd9, FACT-de174e9b06853330 |
| shared_mutable_state | no mutable_global or external_state_write on this path | 2: FACT-4ab7f1d5c5c9fbd9, FACT-de174e9b06853330 |

Every entry point and every reason is in `load-model.json`.

