# Studio redesign: plan

Status: proposal, waiting for the owner's approval (2026-10-17). Nothing here is built yet.

The Studio is rebuilt from zero around one idea: **it is a light governance console for one or more projects, not a
full application.** Every feature the Studio has today stays (the inventory below is the parity list), but the
person reaches any of them in at most three clicks, pages are nearly empty by default, and nothing is loaded before
it is needed. When the new Studio reaches parity it replaces the old one, and the old one is deleted with its tests,
build output and references.

## 1. What is wrong today (measured, not felt)

| Problem | Today |
|---|---|
| Too many places | 41 routes, 15 sidebar entries, 9 System tabs, about 586 components |
| One check, many doors | 9 different buttons start a check, each opening the same preview sheet |
| Following a check is scattered | `/scan`, `/runs/:id`, `/runs`, `/decisions`, plus a banner, a pill, a toast and the tab title |
| Questions shown three times | toast, run page and `/decisions` |
| Two histories | `/runs` (runs) and `/history` (checks) |
| Same framing repeated | Today / Change / Target on 7 views; the pipeline says Current / Ideal / Gap |
| Missing controls | AI on/off and the assistant cannot be chosen before a check; cost is not shown during or after it |
| A dead end | Home "Next step", the palette and "Check again" send the check without `fresh`, the back end answers "already checked", and the Studio jumps to `/scan` showing the old run |
| One project only | no list or switch, although the owner has five projects |
| Weight | 6 MB built, 60% of it Mermaid (only used by the document reader); `library.json` 13.8 MB with base64 images and `functions.json` 4.6 MB sent whole; the server rebuilds every section on start (about 221 MB resident) |
| Naming | one action has six names ("Check the project now", "Re-scan now", "Start the check", ...); "speed" means both a path and a mode |

## 2. Principles

1. **Three clicks to anything.** Every item in the parity list has a written click path of three or fewer.
2. **One place per job.** Each job (start a check, follow it, answer the person's questions, approve a branch) has
   exactly one home. Other places may *point* to it, never repeat it.
3. **Empty by default.** A page shows the one thing the person needs now and folds the rest. Sub-pages live in a
   collapsible group in the sidebar (drawer), closed until the person opens it.
4. **The page explains itself.** Every page starts with one plain sentence saying what it is and what to do next.
   One name per action, everywhere.
5. **Phone first, desktop wide.** Every page is designed at 390 px first, then 768 and 1440. On the phone a bottom
   bar with at most five tabs.
6. **Light.** Budgets enforced by the build (section 6).
7. **Governance stays strict.** The three owner-only questions (branch, consent to run the app, accept/undo), the
   confirm tokens and the protected branches do not change; only where they appear changes.

## 3. Information architecture

Five sections, plus a small footer. Sub-pages are folded under their section.

```
Top bar:  [Project ▾]  ........  [● live status]  [Waiting for you (n)]  [Search ⌘K]  [Assistant]
Sidebar:
  1. Overview
  2. Checks            (Run a check · History)
  3. Problems
  4. Fixes             (Plan · Branches · Target and gaps)
  5. System ▸          (folded) Structure: Map · Functions · Pipeline
                                Behaviour: Code paths · Data · Behind the scenes
                                Interface: Screens · Journeys
                                Infrastructure
  ─────
  Library · Settings
Phone bottom bar: Overview · Checks · Problems · Fixes · More
```

### 3.1 Overview
The verdict in one sentence, the score, the three numbers that matter, and **one** "next step" button. Nothing
else is open; the map preview and the Today → Target strip are gone from here (they live in System and Fixes).

### 3.2 Checks: one page for the whole check
Replaces `/scan`, `/tools`, `/runs`, `/history` and the scan sheet.
- **Idle:** one card "Check the project" with the paths as chips (Complete, Security, Code, Screens, Load), and the
  assistant (on / off / which) and speed mode in a folded "Options". Estimated time and cost shown before Start.
  Always sends `fresh`, so the dead end above disappears.
- **Running:** the same page turns into the live view: a step strip, the current stage, time left, cost so far,
  questions asked inline. The top bar's live dot is the only other place that shows it.
- **History:** one list of every check and fix run, newest first; open one to see it, pick two to compare.
- **Tools** appear here only when something is missing.

### 3.3 Problems
List with search and one filter button; a card opens in a side panel (a full page on the phone) with its evidence
inside it. Selecting cards raises one bar: Fix · Verify · Explain · Plan.

### 3.4 Fixes: everything that changes the code
Replaces Change, Plans, Gaps, Bridge, Timeline, Branches and the accept/undo sheets.
- Top: **Waiting for your approval**: delivered branches with Accept / Undo (the same guarded preview as today).
- **Plan:** the steps in order, each with "Fix this step".
- **Branches:** the full branch control (compare, merge, delete, restore, cleanup, protection).
- **Target and gaps:** today against target, gaps and operations, the ideal plan. One framing, "Today / Target",
  with a "show the difference" switch, used on every view.

### 3.5 System: understanding the project (folded)
The nine views kept, grouped into four categories. They share one layout: a canvas or list, one inspector
component (instead of about eight), the Today / Target switch, and a steps view on the phone.

### 3.6 Waiting for you (top bar, one inbox)
Every question the person must answer in one list: run questions, report decisions, consent to run the app, and
branches waiting for approval (linked to Fixes). Replaces the toast, `/decisions` and Home's "waiting" box; a run
page only links here.

### 3.7 Library, Settings, Assistant
- **Library:** documents, images, diagrams. Diagrams drawn once when the report is written, not in the browser.
- **Settings:** language, theme, time zone, assistants installed and their usage and cost, tools, branch
  protection. Replaces `/assistant` and the duplicate switches.
- **Assistant:** one chat panel opened from the top bar (proposals still go through the preview).

### 3.8 Projects
A project switcher in the top bar listing every project under `~/.eaos/projects`, with its score and last check.
New back-end endpoint; switching moves the Studio to that project's server (started if needed).

## 4. Click paths (examples; the full list is part of phase 6)

| Job | Clicks |
|---|---|
| Start a check | Checks → Start (2) |
| Start a security-only check | Checks → Security chip → Start (3) |
| See a running check | live dot (1) |
| Answer a question | Waiting for you → answer (2) |
| Fix three problems | Problems → select → Fix (3 + confirm) |
| Accept a delivered branch | Fixes → Accept (2 + confirm) |
| One function's call graph | ⌘K → name (2), or System → Functions → function (3) |
| Compare two checks | Checks → History → pick two (3) |

## 5. Visual direction

From the UI/UX Pro Max design-system search (`--variance 2 --motion 2 --density 6`): **Minimalism / Swiss**,
for professional tools and dashboards. Applied as:
- Neutral slate surfaces, one accent colour for the single primary action per page, semantic colours for severity
  only. Light and dark, the first choice follows the system.
- IBM Plex Sans Arabic / Plex Sans and Plex Mono (already bundled, no network fonts).
- 4 px spacing grid; 44 px minimum touch target; contrast 4.5:1; visible focus; reduced motion respected; subtle
  150 to 250 ms transitions, no decorative motion.
- Navigation pattern after Cloudflare and Vercel dashboards: a short sidebar with collapsible groups, an
  account/project switcher at the top, the page title and one primary action at the top of each page.
- The result is written to `design-system/eaos-studio/MASTER.md` and judged by EAOS's own screen review.

## 6. Weight budgets (enforced by the build)

| Budget | Target |
|---|---|
| JavaScript before the first page shows | ≤ 200 KB compressed |
| Total built Studio | ≤ 2 MB (today 6 MB) |
| Mermaid in the browser | none: diagrams rendered to SVG with the report |
| Big sections (`functions`, `library`) | served in pages and per document by the API, never whole |
| Server start | sections rebuilt only when their source changed |
| Server memory at rest | measured before and after; target below today's 221 MB |

The stack stays (React, TanStack Router, react-aria-components, the bundled fonts): it is not where the weight
comes from, and react-aria carries the accessibility and right-to-left behaviour.

## 7. Phases

Each phase on its own branch from `develop`, merged and shown to the owner before the next.

0. **This plan**, approved by the owner.
1. **Clickable prototype** (static, on real report data) of the shell, Overview, Checks, Problems and Fixes at
   390 and 1440 px, served on a dev URL. The owner reviews it before any production code.
2. **Shell, Overview, Checks** in the new Studio (`studio-next/`, served beside the old one), plus the back-end
   pieces they need: `fresh` always on, assistant choice and cost estimate before a check, live cost.
3. **Problems, Fixes, Waiting for you.**
4. **System views, Library, Settings, project switcher**; paged `functions` and `library`; diagrams as SVG.
5. **Proof:** EAOS's own screen and code paths run on the new Studio; every item of the parity list has a click
   path of three or fewer; budgets pass.
6. **Swap and delete:** `studio-next/` becomes `studio/`; the old source, its built output in `eaos/data/studio`,
   its tests and every reference are removed; a test fails if any old route or file name comes back.

## 8. Parity list (from the inventory)

Every one of these keeps a home in the new Studio:
- **Pages:** Home; Problems and evidence; System map, infra, journeys, hidden, code paths, flows, data, pipeline,
  functions and one function, screens and one screen; Change, ideal, timeline, bridge, gaps and one gap, plans, plan,
  step, task, operation; branches; live check, tools, runs and one run, assistant, decisions; history, one check,
  compare; library, document reader, image.
- **Actions (46 in `docs/studio-actions.json`)** and the four verbs on a selection, each through the one preview
  sheet with its confirm token.
- **Shell:** search over everything (⌘K), language and direction, theme, time zone, snapshot mode (opened from a
  file), deep links that keep the page state, selection with ranges and groups, the chat with direct control and
  build-from-a-plan.
