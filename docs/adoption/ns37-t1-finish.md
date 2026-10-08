# NS37.T1, finishing the shell: what was adopted

Checked on 2026-10-08 against the npm registry (version, release date, licence of the exact tarball) and the
projects' repositories. Inputs: the honest limits of the first NS37.T1 pass (a 572 kB `studio.js`, the Studio's own
gate script instead of the shared screen gate, no Lighthouse and no CSS drift counts) and the P3 gate of the v2 plan
(`eaos-dev/planning/studio-v2/MASTER-PLAN.md`: Lighthouse mobile ≥ 90 performance and 100 accessibility, bundle
budgets).

## Dropping the translations of locales the Studio does not speak

React Aria Components ships its built-in strings (a dialog's dismiss button, a search field's clear button, the
date and number formats' labels) for 34 locales, each a separate module that every component imports. The Studio
speaks Arabic and English only; the other 32 locales are dead weight in `studio.js`.

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| `@react-aria/optimize-locales-plugin` | Apache-2.0 | 2.1.0 (2026-10-08) | Adobe, released with React Aria (2.0.2 on 2026-09-01, nightlies daily) | The documented way (react-spectrum.adobe.com, Internationalization, "Optimizing bundle size"): a Vite plugin, through unplugin 2, that resolves every React Aria locale module outside the listed languages to an empty module. `locales: ['ar', 'en']` keeps every Arabic and English region |
| `@react-aria/parcel-resolver-optimize-locales` | Apache-2.0 | 1.x | Adobe | The same for Parcel; the Studio builds with Vite |
| A `resolve.alias` regex in `vite.config.ts` | ours | — | — | Possible, but it would copy the plugin's list of React Aria package folders and break silently when that list changes |

**Decision**: adopt the plugin with `locales: ['ar', 'en']` (language only, so `ar-u-nu-latn` and `en-GB`, the
locales the Studio sets in `I18nProvider`, keep their strings). It runs only at build time; nothing it does reaches
the shipped files except the smaller bundle. `unplugin` comes with it as its only dependency (MIT, 2.x, maintained by
the UnJS organisation) and is pinned by the lock file.

**Pinned**: `@react-aria/optimize-locales-plugin@2.1.0`

## The Studio's screen gate

**Candidates**

| Candidate | Licence | Version (date) | Maintenance | Fit |
|---|---|---|---|---|
| `tools/studio_gates.py` with `eaos/screens/` (pinned Playwright 1.63, axe-core 4.13, Lighthouse, @projectwallace/css-analyzer from `upstreams/toolchain.json`) | ours over Apache-2.0 / MPL-2.0 / MIT | on develop since 0.0.3 | EAOS | The shared gate of every Studio screen and mockup: overflow with layout width, initial scroll, axe, 44 px targets, clipped text, phone height budget, Lighthouse mobile scores, CSS drift counts |
| `studio/scripts/gates.mjs` (the first NS37.T1 pass) | ours | — | — | A second copy of the same geometry checks with a few the shared gate lacked: overlays opened before the check (palette, sheet), Arabic letter-spacing, script errors, no request outside the page's origin, the language and theme actually applied, the page opened from a file |

**Decision**: one gate. The checks only the Studio's script had are generic and move into the shared gate
(`eaos/templates/screens/audit.mjs` and `eaos/screens/audit.py`): page actions run before the measurement, the
Arabic letter-spacing count, script errors, blocked requests and the expected `dir`/`lang`/theme of a variant.
`tools/studio_gates.py --studio` lays out the shipped build with a report's data and runs the shared gate over the
Studio's routes (`studio/gate-matrix.json`); `studio/scripts/gates.mjs` is removed. No new package: every tool is an
EAOS toolchain entry.

**Pinned**: none
