# Third-party notices

EAOS does not vendor, link or redistribute any third-party analysis engine. It **invokes** pinned
binaries the operator installs, reads their structured output, and records which engine produced
what. No engine's source is copied into this repository.

The notices below are kept because we depend on these projects operationally and their authorship
should be visible to anyone reading our results. Full licence texts are in `upstreams/licenses/`,
and the pinned versions, commits and checksums are in `eaos/data/toolchain.json`.

| Engine | Copyright | Licence | Used how |
| --- | --- | --- | --- |
| [enola](https://github.com/enola-labs/enola) | Dejan Menges | Apache-2.0 | separate process; JSON artifacts read |
| [CodeGraph](https://github.com/codegraph-ai/CodeGraph) | Andrey Vasilevsky | Apache-2.0 | separate process; one-shot tool JSON read |
| [Reforge](https://github.com/LyleMi/Reforge) | Reforge authors | Apache-2.0 | separate process; JSON report read |
| [jscpd](https://github.com/kucherenko/jscpd) | Andrey Kucherenko | MIT | separate process; JSON report read |
| [ast-grep](https://github.com/ast-grep/ast-grep) | Herrington Darkholme | MIT | separate process; EAOS's own rule pack, JSON stream read |
| [Lizard](https://github.com/terryyin/lizard) | Terry Yin and other contributors | MIT | separate process; CSV read |
| [knip](https://github.com/webpro-nl/knip) | Lars Kappert | ISC | separate process, every plugin off; JSON report read |
| [react-docgen](https://github.com/reactjs/react-docgen) (`@react-docgen/cli`) | Facebook, Inc. and its affiliates | MIT | separate process; JSON report read |
| [Bandit](https://github.com/PyCQA/bandit) | PyCQA | Apache-2.0 | separate process; SARIF read |
| [Gitleaks](https://github.com/gitleaks/gitleaks) | Zachary Rice | MIT | separate process, secrets redacted; SARIF read |
| [CodeQL](https://github.com/github/codeql-action) (the CodeQL bundle) | GitHub, Inc. | GitHub CodeQL Terms and Conditions | separate process, run only on an open-source codebase public on GitHub.com, as its terms allow; SARIF read |

### Visual evidence tools (pipeline v2)

The live journeys, the crawl and the architecture map run these as separate processes; none of their code is copied
into this repository or into the EAOS Python process. rrweb's recorder is injected unmodified into the pages of the
app under test, and its player is copied unmodified beside the report to replay them. Full licence texts are in
`upstreams/licenses/`, pinned versions in `eaos/data/toolchain.json`.

| Tool | Copyright | Licence | Used how |
| --- | --- | --- | --- |
| [rrweb](https://github.com/rrweb-io/rrweb) and rrweb-player | rrweb contributors | MIT | recorder injected unmodified into each page of a journey; events read as JSON; player replays them in the report |
| [Unlighthouse](https://github.com/harlan-zw/unlighthouse) (`@unlighthouse/cli`) | Harlan Wilton | MIT | separate process on the app's own address; per-page Lighthouse JSON read |
| [CodeCharta](https://github.com/MaibornWolff/codecharta) (`codecharta-analysis`, ccsh) | MaibornWolff GmbH | BSD-3-Clause | separate process; cc.json written and kept as the architecture city |
| [Emerge](https://github.com/glato/emerge) (`emerge-viz`) | Grzegorz Lato | MIT | separate process; dependency graph JSON read, its local page kept |

### Screen audit tools

The screen audit (`eaos/screens/audit.py`, `tools/studio_gates.py`) runs these in a separate Node.js process
(`eaos/templates/screens/*.mjs`); none of their code is copied into this repository or into the EAOS Python
process. axe-core is injected unmodified into the page under test, which MPL-2.0 permits without further
obligation. Pinned versions are in `eaos/data/toolchain.json`.

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

## Design sources

Read when a look is drawn or reviewed (`eaos/design.py`): fetched to the operator's machine at a pinned commit, never
copied into this repository or redistributed. Components and fonts are installed into the built project by their own
package managers.

| Source | Copyright | Licence | Used how |
| --- | --- | --- | --- |
| [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | nextlevelbuilder | MIT | its offline search script and CSV data read |
| [awesome-design-md](https://github.com/voltagent/awesome-design-md) | VoltAgent | MIT | reference DESIGN.md files read as directions, never copied as a brand |
| [tweakcn-theme-picker](https://github.com/BankkRoll/tweakcn-theme-picker) | BankkRoll | MIT | theme token files read |
| [frontend-design (Anthropic skills)](https://github.com/anthropics/skills) | Anthropic, PBC | Apache-2.0 | its SKILL.md read as guidance; the repository's other skills are not used |
| [shadcn/ui](https://github.com/shadcn-ui/ui) | shadcn | MIT | installed into a built project by its own CLI |
| [Fontsource](https://github.com/fontsource/fontsource) and the fonts it serves | their authors | MIT (tooling), OFL-1.1 (fonts) | installed into a built project by npm |
