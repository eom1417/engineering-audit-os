# Domain and data

> A constant repeated in two modules is a question about rule ownership, not yet a defect.

## Rule value duplicated in more than one place

No data for this section in this snapshot.

## Data models and schemas

| Name | kind | Location |
|---|---|---|
| IHttpRequestService | ts_type | examples/custom-client/sdk/src/http/http-request.service.ts:14 |
| RequestOptions | ts_type | examples/custom-client/sdk/src/http/http-request.service.ts:9 |
| IF | table | internal/extractors/goextractor/storage.go:266 |
| IF | table | internal/extractors/goextractor/storage_test.go:282 |
| IF | table | internal/extractors/goextractor/storage_test.go:291 |
| body | table | internal/extractors/rubyextractor/structuresql.go:180 |
| file_new | table | internal/extractors/goextractor/storage_test.go:265 |
| opens | table | internal/extractors/rubyextractor/structuresql.go:120 |
| orders | table | internal/extractors/goextractor/storage_test.go:21 |
| orders | table | internal/extractors/goextractor/storage_test.go:44 |
| public.audit_rows | table | internal/extractors/rubyextractor/structuresql_test.go:34 |
| public.companies | table | internal/extractors/rubyextractor/structuresql_test.go:20 |
| public.employments | table | internal/extractors/rubyextractor/structuresql_test.go:28 |
| public.pairs | table | internal/extractors/rubyextractor/structuresql_test.go:146 |
| response | table | internal/engine/cache.go:962 |
| users | table | internal/extractors/goextractor/storage_test.go:14 |
| users | table | internal/extractors/goextractor/storage_test.go:41 |
| was | table | internal/extractors/goextractor/storage.go:37 |
| was | table | internal/extractors/goextractor/storage_test.go:263 |
| was | table | internal/extractors/goextractor/storage_test.go:278 |
| weird | table | internal/extractors/rubyextractor/structuresql_test.go:152 |

## Configuration contract

| Name | Read in | default |
|---|---|---|
| AFTER | packaging/pypi/local_test.sh:201 | no |
| ALPINE_IMAGES | packaging/pypi/musl_test.sh:182 | no |
| ANGULAR_CORPUS | internal/extractors/tsextractor/angular_probe_test.go:168, internal/extractors/tsextractor/angular_probe_test.go:34 | no |
| ARCH | install.sh:24, install.sh:27, install.sh:37 | no |
| ASSET | install.sh:40, install.sh:48, install.sh:64 | no |
| BASE | install.sh:38, install.sh:39, install.sh:67 | no |
| BASH_SOURCE | packaging/pypi/index_test.sh:23, packaging/pypi/linux_test.sh:28, packaging/pypi/local_test.sh:20 | no |
| BEFORE | packaging/pypi/local_test.sh:201 | no |
| BIN | packaging/pypi/local_test.sh:106, packaging/pypi/local_test.sh:115, packaging/pypi/local_test.sh:168 | no |
| BIN_NAME | install.sh:70, install.sh:85 | no |
| BUILD_IMAGE | packaging/pypi/musl_test.sh:106, packaging/pypi/musl_test.sh:92 | no |
| BUILD_IMAGES | packaging/pypi/linux_test.sh:165 | no |
| BUILD_IMAGES_DEFAULT | packaging/pypi/linux_test.sh:67 | no |
| CI | internal/updatecheck/updatecheck.go:132, pkg/cli/hints.go:13 | no |
| COUNT | packaging/pypi/linux_test.sh:192 | no |
| DEMO | examples/custom-client/run.sh:19, examples/custom-client/run.sh:20, examples/custom-client/run.sh:21 | no |
| DIST | packaging/pypi/index_test.sh:103, packaging/pypi/index_test.sh:117, packaging/pypi/index_test.sh:147 | no |
| DOCKER_PLATFORM | packaging/pypi/linux_test.sh:40, packaging/pypi/musl_test.sh:35 | no |
| ENOLA | examples/cross-repo/run.sh:10, examples/cross-repo/run.sh:11, examples/cross-repo/run.sh:19 | no |
| ENOLA_CS_CORPUS | internal/extractors/dotnetextractor/kindtable_test.go:101 | no |
| ENOLA_DARWIN_AMD64 | packaging/pypi/index_test.sh:84, packaging/pypi/index_test.sh:85 | no |
| ENOLA_DIFF_BASELINE | internal/diff/counts_test.go:235 | no |
| ENOLA_DIFF_CURRENT | internal/diff/counts_test.go:236 | no |
| ENOLA_E2E | pkg/install/hooks_e2e_test.go:30 | no |
| ENOLA_ESLINT_RESULTS | examples/providers/js/eslint/enola_eslint_provider.mjs:40 | no |

Showing 25 of 117; the rest stays in the fact records.
