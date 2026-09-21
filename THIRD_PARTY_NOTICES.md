# Third-party notices

EAOS does not vendor, link or redistribute any third-party analysis engine. It **invokes** pinned
binaries the operator installs, reads their structured output, and records which engine produced
what. No engine's source is copied into this repository.

The notices below are kept because we depend on these projects operationally and their authorship
should be visible to anyone reading our results. Full licence texts are in `upstreams/licenses/`,
and the pinned versions, commits and checksums are in `upstreams/registry.yaml`.

| Engine | Copyright | Licence | Used how |
| --- | --- | --- | --- |
| [enola](https://github.com/enola-labs/enola) | Dejan Menges | Apache-2.0 | separate process; JSON artifacts read |
| [CodeGraph](https://github.com/codegraph-ai/CodeGraph) | Andrey Vasilevsky | Apache-2.0 | separate process; one-shot tool JSON read |
| [Reforge](https://github.com/LyleMi/Reforge) | Reforge authors | Apache-2.0 | separate process; JSON report read |
| [jscpd](https://github.com/kucherenko/jscpd) | Andrey Kucherenko | MIT | separate process; JSON report read |

Two projects were evaluated and deliberately not used:

- **Serena** — licensed per component: SolidLSP under MIT, the Serena application under
  GPL-3.0-or-later. Its capability is already covered by CodeGraph under Apache-2.0, so taking on a
  copyleft obligation would buy nothing. Not integrated.
- **ArchMind** — ships no LICENSE file, so every right is reserved by default. Its architectural
  ideas informed our thinking; none of its code is present here.
