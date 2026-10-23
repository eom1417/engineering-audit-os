# EAOS governance console: final information architecture

Lead of the design committee, 2026-10-18. Merged from the three concepts in `committee/designer-{1,2,3}/`, on the
brief (`brief/STANDARDS.md`, `brief/FEATURES.md`: 198 features, `brief/sample-data.json`). Origins are marked
**D1**, **D2**, **D3**; **L** marks a decision the lead made when the three differed. The foundation that implements
it is in `prototype/` (see `prototype/SCREENS.md`); the visual system is in `DESIGN-SYSTEM.md`.

## 1. What was merged, and why

The three concepts agree on the skeleton: five places and a project menu, one sentence and one step per screen, one
home per job, previews before anything that changes code, owner-only decisions in one inbox. They differ in names,
accent, where the plan and history live, the search, the live indicator and the governance gesture. The choices:

| Question | Chosen | Origin | Why |
|---|---|---|---|
| First screen name | **الحالة / Status** | D3 | Plain and exact in both languages. "Now / الآن" (D2) collides with "running now" in Activity; "Overview / الوضع" (D1) suggests a dashboard. |
| The inbox name | **ينتظرك / Waiting for you** (tab label "Waiting") | D1, D2 | It also holds the sign-in wait, which is not a decision, so D3's "قراراتك / Your decisions" would be untrue. |
| Problems | **المشاكل / Problems** | D1, D2 | The Gulf owner says مشاكل; the data already says "223 مشكلة". "Card" is never shown. |
| Starting and following work | **النشاط / Activity** | all three | Agreed. |
| Understanding the system | **افهم / Understand** | D1, D2 | Names the purpose; "استكشف / Explore" (D3) names a browsing habit. |
| Tab order | Status, Waiting, Problems, Activity, Understand | D1 | What is true, what needs me, what is wrong, what runs, how it is built. The waiting count sits second, near the thumb. |
| The plan (steps, waves, fix a step) | A second view of **Problems** (List / Plan) | D2, D3 | Plan steps are groups of problems and end in Fix; one place for "what to fix and in which order". |
| History of checks | **Understand, Records** group; the trend sentence on Status points to it | D1 | History is understanding, not a run. Activity holds runs only. |
| Branches | **Project menu**, with the **branch chip on Status** opening it in one press | D3 chip, D1 menu | Branches are weekly work, but merge / delete / protect stay at 3 presses. |
| Tools, assistants, your app, settings | Project menu pages | D1 | Setup, used rarely, out of the daily places. |
| Starting anything that is not a check | One **launcher** sheet ("What EAOS can do now", then every action, then Expert) | D3 | One door for 44 actions; recommended first (PRJ-08), searchable (RUN-13). Status's "More work…" opens the same sheet, under the same name. |
| Search and chat | **One box: "Search or ask"** (Ctrl/Cmd+K); Ask is a mode of it | D2 | One control instead of two in the header; the last results are always "Ask your assistant" and "Search the check's records". |
| Live indicator | **Live strip** above the tab bar (phone), **live card** at the sidebar foot (desktop); accent when it waits for you | D2, D3 | Visible on every screen without crowding the header; the same object on both sizes. |
| Desktop navigation | **Sidebar** (start side: right in Arabic) with Understand's groups under it | D1, D2 | Scales to the Understand groups; Cloudflare / Supabase restraint. D3's top tabs could not show sub-places. |
| Accent strategy | **One accent means "your move"** (lapis ink); a second hue only for **EAOS at work** (teal); the **assistant** is dotted violet | D1/D2 principle, D3 hues | The person can tell at a glance what is theirs, what the machine is doing, and what is only the assistant's opinion. |
| Severity | **One ember hue whose chroma rises with severity**: critical and high are vivid, medium and low near-neutral taupe; always with the bar glyph and the word | L (D2's calm + D3's ordinal rigour) | 202 medium rows never paint the page, and the ramp still passes the ordinal validator (one hue, monotone lightness). |
| Page anatomy | Context line, **lede** (the sentence, numbers are links), **guide** (what to do), **one primary step**, rows, closed folds | D3 lede, D1/D2 guide | Every screen explains itself in one sentence and one step; nothing else is visible until asked. |
| Governance gesture | Free **preview** (drawer) → for owner-only irreversible acts a **confirm sheet**: owner band, the binding choices, "I understand" tick and the act button together in the footer, focus on Cancel | D1 band, D3 sheet, D2 consequence wording | Calm and explicit; the act button names the consequence ("Accept and merge into develop"); a centred dialog on desktop marks the moment. |
| Accept / Undo naming | **اقبل / ارفض, Accept / Reject** (the catalogue action stays `undo`) | L | For a non-developer "Undo" reads as reversing their own action; "Reject" says exactly that the fixes never enter the project. |
| Dense data | Sentence before numbers; one 100% bar, not a chart wall; lists of rows paged 50 at a time; maps preview then explorer, always with a list twin; no line chart under 4 checks | D3 dataviz, D1 paging, D2 calm | Stays light on the machine and readable on a phone. |
| Provenance on target views | Rules = solid, assistant = dotted, not measured = hollow; same grammar on maps | D3 | The person can always tell rules from AI (PLN-13). |

Rejected, with reason: D3's margin rule for "measured" on every row (decoration without new meaning: measured is the
default); D2's approval page with two choice cards plus a second step (the confirm sheet is clearer and reused for every
irreversible act); D1's facet rail always open on the desktop (a quieter page wins; filters are one press away).

## 2. The shape

```
[project name v]  Project menu: language, theme, this project's pages, other projects
 |- الحالة   Status .......... the sentence, the next step, what waits / runs, problems at a glance, health, 4 folds
 |- ينتظرك  Waiting for you . fixes to accept or reject, run questions, your sign-in, decisions from the check
 |- المشاكل  Problems ........ List | Plan  ->  one problem  ->  Fix / Verify / Explain / Plan (preview)
 |- النشاط   Activity ........ Check the project, More work, Now, In line, Recent, All runs  ->  one run
 '- افهم     Understand ...... 4 groups, 23 views  ->  one item
 Global: Search or ask (Ctrl/Cmd+K), waiting count, live strip / card, banner slot, notices, selection bar
```

Three levels, never four: a **place**, a **view**, an **item**. Anything deeper is a fold inside the item, a sheet,
or a pointer placed one level up (D1).

## 3. What lives where

| Place | Its sentence (lede + guide) | What lives here | Never here |
|---|---|---|---|
| **الحالة / Status** `#/status` | "223 مشكلة، منها 107 يصلحها EAOS وحده." + "Where your project stands, and the step that fits now." | Context line: branch chip (PRJ-05, opens Branches) and freshness chip (PRJ-04, opens its drawer). Lede (PRJ-01). Next step + More work… (PRJ-08). Now rows, only when true: what waits (DEC-01), what runs or waits its turn (RUN-01). Problems at a glance (PRJ-03). Health: a row and drawer on the phone, an open aside card on the desktop (PRJ-02, HIS-02). Folds: Where things stand (PRJ-06, FIX-14, project note), Your journey (PRJ-07, BLD-03/04), About this check (PRJ-09, stages, SET-06), What was measured (PRJ-10). First-time and loading states (PRJ-11/12). | Lists, forms, answers |
| **ينتظرك / Waiting for you** `#/waiting` | "4 أمور تنتظرك." + "Everything that needs your answer or approval is here. Nothing else waits for you." | Groups appear only when they hold something, in urgency order: Your sign-in (SGN-03/04/05), Questions from runs (DEC-02..06, FIX-08, FIX-14), Fixes ready for your decision (FIX-09, FIX-11..13, SCR-04), Decisions from the check (DEC-07..09). Fold: Already decided (DEC-10/11). Each item also has its own address `#/waiting/<id>`. | Anything that does not need the person |
| **المشاكل / Problems** `#/problems` | "223 problems. EAOS fixes 107 by itself; 116 need you." + "Pick problems, then choose what EAOS does with them." | View **List**: who acts, search, Filter (facets + Group), Select a group, the assistant band, rows, selection bar with the four verbs (PRB-01..05, 11, 12; SEL; FIX-01). **One problem**: why, the assistant's decision, where, evidence with code, in the plan, same file, note (PRB-06..10, 14, 15; PLN-05). View **Plan** `#/problems/plan`: steps, waits-for, waves, Fix the next step (PLN-02..06, FIX-15, BLD-03). | Answers (point to Waiting), runs |
| **النشاط / Activity** `#/activity` | "Nothing is running. The last check took 13 minutes, yesterday." + "Start a check here, or pick work for EAOS." | **Check the project...** (the only home of CHK-01..04, SGN-01/02/08). **More work...** (the launcher: PRJ-08, RUN-13, APP-01..03, BLD-01/02, FIX-16). Now (RUN-01, CHK-07/08/12, RUN-08), In line (RUN-02), Recent and All runs (RUN-03). One run `#/activity/run/<id>` (RUN-04..12, CHK-08..11, FIX-07/10, SCR-04, CHT-05) with its stage sheet. | Decisions (point to Waiting) |
| **افهم / Understand** `#/understand` | "How your project is built today, what it should become, and the record of every check." + "New here? Start with the story." | An index, four open groups (below). Every view has its own search and opens items in a sheet (phone) or an inspector (desktop). | Code-changing actions, except "Fix this gap / component", which open the normal Fix preview |
| **Project menu** (the project name) | "This project's setup, and your other projects." | Language and theme toggles (SET-01/02). This project: Branches (BRN, PRJ-05), Your app (APP state, SGN-02/06/07, consent kept), Assistants and cost (AST, CHK-06), Tools (CHK-05), Settings (SET-03/05/06/07, OFF-05). Projects on this computer (PJS-01..04). New project from a plan (BLD-01, opens the launcher action). | Daily work |

Understand index (each row: name, one line of purpose, a count; "Start here: the story" pinned on top):

| Group (AR / EN) | Views |
|---|---|
| **التغيير والهدف / Change and target** | The story: today, change, target, with its Bridge tab (PLN-01, PLN-10); Gaps (PLN-07/08); Operations (PLN-09); Ideal target (PLN-11..13); How EAOS decided (SYS-16) |
| **كيف بُني / How it is built** | Components (SYS-01..04, 18); Code paths (SYS-07/08); Functions (SYS-05/06); Data (SYS-09/10); Seen and unseen (SYS-11); Infrastructure (SYS-13); Pipelines, all stacked (SYS-14/15); Architecture and design (SYS-17) |
| **الشاشات / Screens** | Reviewed pages (SCR-01); Every screen and one screen (SCR-02/03, LIB-06); User journeys (SYS-12) |
| **السجلات / Records** | Library and a document (LIB-01..06); Report files (LIB-07); Checks over time, a past check, compare (HIS-01..07) |

Steps an assistant drives inside a run (Appendix H.1: `wait`, `fix_read/edit/skip`, `build_read/edit/skip`,
`blueprint_spec`, `extend_plan`) are never buttons on a page: they show as events in What happened, and are findable in
the launcher's Expert group marked "normally your assistant does these inside a run" (D2, D3).

## 4. Navigation

**Phone (390 px), drawn left to right; Arabic mirrors.** Top bar 56 px, tab bar 64 px + safe area.

```
+--------------------------------------------------+
| [E engineering-audit-os v]                  [Q]  |  project menu | Search or ask
|  banner slot (only while true)                   |
|  context chips                                   |
|  LEDE: the sentence, numbers are links           |
|  guide sentence                                  |
|  [ the one primary step ]  quiet option          |
|  rows ... closed folds ...                       |
|                                                  |
|  ( * Checking: stage 14 of 36 ...   Follow > )   |  live strip, only while something runs or waits
| Status | Waiting (4) | Problems | Activity | Und. |  tab bar; the selection bar replaces it while ticking
+--------------------------------------------------+
```

- Tabs always carry icon and word; Waiting carries the DEC-01 count, its accessible name is the full sentence.
- Rows push pages; previews, filters, facts and menus rise as **bottom sheets** (max 92 % height, drag handle, Close,
  Esc, focus trapped and restored). A sheet has an address (`?sheet=...`), so the system back closes it.
- Back returns to the same scroll position and filters. Leaving Problems clears the selection (SEL-03).

**Desktop (1440 px).** Sidebar 256 px on the start side; content centred (reading 720, Status 1120, lists 1240).

```
+------------------------------------------------------------------+--------------+
|  content: the same anatomy                                        | [E project v]|
|  Problems: list column | detail panel 560 (sticky, own scroll)    | [Q Search  K]|
|  previews: end drawer 480 | confirms: centred dialog 540          |  Status      |
|                                                                   |  Waiting  (4)|
|                                                                   |  Problems    |
|                                                                   |  Activity    |
|                                                                   |  Understand  |
|                                                                   |    4 groups  |
|                                                                   |  live card   |
|                                                                   | [ع][EN] (moon)|
|                                                                   |  Live 0.0.36 |
+------------------------------------------------------------------+--------------+
  (Arabic shown: the sidebar is on the right; English mirrors it to the left)
```

- Keyboard (SET-07): Ctrl/Cmd+K opens the box; arrows and Enter in results; Esc closes the sheet or clears the
  selection; Shift-click selects a range; Tab walks every control; the skip link is first; focus moves to the page's
  heading after each navigation (D2 `focus-on-route-change`).

## 5. Global elements

- **Project button** (phone top bar, desktop sidebar top): opens the project menu (D1).
- **Search or ask** (D2), a **light global search** (D48): an empty query lists the places; a query searches only small,
  already-loaded indexes: places (every screen's title in both languages), waiting decisions, problems (title, id,
  places, kind, why), catalogue actions, runs, branches, plan steps, your app's screens, code paths, gaps, components,
  and documents by **title, path and headings**. Up to 40 results, grouped by kind (`role=group` with a label); every
  word must match, Arabic-aware folding (SRC-02). It **never loads** the large sections from the box: the functions
  section (about 4.6 MB) and the library's text. One level deeper, always offered under "Search deeper": **Search
  functions for "…"** (opens Functions with the query, which loads on first open), **Search the check's records for
  "…"** (full text of facts, claims and report sections, PRB-13, free) and **Ask your assistant: "…"**.
- **Floating assistant** (the owner's request, 18 Oct): a small button on every screen (not on the full Ask view, not
  before a project opens; Ctrl/Cmd+I). Phone: a 52 px circle at the end corner above the tab bar, lifted above the live
  strip and the selection bar. Desktop: a labelled pill at the end corner of the content area. One press opens the
  conversation **in place**: a side panel on the desktop (from 1280 px the page reflows beside it and stays usable), a
  bottom sheet on the phone. It carries the page's context (a problem, a run, a branch, a map node, a document…) as a
  removable chip and suggests three questions for that page. It is the **same conversation** as the full Ask view
  (`#/ask`, "Open the full view"; still reachable from Search or ask): proposals open their normal previews, depth per
  turn, what it read, the cost footer, the owner-only direct control. States: ready, thinking, failed (Retry), no ready
  assistant (why, `claude login`, Assistants and cost), offline copy (how to open it live). Address: `?ask=1`.
- **Waiting count** (DEC-01): one number everywhere (tab, sidebar, Status row, window title, announcements) =
  run questions + waiting decisions + waiting branches + a sign-in wait.
- **Live strip / live card** (ACT-01, D2/D3): only while something runs or waits; teal dot for EAOS at work, accent
  ring and accent background when it waits for the person; one press opens that run or that wait.
- **Banner slot** (D3): exactly one of offline copy, stale check, reconnecting, partial report, loading parts.
- **Notices** (ACT-02): one line, 5 s, polite region, the action's own words; refusals stay until closed and say why.
- **Selection bar** (SEL): count, group name, Clear, and Fix / Verify / Explain / Plan; replaces the tab bar on the
  phone, floats under the list on the desktop.
- **Window title** (ACT-04): "(14/36) Status - engineering-audit-os - EAOS" while watched work runs.

## 6. One home per job (others only point)

| Job | Its one home | Pointers |
|---|---|---|
| Start a check | Activity, **Check the project...** (the check preview) | Freshness drawer "Check now", empty Status, stale banner, the box |
| Start any other work | The **launcher** sheet ("More work..." in Activity) | Status "More work…", Project menu "New project from a plan", the box |
| Act on problems | The **verb preview** (one component for Fix, Verify, Explain, Plan) | Status next step, problem verb row, selection bar, assistant band, plan step |
| Follow any run | The **run page** | Live strip / card, Activity rows, notices, the waiting fix card |
| Answer a question or decision | Its **card in Waiting** | Status waiting row, a problem's decision block, a run's question event |
| Accept or reject a fix | The **fix card in Waiting** and its **confirm sheet** | Status waiting row, the launcher, the run's result, Branches row |
| Sign in to your app | **Waiting, Your sign-in** | Live strip (accent), the check page band |
| Choose the branch EAOS checks | **Branches, "EAOS checks develop: Change..."** | DEC-03 question (same chooser), freshness drawer |
| Ask your assistant | **One conversation**, shown in place by the **floating assistant** or in full at `#/ask` | The floating button on every screen, Search or ask's "Ask your assistant: …", "Ask about this run", "Ask why it failed" |

## 7. One name per action

| Action | Arabic | English | Opens |
|---|---|---|---|
| Check | افحص المشروع… / ابدأ الفحص | Check the project… / Start the check | check preview / starts |
| Other work | عمل آخر… | More work… | the launcher (Status and Activity) |
| The four verbs | أصلح… / تحقّق… / اشرح… / خطّط… | Fix… / Verify… / Explain… / Plan… | the verb preview |
| Confirm a verb | ابدأ: أصلح 3 مشاكل | Start: Fix 3 problems | starts the run |
| Accept a fix | اقبل… → اقبل وادمج في develop | Accept… → Accept and merge into develop | confirm sheet → merges |
| Reject a fix (catalogue `undo`) | ارفض… → ارفض واحذف الفرع | Reject… → Reject and delete the branch | confirm sheet → deletes, recovery point kept |
| Answer | أرسل الجواب / أجب بكلامي | Send the answer / Answer in my own words | saves (owner) |
| Run controls | أوقف مؤقتًا / كمّل / أوقف / أعد المحاولة | Pause / Resume / Stop / Retry | at once; Stop asks once |
| Follow | تابع | Follow | the run page |
| Hand-off | انسخ الطلب لمساعدك | Copy the request for your assistant | copies |
| Chat | اسأل مساعدك | Ask your assistant | the floating panel (same conversation as the full view) |
| Redo part of a check | أعد من هنا… | Redo from here… | its preview |

Plain words replace system words everywhere: problem (never card), check (not scan or audit), the branch EAOS checks
(not analysis branch), the branch open in your folder (not checkout), request for your assistant (not handoff), checks
(not gates), fix batch (not wave), not measured (never 0). A label ending in "…" opens a preview: nothing happens yet.

## 8. Addresses (LNK-01)

One page, hash routes, every state addressable: `#/<place>/<item>?<view state>&sheet=<name>:<arg>&lang=ar|en&theme=light|dark`.
Examples: `#/problems?who=you&sev=high,medium&group=area&q=toolchain`, `#/problems/TASK-006?sheet=fact:EV-7f2a91`,
`#/waiting?sheet=accept:branch-wave-3`, `#/activity/run/R-14?sheet=stage:engines`, `#/understand/components?mode=change&focus=eaos/facts`.
An address from an older check opens a calm page: what is missing, why, and the way back (S-53). Prototype-only state
variants use `?state=` (empty, loading, running, signin, stale, offline).

## 9. Main flows, with presses

A press is a tap, click or Enter that changes what is on screen; typing and scrolling are free. Counted from Status with
nothing open. **+c** = the governance presses after a preview (tick "I understand", then the act button); they are
never removed and not counted.

1. **First open, never checked** (PRJ-11): Status says "This project has not been checked yet. A check reads the code
   and changes nothing in it." **Check the project…** (1) opens the check preview (estimate "no basis yet", path
   Complete, Claude Code ready, Codex not signed in, sign-in way). **Start the check** (2). The live strip appears on
   every screen; it (3) opens the run. Offline copy: the only step is Copy the request for your assistant. A folder of
   several projects first asks which one (PJS-03, before Status opens).
2. **Check and follow**: Activity (1), Check the project… (2), optionally a path card, Start the check (3). Busy: the
   button reads "Queue the check" and says what holds the slot. Refused (assistant not answering, branch needed): the
   question replaces the Start button in place (DEC-05 / DEC-03). Following costs nothing: strip or card (1), a stage (2),
   Redo from here… (3). If the check needs the person, the strip turns accent ("waits for your sign-in, 14 min left").
   When it ends: notice "The check finished: 223 problems"; an open list does not reshuffle (PRB-11).
3. **Answer a decision**: Waiting (1), an option (2), Send the answer (3) → "Your answer is saved. Saving changes
   nothing yet: your assistant reviews it (read only)…" (DEC-09, G15). In my own words: Waiting (1), Answer in my own
   words (2), type, Send (3); never consent (G14).
4. **Fix what EAOS fixes by itself**: Status next step "Start a fix batch for 107 problems…" (1) opens the preview
   (problems, left out with why, files, 11 batches, estimate, risk with why, where it is built and delivered, who runs
   it, the owner switch "Accept it by itself", consent note, cost note, from the terminal). **Start: Fix 107 problems**
   (2). **2 presses.**
5. **Fix a chosen few**: Problems (1), tick a row (2), more ticks, **Fix…** in the selection bar (3), Start. A whole
   group: Problems (1), Select a group (2), "Security 26" (3), Fix…, Start. One problem: Problems (1), the row (2),
   Fix… (3), Start. After Start the selection clears, the strip shows "Fixing: 0 of 3 tried", a notice offers Follow it.
6. **Accept or reject a delivered fix**: Waiting (1): the card "Fixes are ready on their own branch,
   `eaos/develop/wave-3`: tests passed (38), 1 file changed, closes TASK-002". **Accept…** (2) opens the confirm
   sheet: owner band "Only you decide", merges into develop (main shown protected, not choosable), delete the branch
   after merging (on, recovery point kept), files that change, checks recorded, valid until 10:10; **+c**: tick "I
   understand EAOS cannot undo a merge", **Accept and merge into develop**. Reject… (2) opens the same sheet with "Its
   1 file never reaches your project" and a red **Reject and delete the branch** (+c). Refusals replace the body with
   the reason and one way on (a newer branch waits: Open it; the base moved: Preview again).
7. **Sign in to the app**: strip (accent) or Waiting (1), Sign in now (2): the live picture you drive, the keys row,
   What your app sent (codes and mails), then **I have signed in** (never automatic) or Go on without signing in.
8. **Switch project**: project button (1), a project (2): its own interface opens ("did not start in time, try again").
9. **Understand the system**: Understand (1), The story (2), a component (3) → Select its problems points to Problems,
   filtered. Or Understand (1), Components (2): phone shows a still map preview and the ranked list, Open the map for the
   explorer; desktop shows the map with an inspector.
10. **Offline copy**: the banner says what it is; every button stays and opens "Open the live interface" with
    `eaos studio` and the request to paste to an assistant (OFF-01..03, G22).

## 10. The three-click table (every feature ID)

**Measured, not claimed.** `prototype/tools/presses.cjs` presses every feature from Status in a headless browser at
390 px and 1440 px, in Arabic and in English, counts the presses and asserts the end state (`tools/presses-results.json`);
`prototype/tools/clicks.py` generates this table from those results and fails on a missing feature, a failed run or a
count above 3. Counting rule (D46): start on Status (a state-dependent feature starts on Status with its `?state=`; a
page that opens instead of Status starts there); one press = one click on a visible tab, row, button, chip, toggle or
fold; typing is free; the press that opens a preview counts; the governance tick and act after it are not pressed
(**+c**). The "Measured presses" column is the labels actually pressed (English run at 390 px). Phone / Desktop are the
larger of the Arabic and English counts.

| ID | P | Feature | Where it lives | Measured presses (English, phone) | Phone | Desktop | Origin |
|---|---|---|---|---|---|---|---|
| PRJ-01 | P1 | Verdict and next step | Status: the lede (verdict; its numbers open Problems) and the next step (1 opens its preview) | visible at once | 0 | 0 | D3 lede, D1/D2 next step |
| PRJ-02 | P1 | Health score | Status: Health row opens the Health drawer on the phone; the desktop aside shows it open; an area opens its problems | Health 68 of 100, fair | 1 | 0 | D2 aside, D3 meters |
| PRJ-03 | P1 | Problems at a glance | Status: Problems at a glance (severity bar, counts, who acts); each count opens the list on the same field | visible at once | 0 | 0 | D3 bar, D1 counts |
| PRJ-04 | P1 | Is this check still current? (freshness) | Status: freshness chip (state visible); its drawer has the facts, Check now and the copy instruction | Does this check still match the code? | 1 | 1 | D3 |
| PRJ-05 | P2 | The four branches, never mixed up | Status branch chip opens Branches, top block "the four branches"; desktop aside says it in one sentence when all agree | develop | 1 | 1 | D3 chip, D1 sentence |
| PRJ-06 | P1 | Where things stand (status and handover) | Status fold "Where things stand" (status, last batch, waiting branch, handover) | Where things stand | 1 | 1 | D1/D2 |
| PRJ-07 | P2 | The journey and its steps | Status fold "Your journey" | Your journey | 1 | 1 | D1/D2 |
| PRJ-08 | P3 | What EAOS can do now | Status "More work..." opens the launcher sheet (the same sheet and the same name as in Activity) | More work… | 1 | 1 | D3 launcher |
| PRJ-09 | P2 | Project facts | Status fold "About this check" (languages, files, lines, stages, scan, EAOS stamp) | About this check | 1 | 1 | D1 |
| PRJ-10 | P2 | What was measured and what was not (coverage) | Status fold "What was measured"; the same coverage row appears in place in any view missing its data | What was measured | 1 | 1 | D1/D3 |
| PRJ-11 | P1 | First time: nothing checked yet | Status in its first-time state: one sentence and Check the project | start `/status?state=empty`; visible at once | 0 | 0 | all |
| PRJ-12 | P2 | Data integrity states | In place on every view: loading banner, partial-report line, contract line; the missing-link page (S-53) | start `/status?state=loading`; visible at once | 0 | 0 | D1 |
| CHK-01 | P1 | Start a check | Activity: Check the project... (its one home, the check preview); pointers: freshness drawer, empty Status | Activity > Check the project… | 2 | 2 | all |
| CHK-02 | P2 | Check by path | Check preview: path cards, each saying what it looks at | Activity > Check the project… | 2 | 2 | all |
| CHK-03 | P2 | Speed mode | Check preview, Options fold: speed mode with its token warning | Activity > Check the project… > Options | 3 | 3 | D2 |
| CHK-04 | P2 | With or without AI, and which assistant | Check preview: the assistant row (with AI / rules only, which assistant), always visible | Activity > Check the project… | 2 | 2 | D1 |
| CHK-05 | P2 | Tools readiness and install | Project menu, Tools; a readiness line in the check preview when tools are missing | Project and settings > Tools | 2 | 2 | D1 |
| CHK-06 | P1 | Is my assistant ready? | Project menu, Assistants and cost (Ask again); also a row in every preview that uses an assistant | Project and settings > Assistants and cost | 2 | 2 | D1/D2 |
| CHK-07 | P1 | Live progress of the check | Live strip (phone) or sidebar live card (desktop) while running; Activity, Now | start `/status?state=running`; Checking: stage 14 of 36, about 12 to 18 min lef | 1 | 1 | D2/D3 |
| CHK-08 | P1 | Stage-by-stage progress | The running check's stages by dependency layer on Activity, Now; the last check's: Status, About this check, Show the stages | About this check > Show the stages | 2 | 2 | D3 |
| CHK-09 | P2 | One stage in detail | A stage opens the stage sheet: Status, About this check lists the stages that did not plainly finish; also Activity and the run page | About this check > Sort the problems | 2 | 2 | D1 |
| CHK-10 | P2 | Redo from a stage | Stage sheet: Redo from here... / Run its failed tools again... (from Status, About this check, a stage) | About this check > Sort the problems > Redo from here… | 3 | 3 | all |
| CHK-11 | P3 | Replay the last check | Activity, the last check's run: Replay x10 / x30 | Activity > 13 min > Replay ×10 | 3 | 3 | all |
| CHK-12 | P2 | Other flows' progress | Activity, Now: one line per flow; a line opens its run (same run page for every flow) | start `/status?state=running`; Activity > Checking the project | 2 | 2 | D1 |
| APP-01 | P2 | Run the app safely | More work..., Run your app safely... (consent asked in its preview); also Project, Your app | More work… > Run your app safely… | 2 | 2 | D3 launcher |
| APP-02 | P3 | Get the app running (with the assistant) | More work..., Get your app running with your assistant... | More work… > Get your app running with your assistant… | 2 | 2 | D3 |
| APP-03 | P2 | Record every screen (safety net) | More work..., Record every screen... | More work… > Record every screen… | 2 | 2 | D3 |
| RUN-01 | P1 | What runs now | Live strip / sidebar card on every screen while something runs; Activity, Now | start `/status?state=running`; visible at once (visible on every screen while a run holds the slot) | 0 | 0 | D2 |
| RUN-02 | P2 | The queue | Activity, In line (move up, move down, remove) | Activity | 1 | 1 | all |
| RUN-03 | P2 | Run history | Activity, All runs (search, filter) | Activity > All runs (10) | 2 | 2 | all |
| RUN-04 | P1 | One run: facts | Run page, Facts fold; on the desktop the facts sit in the run page aside | Activity > Fix: TASK-002 > Facts | 3 | 2 | D2 |
| RUN-05 | P1 | One run: what happened | Run page: What happened (the timeline) | Activity > Fix: TASK-002 | 2 | 2 | all |
| RUN-06 | P1 | One run: progress and screens | Run page: progress and the before/after screens | Activity > Fix: TASK-002 | 2 | 2 | all |
| RUN-07 | P1 | One run: result or error | Run page: result or error at the top, with what to do now | Activity > Fix: TASK-002 | 2 | 2 | D2 |
| RUN-08 | P1 | Run controls | Activity, Now card: Pause / Stop; all controls in the run header | start `/status?state=running`; Activity > Pause | 2 | 2 | D1 |
| RUN-09 | P2 | Handing a run to an assistant elsewhere | Run page in its hand-off state: the request in both languages, Copy, who took it | Activity > All runs (10) > Explain 5 problems | 3 | 3 | all |
| RUN-10 | P2 | It goes on by itself | Run page (and the strip text): "goes on by itself in 2 min with Codex" | start `/status?state=resume`; Claude Code reached its usage limit; it goes on  | 1 | 1 | D2 |
| RUN-11 | P3 | The run log survives | Run page, Facts fold: "the record is intact"; older runs keep a summary | Activity > Fix: TASK-002 > Facts | 3 | 2 | D1 |
| RUN-12 | P2 | Diagnose a run with the assistant | Run page of a failed or stopped run: Ask your assistant why | Activity > Fix: TASK-005, TASK-008, TASK-011 > Ask your assistant why | 3 | 3 | all |
| RUN-13 | P3 | Run any action of the catalogue | More work..., any action: its form inside its preview; "understand" actions answer in place | More work… > Where things stand | 2 | 2 | D3 |
| PRB-01 | P1 | The problem list | Problems: the list, in plan order, "showing n of total" | Problems | 1 | 1 | all |
| PRB-02 | P1 | Search problems | Problems: the search field, always visible | Problems | 1 | 1 | all |
| PRB-03 | P1 | Who acts | Problems: All / Need you / EAOS fixes, with the same counts as Status | Problems > Need you | 2 | 2 | all |
| PRB-04 | P1 | Filters with counts | Problems, Filter: facets with counts, zero values kept, active filters removable one by one | Problems > Filter | 2 | 2 | D2/D3 |
| PRB-05 | P2 | Group the list | Problems, Filter: Group (none, area, component, plan step) at the top of the same sheet | Problems > Filter > By area | 3 | 3 | D2 |
| PRB-06 | P1 | One problem | Problems, a row: the problem (phone page, desktop panel) | Problems > High | 2 | 2 | all |
| PRB-07 | P1 | The assistant's decision on a problem | One problem: "Your assistant's decision" (dotted AI block) | Problems > High | 2 | 2 | D3 AI marker |
| PRB-08 | P1 | Evidence with code | One problem: Evidence, the first fact with its code, the others one press away | Problems > High | 2 | 2 | D2 |
| PRB-09 | P2 | One evidence fact | One problem, Open the fact: the evidence sheet with every problem resting on it | Problems > High > Open the fact | 3 | 3 | all |
| PRB-10 | P2 | Its place in the plan | One problem: "In the plan" (step, task k of n, done when, waits for) | Problems > High | 2 | 2 | D1 |
| PRB-11 | P2 | A stable list while data changes | Problems: "A new check arrived. The list stays until you ask" with Show the changes | start `/status?state=newcheck`; Problems | 1 | 1 | all |
| PRB-12 | P1 | What your assistant will fix itself | Problems: the assistant band (Fix them all... / Select them) | Problems | 1 | 1 | all |
| PRB-13 | P3 | Ask the records | Search or ask: last row "Search the check's records for ..." | Search or ask > (type "toolchain") > Search the check's records for "toolchain" | 2 | 2 | D1/D2 |
| PRB-14 | P3 | What a change touches | One problem, a place: What changing it touches | Problems > High > What changing it touches | 3 | 3 | D2 |
| PRB-15 | P3 | Leave a note | One problem: Leave a note (fold); a project note: Status, Where things stand | Problems > High > Leave a note | 3 | 3 | all |
| FIX-01 | P1 | Four verbs on one problem, many, or a group | The verb row of a problem or the selection bar; Status's next step opens Fix on the fixable group at 1 | Problems > High > Fix… | 3 | 3 | all |
| FIX-02 | P1 | Preview of a verb | The verb preview (end drawer / bottom sheet); from Status's next step | Start a fix batch for 107 problems… | 1 | 1 | D1 |
| FIX-03 | P1 | Where a fix is built and delivered | Fix preview: "Where it is built and delivered", always open (governance never folds) | Start a fix batch for 107 problems… | 1 | 1 | D3 |
| FIX-04 | P2 | Which assistant runs it | Fix preview: "Who runs it" (pick when two are ready) | Start a fix batch for 107 problems… | 1 | 1 | all |
| FIX-05 | P2 | Accept automatically when the checks pass | Fix preview: owner switch "Accept it by itself when its checks pass" (seal) | Start a fix batch for 107 problems… | 1 | 1 | D1/D3 |
| FIX-06 | P1 | Start: confirmation rules | Fix preview: Start names verb and count; expired / moved base refuse in place with Preview again | Start a fix batch for 107 problems… | 1 | 1 | all |
| FIX-07 | P1 | Live fix progress | Live strip / sidebar card opens the fix run (problems tried of given, edits, gates, screens) | start `/status?state=fixing`; Fixing: 1 of 3 tried | 1 | 1 | D2 |
| FIX-08 | P2 | When the changes fail together | Waiting, Questions from runs: "The changes fail together" with its two choices | Waiting, 4 things wait for you > Examples of what a run may ask you | 2 | 2 | D1 |
| FIX-09 | P1 | Result of a fix | Waiting: the fix card (tests, files, problems it closes, the diff fold) | Waiting, 4 things wait for you | 1 | 1 | D1 |
| FIX-10 | P2 | Nothing changed | Activity, the run "Nothing changed" (the assistant's words, Retry) | Activity > All runs (10) > Fix: TASK-019 | 3 | 3 | all |
| FIX-11 | P1 | Accept: take the branch in | Waiting, the fix card: Accept... opens the confirm sheet | Waiting, 4 things wait for you > Accept… | 2 +c | 2 +c | D1 card, D3 confirm sheet |
| FIX-12 | P1 | Undo: throw the branch away | Waiting, the fix card: Reject... opens the confirm sheet (danger button, recovery point said) | Waiting, 4 things wait for you > Reject… | 2 +c | 2 +c | D3, L name |
| FIX-13 | P1 | Branches waiting for a decision | Waiting: Fixes ready for your decision, newest first | Waiting, 4 things wait for you | 1 | 1 | all |
| FIX-14 | P3 | Close a stuck batch | Status, Where things stand: Close this batch... (while a stopped batch is open); also the stopped run's page | Where things stand > Close this batch… | 2 | 2 | D1 |
| FIX-15 | P2 | Fix a plan step | Problems, Plan: Fix the next step... (every step row has its own Fix...) | Problems > Plan > Fix the next step: M01… | 3 | 3 | D2/D3 |
| FIX-16 | P3 | The batch tools (expert) | More work... (Status or Activity), the Expert group: batch tools ("normally your assistant does these"); also found by its search | More work… > Expert > Open a batch… | 3 | 3 | D2/D3 |
| DEC-01 | P1 | Everything that waits for me | Waiting; its count is on the tab bar / sidebar on every screen | Waiting, 4 things wait for you | 1 | 1 | D1/D2 |
| DEC-02 | P1 | A question from a run | Waiting, Questions from runs: the question card, options inline (option, then Send the answer) | Waiting, 4 things wait for you > Examples of what a run may ask you | 2 | 2 | D1 |
| DEC-03 | P1 | Owner-only: which branch EAOS works on | Waiting, Questions from runs: "Which branch should EAOS check and fix?" (same chooser as Branches, Change) | Waiting, 4 things wait for you > Examples of what a run may ask you | 2 | 2 | all |
| DEC-04 | P1 | Owner-only: consent to run the app | Waiting, Questions from runs: "May EAOS run your app in an isolated copy?" | Waiting, 4 things wait for you > Examples of what a run may ask you | 2 | 2 | all |
| DEC-05 | P1 | The assistant is not answering | Waiting, Questions from runs: "Your assistant is not answering"; also in place of the check's Start | Waiting, 4 things wait for you > Examples of what a run may ask you | 2 | 2 | D2 |
| DEC-06 | P2 | A different answer in my own words | Waiting, a card: Answer in my own words (1-4,000, draft kept, never consent) | Waiting, 4 things wait for you > Answer in my own words | 2 | 2 | all |
| DEC-07 | P1 | A report decision | Waiting: Decisions from the check | Waiting, 4 things wait for you | 1 | 1 | all |
| DEC-08 | P2 | Where report decisions come from | Waiting card: its source line, and the fold "Why is this asked?" | Waiting, 4 things wait for you > See the changes | 2 | 2 | D1 |
| DEC-09 | P1 | Answer a report decision and follow it | Waiting: pick an option, Send the answer: "Your answer is saved" and the queued review | Waiting, 4 things wait for you > Review it firstRecommended > Send the answer | 3 | 3 | D3 |
| DEC-10 | P2 | Already decided | Waiting: the fold Already decided (also #/waiting/decided) | Waiting, 4 things wait for you > Already decided | 2 | 2 | all |
| DEC-11 | P3 | Copy an answer | Already decided: Copy the answer for your assistant (works offline) | Waiting, 4 things wait for you > Already decided > Copy the answer for your assistant | 3 | 3 | all |
| BRN-01 | P2 | Branch inventory | Status branch chip opens Branches (also Project menu, Branches) | develop | 1 | 1 | D3 |
| BRN-02 | P2 | Find and filter branches | Branches: search and Your work / All | develop > Your work | 2 | 2 | all |
| BRN-03 | P2 | Compare with a base | Branches: Compare with... | develop > Compared with | 2 | 2 | all |
| BRN-04 | P2 | One branch in detail | Branches, a branch | develop > feature/login-by-hand | 2 | 2 | all |
| BRN-05 | P1 | Choose the analysis branch | Branches: "EAOS checks develop: Change..." | develop > EAOS checks | 2 | 2 | all |
| BRN-06 | P2 | Merge a branch, with preview | A branch: Merge... (preview, then confirm sheet) | develop > feature/login-by-hand > Merge into develop… | 3 +c | 3 +c | D3 |
| BRN-07 | P3 | Propose a conflict resolution | A branch: the quiet merge check finds conflicts, Propose a resolution... | develop > fix/report-links > Propose a resolution… | 3 | 3 | D2 |
| BRN-08 | P2 | Delete a branch | A branch: Delete... (unmerged commits need a second confirmation) | develop > feature/login-by-hand > Delete locally… | 3 +c | 3 +c | all |
| BRN-09 | P3 | Restore a deleted branch | Branches: fold Deleted branches, Restore... | develop > Deleted branches you can restore > Restore… | 3 | 3 | all |
| BRN-10 | P3 | Protect or unprotect a branch | A branch: Protect... / Remove protection... | develop > feature/login-by-hand > Protect… | 3 | 3 | all |
| BRN-11 | P3 | Clean up merged branches | Branches: Clean up merged branches... (the exact list, then confirm) | develop > Clean up merged branches… | 2 +c | 2 +c | all |
| BRN-12 | P3 | Refresh remote branches | Branches: "Fetched 2 hours ago", Refresh | develop > Refresh | 2 | 2 | D2 |
| PLN-01 | P1 | Today, change, target in one story | Understand: the story summary on top; The story | Understand > Start with the story | 2 | 2 | D1/D3 |
| PLN-02 | P1 | The plans and their progress | Problems, Plan | Problems > Plan | 2 | 2 | D2/D3 |
| PLN-03 | P2 | One plan step | Problems, Plan, a step | Problems > Plan > Shape domain into its target form: its problems  | 3 | 3 | D2/D3 |
| PLN-04 | P2 | Dependencies between steps | Problems, Plan: every step says what it waits for, with task counts | Problems > Plan | 2 | 2 | D2 |
| PLN-05 | P2 | One task and what it waits for | One problem: "In the plan" with what it waits for | Problems > High | 2 | 2 | D1/D2 |
| PLN-06 | P2 | Waves timeline | Problems, Plan, Waves | Problems > Plan > Waves | 3 | 3 | D2/D3 |
| PLN-07 | P2 | Gap register | Understand, Gaps | Understand > Gaps | 2 | 2 | all |
| PLN-08 | P2 | One gap | Understand, Gaps, a gap | Understand > Gaps > eaos | 3 | 3 | all |
| PLN-09 | P2 | The ordered operations | Understand, Operations | Understand > Operations | 2 | 2 | all |
| PLN-10 | P3 | Bridge from today to the target | Understand, The story, Bridge tab | Understand > Start with the story > Bridge | 3 | 3 | D1 |
| PLN-11 | P2 | The ideal target per view | Understand, Ideal target | Understand > Ideal target | 2 | 2 | all |
| PLN-12 | P3 | Re-plan the ideal | Understand, Ideal target, Plan it again... (preview) | Understand > Ideal target > Plan it again… | 3 | 3 | all |
| PLN-13 | P3 | How each target was made | The provenance line on top of every target view; its detail | Understand > Start with the story > Drawn by the rules, then planned on top by your  | 3 | 3 | D1, D3 rule grammar |
| SYS-01 | P1 | Components map: today, change, target | Understand, Components (map: today / change / target) | Understand > Components | 2 | 2 | all |
| SYS-02 | P2 | One component | Components, a component (sheet; desktop inspector) | Understand > Components > eaos | 3 | 3 | all |
| SYS-03 | P2 | Components as a ranked list | Components: the ranked list under the map preview (phone); List toggle (desktop) | Understand > Components | 2 | 3 | D1 |
| SYS-04 | P3 | Unseen work on the map | Components: the Unseen work lens | Understand > Components > Unseen work | 3 | 3 | all |
| SYS-05 | P2 | Functions explorer | Understand, Functions (paged, loaded on first open) | Understand > Functions | 2 | 2 | all |
| SYS-06 | P2 | One function and its call graph | Functions, a function | Understand > Functions > bundle | 3 | 3 | all |
| SYS-07 | P2 | Code paths | Understand, Code paths | Understand > Code paths | 2 | 2 | all |
| SYS-08 | P2 | One code path | Code paths, a path | Understand > Code paths > Answer a decision | 3 | 3 | all |
| SYS-09 | P2 | Data stores and write chains | Understand, Data | Understand > Data | 2 | 2 | all |
| SYS-10 | P2 | One store | Data, a store | Understand > Data > runs: written from 3 files | 3 | 3 | all |
| SYS-11 | P2 | What the user sees against what runs unseen | Understand, Seen and unseen | Understand > Seen and unseen | 2 | 2 | all |
| SYS-12 | P2 | Screens and user journeys | Understand, User journeys | Understand > User journeys | 2 | 2 | all |
| SYS-13 | P3 | Infrastructure | Understand, Infrastructure | Understand > Infrastructure | 2 | 2 | all |
| SYS-14 | P3 | Pipeline map | Understand, Pipelines (all six stacked) | Understand > Pipelines | 2 | 2 | D1 |
| SYS-15 | P3 | One pipeline stage | Pipelines, a stage (every stage directly under its pipeline) | Understand > Pipelines > Stage 1: facts | 3 | 3 | D1/D2 |
| SYS-16 | P3 | AI nodes (EAOS's own AI decisions) | Understand, How EAOS decided | Understand > How EAOS decided | 2 | 2 | all |
| SYS-17 | P3 | Architecture and design sources | Understand, Architecture and design | Understand > Architecture and design | 2 | 2 | all |
| SYS-18 | P2 | Navigating any map | Every map: zoom, pan, fit, keyboard, list twin, key of what is drawn; phone: Open the map | Understand > Components > Open the map | 3 | 2 | D3 |
| SCR-01 | P2 | Reviewed pages with their issues | Understand, Reviewed pages | Understand > Reviewed pages | 2 | 2 | all |
| SCR-02 | P2 | Every screen | Understand, Every screen | Understand > Every screen | 2 | 2 | all |
| SCR-03 | P2 | One screen | Every screen, a screen (viewport, before / after) | Understand > Every screen > IdealPage | 3 | 3 | all |
| SCR-04 | P2 | Before and after a batch | The fix run's page: Screens before and after | Activity > Fix: TASK-002 | 2 | 2 | D2 |
| LIB-01 | P2 | Documents by purpose and reading order | Understand, Library | Understand > Library | 2 | 2 | all |
| LIB-02 | P2 | Search the library | Library: its search field, always visible | Understand > Library | 2 | 2 | D1 |
| LIB-03 | P2 | Read a document | Library, a document | Understand > Library > 2 | 3 | 3 | all |
| LIB-04 | P2 | Links inside documents | Inside a document: problem ids, documents and images open in place | Understand > Library > 2 | 3 | 3 | all |
| LIB-05 | P3 | Diagrams | Inside a document: diagrams drawn, full screen, copy the source | Understand > Library > 2 | 3 | 3 | all |
| LIB-06 | P3 | Images | Library, Images tab; a screen's pictures | Understand > Library > Images | 3 | 3 | D3 |
| LIB-07 | P3 | Report files and the full report | Understand, Report files, a file | Understand > Report files > Open the full report | 3 | 3 | D1 |
| HIS-01 | P2 | Checks over time | Understand, Checks over time | Understand > Checks over time | 2 | 2 | D1/D2 |
| HIS-02 | P2 | Score trend | Status: the trend sentence (Health row on the phone, aside on the desktop); Checks over time | Health 68 of 100, fair | 1 | 0 | D3 dataviz rule |
| HIS-03 | P2 | Open problems by severity over time | Checks over time: open problems by severity | Understand > Checks over time | 2 | 2 | all |
| HIS-04 | P2 | Fixes taken in over time | Checks over time: fixes taken in | Understand > Checks over time | 2 | 2 | all |
| HIS-05 | P3 | Events | Checks over time, Events | Understand > Checks over time > Events | 3 | 3 | all |
| HIS-06 | P3 | One past check | Checks over time, a past check | Understand > Checks over time > 10 | 3 | 3 | all |
| HIS-07 | P2 | Compare two checks | Checks over time, Compare; the trend sentence opens it once two scores exist | Understand > Checks over time > Compare two checks | 3 | 3 | D1 |
| AST-01 | P2 | Assistants on this computer | Project menu, Assistants and cost | Project and settings > Assistants and cost | 2 | 2 | all |
| AST-02 | P2 | What the last check used, stage by stage | Assistants and cost: What the last check used ("a measure, not a bill") | Project and settings > Assistants and cost | 2 | 2 | all |
| AST-03 | P2 | What each run used | Assistants and cost: What each run used; also a run's facts | Project and settings > Assistants and cost | 2 | 2 | all |
| AST-04 | P3 | What to improve | Assistants and cost: What to improve | Project and settings > Assistants and cost | 2 | 2 | all |
| AST-05 | P3 | Conversation cost | Floating assistant panel footer: this conversation's answers and cost; Assistants and cost, Conversations | Ask your assistant about this page (Ctrl I) | 1 | 1 | all |
| CHT-01 | P1 | Ask about the project in my own words | The floating assistant button on every screen (Ctrl/Cmd+I): the conversation opens in place, with the page's context as a removable chip and suggested questions; Search or ask's "Ask your assistant: ..." opens it too | Ask your assistant about this page (Ctrl I) | 1 | 1 | D2 |
| CHT-02 | P2 | The answer as it is written | Floating assistant panel: what it reads now (live) and the answer as it is written; "What it read" on every answer | Ask your assistant about this page (Ctrl I) | 1 | 1 | all |
| CHT-03 | P1 | Proposals I confirm | Floating assistant panel: up to 4 proposals with a why; each opens its normal preview | Ask your assistant about this page (Ctrl I) | 1 | 1 | all |
| CHT-04 | P3 | Direct control for an hour | Floating assistant panel (or the full view): "Let it act for an hour" (owner; end time shown; never owner-only acts) | Ask your assistant about this page (Ctrl I) > Let it act for an hour | 2 | 2 | D2 |
| CHT-05 | P2 | Diagnose with context | Press the floating assistant on a run page: the run is its context chip (also "Ask your assistant about this run") | Activity > Fix: TASK-002 > Ask your assistant about this page (Ctrl I) | 3 | 3 | all |
| CHT-06 | P2 | Model per turn | Floating assistant panel: Quick / Balanced / Deep beside Send | Ask your assistant about this page (Ctrl I) > Deep | 2 | 2 | D2 |
| CHT-07 | P2 | A conversation goes on | Floating assistant panel and the full Ask view are the same conversation; it goes on; New conversation in the full view | Ask your assistant about this page (Ctrl I) | 1 | 1 | all |
| BLD-01 | P3 | A new project from its plan | More work...: New project from a plan... (also from the project menu) | More work… > New project from a plan… | 2 | 2 | D1 |
| BLD-02 | P3 | Extend this project with a feature | More work..., Add a feature from a plan... | More work… > Add a feature from a plan… | 2 | 2 | D3 |
| BLD-03 | P3 | Build milestone by milestone | Status next step while building ("Build milestone 2..."); Problems, Plan | More work… > Build the next milestone… | 2 | 2 | D1 |
| BLD-04 | P3 | Build journey progress | Status, Your journey (build); the build run page | Your journey | 1 | 1 | D1 |
| PJS-01 | P2 | Projects on this computer | Project menu: Projects on this computer | Project and settings | 1 | 1 | all |
| PJS-02 | P2 | Switch to another project | Project menu, a project (opens its own interface) | Project and settings > E | 2 | 2 | all |
| PJS-03 | P3 | A folder holding several projects | Chooser on opening a folder of projects; later Project menu, In this folder | start `/open?kind=folder`; visible at once (the chooser opens instead of Status) | 0 | 0 | D1 |
| PJS-04 | P3 | Several reports in one offline export | Offline export: report chooser on opening; later Project menu, Reports in this file | start `/open?kind=export`; visible at once (the report chooser opens instead of Status) | 0 | 0 | D1 |
| SGN-01 | P2 | Does the app need a sign-in? | Check preview: "Your code shows a sign-in at /login" | Activity > Check the project… | 2 | 2 | all |
| SGN-02 | P2 | How the check opens pages behind a sign-in | Check preview: sign-in way (By hand / A test user / None), kept per project; Project, Your app | Activity > Check the project… > A test user | 3 | 3 | all |
| SGN-03 | P1 | The check waits for my sign-in | Live strip turns accent with the time left; Waiting, Your sign-in | start `/status?state=signin`; The check waits for your sign-in to your app, 14 | 1 | 1 | D2/D3 |
| SGN-04 | P1 | Sign in by hand | Waiting, Your sign-in: Sign in now (the picture you drive, "I have signed in") | start `/status?state=signin`; Waiting, 5 things wait for you > Sign in now | 2 | 2 | all |
| SGN-05 | P1 | What the app sent (codes, links) | Sign-in view: What your app sent (phone tab, desktop beside the picture) | start `/status?state=signin`; The check waits for your sign-in to your app, 14 > What your app sent | 2 | 1 | D1 |
| SGN-06 | P3 | My session stays private | Project, Your app: Forget my sign-in... | Project and settings > Your app > Forget my sign-in… | 3 | 3 | D1 |
| SGN-07 | P2 | Asked again only when it expired | Project, Your app: "your sign-in is kept and still works"; said in the check preview | Project and settings > Your app | 2 | 2 | all |
| SGN-08 | P3 | The published address, read only | Check preview, Options: the published address | Activity > Check the project… > Options | 3 | 3 | all |
| ACT-01 | P1 | What is happening, from anywhere | Live strip (phone) / live card (desktop) and the waiting count, on every screen | start `/status?state=running`; visible at once | 0 | 0 | D2 |
| ACT-02 | P2 | Change notices | Notices: one line, 5 s, polite; refusals stay and say why | visible at once (behaviour on every screen) | 0 | 0 | all |
| ACT-03 | P2 | Only what changed reloads | Only the named sections reload; a list being read never reshuffles | visible at once (behaviour on every screen) | 0 | 0 | all |
| ACT-04 | P3 | Progress outside the interface | The window title carries n/N and a done mark | visible at once | 0 | 0 | all |
| ACT-05 | P2 | Connection and recovery | The banner slot: reconnecting, quiet, refused, reset; last answer kept and marked | start `/status?state=reconnecting`; visible at once | 0 | 0 | D3 slot |
| ACT-06 | P2 | Announcements for screen readers | One polite live region, at most one announcement per 3 s, newest wins | visible at once (behaviour on every screen) | 0 | 0 | all |
| SRC-01 | P1 | One search over the whole project | Search or ask: top-bar button (phone), sidebar field (desktop), Ctrl/Cmd+K; a light index (IA 5); functions and document text one row deeper | Search or ask | 1 | 1 | D2 one box |
| SRC-02 | P1 | Arabic-aware matching | Every search box (same Arabic-aware folding) | Search or ask > (type "الامان") | 1 | 1 | all |
| SRC-03 | P2 | Search within a view | Each view's own search (Problems 1, Branches 1, All runs 2, Functions 2, Library 2) | Problems | 1 | 1 | all |
| SEL-01 | P1 | Select problems | Problems: tick a row (shift for a range); Select all shown (desktop) | Problems > Select this problem: TASK-001 | 2 | 2 | all |
| SEL-02 | P1 | Select a group in one step | Problems, Select a group, a group with its count | Problems > Select a group > High | 3 | 3 | all |
| SEL-03 | P1 | Selection rules | The selection bar (count, group name, at most 500, Esc clears, leaving Problems clears) and the preview's left-out list | Problems > Select this problem: TASK-001 | 2 | 2 | D1/D3 |
| SEL-04 | P1 | Act on the selection | Problems: tick, then a verb in the selection bar (opens its preview) | Problems > Select this problem: TASK-001 > Fix… | 3 | 3 | all |
| LNK-01 | P2 | Every view state is addressable | Every state is its address (#/path?query, including lang and theme) | visible at once (every state is its address; behaviour on every screen) | 0 | 0 | all |
| SET-01 | P1 | Language and direction | Phone: Project menu, Arabic / English. Desktop: sidebar foot | Project and settings > العربية | 2 | 1 | D2 |
| SET-02 | P3 | Theme | Phone: Project menu, Light / Dark. Desktop: sidebar foot (first follows the system) | Project and settings > Dark | 2 | 1 | D2 |
| SET-03 | P3 | Time zone | Project menu, Settings, Time zone (any time shows its exact day, time and zone on press) | Project and settings > Settings > Universal time UTC | 3 | 3 | all |
| SET-04 | P2 | Numbers and mixed text | Everywhere: Western digits, Arabic number agreement, paths and ids isolated left to right | visible at once | 0 | 0 | all |
| SET-05 | P3 | Kept choices of this project | Project menu, Settings: Choices kept for this project | Project and settings > Settings | 2 | 2 | all |
| SET-06 | P3 | Version and contract | Status, About this check (EAOS stamp); Project menu, Settings | About this check | 1 | 1 | D2 |
| SET-07 | P2 | Keyboard and accessibility | Skip link on the first Tab; Project menu, Settings, Keyboard and accessibility | visible at once | 0 | 0 | all |
| OFF-01 | P2 | Opened from a file: read-only | The offline banner on every screen; every action stays and explains how to open it live | start `/status?state=offline`; visible at once | 0 | 0 | D1 (Stripe test-mode lesson) |
| OFF-02 | P2 | How to open it live | Offline banner: How to open it live (`eaos studio`, Copy) | start `/status?state=offline`; How to open it live | 1 | 1 | all |
| OFF-03 | P2 | Ask an assistant instead | Any action offline: the Open it live sheet with Copy the request for your assistant | start `/status?state=offline`; Copy the request for your assistant | 1 | 1 | all |
| OFF-04 | P3 | Opened without its key | Opened without its key: one page saying how to get the address | start `/open?kind=nokey`; visible at once (the page opens instead of Status) | 0 | 0 | all |
| OFF-05 | P3 | On a remote server | Project menu, Settings, Access | Project and settings > Settings | 2 | 2 | D2 |
| OFF-06 | P3 | Live but read-only | Live but read-only: one banner, "Nothing can be started here" | start `/open?kind=readonly`; visible at once (the page opens instead of Status) | 0 | 0 | all |

Measured: 198 of 198 feature IDs, each at 390 and 1440 in Arabic and English. Failed: none. Missing: none. Above 3: none. Worst-case presses: 0 -> 19, 1 -> 41, 2 -> 86, 3 -> 52.

**Kept at 3 or below by design**, confirmed by the measurement: merge, delete, protect and conflict help on a branch
(the branch chip on Status opens Branches in 1, and the branch page already runs the free merge check, so "Propose a
resolution" sits on it, D3/D2); one plan task (its waits-for lives on the problem page, D1/D2); any pipeline's stage
(all six pipelines stacked, D1); speed mode, AI choice and the published address (one Options fold inside the same
preview, D2); auto-accept and delivery (governance is never folded, D1/D3); Accept and Reject (the action is on the
Waiting card, the confirm is part of the feature, D1/D3); direct control and model depth (controls inside the Ask
composer, D2). **Corrected after the gate review** (the measurement found 4): Redo from a stage is 3 when idle because
Status's "About this check" lists the stages that did not plainly finish (a stage 2, Redo from here… 3); the Expert
batch tools are 3 through More work… on Status (the Expert group 2, a tool 3) and are also found by the launcher's
search; run questions are reached from Waiting's "Questions from runs" row (2).

## 11. The open points of FEATURES Appendix H, decided

1. Steps an assistant drives inside a run are never page buttons: events in What happened, plus the launcher's Expert
   group (FIX-16, RUN-13).
2. The stage view is drawn for about 40 stages: dependency layers as columns on the desktop, as numbered groups on the
   phone; a new stage adds a row, not a layout.
3. Problem lists render 50 rows at a time ("Show 50 more"), facet counts are computed once per data change, and the
   list keeps its order when data lands: it stays fast at 5,000.
4. Freshness is one set of states with one glyph and word each (DESIGN-SYSTEM.md, section 2.5).
5. The four sources of "waiting" are one list and one count everywhere (DEC-01).
