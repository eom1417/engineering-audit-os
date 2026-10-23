# EAOS design system

The visual and interaction system of the EAOS governance console. Lead's final version, merged from the three
concepts (origins D1 / D2 / D3, L = lead). Implemented in `prototype/assets/tokens.css` (every value below) and
`prototype/assets/app.css` (every component below). Builders use only these tokens and classes.

## 1. Direction

**A clear ledger, signed in ink.** Paper rows on a cool page, hairlines instead of boxes, one plain sentence as the hero
of every screen, and colour spent only on meaning: lapis ink for the person's move, teal for EAOS at work, dotted violet
for the assistant's opinion, a quiet ember ramp for severity.

References, structure only (never the look): Linear (one inbox, list + detail, keyboard), Vercel (one card that matters,
one page per run), Stripe (a sentence before the numbers; the persistent test-mode banner, our offline banner), GitHub
(the merge box: checks, target, protected rules, one confirm), Cloudflare and Supabase (a sidebar that keeps many
sub-places findable without showing them; a single accent on a grey ladder), Raycast (one box that searches and asks).

Tools used (all local): UI/UX Pro Max `--design-system` (D1, D2, D3: "Minimalism & Swiss Style", kept; dark-default and
acid-green identity rejected) and, by the lead, `--domain ux` for confirmation dialogs, focus in modals, fixed-element
stacking, bulk actions and loading without layout shift (all applied below); the `dataviz` palette validator on the
severity ramp (rerun on the final values) and on the operations set; WCAG contrast computed for every pair below.

## 2. Colour

### 2.1 Rules

1. **Accent = your move.** The primary step, the waiting count, links, focus, selection, owner-only acts. When nothing
   waits for the person, a calm screen shows the accent at most twice (the next step and the count). (D1, D2)
2. **Teal = EAOS at work**: the running dot, progress fills, the running stage. Never a button. (D3)
3. **Dotted violet = the assistant**, always a hypothesis: its decisions, recommendations from AI nodes, its words. (D3)
4. **Green / red = outcomes only** (passed, done, merged / failed, refused, destructive). **Amber = conditions**
   (stale, behind, partial, stalled, expiring).
5. **Never colour alone**: every state ships with a glyph and a word; severity with its bar glyph and its word.
6. Dark lifts surfaces by tone (canvas < surface < raised), shadows only deepen. The first visit follows the system
   theme; a choice is remembered.

### 2.2 Tokens, light and dark (WCAG contrast computed on the final values)

| Token | Light | Contrast (light) | Dark | Contrast (dark) | Meaning |
|---|---|---|---|---|---|
| `--canvas` | `#F5F7FA` |  | `#0D1219` |  | page |
| `--surface` | `#FFFFFF` |  | `#141B24` |  | rows, panels, sheets |
| `--raised` | `#FFFFFF` |  | `#1A2330` |  | menus, drawers (dark lifts by tone) |
| `--sunken` | `#EEF1F6` |  | `#0A0F15` |  | code, tracks, wells |
| `--hover` | `#F0F3F8` |  | `#1E2835` |  | row hover and press |
| `--line` | `#E2E7EE` | 1.24 on surface | `#263142` | 1.32 on surface | hairlines (decorative, never a control edge) |
| `--line-strong` | `#7B8597` | 3.72 on surface; 3.47 on canvas | `#66748C` | 3.66 on surface; 3.97 on canvas | control edges: inputs, checkboxes, switches (3:1 non-text) |
| `--ink` | `#101B2C` | 17.28 on surface; 16.10 on canvas; 15.26 on sunken | `#E9EEF5` | 14.86 on surface; 16.12 on canvas; 16.49 on sunken | text |
| `--ink-2` | `#3C4859` | 9.28 on surface; 8.65 on canvas | `#B7C1CF` | 9.52 on surface; 10.33 on canvas | secondary text |
| `--ink-3` | `#586477` | 5.99 on surface; 5.58 on canvas; 5.29 on sunken; 5.39 on hover | `#8E9AAC` | 6.08 on surface; 6.59 on canvas; 6.75 on sunken; 5.23 on hover | meta, captions |
| `--ink-off` | `#9AA4B4` | 2.52 on surface | `#5D6879` | 3.07 on surface | disabled only (exempt) |
| `--accent` | `#2A49C8` | 7.28 on surface; 6.78 on canvas | `#8DA2FF` | 7.22 on surface; 7.82 on canvas | your move: primary step, waiting count, links, focus, selection |
| `--accent-hover` | `#213BA6` | 9.37 on surface | `#A6B6FF` | 8.88 on surface | hover / pressed |
| `--accent-soft` | `#EBF0FF` |  | `#1C2A4A` |  | selected rows, waits-for-you rows |
| `--accent-ink` | `#2340B5` | 7.46 on accent-soft | `#A9B8FF` | 7.43 on accent-soft | accent text on accent-soft |
| `--live` | `#0A6F7A` | 5.89 on surface; 5.10 on live-soft | `#3EC1CB` | 8.00 on surface; 6.44 on live-soft | EAOS at work: running dot, progress fill |
| `--live-soft` | `#E1F2F3` |  | `#10303A` |  |  |
| `--ai` | `#6942CF` | 6.40 on surface; 5.58 on ai-soft | `#B197FF` | 7.21 on surface; 6.20 on ai-soft | the assistant (always a hypothesis) |
| `--ai-soft` | `#F2EDFE` |  | `#2A2148` |  |  |
| `--ok` | `#17764A` | 5.64 on surface; 4.92 on ok-soft | `#4CC283` | 7.72 on surface; 6.36 on ok-soft | outcomes: done, passed, merged |
| `--ok-soft` | `#E4F3EB` |  | `#13301F` |  |  |
| `--caution` | `#915708` | 5.88 on surface; 5.35 on caution-soft | `#F0B44A` | 9.35 on surface; 7.88 on caution-soft | stale, behind, partial, stalled, expiring |
| `--caution-soft` | `#FFF3DC` |  | `#33270F` |  |  |
| `--danger` | `#BF2630` | 5.94 on surface; 5.17 on danger-soft | `#FF7275` | 6.53 on surface; 5.79 on danger-soft | failed, refused, destructive |
| `--danger-soft` | `#FDEBEC` |  | `#3A1C21` |  |  |

On-colour pairs:
- white on accent (light) 7.28; on accent-hover 9.37; dark `--on-accent` #0D1219 on accent 7.82
- white on danger (light) 5.94; dark `--on-danger` on danger 7.08
- ink on accent-soft: light 15.18, dark 12.18; ink on ai-soft: light 15.08, dark 12.78
- focus ring (accent) against canvas: light 6.78, dark 7.82

Focus ring: 2 px `--accent` outline, 2 px offset (filled buttons add a 2 px surface gap): 6.78:1 on the light canvas,
7.82:1 on the dark canvas. Scrim: `rgb(16 27 44 / .45)` light, `rgb(0 0 0 / .6)` dark.

### 2.3 Severity: one ember hue, calm at the bottom

Ordinal, so one hue whose darkness and chroma rise with severity (L). Critical and high are vivid; medium and low are
near-neutral taupe so the 202 medium rows of the sample never paint the page (D2's aim) while the ramp stays a true
ordinal scale (D3's rigour). The glyph is four bars filled from the start side (critical 4, high 3, medium 2, low 1;
info is an outline ring) and the word is always written beside it.

| Severity | Light | Contrast on surface | OKLCH L | Dark | Contrast on surface | OKLCH L |
|---|---|---|---|---|---|---|
| critical | `#8A1C23` | 9.25 | 0.42 | `#FF9088` | 7.92 | 0.77 |
| high | `#B3401A` | 5.73 | 0.53 | `#F07A45` | 6.25 | 0.71 |
| medium | `#9E8178` | 3.58 | 0.63 | `#9C7F74` | 4.70 | 0.62 |
| low | `#BFAEA7` | 2.14 | 0.76 | `#655550` | 2.45 | 0.46 |
| info | `#8A94A4` | 3.06 | 0.66 | `#6F7B8F` | 4.05 | 0.58 |

`dataviz` validator, `--ordinal`, on critical..low: **light: all checks pass** (monotone lightness, adjacent ΔL ≥ 0.06,
light end 2.14:1 ≥ 2:1, hue spread 21°); **dark: all checks pass** (light end 2.45:1, hue spread 18°). Low sits under
3:1 on purpose: the glyph shape and the word carry it. Info is not part of the fill ramp (outline only).

### 2.4 Run and stage states (glyph + word; colour third)

| State | Glyph (sprite id) | Colour | Arabic | English |
|---|---|---|---|---|
| queued | open circle (`circle`) | ink-3 | ينتظر دوره | Waiting its turn |
| running | dot with a breathing ring (`.dot--live`; still under reduced motion) | live | يعمل | Running |
| paused | two bars (`pause`) | ink-2 | متوقف مؤقتًا | Paused |
| waiting for you | dot inside an accent ring (`.dot--you`) | accent | ينتظرك | Waits for you |
| done | check in circle (`check`) | ok | انتهى | Done |
| nothing changed | circle with a dash (`dash`), never green | ink-2 | لم يتغيّر شيء | Nothing changed |
| stopped | square (`stop`) | ink-2 | أُوقف | Stopped |
| failed | cross in circle (`fail`) | danger | لم يكتمل | Did not finish |
| stalled (30 s silent) | dot, amber (`.dot` + caution) | caution | لا رد منذ 30 ثانية | Not heard from for 30 s |
| skipped / not reached / not asked | dash, dimmed row | ink-3 | لم يُشغَّل / ليس في هذا الفحص | Skipped / Not in this check |
| replay | amber stamp "a replay, not a check running now" | caution | إعادة عرض | A replay |

### 2.5 Freshness (PRJ-04), one set

| State | Glyph | Colour | Chip words (EN) |
|---|---|---|---|
| fresh / fresh with only EAOS's accepted fixes | `check` | ok | Current, checked yesterday 18:44 |
| behind, dirty, branch moved, EAOS updated | `warn` | caution | Changed since: 3 commits |
| other branch | `branch` | caution | The check is of develop; you are on feature-x |
| rewritten | `fail` | danger | The checked commit is gone from history |
| unknown (not git, unreachable, older report) | `info` | ink-3 | Unknown: <reason> |

### 2.6 The AI marker and provenance

- **AI block** (`.ai-block`): `--ai-soft` background, a 3 px **dotted** `--ai` rule on the start edge, the label
  "Your assistant" with the `ai` glyph, and the sentence "a hypothesis until the checks confirm it" the first time on a
  page. Tag form: `.tag--ai` (dashed violet outline).
- **Provenance grammar** (PLN-13, maps): rules = solid outline, planned by the assistant = dotted outline, not measured
  = hollow (1 px dashed `--line-strong`). Traced link = solid, possible link = dotted, where records stop = hollow node.
- **Owner-only**: the seal glyph (`seal`) with "Only you decide" (`.tag--owner`, `.owner-band`). Used only on acts
  G1 reserves for the person.

### 2.7 Operations (maps: today, change, target)

Retain is quiet grey ("no change"); the other five are categorical in a fixed order, the glyph inside the node is
mandatory: introduce `plus`, rebuild `retry`, merge (two lines joining), modify (tilde), delete `minus`.

| Operation | Light | Dark |
|---|---|---|
| introduce | `#1E9A6A` (3.57) | `#22A375` (5.42) |
| rebuild | `#E0791F` (3.03) | `#D9772B` (5.47) |
| merge | `#B8428C` (5.00) | `#D763A8` (5.15) |
| modify | `#2F6FDB` (4.75) | `#5A8EF0` (5.41) |
| delete | `#D23C3C` (4.72) | `#E25858` (4.76) |
| retain | `#586477` (5.99) | `#8E9AAC` (6.08) |

`dataviz` validator (adjacent): light passes with CVD 7.7 in the 6-8 band (glyph mandatory, it is); dark passes all.
On maps any two may touch, so the legend lists only what is drawn and "Show only one operation" is always offered.
Sequential magnitude (findings bands, files) uses one hue in five steps from the surface tone: ember for findings,
lapis for neutral size. Never a rainbow.

## 3. Type (Arabic first)

One family for both scripts: **IBM Plex Sans Arabic** 400 / 500 / 600 / 700 (its Latin serves English), **IBM Plex
Mono** 400 / 500 for real identifiers only (paths, commits, branches, ids, code), always isolated left to right
(`<bdi class="mono">`). Bundled in `assets/fonts`, split Arabic / Latin by `unicode-range`, `font-display: swap`.

| Token | Arabic size / line | English line | Weight | Use |
|---|---|---|---|---|
| `lede` | 24 / 38 phone, 30 / 46 desktop | 32 / 38 | 600 | the page's sentence, one per page, `text-wrap: balance` |
| `figure` | 40 / 44 | 44 | 600, tabular | the score, one per page at most |
| `title` | 20 / 32 | 28 | 600 | detail titles (one problem) |
| `head` | 17 / 28 | 24 | 600 | section heads, sheet titles, waiting questions (18 / 30) |
| `body` | 16 / 27 | 24 | 400 (500 row titles) | text; never below 16 on the phone |
| `small` | 14 / 23 | 20 | 400 | second lines, meta, help |
| `label` | 14 / 20 | 20 | 500 | buttons, chips |
| `caption` | 13 / 20 | 18 | 500 | tab labels, tags, badges: the floor |
| `mono` | 13 / 20 | same | 400 | identifiers |
| `code` | 13 / 21 | same | 400 | evidence excerpts, diffs |

Rules: Arabic is never letter-spaced; English lede -0.01em. No all-caps, no eyebrow labels, no meta strings joined by
dots. Emphasis by weight (Arabic has no italic). Western digits always; tabular figures in counts, timers, columns;
proportional in sentences. Reading measure 62-72 characters.

## 4. Space and layout

- **Spacing** (4 base): 4, 8, 12, 16, 20, 24, 32, 40, 48, 64 (`--s1`..`--s16`). Page gutter 16 phone, 32 desktop.
- **Targets**: 44 x 44 minimum on every control outside running text on a touch screen (< 1024 px): small buttons
  (`.btn--sm`), segmented controls, filter chips, summaries and inputs grow to 44 px; small stand-alone links (section
  links, timeline times, inline "Open the stage", ids in a meta line) keep their look and get an invisible hit area
  (`::after`, inset −12 px); checkboxes and radio cards use their label as the target; map nodes carry a 22 px
  transparent ring, and the explorer zooms with a list twin. Pointer screens keep the denser 36 px sizes. Checked by
  `tools/targets.cjs` (0 offenders at 390 px, Arabic and English). 8 px between targets.
- **Rows**: 56 (one line) / 76 (problem row) minimum on the phone, hairline separated inside a panel, never a card each.
- **Breakpoints**: 390 base; 768 (sheets get a max width of 600); 1024 (sidebar, drawers, dialogs, split views);
  1440 (detail panel 560).
- **Widths**: reading column 720 (Waiting, a run, documents), Status 1120 (main + 340 aside), lists 1240 (list + 560
  panel), drawer 480, dialog 540, sidebar 256.
- **Logical properties only** (`inset-inline-start`, `margin-inline-end` ...): one stylesheet serves RTL and LTR.
  Directional icons mirror (`.icon--dir`); code blocks are always left to right.

## 5. Radius, elevation, layers

| Radius | Value | Use |
|---|---|---|
| `--r-xs` | 4 | tags, checkboxes, code chips |
| `--r-sm` | 8 | buttons, inputs, chips, segmented controls |
| `--r-md` | 12 | panels, cards, code blocks |
| `--r-lg` | 18 | sheets and dialogs (phone sheets: top corners only) |
| `--r-full` | 999 | count badges, the live strip, filter chips |

Elevation: **e0** flat (pages, rows, hairlines); **e1** panel = surface + 1 px `--line` + `--shadow-1`; **e2** floating
(live strip, selection bar, toasts) `--shadow-2`; **e3** sheets, drawers, dialogs `--shadow-3` over the scrim. Dark:
the raised tone carries depth. Layers: sticky 10, strip 20, nav 30, popover 40, sheet 50, toast 60, confirm 70.

## 6. Motion

Only `opacity` and `transform` move; motion answers an action or shows that EAOS is working.

| Token | Value | Use |
|---|---|---|
| `--t-press` | 100 ms ease-out | hover, press, checkbox, switch |
| `--t-fade` | 140 ms ease-out | fold chevron, content swaps |
| `--t-enter` | 220 ms cubic-bezier(.2,.8,.2,1) | sheet, drawer, dialog, toast in |
| `--t-exit` | 150 ms cubic-bezier(.4,0,1,1) | out (about 70 % of enter) |
| `--t-progress` | 400 ms linear | progress `scaleX` when a progress event arrives |
| breathe | 2 s opacity loop | the one running dot; paused under reduced motion |

**Reduced motion** (`prefers-reduced-motion: reduce`): every duration becomes 0 except fades of at most 100 ms; the
running dot is a still ring; folds open at once (height is never animated); skeletons never shimmer; maps jump; the
replay steps without tweening. Lists never animate a reorder.

## 7. Icons

One inline SVG sprite in `index.html` (about 50 symbols, 24 grid, 1.6 stroke, round joins), drawn for EAOS in the
Phosphor manner: `status waiting problems activity understand search ask ai chev chev-down back branch check tick clock
seal pause play stop filter group select globe moon sun copy warn x plus minus file lock info terminal retry offline
layers book history screen code gear tool folder app external note dash fail circle map`. 20 px in rows and buttons,
24 px in the tab bar. Always beside a word, except Close, Back and the search button, which carry accessible names.
Mirror in Arabic: back, chevrons, forward arrows (`.icon--dir`). Never mirror: check, clock, play, search, branch, code.
No emoji, no illustration.

## 8. Data visualisation for large sets

- **Is it a chart at all?** One value is a sentence or a figure ("68, fair"), not a gauge. A trend needs 4 measured
  checks: the sample has one scored check, so the text says "The trend appears after the next check" (D3).
- **Problems by severity**: one 100 % bar (10 px, 2 px surface gaps, critical at the start) with a legend of direct
  counts that add up to the total; zero values stay visible, dimmed; each value opens the filtered list. While counting:
  a sunken track and "Counting…", never 0.
- **Health areas**: meters (6 px sunken track, neutral `--ink-2` fill, ticks at 40 / 60 / 75 / 90), the score and band
  word in ink. Not measured: an open track, the hollow "Not measured" tag, the reason and the producing step.
- **Over time** (HIS): step line 2 px for score and fixes taken in; stacked columns with 2 px gaps for open by severity;
  a check with no value is a labelled gap, never zero; one axis per chart.
- **Lists at scale**: rows, not tables, on the phone; 50 rows at a time with "Show 50 more"; counts always "n of total";
  facets over 12 values fold; the list never reorders under the reader (PRB-11).
- **Maps** (56 components, 282 links): SVG on EAOS's computed layout; at rest only the heaviest 40 links (1 / 1.5 /
  2.5 px by weight, ink at 18 %); focus keeps the neighbourhood and fades the rest to 20 %; at most 500 SVG marks, then a
  canvas layer with an invisible keyboard list; past that EAOS groups first. The phone shows a still preview and opens
  the explorer on demand. Every map and chart has a list or table twin and a key listing only what is drawn.
- **Functions** (7,759 in the sample): never one graph; a paged table with shortcuts (most complex, with problems, most called); one
  function shows 5 columns of calls, 6 per column, "and n more". **Pipelines** over 200 stages draw what is in view.
- **Interaction**: hover and keyboard focus show the same readout; a tap pins it on the phone; zoom 0.7x-8x with buttons
  as well as gestures; chart code loads with its view only.

## 9. Components and their states

Class names are in `app.css`. Every interactive state below is implemented in the prototype unless marked (builders).

**Page anatomy** (`.page`, `.context`, `.lede`, `.guide`, `.actions`, `.section`): context line (back link or chips) →
lede (the sentence; numbers are links underlined in accent) → guide (one plain sentence: what this is, what to do) →
one primary step + at most one quiet option + a note → rows → closed folds. The `h1` is the lede; focus moves to it on
navigation without a visible ring.

**Buttons** (`.btn`): `--primary` (accent fill; the next step, Send, Start, Accept), `--secondary` (outline), `--quiet`
(accent text), `--plain` (ink-2 text), `--danger` (only the final Reject / Delete), `--icon` (44 px). The seal glyph
inside a primary marks an owner-only act. States: default, hover, pressed, focus-visible (2 px ring + gap), disabled
(sunken fill, `--ink-off`, and always a reason nearby or in `title` / `aria-describedby`), busy ("Updating the
preview…" in place, width kept). Labels name the act and its count; "…" means a preview opens first.

**Chips** (`.chip`, `--ok`, `--caution`): context facts that open their place (branch, freshness); 36 px visual,
44 px hit. **Filter chips** (`.fchip`): active filters, removable one by one, "Clear all" last.

**Tags** (`.tag`): `--you` (needs you), `--eaos` (EAOS fixes), `--state`, `--ok`, `--caution`, `--danger`, `--live`,
`--ai` (dashed violet), `--owner` (seal, "Only you decide"), `--nm` (dashed: not measured), `--free`. **Count**
(`.count`): accent pill, tabular digits, its accessible name is the full sentence.

**Severity glyph** (`.sev .sev--high`): four bars + word; `sev(level, false)` keeps the word for screen readers only.

**Segmented control** (`.seg`, `.seg--count` stacks label over count): who acts, list / plan, language, theme, group.
`aria-pressed` or `aria-current` marks the chosen one.

**Field** (`.field`): search icon, input, 44 px, every word must match, Arabic-aware. **Checkbox** (`.check`), **radio
card** (`.opt`, `.opt--off` for protected / unavailable with its reason), **switch** (`.switch`), **textarea**
(`.input`, counter "312 of 4,000", draft kept). Focus rings on the visual box.

**Rows and lists** (`.panel.rows`, `.row`, `.row--you`, `.prow`): states default, hover, focus, selected (accent-soft +
checked box), open in the split view (ink start bar), left out (reason line), waits for you (accent start bar and soft
background). Problem row: checkbox, severity glyph and word, state tag, who-acts tag at the end; title (2 lines);
meta line with id, area, first file.

**Fold** (`details.fold`): chevron, title, one-line summary, closed by default; `aria-expanded` native. **Facts**
(`dl.facts`): key / value grid.

**Sheets** (`.sheet`): one component, five kinds. `sheet` and `drawer` rise from the bottom on the phone; on the
desktop the drawer docks at the end side (480). `dialog` is a bottom sheet on the phone and a centred dialog (540) on
the desktop (confirms). `search` is full height on the phone, a centred palette on the desktop. `menu` is the project
menu. Head (title, sub, Close), body (scrolls), sticky foot. Focus moves in (to `[data-autofocus]` or the sheet), Tab
is trapped, Esc and the scrim close, focus returns to the opener, the page behind does not scroll. A sheet is an
address (`?sheet=name:arg`): back closes it.

**Search or ask** (`?sheet=search`, D48): a light global search over small indexes only (places, decisions, problems,
actions, runs, branches, plan steps, your app's screens, code paths, gaps, components, documents by title, path and
headings); results in groups (`role=group`, labelled by a visible group name, no list role), arrows move a highlight,
Enter opens. It never loads the functions section or the library text: "Search deeper" offers Search functions for
"…" (opens Functions), Search the check's records for "…" (full text, PRB-13) and Ask your assistant.

**Floating assistant** (`assets/assist.js`, `.fab`, `.assist`): one button on every screen except the full Ask view
and the opening pages; Ctrl/Cmd+I toggles it, Esc closes it. Phone: a 52 px circle (`--ai` glyph on `--surface`, e2) at
the end corner above the tab bar; it rises above the live strip and the selection bar and never covers a primary action
(`tools/targets.cjs` checks at the top and bottom of every screen); pages keep 64 px more bottom padding. Desktop: a
48 px pill with the label "Ask your assistant" at the end corner of the content area. Pressed, it opens the panel:
- phone: a modal bottom sheet (88 % height, scrim, Tab kept inside, focus on the sheet so no keyboard pops up);
- desktop: a non-modal side panel, 400 px at the end side; from 1280 px the page reflows beside it (split views fold
  to one column), below that it overlays the end side; the button hides while the panel is open.
Anatomy: head (AI glyph, "Ask your assistant", "Claude Code is ready; it reads and changes nothing", **Open the full
view**, Close); the shared conversation (`EAOS.askAPI`, the same turns as `#/ask`: what it read, the answer as it is
written, up to 4 proposals that open their normal previews, depth and cost per answer), the owner-only "Let it act for
an hour" fold and the cost footer; the composer pinned at the bottom: the **context chip** of the page it was opened
from (a problem, a run, a branch, a map node, a document, a place; its × asks about the whole project instead), three
**suggested questions** for that page (a sideways row of 44 px buttons), the text box, Quick / Balanced / Deep and Send.
States: ready; thinking (the answer streams with the live dot, Send reads "Thinking…" and waits); failed (the reason and
Retry); no ready assistant (why, `claude login` with Copy, Assistants and cost); offline copy (it explains and offers
"How to open it live"). Address `?ask=1` opens it on any screen.

**Verb preview** (`?sheet=verb:<verb>[:target]`): free band "Free preview: nothing has changed yet" → what it does →
included / left out with why → files, batches, estimate with its basis, risk with why, if it fails → where it is
built and delivered (always open; Change shows the branches, protected ones listed with the reason, not choosable) →
who runs it → owner switch "Accept it by itself" (changing it shows "Updating the preview…" then previews again) →
consent and cost notes → From the terminal fold. Foot: **Start: <verb> <n> problems**, Copy the request, "valid for
10 minutes, until 10:10". Disabled while the preview reports a problem or updates.

**Confirm sheet** (owner-only, irreversible; `?sheet=accept:<id>`, `reject:<id>`): owner band ("Only you decide.
Neither your assistant nor EAOS can decide this for you.") → the act in one sentence → the choices the confirmation
binds (merge target with protected branches shown and locked, delete after merging with "nothing is lost") → facts
(files that change, checks recorded). Foot: the **"I understand …" tick and the act button together**, Cancel first in
reading order and focused, the act button disabled until ticked, "valid until". States: preparing, ready, refused
(body replaced by the reason and one way on: Go to the newer branch / Preview again / Reload), expired, done (notice +
the card moves to Already decided). Danger fill for Reject / Delete; accent fill + seal for Accept / Merge / Protect.

**Waiting card** (`.wcard`): accent start bar; meta line (Only you decide, source, what it blocks); the question
(18 / 30); recommendation (AI block when it comes from the assistant); options as radio cards, recommended first and
tagged; Send the answer (disabled until chosen) and Answer in my own words; "Why is this asked?" fold. States: waiting,
chosen, own words open, saved ("Your answer is saved…" + the queued review), locked offline (copy the answer), fix card
(tests, files, closes, the diff fold, Accept… / Reject… / Open the run).

**Evidence and code** (`.fact`, `.code`, `.diff`): engine and rule, `file:line`, summary, excerpt with line numbers and
the cited line on an accent-soft band with a 3 px accent rule; "Line hidden: it holds a secret"; "No code: <reason>";
other places; diff lines with + / − signs as well as tints; bounded at 64 KiB with "only its start is shown".

**Live strip / live card** (`.live-strip`, `.side-live`): dot, one line, Follow; accent variant when it waits for you;
the card adds a progress bar (scaleX). **Selection bar** (`.selbar`): count, group name, Clear, the four verbs.

**Notices** (`.toast`, `--refusal`): one at a time, polite region, 5 s; refusals stay and say why and what to do.

**Banner** (`.banner`, `--caution`, `--offline`): one line under the header with its single action.

## 10. State templates (the same everywhere)

| State | Pattern | Example words (EN) |
|---|---|---|
| Empty | the lede says what will be here; one action fills it | "This project has not been checked yet." Check the project… |
| Loading | skeleton rows at real height, still (no shimmer), `aria-busy`; counts say "Counting…"; after 1 s the banner names the parts left | "Reading the last check: 3 of 27 parts left." |
| Not measured | hollow tag "Not measured", the reason in plain words, the step that produces it and its button; never 0, never "coming soon" | "No load test ran. The Speed and scale path measures it." |
| Running | teal dot, the step in words, n of N, time left with its basis | "Checking: stage 14 of 36, about 12 to 18 min left" |
| Waiting for the person | accent ring, the count rises, the strip turns accent, one press to the card | "The check waits for your sign-in, 14 min left" |
| Failed | what happened, what to do now, recoverable or not, technical detail one press away | "The last check stopped at engines: semgrep failed to install. What finished is kept." |
| Stale | amber banner with Check now… | "3 commits and 12 files changed on develop since this check." |
| Offline copy | banner; every action stays and opens "Open the live interface" (`eaos studio` + the request to copy); answers locked | "A read-only copy from yesterday 18:44." |
| Reconnecting | banner; the last good answer stays, marked | "Reconnecting. Showing what was true at 09:58." |
| Refused | the reason, its stable code in detail, one way on | "A newer fix waits on wave-4. Decide it first." |
| Irreversible | preview first, then the confirm sheet (above) | "I understand EAOS cannot undo a merge." |

## 11. Words, numbers, direction

- Every visible word comes from the one dictionary `EAOS.DICT`: defined in `assets/app.js` (shell, Status, Waiting,
  Problems) and extended, before any screen draws, by `assets/words-ac.js` (keys `ac.`) and `assets/words-un.js`
  (keys `un.`), Arabic and English side by side; `tools/sweep.cjs` fails on a missing word.
  Plurals are objects: Arabic `{zero, one, two, few, many, other}` chosen by `Intl.PluralRules('ar')` (so "مشكلة
  واحدة، مشكلتان، 3 مشاكل، 107 مشاكل، 223 مشكلة"), English `{one, other}`.
- Western digits with comma grouping in both languages; times in the device's zone, relative ("yesterday 18:44") with
  the exact day, time and zone on press.
- Report text keeps its own words; paths, symbols and settings inside it are isolated left to right (`rich()`), with
  break points after `/` and `.` so long paths wrap on a phone.
- Gulf-friendly plain Arabic, short sentences, the person addressed directly ("ينتظرك", "قرارك وحدك").

## 12. Accessibility checklist (binding)

axe-core (WCAG 2.0 / 2.1 / 2.2, A and AA) reports **zero** violations over 31 screens and sheets × 390 / 1440 × Arabic /
English × light / dark (`tools/axe.cjs`). Patterns that keep it at zero: scroll regions (`.code`, wide tables) are
keyboard-focusable and named (`tabindex="0"`, `role="region"`, an `aria-label`; done once after every render by the
core); every `role="progressbar"` has a name; a link that switches a view marks its on state with `aria-current`, never
`aria-pressed` (that belongs to real toggle buttons); search results are labelled groups, not headings inside a list role.

Contrast ≥ 4.5:1 for text and ≥ 3:1 for control edges (tables above); visible focus everywhere; 44 px targets; skip
link; landmarks (banner, navigation, main, complementary); one `h1` per screen; sheets are modal dialogs with trapped,
restored focus; Esc closes; Ctrl/Cmd+K opens the box; Shift-click range; live announcements at most one per 3 s
(newest wins); reduced motion honoured; works in light and dark, Arabic and English, 390 to 1440.

## 13. Building a screen (for the two builders)

1. Read `IA.md` (what lives where) and `prototype/SCREENS.md` (your screens, their addresses and features).
2. Add your words to `EAOS.DICT`, both languages: `app.js` for the shell, `words-ac.js` (`ac.`) or `words-un.js`
   (`un.`) for the places. No visible word in a screen file.
3. Write `assets/screens/<place>.js`: `EAOS.screen({ id, path: '/activity/run/:id', place: 'activity', title, render(ctx) })`
   returns the page markup using the anatomy and classes above; `EAOS.sheet(name, { kind, render(arg) })` for sheets;
   `EAOS.act(name, fn)` for `data-act` / `data-change` / `data-input` handlers; `EAOS.refresh()` after a state change.
   Helpers: `t`, `tn`, `L`, `num`, `esc`, `rich`, `icon`, `code`, `sev`, `chk`, `fmtWhen`, `href`, `setQuery`, `toast`.
4. Load it in `index.html`; a later `EAOS.screen()` with the same address replaces the earlier one. List it in `DONE`
   in `assets/screens/todo.js` and run `node prototype/tools/screens-md.js > prototype/SCREENS.md`.
5. Check: `PLAYWRIGHT_BROWSERS_PATH=/workspace/eaos-beta-trial/tools/browsers node prototype/tools/shoot.cjs <dir>
   name=/your/address` (390 and 1440, Arabic and English, light and dark) and look at every picture;
   `node prototype/tools/sweep.cjs`, `node prototype/tools/sheets-sweep.cjs`, `node prototype/tools/targets.cjs` and
   `node prototype/tools/axe.cjs` report no issue; add or update the feature's recipe in `tools/presses.cjs`, run it,
   and `python3 prototype/tools/clicks.py` regenerates the IA table from the measurement and still passes.
