# Changelog

## 0.0.44 (2026-10-19)

- **The test sign-in is a step of its own, made by the assistant on the running app**: the setup tried the sign-in
  with every attempt, installing and starting the app again for each, and the assistant, told to sign in "the way the
  app allows locally", refused an app that signs in only with Google. Now the setup only starts the app (a sign-in
  page is the app working), and the step "Prepares a test sign-in" asks the assistant for the seed script on the app
  as it runs: it is told the copy and its database are the check's own, how to get in (a development sign-in, the
  pages, the app's scripts, the database, a session the app accepts), what is still lacking after each try, until
  every kind of user signs in or five minutes pass; then the person is asked to sign in by hand, a test user chosen
  included. A trial app signing in with Google only: started in about 30 seconds, three kinds signed in, pictured
  four minutes after the check began.

## 0.0.43 (2026-10-19)

- **EAOS's own Studio starts in a check**: started by the assistant without launch keys, it knew no port and refused
  every request to 127.0.0.1 (421), so the check of EAOS itself failed to run its app. A server without a port in its
  keys answers on the port it listens on; another host is still refused.
- **A refusal ends the wait**: the setup waited three minutes for a 200 at each attempt while the app answered at once
  with a 4xx, 13 minutes for five attempts; an answer below 500 now ends the wait, and the next step tells the
  assistant what was refused.

## 0.0.42 (2026-10-19)

- **The Studio says which EAOS runs**: its side bar, settings and tools showed the version that made the last check
  (0.0.37 after an update to 0.0.41), as if the update had not landed. They show the running one now, and the
  settings say which version made the check when it differs.

## 0.0.41 (2026-10-19)

- **Every kind of user is checked**: a check opened the app as one user and pictured only what that user sees (an
  app with administrators, support and customers was checked as support alone, and nobody was told). Now the
  assistant reads the kinds of users from the code, each with the line that makes it one and its own pages
  (`roles.json`, checked against the code). Run locally, the setup makes a temporary user of each kind in the isolated
  copy's own database (an app that signs in only with Google included) and the crawl and the pictures run once as
  each; signed in by hand, or on the published address, the account given is checked and the report says which kinds
  it could not open. Each page of one kind another kind's session opens is named in the report and the Studio (a trial
  app's missing guard on /admin/users was found so). The Studio's Screens show each kind apart.
- **A page that refuses a user (403) is the app answering**: the setup took the customer page refusing the
  administrator for an app that does not start.
- **An opened fold stays open**: a running check's page is drawn again at each event, and that closed the facts, "See
  the change" and every fold under the person after a few seconds; a redraw now keeps what they opened.
- **A fix counts what it tried once**: its title counted every file edit ("12 of 53 tried"), its list the problems
  ("9 of 53"), and its bar a third measure, so the numbers disagreed and moved apart as it went; all three now count
  the problems tried.
- **A change's code stays in its event**: "See the change" spread the run's page past the screen (241 pixels on a
  computer, 987 on a phone); the code now slides inside the event.

## 0.0.40 (2026-10-19)

- **On a phone, the Studio keeps its size**: a long file path in a problem's row made the page wider than the screen
  (the row was a grid as wide as its longest line, and the path's "…" never applied), so the phone zoomed the whole
  Studio out, and in again as a filter changed the rows: the text grew and shrank and rows ran off the screen. The row
  now holds its width and the path ends in "…"; the page can no longer be wider than the screen.
- **Typing is never broken by a live redraw**: the assistant's box, a sheet's field and the sign-in field keep what is
  typed and where the caret is (a redraw sent the caret to the start: "مساء الخير" landed before "السلام عليكم").
- **The problems' filters**: a segmented control that does not fit slides sideways on one line, its chosen choice in
  view after each redraw (the four "Group the list" buttons ran into each other), and a value with no problem cannot be
  picked (it led to "Show no problems").
- **The Understand tabs stay still**: the strip was one pixel taller than itself, so it moved up and down under a
  finger; the assistant's suggestions likewise.

## 0.0.39 (2026-10-19)

- **The run's database starts on a new server run as root**: PostgreSQL refuses root, so a dedicated account runs it,
  and pgserver's binaries sat in EAOS's virtualenv under /root, which that account cannot enter ("Permission denied:
  pg_ctl", every app with a database failed to start). They are now copied once, with their libraries, to
  /opt/eaos-pg. This computer never showed it: its PostgreSQL came from the system, outside /root.
- **Claude in a Studio on a remote server**: a Studio started by an assistant took that assistant's session sign-in,
  which Remote replaces, so the Studio's Claude later answered "401 unauthorized" and the check stopped at its start.
  The fix is a long-lived token the Studio uses whatever session started it: `claude setup-token`, saved as the
  project secret `CLAUDE_CODE_OAUTH_TOKEN`; Claude's not-signed-in, expired and failed messages now say so.

## 0.0.38 (2026-10-19)

- **Any app is run, not only a JavaScript one**: a project with no JavaScript web app (EAOS itself, a Python app) was
  skipped with "EAOS runs JavaScript web apps for now", nobody asked, and its tests then ran an earlier app's profile
  (`npm ci` in a folder gone). Now the assistant reads the project's documentation and says how to install and start
  it (Python included: python, pip, uv, poetry, uvicorn, gunicorn); EAOS itself starts this way, on its own Studio.
- **A new project's app is run, signed in, from start to end** (a real Express app with a sign-in, checked from the
  Studio):
  - the check's own window asks whether to run the app (it was a separate action, so a new project's check skipped
    its pages, sign-in and speed and said so only in a stage's detail); `eaos check --run-app` in the terminal;
  - the lock no longer calls `GET /logout` with the person's session (it ended it for every page stage after it, which
    then pictured the sign-in page);
  - the session is tried on a server app's pages (`GET /notes`), never on its sign-in page: only its public first page
    was tried, so an empty session passed and the person was never asked;
  - one app from the sign-in to the last page stage, the lock included: an app keeping its sessions in memory forgot
    the person's at each restart, and the check asked them to sign in again for every stage;
  - the sign-in browser opens on the sign-in page the pages are sent to, and "I signed in" with the pages still signed
    out asks again instead of ending as if nobody had come;
  - a plain Node server's speed is measured (no build step is its production), and k6 sees its script in a new
    project's report, whose folder was never saved and so was hidden from the run.
- **A check in five parts, in its order**: reading your project, the analysis tools, running your app, your assistant
  reviews, the plan and the reports; each part with how many of its stages ended and its own time. The board's
  "layers" counted only part of what a stage waits for, so a stage drawn in layer 6 ran after one in layer 8.
- **A pause stops the clocks**: the check's time, each stage's and each part's freeze while it is paused and go on from
  there (the pauses kept as spans of the run); they counted on before.
- **A Python app's installs stay in its run**: each run has its own virtual environment, first on PATH whatever the run
  chose, so `pip install` never lands in EAOS's own environment (a trial once broke EAOS's that way).

## 0.0.37 (2026-10-19)

- **The problems' filters stick**: choosing an area, a severity or a state and pressing Show kept nothing, because
  closing the sheet went back in the browser's history and took the filters with it; a sheet that changed the address
  now closes in place. `eaos problems --area … --severity …` filters the same way in the terminal.
- **A check's clock, live**: the time since the check began and each running stage's own time tick every second (one
  ticker, nothing drawn again), what each took once ended; a stage's counted steps fill a bar and its programs tick from
  their start. `eaos watch` says the time since the run began and the stages in plain words.
- **Parallel stages said plainly**: "n of N stages done, m running now" instead of "stage n of N", the mode and how many
  assistants it allows; each running program is shown under the stage that started it (it was always the last one).
- **An AI stage answered only in part is PARTIAL**: when some of its batches failed (a usage limit midway) the check no
  longer says COMPLETE; running the stage again asks only those batches. The scheduler lets lighter stages start while
  a heavier one waits for room, and counts the memory of assistants that just started. Speed mode's note says what it
  costs: the usage limit spent in less time, not more tokens.
- Fixed: the rules and the assistant giving the same answer were asked as a disagreement; `eaos usage` printed
  unrounded costs; a check without the assistant showed the cost of the check before it.
- **The new Studio is the only one**: the console (`console/`, built into `eaos/data/studio`) replaced the old React
  Studio, whose folder (`studio/`, its 490 MB of packages with it) and its redesign plan are deleted.
- **A check never says complete when its assistant was lost midway**: Claude Code's "session limit" is read as a usage
  limit with the time it resets; the stages it could not run make the check PARTIAL, are named on the check's page with
  when the assistant comes back, and one press runs them again with a real estimate of their time. The Studio follows
  only the check that started its stages, and reads the report again when a check ends or the tab is seen again.

## 2026-10-17

- **The Studio regrouped into five sections** (Overview, Checks, Problems, Fixes, System) with System's nine maps folded
  under it in four categories, Library and Settings below, and four tabs and More on the phone; every job is three
  clicks or fewer from Overview (34 of 34 measured at phone and desktop sizes). **Checks** is one page to start a check,
  follow it live and look back; **Waiting for you** in the top bar holds every question, decision and branch waiting for
  approval; **Fixes** opens on those branches with Accept and Undo. The existing pages were reconnected, not rewritten;
  the old addresses lead to the new ones. A check pressed anywhere is a new one (before, some buttons answered "already
  checked"), it can leave the AI out, and starting it has one name. A document reads its own text and pictures instead
  of the whole 15 MB library; the build keeps the Studio's weight within budget.
- **Projects kept apart**: a project's app and its commands see only their own project (other projects, their reports,
  sessions and Studio keys are hidden from them); its database needs a password; jobs, caches and the busy port are its
  own; `eaos clean` spares another project's live run; the Studio's key is never handed to a forged request. A project
  switcher opens each project's own Studio; an idle local Studio stops by itself. Two real projects checked at once:
  isolation held both ways, at most 4.3 GB of 8 used.
- **Full governance from the terminal and MCP, without the Studio**: `eaos check` (with its estimate) / `watch` / `stop`
  / `pause` / `resume` / `retry`, `problems`, `waiting` and `answer`, `fix|verify|explain|plan` on cards or groups with
  their preview, `runs`, `history`, `compare`, `usage`, branches with preview and confirm, over the Studio's own core;
  the person's own decisions (branch, running the app, accept, undo, merge, delete, restore) need their word on every
  surface. Proven by a real fix from the terminal alone, accepted after its prompt.
- **Sign-in for any app** (cards 12 to 21): EAOS finds whether the screens need a sign-in; the person signs in by hand,
  any method, from the Studio or with `eaos sign-in` (a page of its own when the computer has no display), the app's
  codes shown from its output and Mailpit; one private session serves every page stage, is checked before use and asked
  again only when it expired; `--sign-in hand|test_user|none` everywhere; the published address only read.
- Fixed: a YAML file beginning with `---` stopped a whole check; `eaos usage` counted only a run's last turn; a fix
  could never pass its gates where the tools folder is a link.

## 0.0.36 (2026-10-17)

- **A check runs its stages side by side, as much as the computer can take**: a stage starts as soon as the stages it
  waits for have ended (every read of another stage declared, so a parallel check finds exactly what a serial one
  finds), and beside the others only while there is free memory for it and the processors are not saturated; one
  always runs, so a small computer is slower, never choked or stuck (`assistants/resources.py`). The 24 engines follow
  the same rule. On EAOS itself, without the assistant: 13 minutes instead of 19, never under 1.1 GB free.
- **Speed mode**: an AI stage's batches asked on several assistants at once, as many as the free memory holds (at most
  five), the same answers in the same order; every assistant run is logged once (the card sorting looked as if it ran
  three times).
- **Paths of a check**: complete, security, code, look and screens, speed and scale, alone or together, chosen wherever
  a check starts (Studio, `eaos start --path`, the assistant); a path's own stages, engines and cards only. Each was
  run on EAOS: security in 3 minutes with its 8 engines, code in 12 with its 15.
- **The page stages share one running app and sign-in**; the Studio's stop ends every command of every stage running
  beside it, with the programs those started.
- **EAOS removes what it makes, as it goes**: a stopped run's copy, a gone runtime's database, a closed batch's copy
  and its bisection's logs, a tool's older release, raw assistant streams past the newest ten runs (each keeps its
  summary), the syntax cache's entries for files that changed (175 MB on EAOS), and the tools' download caches (about
  2 GB of npm, pip and uv caches had stayed in the person's home).
- Fixed: Lizard's workers deadlocked now and then until the ten-minute timeout (it runs as one process, 6 s); a check
  without AI failed to set the app up; `eaos start --path` went on to the next step and ignored the path.

## 0.0.35 (2026-10-15)

- **What a check uses, written down** (README, GUIDE, in English and Arabic): measured on EAOS itself, a whole check is
  about an hour of model time, worth about US$22 at API list prices, most of it sorting the cards, the screen review and
  the ideal target; a fix batch uses much more, so a large one starts in a fresh five-hour window.
- ROADMAP brought up to date: the design library is done; the proof of 0.0.34 and card sorting run three times are next.

## 0.0.34 (2026-10-15)

- **A batch with a design card is not refused for how its screens look**: a design card changes a shared part (a font,
  a card, a strip) that shows on pages its finding never named, so each run of batch 8 found one more such page and 33
  sound design cards were left out. Such a batch may now change any screen's look (`waves.declared_screens`); a page's
  errors and its server's answers stay locked, and a batch of code changes keeps every screen locked. When the lock
  breaks, it names every screen that differs at once, not one per run.
- **The speed baseline measures the program, found at setup**: a route that answers "not found" no longer counts as
  served (`runtime_baseline._answer`), so a server of the pages alone (`vite preview`) is refused at setup, where the
  assistant is asked for the real server, not only later by the check. A production run that worked is tried first by
  the next setup instead of being detected away (the assistant had found EAOS's real server, and each setup lost it).
- **Filter strips look like the System maps' tabs**: one global style for every row of filters (the library, functions,
  screens, gaps, the problems' filter sheet and the System tabs): one line sliding sideways, plain text, a light
  highlight, the chosen item on the accent.
- CodeQL on Python, which failed in the last check, works: run under the Studio's PYTHONSAFEPATH, it analysed Python and
  JavaScript and reported 7 findings (the fix shipped in 0.0.29's day, after that check).

## 0.0.33 (2026-10-15)

- **A large module is split once its complex functions are simplified, never before**: the plan already said a split
  waits for its module's simplification, but no batch read it, so EAOS's five largest modules went into batch after
  batch beside or ahead of their simplifications and failed every time. Now a batch never takes a card waiting for one
  not done (`decisions.waiting`): `fix_start` leaves it for a later batch, refuses it by name when asked for, and the
  Fix preview lists it as "waits for TASK-…". A card set aside only because it came too early opens again once the
  cards it waits for are done (`ledger._reopen_waited`), and a split waits only for simplifications a batch can make.
- **Every complexity card has a finish line, each target judged by one ruler** (`eaos/finish_line.py`): one card mixed
  seven kinds of engine finding and was judged on the whole file by whichever engine spoke, so six cards of a batch
  could not pass whatever the assistant changed. Now the card lists exactly what it must clear, fixed when it is made:
  a branching score by EAOS's own count (the gates' one; engines scored one function 15, 40 and 49), an exact count
  (too many parameters, nesting too deep, too long) by the engine that stated it, never the size of a file or a class
  (a split's work). A target follows its function by name, so moving it does not clear it. A card with nothing left to
  clear is a question for the person, never work a batch cannot finish. On those six cards: two get 4 and 2 precise
  targets, four become questions. The assistant sees the finish line before it starts and, when the check still fails,
  what is left; it sees up to 24 facts behind a card instead of 6. Older cards' probes count only their own engines and
  what is past its threshold.
- **A batch is seen live on the map, card by card**: nothing wrote the flow `fix`, so the live map and the journey
  strip read "waiting" through every batch. A batch is now drawn from its state at each save (`waves.draw`,
  called by `guided.save`): the copy opened, a step per card kept or set aside, the end checks as they are reached
  (`batch_finish._phase`), then its handover, or its stop.
- **A run's page shows the same numbers at every refresh**: it drew a long run's replayed events one by one (500
  drawings), so each refresh caught it mid-way, at another count and step; its new events are now drawn together.
- **A batch that fails its checks finds the culprit in one run when the failure names it** (`waves._named`): before
  halving, the batch is tried without the changes to a file the failing checks printed; halving 68 changes ran the whole
  suite again and again, on half-applied splits whose every Studio test waited out its 30 seconds, for over an hour,
  though the failure named the one file.
- **A change is sized against the copy just before it** (`waves._sizes_before`), not against the check on record: a
  one-line repair to an 876-line test file was refused as "growing" it, from the 861 lines an older check had counted.
- **Each batch says how it did on the first try**, and a card failing in a second batch is reported as a defect of EAOS,
  not of the project (the ledger counts each card's failed batches).
- **Moving a complex function in a split keeps its allowance** (`tools/code_limits.py`): it may not grow, but moving it
  to another module, or out of its class, no longer counts as a new over-limit function.
- The Fix preview says why a card is left out in the person's language.

## 0.0.32 (2026-10-15)

- **A batch that stops frees its cards at once**: a batch retired because the code moved on (or abandoned) now brings
  the ledger and the Studio up to date when it closes; before, its 74 cards stayed "in the batch" and every next batch
  refused them ("every selected card is already handled").
- **The Fix preview says why it cannot run in the person's language**: a selection that cannot run is said in Arabic
  and English, and the Studio shows the one the page is in.

## 0.0.31 (2026-10-14)

- **EAOS's own sentences translated professionally, once, for everyone**: the shipped memory
  (`eaos/data/translation-memory.json`) now holds what the reports of different projects share (a template met in
  two projects' reports is EAOS's), translated by a strong model and reviewed: the cheap model had 205 of 374 Arabic
  and 309 of 507 English translations wrong (code names translated, meanings reversed, terms inconsistent). It holds
  509 Arabic and 654 English templates; `tools/translation_seed.py` lists what to add from new reports and merges
  the reviewed translations.
- **Less is sent**: command lines are never sent; package versions (`name@1.2.3`) and camelCase names become slots
  too, so one sentence about many functions is one template; batches are twice as large, so the fixed start of
  each call is paid half as often.
- On a project EAOS never saw (RendaPerene): 52% of its templates come from the shipped memory, and the rest took
  6 calls, 2 minutes and $0.28 with the person's own assistant, 9 pieces left as written. No other account, key or
  service is needed.

## 0.0.30 (2026-10-14)

- **Translation at a fraction of its cost** (`eaos/bilingual.py`): on EAOS's own check it took 24 calls, 54 minutes
  and $2.19, 77% of its output the model's thinking, and left 1009 pieces in English in the Arabic report. Now:
  - the smallest model translates without thinking (Claude: `MAX_THINKING_TOKENS=0`; Codex: low reasoning);
  - the unit is a whole piece, a heading, a list item, a paragraph with its wrapped lines joined, or a table cell, not
    a line cut mid sentence;
  - numbers, paths, code, ids and identifiers (a list of them as one) become numbered slots, put back after: never
    altered, and two pieces that differ only by them are one template, translated once (2818 lines became 633);
  - each item goes and comes back under its own key, so an item left out cannot move the answers after it; an answer
    that lost a slot or is still in the wrong language is asked once more, then left as written;
  - the model is told the terms EAOS uses (its labels and a short list);
  - EAOS ships its own sentences translated (`eaos/data/translation-memory.json`, made by
    `tools/translation_seed.py` from its own check and reviewed), so a first check spends nothing on them.
  On the same report: 14 calls, 4 minutes, $0.59, no thinking, 25 pieces left unsound, and the English left in the
  Arabic report is names and commands. The next check sends only what is new.
- **The build keeps its own times on the live map**: drawn again after each step, a build no longer starts its time
  over; each milestone keeps when it began and ended.
- **"Extend the project" is offered once the project is checked**, since extending reads the check.
- **System components of a project not built yet**: the page lists the target's planned components, each with its job,
  where it showed nothing.

## 0.0.29 (2026-10-14)

- **Three journeys on one engine**: check and fix, build from a plan, and the new extend the project are declared as
  data (`eaos/data/journeys.json`): each step, in order, with the flow that draws it on the live map or the page that
  shows it. `eaos/journeys.py` picks the journey from the project's state and judges each step; the journey and its
  flows left `guided.py`, whose check steps read their words from the same file.
- **Extend a checked project**: `extend_start` reads the plan of a feature, a page or a part with the project as its
  check read it (its parts, layers and rules, the functions to reuse, its look); `extend_plan` holds the spec to the
  project (every file in a layer it allows, every reuse a function it has and may use, no function written again) and
  adds its cards to the project's plan as one "Extension" milestone, built by the usual batches through every gate. A
  later check keeps the cards not built yet. In the Studio: "Extend the project" beside "Build from a plan".
- **The build in the Studio**: a build draws its progress as the flow `build` (a stage per milestone, a step per card),
  so the journey strip, the live map and the stage panel show it as they show a check; the library's "The blueprint
  and the look" group shows BLUEPRINT.md, DESIGN.md and a feature's plan before any check exists.
- **One set of gates** (`eaos/gates.py`): a fix, a build card and a feature's card pass the same gates (layers, files
  in no layer, vendors outside their adapter, import cycles, broken references, copies, dead code, complexity, size,
  security), a fix against its check, a build against nothing. A fix now also refuses a new import cycle and names
  each forbidden import instead of counting them.
- **One shape for the target**: a check and a build write `target-architecture.json` alike, in the same place (its
  parts are the layers), so the reports and the Studio draw both the same way; BLUEPRINT.html keeps its layer drawing
  after the first update.
- **Each milestone's screens reviewed against its look**: after a milestone with screens, the check's own stages
  (facts, features, setup, screens, visual) picture them on its copy and the assistant reviews them against DESIGN.md
  (now kept from the spec where the review reads it); what departs is fixed first in the next milestone. Once the
  acceptance check is done, a build goes on as check and fix.
- **Card readiness has one home** (`decisions.ready`), read by the batches, the Studio, START-HERE and cards.json.
- **The design suggestion returns in the Studio**: UI UX Pro Max's search now runs in the tools' environment, so
  PYTHONSAFEPATH no longer breaks it.

## 0.0.28 (2026-10-14)

- **A design library at almost no tokens**: four free, pinned design sources join the toolchain (UI UX Pro Max's
  styles, palettes, font pairings and UX rules by product type, searched offline by its own script; awesome-design-md's
  reference design systems; tweakcn's themes; Anthropic's frontend-design guidance), with shadcn/ui components (right
  to left included) and Fontsource fonts installed into a built project by their own tools. One EAOS design standard
  holds them together (`eaos/data/design.json`): phone first, both directions, one theme as tokens, readable contrast
  in light and dark, Arabic typography, and a catalogue of fourteen Arabic fonts with what each suits.
- **The look of a build**: `blueprint_start` returns the design brief with the design system suggested for the
  product; the spec's look carries the whole DESIGN.md, and the shared-look card installs it with the components and
  fonts, held to the standard.
- **A redesign, the person's choice**: `design_brief` and `design_choose` let the assistant propose directions from the
  same sources and save the chosen DESIGN.md beside the report; the screen review then judges every page against it
  (going on from the visual stage, the rest of the check kept), and every departure is a design card fixed in a batch.

## 0.0.27 (2026-10-14)

- **A check goes on from where it went wrong, never a whole new one for one stage**: the check map's stage panel has
  "Redo this stage and what depends on it" and, when tools failed in it, "Run the tools that failed again". It runs on
  the very commit that was checked, the stage and every stage reading what it makes run again (a stage now declares
  what it reads besides what it waits for: the load model reads the engines), and the rest is kept as it was
  (`audit again_from=<stage> engines=[...]`, `eaos/pipeline/run.py again`). A tool run again alone joins the other
  tools' results of the same check instead of replacing them.
- **A tool that fails is said, never read as clean**: CodeQL failed on EAOS's Python in a 1 h 46 min check while the
  engines stage said ok. The stage now names the tools that failed, the check is PARTIAL, and its result says
  "Done, but these tools failed: ..." with where to run them again.
- **CodeQL reads Python where the Studio runs**: the Studio's PYTHONSAFEPATH kept CodeQL's Python extractor from
  importing its own modules; the tools now run without EAOS's own Python settings.
- **START-HERE.md is this check's**: it was written only when missing, so the page of a check in the morning (177
  problems, 156 to decide) stood over the afternoon's (79, all fixed alone), translated as it was. The reports stage
  writes it every check, and a new check clears the old one.
- **The triage asks only what is new or changed**: each card's verdict is kept under its own evidence and the task's
  words, so a check gone on from a stage (CodeQL's new cards) pays for those cards alone, not every card again.
- **Build from a plan in the Studio**: "Build from a plan" in the assistant's panel takes the new project's name, its
  files (PDF, Word, HTML, Markdown, text) and the pictures of its screens, or pasted words; the person's assistant
  reads them, looks at every picture, asks only real choices and draws the structure, the look and the whole build
  plan in a new folder beside the project (POST /api/plan). The build starts once the person agrees.
- **The plan's look is built once**: the spec carries the one theme, its colours, fonts, shared components and the
  screens with their features and pictures (`look`); the shared-look card makes them design tokens no screen
  overrides, and each feature's card says which screen and picture it follows. A plan is read from a folder too, its
  pictures kept for the assistant (`eaos/plan_source.py`).
- **A build never builds a weakness in**: every build card passes Bandit and Gitleaks as a fix does, and a milestone
  closes with CodeQL too where it may run (tried: a shell command built from input and an AWS key are refused).
- **The repository's face, in English first and in Arabic**: a new README in each language with the EAOS mark,
  banners for light and dark, and pictures of a real check of an open-source example app; the guide and "build from a
  plan" in both languages; issue and pull-request templates, a code of conduct, and an up-to-date security model and
  contributing guide.

## 0.0.26 (2026-10-14)

- **Every document in both languages, switched with the Studio's**: the documents came out mixed (on EAOS, the median
  42% Arabic in an Arabic report, START-HERE wholly English). The check's last step translates only the lines in the
  other language, by the smallest model (Claude's Haiku: the whole report about half a dollar the first time), keeps
  them in a translation memory so the next check sends only what is new, and leaves code, paths and names as written.
  The reader shows each document and its title in the person's language at once.
- **A run proposal may say where the app keeps its language**, so every screen is pictured in each language.
- **A card that adds a module past the line limit, or one in no declared layer, is refused on the card**, not found
  when a batch's changes meet.
- A run proposal's safety and its merge into run.json live in `eaos/run_profile.py`.
- **An app that keeps a live connection open starts in the check**: the setup's probe waited for the network to go
  idle, which a page holding a server-sent stream never does (EAOS's own Studio: 60 s, then failed); it now waits for
  the page to load and gives the network five seconds (200 in 6 s).
- **The assistant beside the work**: a button in a corner of every page opens a small panel that moves to any corner
  and keeps the conversation across pages (eaos/studio/actions/chat.py, POST /api/chat). It reads with EAOS's reading
  tools only and the project's files; what it would do comes back as a card: an action opens the command centre's own
  preview, a run's control waits for the person's press. Quick answers by Claude's Haiku (about $0.09 a diagnosis),
  a deep diagnosis by the assistant's own model; a failed run's page asks it why ("Diagnose with the assistant"),
  with the run's last events and log. Its use shows on the Assistant page.
  The answer shows as it is written, with what the assistant reads now; the person picks the model (quick, balanced,
  deep) and sees each answer's cost. **Direct control**, turned on by the person for an hour and kept by the server:
  the Studio runs at once the assistant's proposals of a check, running the app, its speed or its nodes, and the runs'
  controls, through its own preview and queue; accepting, undoing, choosing a branch and editing code stay the person's.
- **The Assistant page**: which assistants are on this computer (installed, signed in, model), and what the work used
  (eaos/usage.py, /api/usage): the last check stage by stage, every run (a run still going by its messages so far),
  tokens, the cost at API prices, time, turns, and the measures to improve it: the cost per fixed card, the share of
  the conversation read again, the share of thinking. Read from what every call already leaves; nothing estimated. On
  EAOS: the last check's AI stages $10 (card triage $4.6), batch 5 $48 with 138 of 140 million tokens read again.

## 0.0.25 (2026-10-14)

- **Every security finding reaches a card**: Bandit (Python's syntax tree) and Gitleaks (secrets) join Semgrep, and
  CodeQL (data traced across the program) runs on open-source projects public on GitHub.com, the only ones its terms
  allow. Two engines reporting a weakness within five lines of each other make a likely card; a finding no other engine
  confirms is a card the assistant's triage decides on the code. Findings group by file and weakness, audit hints by
  weakness across the project: on EAOS, 103 findings make 27 cards, 12 of them agreed. Before, a finding only one
  engine reported stayed a fact, and EAOS read its own security as 100 with 82 of them.
- **Semgrep's severity is read**: it writes the level on the rule, and every one of its findings was read as low.
- **A known risk kept counts**: a vulnerable library with no fixed version, closed by the assistant, still weighs on
  the security score, counted apart as accepted.
- **A fix may not bring a weakness in**: every change a batch makes is read by Bandit and Gitleaks, and one that adds a
  finding in the files it touched is taken back. A security card passes only when the engines that found it, asked
  again on the changed copy, no longer do; an engine that did not run never passes it.
- **No triaged fix is checked by "human review"**: a card the assistant decided to fix is accepted by its own probe
  asked again on the changed copy.
- **A module is split after its complex functions are simplified**, and an oversized module counts in the structure
  score.
- **Large tools install from disk, not memory** (the CodeQL bundle is 1.2 GB on a Mac).
- **Speed is measured on the real program**: a run proposal may start a Python server (python, pip, uv, uvicorn,
  gunicorn), not only JavaScript tools; a baseline may name the folder its server starts in and the headers a load
  sends (a token the program writes to a file). Each route is asked once first: a stream that never ends, or a route
  refusing without a value it needs, is left out and named. On EAOS's own server: 7 routes loaded with its token, no
  error, where before every API route answered 401.
- **Skipping a kept card keeps the batch true**: the other changes take their new commits, and one that no longer
  applies without it fails with why, instead of staying kept with a commit the copy lacks.
- **A fix run that kept no change ends "nothing changed"**, not failed, and may be tried again.
- **The inbox merges two askings of one topic by who asks**: two of one asker's questions are two topics however
  alike they read; across askers, the same thing named in quotes is one.
- **A change to the app's files runs the app's own checks on the card itself** (its type check, lint and tests,
  seconds): in batch 5 an unused import in one Studio file broke the type check and the build, and was found only
  when all 51 changes met.
- **Less code**: the ledger's support for commits made before 0.0.8, which nothing uses, is gone; two modules left the
  over-600-lines list (`plan.py`, `studio/export.py`).

## 0.0.24 (2026-10-14)

- **A batch is no longer blamed for its surroundings**: when its changes fail the checks together, the same checks run
  once on the code before the batch; what fails there too is set aside, and no sound fix is left out for it.
- **Screens are compared on the data they were recorded on**: the folders the app reads outside the project are kept
  as they were when the screens were recorded.

## 0.0.23 (2026-10-13)

- **Design fixes may change the screens they are about**: the behaviour lock accepts a different look on the screens
  a batch's design cards declare, and still refuses any other change.
- **Finding the change responsible rebuilds what the build makes in every half**: without it every half failed alike,
  for hours, and every Studio fix would have been left out.

## 0.0.22 (2026-10-13)

- **A batch rebuilds what its project's build generates**: when its changes touch the app, the build runs in a copy of
  the batch before the checks and the files it changes come back as one commit, so a Studio fix is never left out
  because the shipped Studio was not rebuilt.
- **Stopping a batch's finish leaves it whole**, and is not recorded as a failure.
- **Every card is tried**: an old reason for skipping a card is no reason now.

## 0.0.21 (2026-10-13)

- **Cards a closed batch had skipped open again**: 0.0.20 stopped a batch closed without handing anything over from
  skipping its cards, but the cards it had skipped before stayed skipped; they are open again (the 7 module splits).

## 0.0.20 (2026-10-13)

- **The check holds the project to the code laws**: every function past the complexity limit of 15 is a card, one per
  file (it held to 60 and the three worst before: 6 cards for 105 such functions on EAOS).
- **The score says only what was measured**: performance is scored only once the load ran on the running program.
- **A closed batch hides nothing**: a batch closed without handing anything over no longer marks its cards skipped.
- **Plain reasons**: a load on a server of the pages alone says so, and the setup asks the assistant for the real
  server; an impossible engine measure (-1 lines) no longer breaks the functions section.

## 0.0.19 (2026-10-13)

- **The Studio belongs to the computer, not to an assistant**: on a server run by systemd it is a service of its own
  (it outlives the assistant's session and comes back after a crash on its kept port and token), and told the routed
  address once (`open_studio(address=)`) it answers there with a plain address. The MCP instructions send it at once.
- **A batch survives its assistant**: a run whose assistant stopped (a limit, an expired sign-in, a crash) goes on by
  itself from the card it stopped at, with another signed-in assistant first after a limit; the bar counts every card
  the batch already tried.
- **No sound card is lost**: changes that pass alone but fail together are repaired on top (fix_edit card REPAIR)
  before any card is left out; a module split no longer reads as new complexity.
- **Honest numbers**: readiness reads the load threshold as written; a load never measures a server of the pages
  alone; journeys read the Studio's own links (60 broken links and 29 screens with no way in were false: now 0 and 4);
  the time left is no longer inflated.
- **The person's language**: card titles in the Studio's language, and texts an assistant writes in another language
  are sent back once to be written again; the run page wraps on a phone; the assistant's fixes follow the filters.

## 0.0.18 (2026-10-13)

- **EAOS's own structure, fixed by EAOS** (the second fix batch, 45 of 55 cards kept): 23 copied functions merged into
  one home each, oversized modules split along their responsibilities (Studio pages and `ideal`, `live_setup`,
  `system_map`, `behavior_lock`), complex functions broken into small ones. Functions past complexity 15 went from 198
  to 181, modules past 600 lines from 20 to 14. The combined checks found what single cards could not see (import
  cycles between a split module and its new parts, one helper over the limit, new modules missing from the layer
  policy, the Studio build): fixed on top, so no sound card was dropped.

## 0.0.17 (2026-10-13)

- **EAOS's tests pass in the check's isolated copy as on this computer.** The check and every fix batch run the Python
  suite in an isolated copy (no git, an empty home, no tools installed); three tests depended on this computer and
  failed there, so the check read "unittest fails, cause unknown" and a batch could have refused sound changes.

## 0.0.16 (2026-10-13)

- **The app starts again in the check**: 0.0.15 found the Studio's hash routes (`/#/system`...), and the setup probe
  read a same-page navigation (no request, so no answer) as status 0: the app "did not start" and setup, record,
  journeys, crawl, screens and baseline stood still. A hash route drawn in the loaded page now answers. A real
  browser test on a small hash-routed app guards it, and the probe was run on EAOS itself with the beta-trial profile.

## 0.0.15 (2026-10-13)

The check covers the code laws and the UI it had missed on EAOS itself:
- **The UI is read**: TanStack routes built in code (`createRoute`, hash history at `/#/x`) and Starlette `Route(...)`
  are found (EAOS's Studio: 38 pages instead of one root layout, 19 server routes instead of none); every check
  picture belongs to its screen with its issues (54 of 54, none before); the pictured Studio loads all its data.
- **Oversized modules**: a production module past 600 lines is a card to split it along its responsibilities, and the
  structure aspect counts them (20 on EAOS, judged "keep" before). **Copied functions**: a large shared shape is a
  precise detector of its own (47 on EAOS), copies in the same files one card.
- **One card per problem**: a screen problem in a shared part (the top bar, the language) is one card for every page;
  a semantic claim that restates the ledger is dropped.
- **The owner's share** (`eaos/owner_share.py`) covers every waiting question, not only the cards; a doubted card
  closes as not proven, judged again next check; planners decide technical choices; the check writes in the Studio's
  language.
- **The Python suite is measured** by the check (coverage, timings) as the batch gates run it, one detector for both.
- The findings' severity reaches the planner; the phone top bar shows the freshness as a count.

## 0.0.14 (2026-10-13)

- **A fix keeps the code laws or is taken back**: after each card, `eaos.execute.new_debt` compares the files the card
  touched with the check's facts: a new copied block or function, new dead code, or more decisions past the complexity
  limit refuses the card, as a breakage does (splitting a function of 60 into three of 20 is less, so it is kept).
- **The project's Python tests gate every batch**: a `tests/` suite beside the app runs with the profile's checks
  (pytest when configured, else unittest), and only the tests a change newly breaks count against it.
- **Each refused card carries its own reason**: the halving search keeps every run's verdict and logs, instead of
  stamping the batch's first failure on every culprit. The fixing assistant is told to keep public functions'
  names, parameters and modules: the lock compares them.
- **The Studio**: the screen pictures show in the live Studio (`/api/report-image`, loaded with the launch token);
  the decisions page shows only what waits for the person, the answered ones folded under one line; the assistant
  writes every message of a run in the person's language.

## 0.0.13 (2026-10-13)

- **The code laws, for every project and for EAOS itself**: least code for the best result, one home for every rule
  (written once, called everywhere), nothing dead, small functions and modules with one job. Written once in
  `eaos/code_laws.py` and carried into every assistant's work: the semantic reading looks for where the code breaks
  them, the ideal planner plans toward them, the triage and the reviewers judge by them, and the fixing assistant
  (MCP instructions and the Studio's fix prompt) keeps them.
- EAOS holds itself to them: `tests/test_code_limits.py` refuses a function written twice, an unused import or
  variable, a new function over complexity 15 or module over 600 lines, and any growth of today's listed ones.
  Six duplicated helpers now have one home each; a re-export shim and the leftovers are gone.

## 0.0.12 (2026-10-13)

- **EAOS fixed by EAOS**: a batch of 181 cards from EAOS's own check, run by the assistant with automatic accept;
  160 kept, each its own commit. 137 complex functions split into small named helpers with the same behaviour
  (functions above cyclomatic complexity 25 went from 360 to 94, the worst from 134 to 74); dead constants and
  functions removed; `eaos/recheck.py` runs through the CLI's parser; katex upgraded; Studio fixes from the visual
  review (right-to-left text, the phone top bar, empty states, small controls).
- Left out: 8 cards the behaviour lock rejected, 13 the assistant judged need a redesign or the owner's design choice.
- After the batch: a test imported a renamed helper and `eaos/fact_claims.py` was missing from the layering policy;
  both fixed, the Studio rebuilt.

## 0.0.11 (2026-10-12)

- **Branches under control from the Studio**: a group of fixes is built on a new branch named from the group, on an
  EAOS branch still waiting (continue on it, one accept), or directly on the base branch (checked in the isolated copy,
  then landed with no extra branch). Accept chooses the branch to merge into and deletes the branch after merging by
  default. The branch picker lists only the person's branches; a protected branch offers no analysis or fix.

## 0.0.10 (2026-10-12)

- **An efficient, complete check**: one theme, one picture per distinct page (46 instead of 308 on EAOS itself);
  every page is still found, the heavy Lighthouse audit runs on at most 10; the assistant reviews each page once and
  gives one finding per problem per page; a new complete check replaces the previous check's bulky data, and
  `eaos clean --pictures` deletes old pictures.
- **Few cards, the assistant decides the simple ones**: one card per real problem (per page and kind, per file and
  kind); the triage resolves each card it confirms (fix, keep, or a question for the owner) and the owner's
  questions are capped at 10% of the cards (867 cards and 847 owner decisions became 323 and 32 on EAOS's report).
- **The Studio**: the Screens page is a gallery of the pictures with problems, each problem boxed where it shows;
  "Fix with your assistant's recommendations" and an "Accept automatically when the checks pass" option.

## 0.0.9 (2026-10-12)

The information stages the slim-down removed are back, restored from `archive/before-slim-2026-10-12`, and everything
they learn reaches the person's assistant, which now judges every aspect of the program: keep it (and why it is right)
or improve it (with its plan and cards).
- **Stages restored**: `verify` (the run profile's own test command in the isolated copy, with Python or Node V8
  coverage; without consent or command, which test imports which file and why nothing ran), `journeys` (rrweb and
  failure traces, capped on disk), `readiness` (new: resilience, security, observability and the k6 baseline against
  the intake, as findings with evidence, from the old handover kits), `architecture` (CodeCharta city and Emerge
  clusters, JSON only, with their hotspots and clusters), `sustainability` and `transform` (the six indicators and a
  canonical home per repeated definition). Tools back in the toolchain: temurin-jre, rrweb, codecharta, emerge.
- **Every aspect reaches the assistant**: `eaos/aspects.py` digests eleven aspects for the ideal planner's bundle and
  the semantic reading; the planner answers a verdict per aspect; the rules give theirs where it does not;
  target-architecture.json, TARGET-STATE.md and GAP-AND-STRATEGY.md list every aspect with its verdict and who gave it
  (test_aspects: every restored aspect is in the planner's bundle and its verdicts reach the gap report).

## 0.0.9 (2026-10-12)

- **Every aspect of the program reaches the person's assistant**: the information stages the slim-down removed are
  back (sustainability indicators, canonical homes of repeated code, the architecture map, test coverage run with
  the person's consent, light user journeys) with a new record of behaviour under load and failures (performance,
  resilience, health, telemetry, security surface). The ideal planner judges every aspect: keep (with why) or
  improve (with the plan); the gap and target reports show those verdicts. 34 stages.
- **The test suite is an aspect too**: the check reads each test's time from the runner's own report (pytest,
  vitest, jest) and, through Coverage.py's "who tests what", the tests that run no line no other test runs; the
  assistant judges the suite (merge, speed up or delete). No new tool: both are switches of tools already in use.

## 0.0.8 (2026-10-12)

The fifteen fixes of the 2026-10-12 review; each is proven by the test named after it.
- **A stale fix batch no longer blocks every fix**: a batch whose base is not the current code is retired by one
  helper (status, fix_start, after a check); a failed fix_finish leaves the batch as it was; `tried` holds card keys
  (test_continuity: a batch left on code that moved on is retired).
- **Honest progress**: cards are keyed on the observation uid; a problem no longer found leaves the ledger and never
  counts; progress is the cards fixed and merged; one problem count on every page (test_journey: progress counts
  only the fixes merged).
- **Fixing from the Studio**: the fix run may call fix_abandon, findings and plan; the person's answer acts and a
  direct step is not blocked by a question; a run that kept nothing says so; the preview chooses where to build,
  the new branch (`eaos/<branch>/wave-N`) and where to merge, and pins the base commit (test_studio_actions,
  test_branches).
- **A true report**: the assistant's verdicts are applied once, before ranking, the plan, the reports and the
  ledger (rejected cards leave with their reason, doubted ones are judged again on their measurements and never
  auto-fixed); complexity needs a value over its threshold and ranks by severity, one card per function hotspot;
  files loaded by path and package data are not dead code; complexity alone is modify, not rebuild; CLI features by
  subcommand; plain areas and labels (a `ux` area), real sections and sizes, design cards deduplicated, minified and
  generated files left out (test_joint_decision, test_claims, test_deadcode, test_target_projection, test_features,
  test_plan, test_roadmap, test_facts_scope).
- **The Studio reads well**: markdown and tables in run results and messages; the branches page shows the work
  branches, "on this computer" / "on GitHub", the cleanup in a sheet; decisions without duplicates or questions the
  machine answers, one waiting count (Vitest: runs/parts, branches/model; test_studio_export).
- **Real screen pictures**: an empty "no data" page is not a working app; EAOS's own Studio runs on its report's
  data; dark pictures are taken; pictures are named from the `#/route` (test_live_setup, test_screens).

## 0.0.7 (2026-10-12)

- **EAOS made small: only what the person's journey uses is left.** Removed: the model-provider path (`eaos run`,
  `continue`, `implement`, `improve`, `live execute`); 30 commands outside the journey (19 remain: start, next,
  status, doctor, clean, accept, undo, show, do, assistant, handover, studio, mcp, tools, audit, facts, policy,
  recheck, decided); 14 check stages whose output nobody read (42 → 28: verify, journeys, architecture,
  sustainability, transform, execution guide, quality, pdf, executive, compose, bundles, emit, site, validate); the
  audit-manual era (MASTER-MANUAL, modules, core, controls, sources, duplicate schemas); the old plans and records
  (north star, capability plan, adoption notes, trials); the north-star tooling and the acceptance folder; 15 tools
  only those stages used (CodeCharta, Emerge, Structurizr, Typst, Vale, markdownlint, Zensical, rrweb…). Everything
  removed is kept under the tag `archive/before-slim-2026-10-12`.
- `eaos next` no longer calls a model to fix: the fixes are made by the person's assistant (`/eaos`) or from the
  Studio, through the MCP tools. The assistant code moved from `eaos/runtime/` to `eaos/assistants/`.
- A check writes less: the C4 diagrams come before the four reports (so the reports show them), and the engines'
  working folders (a 130 MB code index on a five-file project) are deleted once their findings are read.
- The Studio lost the "EAOS quality" page, the hidden gallery, the demo mode and the plan-step ids it showed people.
- Tests: 2228 → 536, one hour → 3.3 minutes; `tests/test_journey.py` checks, changes, checks again, fixes and
  accepts on a small project in two seconds. `ROADMAP.md` is now the only plan.

## 0.0.6 (2026-10-11)

- **The check uses the person's assistant unless they said no, and never turns it off silently**: before a check
  starts, the assistant is asked for one word (installed, signed in, answering). When it does not answer, the check
  does not start; the person is told what is wrong and how to fix it, and chooses: check again once fixed, the other
  assistant, or this one check without AI. An assistant that stops answering midway names its reason on the live map
  and in the report (a sign-in that expired, a usage limit, no answer). `eaos doctor` asks each assistant for one
  word, and the MCP tool `assistant_check` shows which is ready.
- **Full governance of the branches from the Studio**: the person's own branches are merged and deleted on their
  confirmation, each preview saying whose branch it is; a branch held by another clean worktree is deleted with it;
  "Clean up merged branches" removes, in one confirmed step, every local branch already in the base or a protected
  branch and the old clean worktrees, each branch kept in a recovery ref so it can be restored.
- **Re-scanning a branch is a new check**, never the check on record.

## 0.0.5 (2026-10-11)

- **The assistant decides before the target, the gaps and the plan; the reports come last** (pipeline v2): the
  check gathers the evidence first, lets the tools propose, lets the person's assistant decide with them, derives
  the gaps and the plan from that joint decision, and writes every report from the final records. The triage now
  runs on the candidate cards and a card it rejects leaves the plan and the gaps; the ideal planner answers each of
  the tools' proposals for the target (accept, modify, reject) and a `reconcile` stage builds the final target from
  those answers, keeping the rule's view beside each change; the plan orderer's steps become the plan's order.
  Every component of the target, and every report, says who decided: agreed, changed by the assistant, the rules
  alone, or a disagreement a guard settled. Without an assistant the path is the same and the findings are those
  of the rules alone, identical to 0.0.4's.
- **The app runs inside the check** once the person agreed (the existing run consent): set up in an isolated copy,
  its behaviour recorded, its journeys recorded with Playwright's trace and rrweb, every page found by Unlighthouse
  and pictured in light and dark at phone and desktop width with axe, its speed measured with k6 and read by the
  load model. Without consent, or when the app does not start, each live stage says why.
- **Visual evidence**: the person's assistant looks at the screen pictures (it may open them and nothing else) and
  every finding names its picture and region and becomes a design card; the architecture map draws the code as a
  city (CodeCharta) and its dependency clusters (Emerge); the report's UI gallery shows the screens with the
  findings drawn on them, replays the journeys from local files and draws the city.
- **The Studio opens from a plain address that keeps working**: on this computer the address is
  `http://127.0.0.1:<port>/`, with no token at its end, and it stays the same when the Studio restarts (an address
  saved before keeps opening it). Installed from inside a project, EAOS opens that project's Studio at once, on
  "Preparing the tools"; `eaos studio --background` does the same from anywhere. On a remote server, the Studio
  gives its server address instead, also with no token at its end (it listens on every interface, and the page
  receives its token itself): set it once in `~/.eaos/remote-origin` (or `$EAOS_REMOTE_ORIGIN`), for example
  `https://<project>--{port}.dev.remote.e-m.sa`.
- **The Studio** names the new stages on the live map and lists every rule-vs-assistant disagreement, with both
  views, on the decisions page.

## 0.0.4 (2026-10-10)

- **The interface first, the tools in the order they are needed**: whenever EAOS is called on a project, the Studio
  opens at once on "Preparing the tools": every tool with its state, overall progress and time left. Tools install
  three at a time, the check's first, once per computer for every project, resumable and checked by sha256. "Start
  the check" unlocks by itself once the tools this project needs are ready; the rest keep installing, faded on the
  live map until each is ready. A failed tool shows its reason and Retry; the check does not start without a tool it
  needs unless the person picks "Start without it", and the report records it. A second start is ready at once, and
  the vulnerability database refreshes itself daily in the background.
- **AI stages take the time the work needs**: no time or cost cut-off; an assistant is ended only when it writes
  nothing at all for 20 minutes, or when the person stops it, and the stop ends the assistant too. Each AI stage's
  prompt says its goal, what it is given, what to return and what a good answer is.
- **A faster check, the same findings**: the slowest engine (CodeGraph) runs beside the others, and the executive
  summary reuses the plan the check already made; a check of EAOS itself went from 17 to 12.5 minutes.
- **The same project gives the same numbers**: the engines' findings no longer depend on when the files were
  copied, so a complexity a card quotes is the same on every fresh copy of the same commit.
- **A fresh tools install works on its own**: Python tools install and run without EAOS's own packages on their
  path, so none misses a library (Semgrep failed on a new computer without attrs).
- **The live check map**: while a check runs, from the assistant, the Studio or `eaos start`, the Studio draws
  EAOS's own stages live: the running stage glows, a light moves to the next ones, and each stage says what it does,
  how long it took, its steps, what it produced and why it was skipped. The setup, safety and fix flows have their
  own maps, a check stopped midway resumes from the stages it finished, and recorded screens show as pictures.
- **AI in the check**: EAOS asks once whether to use the person's assistant (Claude Code or Codex; `--yes` answers
  yes). With a yes, the assistant reads the facts (`semantic`), plans the ideal picture right after the check
  (`ideal`), judges every card on its evidence (`triage`) and orders the plan's steps (`order`). Everything it says
  cites its evidence and stays a hypothesis; anything without evidence is dropped. Without an assistant, or when it
  fails, the rules decide alone, the stage says why, and the check still finishes. AI stages carry an "AI" mark on
  the live map.

## 0.0.3 (2026-10-08)

- **Six code-understanding engines** run inside EAOS, each at a pinned version with its licence recorded:
  ast-grep (EAOS's own React rules), Lizard (complexity, length and parameters per function), complexipy
  (cognitive complexity of Python functions), vulture (unused Python code), knip (unused files, exports and
  dependencies, without running any project configuration) and react-docgen (components and their props).
- **The screen gate** (`tools/studio_gates.py`): pinned axe-core, Lighthouse, css-analyzer and Playwright check every
  screen at phone, tablet and desktop widths, in Arabic and English, light and dark: nothing spills past the screen
  (the page's layout width must equal the screen's), it opens at the top, touch targets are 44px, no accessibility
  violations.
- Fixed: the dead-code and broken-code checks gave different ids to the same commit in a fresh checkout (they hashed
  file times); they now hash content only.

## 0.0.2 (2026-10-03)

- **`/eaos` alone shows a menu** (`$eaos` in Codex): the options that make sense for this project now, the recommended one
  first, with the project's own numbers ("batch 4 is open: 1 kept, 2 left", "eaos/wave-2 waits for you"), in pages of four
  you move through with the arrows (eaos/menu.py, the `menu` tool). Nothing is offered that cannot be done yet: no report
  before a check, no "continue" without open work. In Claude Code, `/eaos` also lists a direct command for each option
  (`/eaos:report`, `/eaos:tasks`, `/eaos:ask`, `/eaos:tools`, `/eaos:continue`, beside `audit`, `fix`, `build`, `status`).
- **Ask about your code**: the `impact` tool (what changing a file or a symbol touches: who imports it, the flows and tests
  through it, the files that change with it) and `ask` (the check's records that answer a question, each with its place).
- `tools_check`: this EAOS's version and every tool it runs, which this project needs, and the one command for what is missing.
- Fixed: `eaos doctor` and every report said 0.0.1 after the package became 0.0.2; a test now holds the package, the code and
  this file to one version.
- **Fixed: on a person's own computer the engines never ran the tools EAOS installed for them.** `eaos tools install`
  puts every tool in `~/.eaos/tools`, but the engines looked for them in a folder of the server EAOS was built on, then
  in PATH, so on a Mac most engines were silently missing. Both now read the same folder (`$EAOS_ENGINE_TOOLS`,
  default `~/.eaos/tools`), and a test fails if any code names a path of one machine.
- **EAOS can be developed from a clone alone, on any computer.** `bash tools/dev_setup.sh` builds everything a developer
  needs; the sample corpus, the engines' sources and the measurements live under `~/.eaos/dev` (`$EAOS_DEV_HOME`,
  `tools/dev_paths.py`) and are fetched at their pinned commits. `AGENTS.md` (and `CLAUDE.md`) tell the assistant
  developing EAOS how the owner works, how versions, the plan and the trials go.

## 0.0.1 (2026-09-29)

Versions restart at 0.0.1 and stay 0.0.x until the first official release, 1.0.0. From the owner's trials:

- **The report cannot go stale in silence.** Building it no longer swallows a failure: the part that could not be built is
  named at the top of the page, in `.report.json` beside it and in `logs/`, and the rest of the page is still made. Every
  page says which EAOS made it (version, commit) and when; after an update, `status` rebuilds a page an older EAOS made at
  once, from the check on record. `eaos doctor` prints the version and commit.
- **Fixed: a batch with a card the assistant fixed could not be closed** (`execution.json would break its contract: tool
  'assistant'`), in the repository's contract and in the copy the package installs.
- **True progress**: a stable key per card, carried by every EAOS commit, so what is merged is read from git; the report
  counts only what is in the person's branch.
- **A merge closes the loop**: accept merges, deletes the branch and rebuilds the report in one step; a merge made by hand is
  noticed and recorded.
- **The branch**: when a project has several branches, EAOS asks which one (never choosing for the person) and everything
  follows it.
- **Handover between assistants**: every step journaled, `note`, `HANDOVER.md`, a session-start hook for Claude Code and Codex
  (`eaos handover --hook`) so a new session knows where the work stopped and on which card, and `eaos handover` for the person.
- An AI assistant's working copies inside a project (`.claude/worktrees/`) are no longer audited as part of it.

## Unreleased

- **Release decision: pilot.** Measured on this repository and on a Go project, with codegraph, enola, jscpd and reforge all running: overall 0.8537, seven of nine domains at target. `structure_polyglot` went 0.3027 → 0.9228, `load_model` 0.0 → 0.9535, `target_architecture` 0.0 → 1.0. The two domains left are not code problems: `transformation_plan` carries one unmeasured indicator because verifying a prediction needs a report taken after the change and the engine never writes code, and `independent_proof` needs a reviewer outside this project. `evaluations/release-evidence.json` states both, and what the evidence does not support.
- **Fixed: CodeGraph was never an adapter.** `engines.analyze` reaches every engine through `ADAPTERS[name].analyze(...)`; CodeGraph had no `analyze`, so every run raised AttributeError, the registry caught it into a status nobody reads, and the engine stayed out of `engines_observed` — which the fact layer's merge was guarded on. A binary indexing 18,241 nodes and 66,477 edges contributed nothing and said nothing about it. Its tools also only answer about a file: given a directory the dependency graph returns `edge_count: 0`, and complexity refuses the call without a `uri`. It is now asked file by file, about the files the report actually speaks about, inside a recorded budget.
- **Fixed: a Go package import was recorded as ambiguous, then as a test file.** A Go import names a package, which is a directory; the resolver demanded a single file and declared ambiguity for 1,336 of 1,430 imports whose candidates all sat in one folder. Resolving to the package moved `imports_resolved_outside_python` from 0.0594 to 0.9769 — and then picked the alphabetically first member, so 315 production imports pointed at a `_test.go` file on the dependency graph the policy, the tracer and the claims all follow. The directory is recorded in `package_path`, and the stand-in file is never a test while a source file exists.
- **Fixed: Go had no traced flows, so no load question could be answered.** Nine entry points produced one flow on 985 Go files — and that flow was a Python packaging script. `func main` was not an entry point at all, and eight of nine handlers could not be linked to a symbol. Flows on Go went 1 → 25.
- **Fixed: "we looked and found nothing" was recorded as "we could not look".** Five of the eight load questions returned `undetectable` with reasons like *no cache site on this path* — an answer worth `False`, recorded as an inability. It is now `answered` when two things hold together: the flow was traced, and every file on it is in a language that question's detector knows. Where either fails it stays `undetectable`, with the reason.
- **Fixed: the no-regression gate compared each run against the file every run overwrites.** A fall in `transformation_plan` from 0.9788 to 0.6667 passed through it without a word. The bar now lives in `docs/capability-high-water.json`, written only upward and stamped with the commit that reached it, and the gate is tested against a fall, not only against a pass. Measurement also runs with the engines on, and the scorer refuses a report produced without them.
- **Fixed: a transform stage's acceptance command was unreadable to its own reader.** The producer wrote `acceptance.argv`; the scorer reads `acceptance.command`. The indicator the change was meant to raise fell to zero while its unit test passed.
- **R14: every document names the record a model can act on, or says why there is none.** Twenty of thirty-three named nothing. Checking that a named twin is itself declared turned up three documents pointing at files no stage owned.
- **The transform stage writes its prediction down before anything changes,** into a declared `predictions.json`, and the guarantee comparison is now tested against a change that actually happened — a project with a real duplicate, the duplicate removed, both sides audited, a verdict per indicator — instead of against a report compared with itself.

- **The output contract now sees the whole report.** Sixteen of thirty documents were outside it entirely — unbudgeted, unowned and unchecked — so "zero violations" was a statement about half the output. `eaos/compose/artifacts.py` declares every artifact with an owner stage, a purpose, a reading order, a budget and, where one exists, the record holding its full detail. `rules.py` reads its budgets from that declaration instead of keeping a second list, examines every markdown file in the report, and adds R13: a produced-but-undeclared document is a violation, and a required-but-absent one is a violation unless the run manifest explains it.
- **Fixed: the bundles stage destroyed 574 lines of measured content on every full run.** `discover.write_all` wrote `SYSTEM-MAP.md`, `FLOWS.md`, `CONTRACTS.md` and `EVOLUTION.md` over the versions the claims stage had already rendered from the ledger, and its own versions were empty because `_facts_by_kind` looked the fact kind up as if it were a set name. The helper is fixed, the three duplicate renderers are gone, the fourth was rendering outbound integrations under the name `EVOLUTION.md` and is now `INTEGRATIONS.md`, and a test fails if any document is written from more than one module.
- **Fixed: `facts/runtime.json` was not reproducible.** Its `by_kind` summary iterated a set, whose order Python randomises per process, so two collections of an unchanged tree differed byte for byte — against the guarantee the fact schema itself states. The kinds are a sorted tuple now, with a test that collects twice and compares bytes.
- Five documents ran 2–5× over the default budget once the contract could see them: `transform-plan.md` at 1,065 lines, `SUSTAINABILITY.md` at 664, `TARGET-ARCHITECTURE.md` at 478, `CANONICAL-HOMES.md` at 382, `STAGES.md` at 253. Each now shows the entries a reader acts on and points at the record holding the rest; `sustainability.json` and `canonical-homes.json` are written for the first time. `SUSTAINABILITY.md` also stopped dumping raw JSON into a human artifact, which R8 had always forbidden and never caught.
- **Fixed: `--only <stage>` was unusable.** A prerequisite was considered met only if it ran in the same invocation, so re-rendering one stage over a finished report answered "prerequisites not completed" while every input sat on disk. A prerequisite is now satisfied by its artifacts existing.
- **Fixed: one run reported two different verdicts.** The engine graded a partial run PARTIAL and the printed summary re-derived it as INCOMPLETE. The summary repeats the manifest's verdict instead of computing its own.
- `README.md` now generates its file inventory from the artifact contract, so every document appears with the reason to open it; whether a given run produced it stays RUN.md's question.
- A policy that leaves files outside every layer reports INCOMPLETE rather than OK, because unclassified files are unchecked files. Three tests cover the clean, incomplete and violated cases.
- Three tests asserted against the product's own doctrine and have been rewritten: one forbade the bundle manifest the stage declares, one called a policy with uncovered files clean, and one expected a verification verdict where no prediction had ever been recorded. The guarantee module is now tested by recording a prediction and grading it.

- **`eaos audit` runs the whole thing in one command.** The pipeline is declared as data — thirteen stages, each naming what it requires, what it produces and when it may legitimately be absent — and executed by one engine that writes `run-manifest.json`. A stage that fails no longer takes the run with it: its dependents are recorded as `not_reached` with the reason, the independent stages still run, and `--resume` repeats only what did not finish. `RUN.md` states what the run did and did not examine before any finding is read.
- **`eaos review-project` no longer carries its own copy of the order.** It is now the pipeline minus the engines and verify stages. Its old hand-written sequence is why five subsystems — sustainability, engines, transform-plan, probe and verify — were unreachable from the command most people ran, without the output ever saying so.
- **Renamed: `eaos audit` (the old agent-run bootstrap) is now `eaos legacy-audit`.** The behaviour is unchanged; the name moved to the command that performs an audit. A fuller retirement of the older run path is stage T4 of `docs/TRANSFORMATION.md`.
- `eaos stages` prints the declared pipeline and refuses a declaration with a forward reference, a cycle, two stages owning one artifact, or an optional stage that does not say when it may be absent.
- The wave document switches to one row per wave once the sectioned form would be mostly chrome: at 83 tasks over 48 waves the old form rendered 332 lines against a budget of 140 and lost every task to trimming.

- Verify the sustainability engine and fix what the verification found. The structural-duplication, sequence, redundancy and scorecard facts never reached the ledger, so a detected duplicate produced no claim, no decision and no card; they are wired in now, each with a probe that can re-decide it.
- Cut the redundancy detector's false positives from 4,691 observations to 216 on this repository — N+1 from 1,014 to 2 — by making a call's identity include its callee and receiver, treating names assigned inside a loop as loop-varying, excluding the loop's own iterable, reporting only computations whose value is stored, and dropping trivial builtins, side-effecting calls and mutually exclusive branches. The reference case still fires.
- Fix the verifiability indicator, which read a summary key that does not exist and therefore always returned 1.0, and compared it against a target of zero so a perfect result read as the worst gap. Every indicator now points the same way, and an indicator that cannot be measured says so instead of reporting a number.
- Stop `eaos sustainability` and `eaos transform-plan` from re-collecting a hand-listed subset of fact sets: doing so reran dependent extractors without their inputs and overwrote 36 traced flows with zero. A test now fails if any command asks for a partial collection.
- Put the list of fact sets in one place. Five modules kept their own copy, and a set added to one was invisible to the others — the duplication this product exists to find, in the product itself. The same applies to declared analysis exclusions, now read once in the facts layer and honoured by every command.



- Fix `verifiable_paths` indicator: `verifiable_paths` is now in `_LOWER_IS_BETTER` (the indicator measures the fraction of flows that stop at the first boundary, so lower is better and the target is 0.0). The executive verdict treats any non-zero gap as a violation; the progress module labels the direction correctly.
- Fix the executive page to handle unmeasured indicators: a `None` value now reads "not measured" instead of the literal string `None`. The page is now safe to read in a meeting.
- Fix `progress.render` to skip indicators that are not measured instead of crashing on `None` arithmetic. A new direction value `unchanged` distinguishes "no movement" from "worsened".
- Add the discovery documents (`eaos/discover.py`): `SYSTEM-MAP.md`, `FLOWS.md`, `DATA-MODEL.md`, `CONTRACTS.md`, `DEPLOYMENT.md`, `OBSERVABILITY.md`, `SECURITY-SURFACE.md`, `EVOLUTION.md`. Every bundle the engine claims to produce is now produced, with content sourced from the persisted fact sets.
- Add the bundle generators: `CANONICAL-HOMES.md`, `gap-matrix.json`, `KPI.md`, `STAGES.md`, `WAVES.md`, `engagement.json`. The five-bundle packager now produces 38 files on a real codebase instead of an empty skeleton.

## Sustainability engine

Add the six-indicator sustainability dashboard, the structural detectors that feed it, and the machine-executable transform plan it produces. Five new fact extractors ship with their own golden snapshots and tests; one new command renders the dashboard, another renders the plan.

- **`eaos/facts/structure.py`** records loops, branches, scopes and call sites for every parsed language. Without these facts, a duplicate call inside a loop is invisible; with them, the L5 detector can see what is happening.
- **`eaos/facts/fingerprint.py`** normalises every function to a shape tree that ignores identifier names. Two functions computing the same rule under different parameter names cluster together; structurally different functions do not. The doctrine's reference example (`compute_total` vs `order_total` vs `invoice_amount`) lands in a single cluster.
- **`eaos/facts/sequences.py`** sliding-windows each function's ordered list of callees. Three functions calling `validate → save → notify` in the same order appear as one cluster, and a different ordering produces nothing.
- **`eaos/facts/redundancy.py`** flags four classes of redundant work: a repeated call with the same arguments, a call inside a loop that does not depend on the loop variable, an attribute access on a loop-bound value (the N+1 idiom), and a pass-through layer whose body forwards its arguments to one call.
- **`eaos/sustainability.py`** computes the six indicators P1..P6 from the new facts alone, ranks moves by gap, attaches a falsifier to each move, and writes `SUSTAINABILITY.md`. Indicators are pure functions of facts; targets are taken from the engagement contract or the declared policy.
- **`eaos/canonical_home.py`** picks a candidate file or directory for a cluster of duplicates. A candidate must be reachable from every duplicate site, must not create a cycle, and must satisfy the project's layering policy. No viable candidate means the project needs a layer rule change before unification is safe.
- **`eaos/transform_plan.py`** turns the dashboard into `transform-plan.json` and `transform-plan.md`. Each stage carries the canonical home, the sites, the steps, the acceptance criterion, the rollback note, the falsifier and the predicted indicator delta. A model or human reviewer can consume the plan stage by stage; nothing requires running the engine again.
- **`eaos sustainability` and `eaos transform-plan`** commands render the artifacts from any project.

The engine runs against itself in seconds; the self-audit reports a single canonicalize move and ten redundancy moves, with zero policy violations.

- Break the import cycle the growing package had formed: the ledger no longer rebuilds the plan or the product report. A new `eaos/views.py` sits above them and refreshes everything downstream in one direction, and the product report renderer moves into the composer. The package is acyclic again, with a test that fails if a cycle returns.
- Express that layering as declared policy: nine layers with seven forbidden directions, each with the reason it exists. Enforcing it immediately caught six real inversions, including the ledger calling the refresh layer that calls it.
- Let a project declare `analysis.exclude` in its policy. Test corpora and fixtures are the project's own call, not a hardcoded default, and the exclusion is reported in the output. This repository now excludes its benchmark fixtures, and its dossier is about the product again.
- Report a maintenance hotspot when the function is among the most branching in the project, not only when its file is top-ranked for attention. Adding modules had pushed the single most complex function out of the ranking and silently dropped the finding.
- Detect a script's `__main__` guard as an entry point, so runnable tools stop looking unreachable.
- Report cross-module writes only for modules the snapshot defines; setting a standard-library attribute is an idiom, not a violated invariant.
- Say plainly on a task card when the claim names no file, instead of printing an empty blast radius.
- Write semantic claims in the reader's language, and refresh the views from the command that changed the ledger rather than from the ledger itself.

- Refresh the derived views whenever the ledger changes. The index reported "tasks 0" next to ten generated cards, and still said no semantic review had run after one had, because the brief, the risk register and the index were written once during assembly and never again. Probing, the semantic pass and plan generation now re-render them.

- A probe now only settles what it can actually settle. A branch-count measurement confirmed a claim about *why* the branches existed; a static check can show that a structure exists but not why, so a claim of cause or responsibility rises to LIKELY at most and the probe is recorded as PARTIAL with the reason.
- Dependency probes can be directional. A claim that one layer must not import another was refuted by an edge running the other way, which is allowed; `direction: one_way` distinguishes the two and reports the reverse edge instead of contradicting the claim.
- An unproven claim now produces an investigation task rather than nothing: prove it or drop it, with no code change until it is decided, and the acceptance criterion is the probe returning a verdict.

- Add `eaos semantic`: the model reads the fact digest and the confirmed claims — never raw files — and may only return interpretations that cite facts already held, each with a falsifier. Model inference can never reach CONFIRMED on its own; a probe has to do that. This is the path that assesses responsibilities, boundaries and internal contracts, and it is labelled as inference throughout.
- Enforce a declared policy as part of the dossier, so a forbidden edge becomes a claim with a task card rather than a separate report.
- Extend the benchmark corpus to nine cases covering every claim class the tool detects, and measure the plan as well as the detection: 8 of 8 planted defects found, no false positives, against 1 of 8 for the grep baseline, with a complete and runnable card for every actionable finding.
- Add `README.md` to the dossier: an index with a reading order for four kinds of reader, and a grade for how well each section is sourced — including the plain statement that responsibilities and internal contracts are not assessed without the model path.
- Add `ONBOARDING.md`: build and test commands taken from declared manifests, the entry points worth trying, the ten files to read first ordered by the graph, the project's own vocabulary, and the traps this snapshot already knows about.
- Render claims in the reader's language from a template and its parameters, and link every finding in the brief to the artifact holding its detail. The Arabic dossier no longer mixes Arabic headings with English sentences.
- Rank answers by structure rather than word overlap, and suggest the next command after every answer. "what handles POST /orders" now returns the entry point first.
- Add `eaos policy check` and `eaos policy init`: the project declares its layers and the dependencies it forbids in `eaos.policy.json`, and every resolved import edge is checked against it. A violation is a fact with a location and the reason the team wrote down, and the command exits nonzero so CI can hold the line. This repository now declares and passes its own policy.
- Add `eaos api-diff`: the exported surface of two snapshots compared, separating what breaks a consumer (a removed name, a removed parameter, a new required one) from what does not (an addition). Function signatures are now captured as facts to make this possible.
- Add three claim classes: a maintenance hotspot where branching concentrates on a central, frequently changed path; module-level state that is actually mutated at runtime, kept separate from tables merely built at import time; and a module writing into another module's namespace. Each carries a probe that can re-decide it on a later snapshot.
- Add `eaos impact-of <path|symbol>`: what a change reaches, computed from resolved imports, traced flows, executed coverage and history — direct and transitive dependents, flows crossing the target, tests that cover it, and files that historically change with it.
- Rank findings by a declared formula — reach × confidence × origin ÷ cost — with every input exposed on the claim, replacing an ordering that effectively sorted by the length of a sentence. New `RISK-REGISTER.md` artifact.
- Add `eaos tasks`: a self-contained card per confirmed claim, with the blast radius from facts, remediation options that always include doing nothing and its cost, a rollback, an effort estimate that states its own confidence, and an acceptance criterion derived from the probe that confirmed the claim. Cards are sequenced into waves, where two tasks touching the same file never share a wave and investigations precede the changes they inform.

- Verify the isolated copy as a whole tree: any file added, removed or modified outside the planned task files now blocks `VERIFIED_IN_ISOLATED_COPY`, and `changes.patch` is derived from the real difference between the original and the delivered candidate. Two regression tests, one reproducing the prior defect where a check could create an unplanned file and still reach a verified state.
- Derive the expected packaged data set from canonical sources instead of the files that happen to exist, so a missing, stale or leftover packaged file fails validation. New `tests/test_packaging.py`.
- Add a deterministic fact layer (`eaos/facts/`) with nine extractors: multi-language syntax (tree-sitter, optional extra), import resolution to real file targets, entry-point detection through framework plugins, configuration and environment reads, size/branching/duplication metrics, repository history, domain constants and data models, the dependency graph with a declared attention ranking, and static flow traces from each entry point. Per-file results are cached by content hash; a cached run is cheaper but byte-identical.
- Add `eaos map`: a full structural picture (system map, coupling atlas, evolution lens) with no model call, in about a second on a mid-size repository.
- Add a unified claim ledger (`eaos/claims.py`, `schemas/claim.schema.json`): every assertion carries confidence, method, evidence or facts, and a mandatory falsifier. Existing findings, architecture records and flows bridge into it without gaining certainty.
- Add `eaos dossier`: assembles `dossier.json` and derives every human artifact from it, under an output contract (`eaos/compose/rules.py`, rules R1–R8) that fails the build on an unsourced claim, a budget overrun, a live risk with no disposition, a task with no runnable acceptance command, or a record dump in a human artifact.
- Add `eaos probe`: re-decides claims mechanically. A claim can declare `probe_spec`, so it stays testable on later snapshots; a failing probe marks it REFUTED and keeps it in the ledger.
- Add `eaos verify --execute`: runs the test suite with coverage in an isolated copy and maps real execution onto components and entry points, so a claim can be confirmed by something that ran.
- Add `eaos delta`: compares two dossiers and exits nonzero on a new confirmed or likely risk, making the tool usable as a CI drift gate.
- Add `eaos ask`: answers strictly from recorded facts and claims with citations, and says plainly when nothing in the records answers the question.
- Add `eaos site`: one self-contained HTML page with navigation and search, rendering the same records.
- Add `eaos evaluate`: measures detection against benchmark cases with declared ground truth and against a grep baseline, and states what was not measured.
- Feed deterministic facts into the model pipeline: the audit now inspects files in attention order and can declare a file budget, with deferred files recorded as omissions rather than silently dropped.
- Add `verify_command` to the roadmap task contract so a task's acceptance criterion can be executed rather than described.
- Enforce the schema keywords the contracts already declared. `pattern`, `minItems`, `maxItems`, `const`, `minimum` and `maxLength` were silently ignored, so a claim with a malformed id and no method passed validation while the schema said otherwise. Unknown keywords are now reported instead of ignored, and `evidence_ids` no longer claims a minimum the ledger deliberately does not require of fact-backed claims.
- Decide duplicated-rule probes from parsed facts instead of a text search. A mention of a constant inside a test's string literal was enough to refute a true finding; a claim is now withdrawn only on a resolved import that actually brings in that name, and weaker evidence yields INCONCLUSIVE.
- Capture the names an import brings in for tree-sitter languages, which is what makes that judgement possible.
- Mark every claim as coming from product code or test code, rank product findings first in the decision brief, and label test-origin findings.
- Stop stating that no execution evidence exists when a verification run produced it.
- Bind argparse commands to the handler registered through set_defaults, including the loop-over-pairs form. Flow tracing on this repository goes from one useless trace to nineteen that reach real code.
- Collapse one flow per handler instead of one per route, and separate traces that stop at the first boundary from traces that reach further code.
- Restrict the public-API surface to top-level packages, split standard-library imports from third-party ones, rank answers by record kind and let an Arabic question reach the rendered Arabic artifacts, and cut long statements on word boundaries.
- Run verification with the interpreter that is actually running EAOS instead of a bare `python` on PATH. On a system that ships only `python3` the default test commands could not start, and a run silently lost all execution evidence. Found by installing the wheel and running it against the repository from outside.
- Add `--exclude` to `eaos map`, `eaos dossier` and `eaos facts`: leave vendored or fixture paths out of analysis, with the exclusion reported in the output rather than applied silently.
- Add `eaos facts <target> --out <dir> --history`: deterministic repository-history facts (churn, co-change, ownership, age, fix density) with no model call. Commit subjects are classified then discarded, so commit text never enters the fact set. Reruns on the same input are byte-identical; timestamps live in `facts/run.json`, not in fact records.
- Redact source with whole-file context before selecting line ranges, preventing multiline private-key bodies from leaking through partial reads or chunk boundaries. Added two regression tests.
- Correct SECURITY.md to distinguish local audit commands, network/command model providers, and isolated-copy remediation.
- Add local development instructions and an Arabic technical review.

## 2.0.0 — 2026-09-17

تغيير محور المنتج إلى Architecture / Structure / Maintainability / Evolvability. إضافة14 قاعدة مستقلة في مجال27، نموذج معماري بأدلة وعقود وملكية قواعد وسيناريوهات تغير، واستعلامات graph/impact/context. default profile architecture مع مجالات مساندة out of scope صراحةً، وfull يحافظ على التغطية العامة. لا ترقية صامتة لسجلات1.0؛ أنشئ run جديدًا. أضيف تحليل الفيديو الثالث وثلاثة مراجع معمارية، مع فصل البذور عن القواعد المعيارية. لا استخراج AST تلقائي ولا LLM provider invocation.

## 1.0.0 — 2026-09-17

إصدار أول للإطار العام وCLI الجرد والأدلة والتحقق وحزم السياق والاستئناف؛ تحليل نصي للفيديوين الأولين. النسخة محفوظة في تاريخ git.
