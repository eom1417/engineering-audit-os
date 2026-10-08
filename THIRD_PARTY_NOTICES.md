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
| [ast-grep](https://github.com/ast-grep/ast-grep) | Herrington Darkholme | MIT | separate process; EAOS's own rule pack, JSON stream read |
| [Lizard](https://github.com/terryyin/lizard) | Terry Yin and other contributors | MIT | separate process; CSV read |
| [complexipy](https://github.com/rohaquinlop/complexipy) | Robin Quintero | MIT | separate process; JSON report read |
| [vulture](https://github.com/jendrikseipp/vulture) | Jendrik Seipp | MIT | separate process; text report read |
| [knip](https://github.com/webpro-nl/knip) | Lars Kappert | ISC | separate process, every plugin off; JSON report read |
| [react-docgen](https://github.com/reactjs/react-docgen) (`@react-docgen/cli`) | Facebook, Inc. and its affiliates | MIT | separate process; JSON report read |

### Screen audit tools

The screen audit (`eaos/screens/audit.py`, `tools/studio_gates.py`) runs these in a separate Node.js process
(`eaos/templates/screens/*.mjs`); none of their code is copied into this repository or into the EAOS Python
process. axe-core is injected unmodified into the page under test, which MPL-2.0 permits without further
obligation. Pinned versions are in `upstreams/toolchain.json`.

| Tool | Copyright | Licence | Used how |
| --- | --- | --- | --- |
| [Playwright](https://github.com/microsoft/playwright) | Microsoft Corporation | Apache-2.0 | separate process; drives Chromium per page, viewport, language and theme |
| [axe-core](https://github.com/dequelabs/axe-core) and [@axe-core/playwright](https://github.com/dequelabs/axe-core-npm) | Deque Systems, Inc. | MPL-2.0 | injected unmodified into the page; WCAG violations read as JSON |
| [Lighthouse](https://github.com/GoogleChrome/lighthouse) | Google LLC | Apache-2.0 | separate process; mobile JSON report read |
| [@projectwallace/css-analyzer](https://github.com/projectwallace/css-analyzer) | Bart Veneman | MIT | separate process; CSS statistics read as JSON |

Two projects were evaluated and deliberately not used:

- **Serena** — licensed per component: SolidLSP under MIT, the Serena application under
  GPL-3.0-or-later. Its capability is already covered by CodeGraph under Apache-2.0, so taking on a
  copyleft obligation would buy nothing. Not integrated.
- **ArchMind** — ships no LICENSE file, so every right is reserved by default. Its architectural
  ideas informed our thinking; none of its code is present here.
