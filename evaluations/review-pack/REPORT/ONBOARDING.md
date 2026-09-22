# Onboarding runbook

> Generated from facts: commands come from declared manifests, reading order from the graph.

## Build and run

No data for this section in this snapshot.

## Test

- 0 test files found; no command has been executed in this run (eaos verify --execute)

## Entry points to try

| Surface | Route | Handler | Location |
|---|---|---|---|
| cli | build_wheel | main | packaging/pypi/build_wheel.py:176 |
| cli | build_wheel | main | packaging/pypi/build_wheel.py:254 |
| http | / | s.handleIndex | pkg/dashboard/dashboard.go:140 |
| http | /orders | listOrders | examples/cross-repo/api/server.go:28 |
| http | /orders/{id} | getOrder | examples/cross-repo/api/server.go:27 |
| http | /path | handler | internal/extractors/goextractor/routes.go:158 |
| http | /path | handler | internal/extractors/goextractor/routes.go:173 |
| http | /path | handler | internal/extractors/goextractor/routes.go:296 |
| http | /path | handler | internal/extractors/goextractor/routes.go:393 |

## The first ten files to read

| File | Score | Why |
|---|---|---|
| pkg/facts/facts.go | 0.7 | centrality 1.0 · change 1.0 |
| internal/version/version.go | 0.5667 | centrality 0.556 · change 1.0 |
| internal/extractors/goextractor/routes.go | 0.5367 | centrality 0.0 · change 1.0 |
| pkg/dashboard/dashboard.go | 0.5264 | centrality 0.0 · change 1.0 |
| internal/engine/cache.go | 0.5207 | centrality 0.0 · change 1.0 |
| packaging/pypi/build_wheel.py | 0.5044 | centrality 0.0 · change 1.0 |
| examples/cross-repo/api/server.go | 0.5 | centrality 0.0 · change 1.0 |
| internal/server/server.go | 0.5 | centrality 0.0 · change 1.0 |
| internal/extractors/detectnames/detectnames.go | 0.4812 | centrality 0.593 · change 1.0 |
| internal/extractors/tsextractor/ts.go | 0.4793 | centrality 0.0 · change 1.0 |

## Project vocabulary

| Name | Kind | Location |
|---|---|---|
| IHttpRequestService | data_model | examples/custom-client/sdk/src/http/http-request.service.ts:14 |
| RequestOptions | data_model | examples/custom-client/sdk/src/http/http-request.service.ts:9 |
| IF | data_table | internal/extractors/goextractor/storage.go:266 |
| IF | data_table | internal/extractors/goextractor/storage_test.go:282 |
| IF | data_table | internal/extractors/goextractor/storage_test.go:291 |
| body | data_table | internal/extractors/rubyextractor/structuresql.go:180 |
| file_new | data_table | internal/extractors/goextractor/storage_test.go:265 |
| opens | data_table | internal/extractors/rubyextractor/structuresql.go:120 |
| orders | data_table | internal/extractors/goextractor/storage_test.go:21 |
| orders | data_table | internal/extractors/goextractor/storage_test.go:44 |
| public.audit_rows | data_table | internal/extractors/rubyextractor/structuresql_test.go:34 |
| public.companies | data_table | internal/extractors/rubyextractor/structuresql_test.go:20 |
| public.employments | data_table | internal/extractors/rubyextractor/structuresql_test.go:28 |
| public.pairs | data_table | internal/extractors/rubyextractor/structuresql_test.go:146 |
| response | data_table | internal/engine/cache.go:962 |
| users | data_table | internal/extractors/goextractor/storage_test.go:14 |
| users | data_table | internal/extractors/goextractor/storage_test.go:41 |
| was | data_table | internal/extractors/goextractor/storage.go:37 |
| was | data_table | internal/extractors/goextractor/storage_test.go:263 |
| was | data_table | internal/extractors/goextractor/storage_test.go:278 |

Showing 20 of 31; the rest stays in the fact records.

## Known traps

- 5 entry points are registered dynamically and cannot be traced statically
- 0 sensitive config files are listed but never read
- 0 steps in the traced flows stop at calls the resolver cannot follow
