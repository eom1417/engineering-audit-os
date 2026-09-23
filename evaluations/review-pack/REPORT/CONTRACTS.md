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
| cli | — | baseline | pkg/command/command.go:175 |
| cli | — | blame | pkg/command/command.go:186 |
| cli | — | build_wheel | packaging/pypi/build_wheel.py:176 |
| cli | — | build_wheel | packaging/pypi/build_wheel.py:254 |
| cli | — | check | pkg/command/command.go:141 |
| cli | — | cluster | pkg/command/command.go:146 |
| cli | — | constraints | pkg/command/command.go:147 |
| cli | — | coverage | pkg/command/command.go:159 |
| cli | — | dashboard | pkg/command/command.go:172 |
| cli | — | diff | pkg/command/command.go:183 |
| cli | — | doctor | pkg/command/command.go:166 |
| cli | — | endpoint | pkg/command/command.go:163 |
| cli | — | gc | pkg/command/command.go:189 |
| cli | — | history | pkg/command/command.go:192 |
| cli | — | hook | pkg/command/command.go:195 |
| cli | — | install | pkg/command/command.go:201 |
| cli | — | log | pkg/command/command.go:178 |
| cli | — | main | cmd/enola/main.go:29 |
| cli | — | plan | pkg/command/command.go:158 |
| cli | — | providers | pkg/command/command.go:168 |
| cli | — | server | examples/cross-repo/api/server.go:15 |
| cli | — | show | pkg/command/command.go:180 |
| cli | — | uninstall | pkg/command/command.go:201 |
| http | ANY | — | internal/extractors/goextractor/routes_test.go:335 |
| http | ANY | / | pkg/dashboard/dashboard.go:52 |
| http | ANY | /a | internal/extractors/goextractor/routeprefix_test.go:226 |
| http | ANY | /api/feature | internal/extractors/goextractor/routes_test.go:268 |
| http | ANY | /api/orders | internal/engine/providers_test.go:101 |
| http | ANY | /api/users | internal/engine/providers_test.go:101 |
| http | ANY | /api/users | internal/extractors/goextractor/routes_test.go:20 |

Showing 30 of 50; the rest stays in the fact records.
