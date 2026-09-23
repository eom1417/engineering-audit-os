# Onboarding runbook

> Generated from facts: commands come from declared manifests, reading order from the graph.

## Build and run

No data for this section in this snapshot.

## Test

- 0 test files found; no command has been executed in this run (eaos verify --execute)

## Entry points to try

| Surface | Route | Handler | Location |
|---|---|---|---|
| cli | baseline | Baseline | pkg/command/command.go:175 |
| cli | blame | Blame | pkg/command/command.go:186 |
| cli | build_wheel | main | packaging/pypi/build_wheel.py:176 |
| cli | build_wheel | main | packaging/pypi/build_wheel.py:254 |
| cli | check | Check | pkg/command/command.go:141 |
| cli | cluster | Cluster | pkg/command/command.go:146 |
| cli | constraints | Constraints | pkg/command/command.go:147 |
| cli | coverage | Coverage | pkg/command/command.go:159 |
| cli | dashboard | Dashboard | pkg/command/command.go:172 |
| cli | diff | Diff | pkg/command/command.go:183 |
| cli | doctor | Doctor | pkg/command/command.go:166 |
| cli | endpoint | Endpoint | pkg/command/command.go:163 |
| cli | gc | GC | pkg/command/command.go:189 |
| cli | history | History | pkg/command/command.go:192 |
| cli | hook | Hook | pkg/command/command.go:195 |

Showing 15 of 26; the rest stays in the fact records.

## The first ten files to read

| File | Score | Why |
|---|---|---|
| internal/facts/accessors.go | 0.7075 | centrality 1.0 · change 1.0 |
| pkg/dashboard/dashboard.go | 0.5274 | centrality 0.003 · change 1.0 |
| cmd/enola/main.go | 0.527 | centrality 0.0 · change 1.0 |
| pkg/command/command.go | 0.511 | centrality 0.0 · change 1.0 |
| packaging/pypi/build_wheel.py | 0.5044 | centrality 0.0 · change 1.0 |
| examples/cross-repo/api/server.go | 0.5 | centrality 0.0 · change 1.0 |
| internal/server/server.go | 0.5 | centrality 0.0 · change 1.0 |
| internal/extractors/tsextractor/ts.go | 0.4793 | centrality 0.0 · change 1.0 |
| internal/config/config.go | 0.4379 | centrality 0.092 · change 1.0 |
| pkg/bootstrap/bootstrap.go | 0.4373 | centrality 0.055 · change 1.0 |

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

- 1 entry points are registered dynamically and cannot be traced statically
- 0 sensitive config files are listed but never read
- 27 steps in the traced flows stop at calls the resolver cannot follow
