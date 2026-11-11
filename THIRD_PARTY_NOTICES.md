# Third-party notices

EAOS does not vendor, link or redistribute any third-party analysis tool. It **runs** pinned tools the person installs
(`eaos tools install`), as separate processes, reads their structured output, and records which tool produced what. No
tool's source is copied into this repository.

The one list of these tools, with their pinned versions, commits, checksums and licences, is
`eaos/data/toolchain.json`: every entry is named below under the same name. Licence texts kept in this repository are
in `upstreams/licenses/` (`<name>-LICENSE`, and `<name>-NOTICE` where the project ships one); a tool without a file
there is marked "not kept" and its licence is read at its repository.

## The pinned tools (`eaos/data/toolchain.json`)

### Reading the code

| Entry | Copyright | Licence | Used how | Licence text |
| --- | --- | --- | --- | --- |
| `jscpd` ([jscpd](https://github.com/kucherenko/jscpd)) | Andrey Kucherenko | MIT | JSON report read | kept |
| `semgrep` ([Semgrep](https://github.com/semgrep/semgrep)) | Semgrep, Inc. | LGPL-2.1 | EAOS's own rules (`eaos/rules/semgrep/`) and the rule set below; SARIF read | kept |
| `semgrep-rules` ([semgrep-rules](https://github.com/semgrep/semgrep-rules)) | Semgrep, Inc. | Semgrep Rules License v1.0 | fetched to the person's computer for non-commercial use and read by Semgrep; never copied here or redistributed | kept |
| `gitleaks` ([Gitleaks](https://github.com/gitleaks/gitleaks)) | Zachary Rice | MIT | secrets redacted; SARIF read | kept |
| `presidio` ([Presidio](https://github.com/microsoft/presidio) analyzer, with [spaCy](https://github.com/explosion/spaCy) and its `en_core_web_sm` model) | Microsoft Corporation; ExplosionAI GmbH | MIT (the model: MIT) | imported by EAOS's own script in its own environment; string literals read, values masked, none written | kept |
| `dependency-cruiser` ([dependency-cruiser](https://github.com/sverweij/dependency-cruiser)) | Sander Verweij | MIT | the JavaScript and TypeScript import graph, with TypeScript installed beside it; JSON read | kept |
| `ast-grep` ([ast-grep](https://github.com/ast-grep/ast-grep)) | Herrington Darkholme | MIT | EAOS's own rule pack (`eaos/rules/ast-grep/`); JSON stream read | kept |
| `lizard` ([Lizard](https://github.com/terryyin/lizard)) | Terry Yin and other contributors | MIT | CSV read | kept |
| `knip` ([knip](https://github.com/webpro-nl/knip)) | Lars Kappert | ISC | every plugin off; JSON report read | kept |

### Running and trying the app

All run on the app's isolated copy on the person's computer, with a database of the run's own.

| Entry | Copyright | Licence | Used how | Licence text |
| --- | --- | --- | --- | --- |
| `schemathesis` ([Schemathesis](https://github.com/schemathesis/schemathesis)) | Kiwi.com and contributors | MIT | pinned; no stage runs it today | kept |
| `supabase` ([Supabase CLI](https://github.com/supabase/cli), `supabase db advisors`) | Supabase, Inc. and contributors | MIT | pinned; no stage runs it today | kept |
| `playwright` ([Playwright](https://github.com/microsoft/playwright)) | Microsoft Corporation | Apache-2.0 | drives Chromium per page, viewport, language and theme | kept, with NOTICE |
| `pytest` ([pytest](https://github.com/pytest-dev/pytest)) | Holger Krekel and others | MIT | runs the behaviour lock's approval tests, with ApprovalTests (Apache-2.0) installed beside it | kept |
| `k6` ([k6](https://github.com/grafana/k6)) | Grafana Labs | AGPL-3.0 | pinned, unmodified, as a separate process; no stage runs it today | kept |
| `mailpit` ([Mailpit](https://github.com/axllent/mailpit)) | Ralph Slooten | MIT | catches the e-mail the app sends from its copy | kept |
| `jscodeshift` ([jscodeshift](https://github.com/facebook/jscodeshift)) | Meta Platforms, Inc. and affiliates | MIT | runs the codemods of mechanical cards on an isolated copy; it parses code, never runs it | kept |
| `axe-core` ([axe-core](https://github.com/dequelabs/axe-core) and [@axe-core/playwright](https://github.com/dequelabs/axe-core-npm)) | Deque Systems, Inc. | MPL-2.0 | injected unmodified into the page under test, which MPL-2.0 permits without further obligation; WCAG violations read as JSON | kept |
| `lighthouse` ([Lighthouse](https://github.com/GoogleChrome/lighthouse)) | Google LLC | Apache-2.0 | mobile JSON report of one address read (`eaos/features/app_run/adapters/screens/audit.py`) | kept |
| `rrweb` ([rrweb](https://github.com/rrweb-io/rrweb) and rrweb-player) | rrweb contributors | MIT | recorder injected unmodified into each page a journey opens; its events kept as JSON for the assistant and a later replay with rrweb-player from local files | kept |

### Design sources

Fetched to the person's computer at a pinned commit, never copied into this repository or redistributed. They are
pinned in the toolchain, and no stage reads them today.

| Entry | Copyright | Licence | What it holds | Licence text |
| --- | --- | --- | --- | --- |
| `ui-ux-pro-max` ([UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)) | nextlevelbuilder | MIT | an offline search script and CSV data | kept |
| `awesome-design-md` ([awesome-design-md](https://github.com/voltagent/awesome-design-md)) | VoltAgent | MIT | reference DESIGN.md files | kept |
| `tweakcn-themes` ([tweakcn-theme-picker](https://github.com/BankkRoll/tweakcn-theme-picker)) | BankkRoll | MIT | theme token files | kept |
| `anthropic-skills` ([Anthropic skills](https://github.com/anthropics/skills), frontend-design only) | Anthropic, PBC | Apache-2.0 | the frontend-design SKILL.md; the repository's other skills are not fetched | kept |

## Evaluated and not used

- **Serena**: licensed per component, SolidLSP under MIT and the Serena application under GPL-3.0-or-later. EAOS's
  own graph already covers its capability.
- **ArchMind**: ships no licence file, so every right is reserved. Its architectural ideas informed our thinking; none
  of its code is present here.
