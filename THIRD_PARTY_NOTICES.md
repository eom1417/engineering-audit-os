# Third-party notices

EAOS does not vendor, link or redistribute any third-party analysis tool. It **runs** pinned tools the person installs
(`eaos tools install`), as separate processes, reads their structured output, and records which tool produced what. No
tool's source is copied into this repository.

The one list of these tools, with their pinned versions, commits, checksums and licences, is
`eaos/data/toolchain.json`: every entry is named below under the same name. Licence texts kept in this repository are
in `upstreams/licenses/` (`<name>-LICENSE`, and `<name>-NOTICE` where the project ships one); a tool without a file
there is marked "not kept" and its licence is read at its repository.

## Shipped with EAOS

| Work | Copyright | Licence | Where |
| --- | --- | --- | --- |
| [IBM Plex Sans Arabic and IBM Plex Mono](https://github.com/IBM/plex) | IBM Corp. | OFL-1.1 | the Studio's fonts (`console/src/fonts/`, built into `eaos/data/studio/assets/` with `FONT-LICENSE.txt`) |

## The pinned tools (`eaos/data/toolchain.json`)

### Reading the code and its dependencies

| Entry | Copyright | Licence | Used how | Licence text |
| --- | --- | --- | --- | --- |
| `codegraph` ([CodeGraph](https://github.com/codegraph-ai/CodeGraph)) | Andrey Vasilevsky | Apache-2.0 | one-shot tool JSON read | kept, with NOTICE |
| `enola` ([enola](https://github.com/enola-labs/enola)) | Dejan Menges | Apache-2.0 | JSON artifacts read | kept, with NOTICE |
| `reforge` ([Reforge](https://github.com/LyleMi/Reforge)) | the Reforge authors | Apache-2.0 | JSON report read | kept |
| `jscpd` ([jscpd](https://github.com/kucherenko/jscpd)) | Andrey Kucherenko | MIT | JSON report read | kept |
| `syft` ([Syft](https://github.com/anchore/syft)) | Anchore, Inc. | Apache-2.0 | CycloneDX SBOM written to the report, read by OSV-Scanner | kept |
| `osv-scanner` ([OSV-Scanner](https://github.com/google/osv-scanner)) | Google LLC | Apache-2.0 | lockfiles and the SBOM checked against the OSV database; JSON read | kept |
| `scc` ([scc](https://github.com/boyter/scc)) | Ben Boyter | MIT | per-file size and complexity read as measurements | kept |
| `semgrep` ([Semgrep](https://github.com/semgrep/semgrep)) | Semgrep, Inc. | LGPL-2.1 | EAOS's own rules (`eaos/rules/semgrep/`) and the rule set below; SARIF read | kept |
| `semgrep-rules` ([semgrep-rules](https://github.com/semgrep/semgrep-rules)) | Semgrep, Inc. | Semgrep Rules License v1.0 | fetched to the person's computer for non-commercial use and read by Semgrep; never copied here or redistributed | kept |
| `trivy` ([Trivy](https://github.com/aquasecurity/trivy)) | Aqua Security | Apache-2.0 | secrets and misconfigurations only; SARIF read | kept |
| `checkov` ([Checkov](https://github.com/bridgecrewio/checkov)) | the Checkov authors | Apache-2.0 | GitHub Actions, Dockerfiles, Terraform and Kubernetes files; SARIF and JSON read | kept |
| `bandit` ([Bandit](https://github.com/PyCQA/bandit)) | PyCQA | Apache-2.0 | SARIF read | kept |
| `gitleaks` ([Gitleaks](https://github.com/gitleaks/gitleaks)) | Zachary Rice | MIT | secrets redacted; SARIF read | kept |
| `presidio` ([Presidio](https://github.com/microsoft/presidio) analyzer, with [spaCy](https://github.com/explosion/spaCy) and its `en_core_web_sm` model) | Microsoft Corporation; ExplosionAI GmbH | MIT (the model: MIT) | imported by EAOS's own script in its own environment; string literals read, values masked, none written | kept |
| `codeql` ([CodeQL](https://github.com/github/codeql-action), the CodeQL bundle) | GitHub, Inc. | GitHub CodeQL Terms and Conditions | run only on an open-source codebase public on GitHub.com, as its terms allow; SARIF read | not kept |
| `dependency-cruiser` ([dependency-cruiser](https://github.com/sverweij/dependency-cruiser)) | Sander Verweij | MIT | the JavaScript and TypeScript import graph, with TypeScript installed beside it; JSON read | kept |
| `sqlfluff` ([SQLFluff](https://github.com/sqlfluff/sqlfluff)) | the SQLFluff authors | MIT | the project's SQL linted in the Postgres dialect; JSON read | kept |
| `spectral` ([Spectral](https://github.com/stoplightio/spectral)) | Stoplight | Apache-2.0 | OpenAPI documents linted; SARIF read | kept |
| `oasdiff` ([oasdiff](https://github.com/oasdiff/oasdiff)) | the oasdiff authors | Apache-2.0 | an OpenAPI document compared with its previous version; JSON read | kept |
| `gitnexus` ([GitNexus](https://github.com/abhigyanpatwari/GitNexus)) | Abhigyan Patwari | PolyForm-Noncommercial-1.0.0 | run on a copy, never on the project; its graph read. **Non-commercial use only**: a commercial user of EAOS is bound by this licence and may skip it (`--skip gitnexus`) | kept |
| `ast-grep` ([ast-grep](https://github.com/ast-grep/ast-grep)) | Herrington Darkholme | MIT | EAOS's own rule pack (`eaos/rules/ast-grep/`); JSON stream read | kept |
| `lizard` ([Lizard](https://github.com/terryyin/lizard)) | Terry Yin and other contributors | MIT | CSV read | kept |
| `knip` ([knip](https://github.com/webpro-nl/knip)) | Lars Kappert | ISC | every plugin off; JSON report read | kept |
| `react-docgen` ([react-docgen](https://github.com/reactjs/react-docgen), `@react-docgen/cli`) | Facebook, Inc. and its affiliates | MIT | JSON report read | kept |
| `codecharta` ([CodeCharta](https://github.com/MaibornWolff/codecharta), ccsh) | MaibornWolff GmbH | BSD-3-Clause | cc.json written and kept as the architecture city | kept |
| `emerge` ([Emerge](https://github.com/glato/emerge)) | Grzegorz Lato | MIT | dependency graph JSON read, its local page kept | kept |

### Running and trying the app

All run on the app's isolated copy on the person's computer, with a database of the run's own.

| Entry | Copyright | Licence | Used how | Licence text |
| --- | --- | --- | --- | --- |
| `schemathesis` ([Schemathesis](https://github.com/schemathesis/schemathesis)) | Kiwi.com and contributors | MIT | tries the running API ("Try the layers"); its NDJSON report read, then removed | kept |
| `supabase` ([Supabase CLI](https://github.com/supabase/cli), `supabase db advisors`) | Supabase, Inc. and contributors | MIT | its advisors read the run's own PostgreSQL; JSON read | kept |
| `pgtap` ([pgTAP](https://github.com/theory/pgtap)) | David E. Wheeler | PostgreSQL | its SQL, fetched at its pinned commit, loaded into the run's own database only; TAP output read | kept |
| `playwright` ([Playwright](https://github.com/microsoft/playwright)) | Microsoft Corporation | Apache-2.0 | drives Chromium per page, viewport, language and theme | kept, with NOTICE |
| `pytest` ([pytest](https://github.com/pytest-dev/pytest)) | Holger Krekel and others | MIT | runs the behaviour lock's approval tests, with ApprovalTests (Apache-2.0) installed beside it | kept |
| `k6` ([k6](https://github.com/grafana/k6)) | Grafana Labs | AGPL-3.0 | unmodified, as a separate process, for load trials; its summary read | kept |
| `mailpit` ([Mailpit](https://github.com/axllent/mailpit)) | Ralph Slooten | MIT | catches the e-mail the app sends from its copy | kept |
| `temurin-jre` ([Eclipse Temurin](https://github.com/adoptium/temurin21-binaries)) | the OpenJDK authors, built by Eclipse Adoptium | GPL-2.0-with-classpath-exception | the Java runtime CodeCharta's ccsh runs on | not kept |
| `jscodeshift` ([jscodeshift](https://github.com/facebook/jscodeshift)) | Meta Platforms, Inc. and affiliates | MIT | runs the codemods of mechanical cards on an isolated copy; it parses code, never runs it | kept |
| `axe-core` ([axe-core](https://github.com/dequelabs/axe-core) and [@axe-core/playwright](https://github.com/dequelabs/axe-core-npm)) | Deque Systems, Inc. | MPL-2.0 | injected unmodified into the page under test, which MPL-2.0 permits without further obligation; WCAG violations read as JSON | kept |
| `lighthouse` ([Lighthouse](https://github.com/GoogleChrome/lighthouse)) | Google LLC | Apache-2.0 | mobile JSON report of one address read (`eaos/live/screens/audit.py`) | kept |
| `css-analyzer` ([@projectwallace/css-analyzer](https://github.com/projectwallace/css-analyzer)) | Bart Veneman | MIT | imported by `eaos/templates/screens/css.mjs` in a separate Node.js process; CSS statistics read as JSON | kept |
| `rrweb` ([rrweb](https://github.com/rrweb-io/rrweb) and rrweb-player) | rrweb contributors | MIT | recorder injected unmodified into each page a journey opens; its player replays the events beside the report | kept |

### Design sources

Read when a look is drawn or reviewed (`eaos/analysis/target_state/look.py`): fetched to the person's computer at a
pinned commit, never copied into this repository or redistributed.

| Entry | Copyright | Licence | Used how | Licence text |
| --- | --- | --- | --- | --- |
| `ui-ux-pro-max` ([UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)) | nextlevelbuilder | MIT | its offline search script and CSV data read | kept |
| `awesome-design-md` ([awesome-design-md](https://github.com/voltagent/awesome-design-md)) | VoltAgent | MIT | reference DESIGN.md files read as directions, never copied as a brand | kept |
| `tweakcn-themes` ([tweakcn-theme-picker](https://github.com/BankkRoll/tweakcn-theme-picker)) | BankkRoll | MIT | theme token files read | kept |
| `anthropic-skills` ([Anthropic skills](https://github.com/anthropics/skills), frontend-design only) | Anthropic, PBC | Apache-2.0 | its SKILL.md read as guidance; the repository's other skills are not used | kept |

A project EAOS builds also gets components and fonts installed by their own package managers, never by EAOS's copy:
[shadcn/ui](https://github.com/shadcn-ui/ui) (shadcn, MIT) by its own CLI, and
[Fontsource](https://github.com/fontsource/fontsource) (MIT tooling; the fonts it serves under OFL-1.1) by npm.

## Method sources

Ideas and prompt structure adapted into EAOS's own words; no code is copied.

| Source | Copyright | Licence | Used how | Licence text |
| --- | --- | --- | --- | --- |
| [security-audit-skill](https://github.com/cloudflare/security-audit-skill) | Cloudflare, Inc. | MIT | ideas and prompt structure adapted for the logic-flaw hunt (`eaos/analysis/logic_flaws/`) | kept |

## Evaluated and not used

- **Serena**: licensed per component, SolidLSP under MIT and the Serena application under GPL-3.0-or-later. CodeGraph
  (Apache-2.0) already covers its capability, so a copyleft obligation would buy nothing.
- **ArchMind**: ships no licence file, so every right is reserved. Its architectural ideas informed our thinking; none
  of its code is present here.
