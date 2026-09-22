# Contracts and boundaries

> Attention signals only: nothing here judges design quality.

## External dependencies

| Name | Language | kind | used in |
|---|---|---|---|
| @nestjs/common | typescript | third party | 2 |
| @example/sdk | typescript | third party | 1 |
| <stdbool.h> | c | unknown | 6 |
| <stdlib.h> | c | unknown | 6 |
| File | ruby | unknown | 6 |
| json | ruby | unknown | 6 |
| --version | ruby | unknown | 5 |
| exit | ruby | unknown | 5 |
| puts | ruby | unknown | 5 |
| :: | ruby | unknown | 4 |
| <stdint.h> | c | unknown | 4 |
| Dir | ruby | unknown | 4 |
| JSON | ruby | unknown | 4 |
| lines | ruby | unknown | 4 |
| %w[vendor node_modules tmp] | ruby | unknown | 3 |
| ** | ruby | unknown | 3 |
| / | ruby | unknown | 3 |
| <string.h> | c | unknown | 3 |
| SKIP_SEGMENTS | ruby | unknown | 3 |
| counts | ruby | unknown | 3 |
| kind | ruby | unknown | 3 |
| receiver | ruby | unknown | 3 |
| source | ruby | unknown | 3 |
| : | ruby | unknown | 2 |
| <assert.h> | c | unknown | 2 |
| <stdio.h> | c | unknown | 2 |
| <wctype.h> | c | unknown | 2 |
| @facts | ruby | unknown | 2 |
| @scopes | ruby | unknown | 2 |
| Gemfile | ruby | unknown | 2 |

Showing 30 of 382; the rest stays in the fact records.

- third party: 2 · standard library: 86

## Entry points

| Surface | Method | Route | Location |
|---|---|---|---|
| cli | — | build_wheel | packaging/pypi/build_wheel.py:176 |
| cli | — | build_wheel | packaging/pypi/build_wheel.py:254 |
| http | ANY | — | internal/extractors/goextractor/routes_test.go:351 |
| http | ANY | / | pkg/dashboard/dashboard.go:140 |
| http | ANY | /a | internal/extractors/goextractor/routeprefix_test.go:287 |
| http | ANY | /api/feature | internal/extractors/goextractor/routes_test.go:280 |
| http | ANY | /api/orders | internal/engine/providers_test.go:125 |
| http | ANY | /api/users | internal/engine/providers_test.go:124 |
| http | ANY | /api/users | internal/extractors/goextractor/routes_test.go:20 |
| http | ANY | /api/users | internal/extractors/goextractor/routes_test.go:21 |
| http | ANY | /api/users/{id} | internal/extractors/goextractor/routes_test.go:22 |
| http | ANY | /b | internal/extractors/goextractor/routeprefix_test.go:292 |
| http | ANY | /courses | internal/engine/cache.go:593 |
| http | ANY | /courses | internal/extractors/goextractor/routeprefix_test.go:45 |
| http | ANY | /courses/{id} | internal/extractors/goextractor/routeprefix_test.go:46 |
| http | ANY | /courses/{id} | internal/extractors/goextractor/routeprefix_test.go:203 |
| http | POST | /events | internal/extractors/goextractor/gin_test.go:36 |
| http | ANY | /health | internal/extractors/goextractor/routes_test.go:164 |
| http | ANY | /health | internal/extractors/goextractor/routes_test.go:230 |
| http | ANY | /orders | examples/cross-repo/api/server.go:28 |
| http | ANY | /orders/{id} | examples/cross-repo/api/server.go:27 |
| http | ANY | /orphan | internal/extractors/goextractor/routeprefix_test.go:176 |
| http | ANY | /path | internal/extractors/goextractor/routes.go:158 |
| http | ANY | /path | internal/extractors/goextractor/routes.go:173 |
| http | GET | /path | internal/extractors/goextractor/routes.go:296 |
| http | ANY | /path | internal/extractors/goextractor/routes.go:393 |
| http | GET | /ping | internal/extractors/goextractor/gin_test.go:35 |
| http | ANY | /rules/{id} | internal/extractors/goextractor/routeprefix_test.go:241 |
| http | ANY | /things | internal/extractors/goextractor/routeprefix_test.go:121 |
| http | ANY | /things | internal/extractors/goextractor/routeprefix_test.go:323 |

Showing 30 of 37; the rest stays in the fact records.
