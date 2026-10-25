# Changelog

## 0.0.78 (2026-10-25)

M6, the whole system in layers. EAOS knew the right layers of ten kinds of project but enforced them only when a project
declared its own `eaos.policy.json`, and it checked no endpoint's guard, no row-level security beyond two hidden rules,
and nothing of what ships to the browser: on the trial app planted with one defect per boundary it found none of the
nine (a screen querying the database, a secret-named setting shipped to the browser, a privileged key in the built
output, a write with no sign-in, a read of anyone's row, a rule kept only in the browser, a table without row-level
security, a policy open to everyone, a write no test reaches). Now every check reads the system as layers:
- **The layer map** (M6.1): every file in a layer of its reference type, by its path, else by what it imports (a
  handler, a database client, a component) into the layer of that role its imports keep; a file in none is a listed
  gap. Beside its layer each file has a side: the browser's, the server's, both, the database's.
- **The boundaries by default** (M6.2): each layer may use only what the reference allows; a breach is a card at its
  import, a low-confidence placement a question; dependency-cruiser gets the same rules and follows browser code to
  server code through any chain of files.
- **What ships to the browser** (M6.3): secret-named settings, privileged keys in code and in the built output, source
  maps shipped, server code imported by the browser, a database driver or SQL in a screen.
- **Every endpoint and its guard** (M6.4): one table (method, route, handler, sign-in, ownership, input check, the data
  it touches) for Next.js routes and server actions, Express, Fastify, Hono, Koa, a bare node:http server, FastAPI,
  Flask, Django and Supabase edge functions; a write with no sign-in, a row read by its id with no owner check, and a
  read that hands anyone data other endpoints guard are cards; a guard EAOS cannot read is a question.
- **The data layer's rules** (M6.5): a table without row-level security, a write policy open to everyone (the two
  hidden access gaps, now here), security on with no policy, a security-definer function or view the public may run, a
  public bucket anyone may list, and who reads and writes each table.
- **The layers tried** (M6.6, M6.7), the new option "Try the layers": the migrations applied to the run's own database
  and tried per table with pgTAP as no one and as another user, with the Supabase CLI's security advisors; the API
  tried by Schemathesis with two test accounts (another user's object, a sign-in ignored, bad input accepted), each
  failure with its request and response; the production build read for keys and source maps.
- **One source of business rules** (M6.8), **operations** (M6.9: each missing item of the reference's infrastructure
  baseline) and **tests** (M6.10: the project's runners, which layers no test reaches, every write no test reaches, the
  project's own tests failing).
- **The layers for people** (M6.11): START-HERE.md and REPORT.html open with the broken critical boundaries in red, then
  each boundary with its state; the Studio's new page "The system in layers"; each card names its boundary and the
  reference's fix.
- **The proof** (M6.12): the detection baseline grew to 16 planted problems, its clean twin `tests/fixtures/baseline-clean`
  must stay without any layer finding, and three corpus apps of the stacks the layers matter for joined the corpus.

## 0.0.77 (2026-10-25)

M5, seeing any app. Without an assistant, EAOS started 4 of the 12 apps of its compatibility corpus and pictured the
expected screens of 2: a Python app (Flask, Django, Streamlit) got the start command `true`, Expo ignored the port it
was given, a static site's preview server ignored it too, SvelteKit's check broke on an empty code block in a blog post;
and where the app ran, screens behind a button, a menu file or a framework's page folder were never pictured, and a
sign-in page stopped everything. Now:
- **Any common stack starts from its files** (M5.1): `live/setup_python.py` finds Django, Flask, FastAPI and Streamlit
  (install, migrations or `init-db`, start, the environment names the code reads); Expo starts its web server on the
  run's port; a static site is built and served by Python's own server. A Redis address is `redis://`, a mail server is
  a host, a database name without the run's database is left unset so the app keeps its own. An engine's version check
  on a loaded host is asked again, never taken for "not installed".
- **Screens found in layers** (M5.2): the pages a framework's files make (Next.js, Nuxt, SvelteKit, Astro, Vue Router's
  file routes, Expo Router, Streamlit's `pages/`), Django's URL configuration with its includes, a server's GET routes
  (kept when they answer with a page), the menus of an app that routes by the hash at their `/#/` address; a page the
  code names is never folded into a template with its siblings. Then **the browser agent** (`live/agent.py`): the
  assistant drives the browser towards a goal a step at a time, each step recorded with its picture, and every later
  check replays the steps with no assistant.
- **Signed in on any computer** (M5.3): a test account by rules on the app's own sign-up and sign-in pages (Django's by
  its own command) before any assistant; when the person is still needed, the question says what EAOS tried. The
  behaviour lock and the walk-through run as each kind of user over that kind's own pages, so a change that breaks a
  page only an administrator opens is caught.

## 0.0.76 (2026-10-24)

M4, the check as loops. The ideal picture took 24 minutes on EAOS's own check (its critique wrote the whole ideal again,
35,000 tokens, and two of its three tries were broken JSON); a stage that broke on a loaded computer was simply lost; a
person read the findings without being told, first and in red, what the check could not see. Now:
- **Loops as data** (M4.1, M4.2): `pipeline/loops.py` puts the 37 stages in six loops; reordering is a change of that
  table. A loop not met runs its broken stages again (the app's loop twice), the first loop not met stops the check, an
  optional loop runs only when its path switches it on.
- **The coverage ledger** (M4.3): what each loop covered and could not, and why, in the manifest; the big gaps in red at
  the top of START-HERE.md and RUN.md.
- **The ideal in 7.9 minutes** (M4.4): the plan pass in three parts side by side, the critique answers only its changes.
- **Repair or rebuild** (M4.5): the recommendation from the target, with each option's cards, files and hours.
- **The laws reach further** (M4.6): one complexity count for the code laws and the hotspots (a nested function counted
  alone; the metrics facts carry `complexity`, version 2); the Studio's JavaScript under the laws with no exception (its 48 complex
  functions and 4 long modules split; `console/tools/same.cjs` drew every screen and sheet the same before and after, and
  found the earlier split had lost the one-branch page, two imports, and
  broken a branch's page with a name defined nowhere); GitNexus's misread Python cycles left out (all six on EAOS).

## 0.0.75 (2026-10-24)

M3, the target code layout. EAOS's code had grown where a change was hard to make safely: 593 functions above
complexity 10, 43 modules above 400 lines, state read four ways, two copies of the request guard, and its check of
itself made 231 cards, 15 of them security, while 96 of the Studio's modules were called dead. Now:
- **Layers and one source of truth** (M3.1-M3.3, M3.5): ten layers held by one import contract; one project state
  (`core/project_state.py`); one request guard, one check, one branch policy; one catalog of the words that name
  EAOS's concepts (`eaos/data/words.json`).
- **The target laws, no exception** (M3.4 and the target): every module of EAOS under 400 lines, every function under
  complexity 10; the outputs compared byte for byte before and after on real reports. `tools/code_limits.py` holds
  EAOS to 400 / 10; the laws EAOS holds every project to stay 600 / 15.
- **Security** (the self-check's 15 cards): every web read over http(s) only (`core/web.py`: urllib also opens
  `file://`); test reports read with `defusedxml` (a new dependency); no SQL built from a name (psql quotes it);
  the database binaries' copy closed to other accounts; sha256 ids; every bind to all networks through one constant
  that the Remote guard allows.
- **Dead code and duplication**: a build script's bundler entries and loads are reached (`facts/bundled.py`: 96 Studio
  modules were said dead); the truly dead removed (two files, five names, `tools/contracts.py` broken since 0.0.7);
  the engines' shared start (the tool's version read once: it took 111 s on a loaded host), the Studio's selection
  bar, answers, estimate and neighbours written once.
- **Cards and the Fix-run page** (from the owner's reports): a nameless target (`<anonymous>`) is judged in its own
  file and a moved function only where it was not (TASK-131); an edit keeps a Windows file's line ends and a text
  found 0 times says to read the lines again (TASK-146); the run page counts the server's progress across retries,
  clears a stopped attempt's words, follows a retried run again, and polls a light list of runs with ETag/304;
  `eaos problems` says each card in the person's language.
- **Measured** (`docs/METRICS.md` "After M3"): engine findings 2,054 to 1,488, cards 377 to 241. The measure found the
  agreeing engines' card titles stored in Arabic and printed so in an English check; the ledger now stores them in
  English and the reports render them in the reader's language. What the laws do not reach yet is card M4.6.

## 0.0.74 (2026-10-24)

M2, fewer and sharper engines: on EAOS's own check one semgrep rule wrote 1,554 of its 1,673 findings and none was a
weakness; Trivy wrote every advisory of a lockfile as a card of its own beside OSV-Scanner's card per package (119 on one
app of the corpus) and downloaded a 1.6 GB database every day for it; every vulture finding was thrown away unread; and
a complexity card needed two engines to agree even on a count only one engine makes. Every engine was run on the twelve
apps of the corpus, the baseline app and EAOS, and each choice below was measured on the claims they lead to: on the same
facts, 1,012 claims became 871, no work target was lost but three test functions EAOS never counts, and 94 were gained.
- **semgrep** (M2.1): `html-in-template-string` silenced (the DOM sinks stay: insecure-innerhtml, insecure-document-method,
  raw-html-join). Reviewing the rest found why the baseline's command injection was missed: the official rule wants
  `child_process` required whole, not `exec` taken from `node:child_process`. EAOS's own rule
  `eaos.security.command-from-text-js` finds a shell command built from text: a card on the baseline app, which now
  finds 6 of its 8 planted problems. Semgrep runs with no time limit per rule
  and file: its own (5 s, a file skipped after three) dropped findings in silence on a loaded computer (37 of 40 of one
  rule on EAOS); the whole scan keeps a limit of 30 minutes, and passing it is said as an error.
- **Complexity** (M2.2): complexipy removed (Python only; on the corpus it found nothing the others did not, on EAOS
  eight files, every one judged by EAOS's own branch count anyway). Reforge and Lizard stay, beside EAOS's own count. A
  count one engine states exactly (too many parameters, nesting too deep, a function too long) is a claim on its own,
  on those targets only; a card is rechecked by the engine that found it, and a branch count, EAOS's own, runs none.
- **Dead code, duplication, security** (M2.3): vulture removed: read again with its names fixed, every finding was a
  name called by dispatch (21 of 21). Trivy keeps secrets and misconfigurations, OSV-Scanner alone answers for packages:
  Trivy found no vulnerable package OSV-Scanner did not, and its database (1.6 GB, refreshed daily) is removed with its
  download, refresh and lock. A dead-code finding EAOS's own detector also reports is one card, not two. Every other
  engine finds something no other does and stays. An engine's dead-code candidate is read as the engine names it
  (`a/b.py:act`, a file's path): read as one dotted name, vulture's and knip's had all been dropped. The code laws count
  EAOS's dead code with EAOS's own detector instead of vulture.
- **One registry** (M2.4): `eaos/data/toolchain.json` is the only list; the engines stage takes its adapters from it.
  Its copy `upstreams/toolchain.json` and the stale `upstreams/registry.yaml` (six tools, two long gone) are removed;
  the four pinned source commits moved into it.
- Engines: 24 to 22; the tools list: 41 to 39.

## 0.0.73 (2026-10-23)

M1, the disk and outputs diet: EAOS's check of itself left 873 MB in its runtime that nothing ever removed and wrote a
409 MB report of 2,483 files, a third of it caches and copies, read whole on every call.
- **The runtime bounded**: an app that is EAOS itself, run in its sandbox, uses the one copy of the tools (it had
  installed its own 611 MB in `run-data`); the run's npm and pip caches go with it; a fix batch's patches are kept for
  the last two batches; the AI run log no longer copies each run's outputs (6 MB for 99 lines).
- **The outputs without duplicates**: the syntax cache moved to the runtime (63 MB), the Studio's data written once
  (no `.js` twins), engine findings once in `engines.json`, `REPORT.html` a second name of the page, compact facts,
  translations of documents that are gone cleared (1,070 of 1,214 files).
- **One lazy facts reader** (`eaos/facts/store.py`): a caller reads only the sets that can hold what it asks; seven
  copies of "read every set" (280 MB per call on EAOS) are gone; a field every fact of a set repeats is written once.
  EAOS's facts: 281 to about 74 MB.
- **Documents from 27 to 8** (START-HERE, the four reports, TARGET-ARCHITECTURE, RUN, the index; PLAN/ and adr/ for
  the assistants): 19 documents read only by the Studio Library removed with their writers; every record kept.
- **Records nobody reads**: of the eight the measurement listed, only `reports.json` had no reader (the four reports
  name each number's source in their text): removed. `live/sign-in.json` is read by the detection baseline,
  `proposals.json` marks the stage three planners require, and five feed the target and the four reports. A run
  removes the retired documents and records a check before left.

## 0.0.72 (2026-10-23)

M0, foundations and guards: before any clean-up (M1-M3) can break something silently, every law and every ability of
EAOS has a number that may only get better.
- **One command for every code law** (`tools/quality.sh`, about a minute): the code limits now hold function length
  (12 longer than 50 lines) and parameters (130 with more than 5), listed and only allowed to shrink; `import-linter`
  holds today's imports between subpackages (5 contracts); EAOS's own engines measure what it ships (jscpd, vulture,
  knip, bandit, semgrep, gitleaks, osv-scanner) and `tools/quality.json` records each number. Not enola: its dead-code
  count moved with the words of the CHANGELOG and METRICS, with no code changed. Proved by planting a `shell=True`
  call: refused by bandit and semgrep. The beta update runs it (step 5a). `knip` reads the Studio's real
  entries (`console/knip.json`): with the adapter's defaults it took all 104 of its files for unused.
- **The detection baseline** (`tests/fixtures/baseline-app`, eight planted problems): the golden trial checks it and
  refuses finding fewer. Today 5 of 8: the secret and the dead function and module become cards, the duplication and
  the broken screen are recorded; the command injection (CodeQL runs only on code public on GitHub), the sign-in screen
  and the logic flaw are missed.
- **The compatibility corpus** (`tools/corpus.json`, 12 real open-source apps pinned at a commit; `tools/corpus.py`):
  today 2 of 12 pass (React Router, Next.js). Without an assistant the Flask, Django and Streamlit apps are not started
  (the start command found is `true`), the Expo apps and the static site never answer, SvelteKit's facts fail, CoreUI
  and Vitesse miss screens: the input of M5.
- **`docs/METRICS.md` from a script** (`tools/metrics.py`).

## 0.0.71 (2026-10-23)

- **A branch decided anywhere waits no more** (EAOS on itself: batches 10 and 11 were merged by EAOS outside the
  Studio, and their question stayed in "Waiting"; its accept answered "not waiting for a decision any more"): whether a
  handed-over branch waits is read from EAOS's state, the one truth (`batch_branch.decided`), not from the Studio's
  record of the run.

## 0.0.70 (2026-10-22)

- **A fix batch is never lost under its own work** (batch 9 of EAOS: develop moved while its hand-over ran, a `status`
  call retired it and removed its copy, the hand-over failed with `KeyError: 'open_wave'`, two hours of kept changes
  lost): a batch is not retired while one of its jobs runs (`jobs.fixing`), and a moved base no longer throws away a
  batch with kept changes: it goes on, and its merge says whether it still fits. The beta update stops while a batch
  of the develop check is open.
- **The assistant's page fits a phone**: an unbroken tag (a refusal) widened the page to 504 px on a 390 px screen, the
  header and the box shifted; a turn's words, codes and tags now wrap. A proposal that needs the person's confirmation
  is no longer run by direct control and shown as an English refusal: it stays the card they confirm; the assistant
  writes a proposal's reason in the person's language; the depth under an answer is a word, not `ac.ask.depth.deep`.

## 0.0.69 (2026-10-22)

- **The screens an app's code names are found, however it moves** (HungerLab on 0.0.68 still "pages 1": it opens on
  `#/onboarding`, a language then a start, moves by buttons, and its development server drew the first screen after
  seconds, while the crawl read the page after 3): the crawl opens every hash route the code names
  (`screens.crawl.code_routes`: `'#/now'` in a string, or `'/now'` in a file that routes by the hash), records where the
  entry led (`#/onboarding`), and waits until a page shows something before reading it; the screens and the safety net
  wait for it too, so a slow app is never pictured blank. The golden app now behaves so: the 0.0.68 crawl found 1 of its
  5 screens, this one 5, and the trial demands them.
- **A card goes in the same batch as the cards it waits for, after them** (chief-ops: ten module splits refused and
  left for "the next batch" while their simplifications were open and ready): the next batch takes a waiting card once
  what it waits for is done or taken before it (`waves.ready_cards`), so a split comes right after its last
  simplification; cards asked for by name bring the ready cards they wait for, first (`waves.with_prerequisites`); a
  card is refused only when what it waits for can neither be done nor taken (needs the person's decision). The batch's
  lanes already keep a waiting card with the one it waits for.

## 0.0.68 (2026-10-22)

- **The crawl finds the pages of an app that moves by buttons** (HungerLab: "pages 1", so nothing was locked, walked
  or protected): it followed links only, and HungerLab opens on a welcome and moves by a tab bar of buttons. The crawl
  now presses the welcome's start button once, then each moving button (a tab bar, a nav or header menu, tabs and menu
  items, at most 15 a page) and follows every address they lead to; a button that would change or remove something
  (save, send, delete, sign out, in English and Arabic) is never pressed, and a published site is still only read.
- **The golden trial reproduces it**: the sample app opens on a welcome and moves by buttons (one link only); the old
  crawl found 2 of its 4 pages, the trial demands all 4.

## 0.0.67 (2026-10-22)

- **An update reaches the Studio already running** (HungerLab's Studio still said 0.0.59 after updating): a Studio kept
  as a service ran the EAOS it started with until someone restarted it. Its record now carries its version, and
  opening the Studio with another EAOS stops it and starts this one (`launch.start`, `_retire`); `install.sh` restarts
  every `eaos-studio-*` service after installing. A Studio that ends no longer removes the record of the one that
  replaced it.

## 0.0.66 (2026-10-22)

- **The safety net no longer refuses a whole batch for one unsteady screen** (HungerLab: the app ran, "0 screens
  recorded", not one of the five cards tried): the pages the crawl found all went into one spec file, and its result is
  the file's, so one page that differs between two recordings (a random tip, the time) failed every page. Each crawled
  page is now its own spec (`lock_specs.features_of`): the steady ones are locked, the unsteady one is refused alone,
  and the fix check already sets aside what fails on the original too (`waves._against_control`). The clock is held
  still in every page test (`page.clock.setFixedTime`), so a screen showing the time stays steady.
- **"Recorded nothing" says why**: the refused screens and their reasons are kept with the state
  (`behavior_lock.refused`), so the refusal names them instead of "no result file"; Playwright's terminal colours are
  stripped from the reasons.
- **The golden trial reproduces it**: the sample app's now screen shows the time and its about screen a random tip;
  the trial demands every other screen locked, the about screen alone refused, and a fix batch able to open.

## 0.0.65 (2026-10-22)

- **The plan's leftovers**: every check writes `RUN.md` beside its manifest again (what ran, what did not and why, as
  the plan said; `pipeline/report.document` was only read by a test); the golden trial also demands `journeys` and
  `baseline` ok and `RUN.md` present; three Studio words nobody read (`ac.why.*`) removed.
- **The report's summary no longer breaks** when every problem of an area was accepted as a risk (it weighs in the
  score but is no open row): the whole summary of the develop report showed `max() iterable argument is empty`; found
  by opening the report from the Studio in a real browser.

## 0.0.64 (2026-10-22)

- **The remedies, whole**: a failed stage the catalog knows no remedy for is put to the person's assistant once in the
  whole check (one allowed action: run it again, or advice for the person); a remedy that needs the person's yes
  (running the app) comes back as their question (`needs_agreement`), and their yes runs the check again from setup
  (`audit person_agreed`); a tool that could not be installed points to `tools_find`; "where things stand" proposes
  `again_from` for a remedy not tried yet; after `run_nodes` the stage that reads the decisions is named to run again.
- **The golden trial proves the fix flow and the report too**: after the check, the app is set up as a fix starts, the
  safety net must record a screen (HungerLab's batch was refused for 0), and the report for people must open by its
  address.

## 0.0.63 (2026-10-22)

- **Any AI node at any time**: `run_nodes` is an MCP job (eaos/node_jobs.py) any assistant starts, and the Studio's list
  names every node (visual_reviewer was missing).
- **A tool a stage lacks is found and added, safely**: `tools_find` reads GitHub's candidates (stars, license, latest
  release); `tools_add` keeps a pinned entry (a version and its sha256, or a commit; a license) only after the person
  agreed, in `<home>/toolchain-added.json`, which the one tool list reads (eaos/tools_catalog.py); an entry with
  `engine` runs in the engines stage through the SARIF reader with no Python (`sarif.Declared`).
- **The stupid details are held once for all** (`tests/test_consistency.py`): a stop code with no words for the person,
  a command the Studio copies with flags `eaos` lacks, a node missing from the list, a stage with no title, a threshold
  on the wrong scale. It found three on its first run, fixed here: `sign_in_declined` had no words, and the Studio
  copied `eaos check --preview` and `--branch`, which do not exist.
- **The golden trial** (`tools/golden_trial.sh`, run by the beta update): a whole check with the app run, without AI,
  on a small app of hash routes with no client router; any stage that runs the app not ok stops the update. Its first
  run found that a plain Node server was never given its port (`PORT` set only when an `.env` named it), fixed.

## 0.0.62 (2026-10-22)

- **EAOS fixes by itself what stops a stage, then runs it again**: the catalog now names a remedy for a reason code
  (`errors.json` reasons[code].remedy): a tool to install (`no_engine_installed`, `browser_missing`), the assistant to
  ask again (`no_provider`, `ai_partial`), a stage that must be ok first (`no_features`, `no_pages`, `no_load_scenario`
  after the crawl), or the person alone (`no_run_consent`, `app_not_running`). After every check the remedies that
  need no person are applied, rules first, and their stages run again once the change is proven, up to three rounds,
  a reason tried once (`eaos/pipeline/remedies.py`; `run.again` takes several stages). The manifest keeps what was
  done (`remedies`), the Status page lists the stages that did not run with their reason in the person's language and
  what EAOS did about it, and the stage board tells "not applicable here" from a failure by its glyph.

## 0.0.61 (2026-10-22)

- **The safety net finds the app's pages by itself**: HungerLab's fix batch was refused for "0 screens recorded": the
  lock takes its pages from the code, which names none (an SPA of `/#/now` routes), and no check had crawled the app.
  The lock now crawls the app it started once, writes its pages to `live/crawl.json`, and locks them: a fix batch opens
  without a check first. The refusal, when it still happens, says the real reason.
- A host's own `<notification_summary>` tag in the assistant's words is no longer shown in the Studio.

## 0.0.60 (2026-10-22)

- **An app whose code names no page is still locked, walked and loaded**: HungerLab's check (an SPA with no client
  router, what EAOS's own blueprint builds) had no `page` in its facts, so `lock`, `record`, `journeys` and `baseline`
  stood still while the crawl had found and pictured its pages. `lock` now runs after `crawl` and reads it: the crawl's
  distinct pages stand in for the code's (`lock_specs.crawled_pages`), one source for the lock, the load and the
  Studio's journeys and screens.
- **A stage that did not run says why, in the person's language**: the Studio's stage sheet showed EAOS's English
  sentence; now every stage row carries the catalog's words (`reason_texts`), the report for people says the reason
  beside "not run", the Studio's head lists what did not run (`not_run`, one source: `pipeline.report.absences`), "Redo
  from here" is offered for every stage once the check ended, and the copied command `eaos check --again-from <stage>`
  exists.
- **The report for people opens in the person's own browser**: "Open the full report" ran a browser on the server and
  showed a server path. The Studio now opens a tab at `/report/<ticket>`, a one-use address minted with the launch
  token, served as HTML with a policy of its own; local or remote alike.
- **The Studio's data is written once the screens are pictured**, so Understand shows them mid-check.
- **A measurement that did not happen is no pass**: a real build's k6 failed (the isolated run of a candidate copy did
  not show it the report folder, `sandbox._own`) and the last milestone was delivered as if measured. The report folder
  of the project is shown to a copy's run, and `setup`, `screens` or `baseline` not run on the finished product hold the
  last milestone (`proof`).

## 0.0.59 (2026-10-22)

- **The finished product is held to every direction the owner named, not only its screens**: the last milestone was
  delivered once its cards, requirements and screens passed, but three things a person feels were never proven: the
  browser journeys (written by the journey cards, never run: the gates ran typecheck, lint and unit tests only), its
  load, and its design beyond small details. Now the last milestone also:
  - runs the project's own journeys (`npm run e2e`), its own Playwright's browsers fetched once into the project's run
    folder (never EAOS's) and removed once the build is delivered; the skeleton declares the `e2e` script;
  - measures its load with the check's own `baseline` stage (k6 on the production build, at the plan's expected users)
    and is held back while a scenario's p95 or error rate is over its threshold;
  - is held back by a design departure of high severity from the screen review against DESIGN.md.
  The finished product's acceptance moved to `eaos/build_look.py` (its screens, design and load); `build_tools.py`
  reads its JSON through it.

## 0.0.58 (2026-10-22)

- **EAOS's own tools in the app's isolated run, from one source**: HungerLab's check (an app built with EAOS) stopped
  ten stages, every one that runs the app: it never answered in the isolated copy. An app with its own Playwright
  (every app built from a plan has one, for its browser tests) met EAOS's scripts there twice: the setup probe and the
  seed script (the setup assistant was told `require('playwright')`) loaded the app's own, another version with no
  browsers. Now the run's environment names EAOS's Playwright once (`EAOS_PLAYWRIGHT`), the probe and the seed load it
  by that path, and a test runs the probe in an app whose own Playwright fails: it must never be loaded.
- **A long Studio run keeps the person's language**: the salon's build from the Studio wrote 67 of its 69 notes in
  English: the run's first words asked for Arabic, and a long session forgets them. Every EAOS answer in a Studio run
  now carries the person's language (`notes_language`), read at every step.

## 0.0.57 (2026-10-22)

- **From a real plan document to a complete blueprint, in the Studio**: a salon's PRD (10 functional and 5 other
  requirements) given to "Build from a plan" was read by the assistant into a spec with all 15 requirements and the
  product's facts, five real choices asked once in "Waiting for you", and a blueprint of 44 cards in 11 milestones.
  It showed three faults, fixed here:
  - **Requirements were optional**: a spec without them was drawn with nothing proving the plan was built. A new
    product's spec now needs `requirements` and `nonfunctional` (a feature added to a project does not).
  - **The new project spoke English in an Arabic Studio**: its state took the computer's language; it now starts in
    the Studio's.
  - **"Where things stand" failed before the project's folder existed**: it now says the next step is reading the plan.

## 0.0.56 (2026-10-22)

- **The whole product built from one press, proven**: a real trial from the Studio built a two-language clinic from its
  plan, 6 milestones and 20 cards, none skipped, with no question to the person. It showed four faults, fixed here:
  - **The finished product's screens were never pictured**: the app's setup ran `npx playwright install` into EAOS's
    browsers, read only in the isolated run; and the probe of the first page, written into the app's copy, loaded the
    app's own Playwright (another version) instead of EAOS's. The setup now never installs the app's test browsers, and
    the probe loads EAOS's Playwright by its path. On the same product the screens are now pictured (accessibility 100,
    best practices 92) and show a real fault: its security policy blocked the font its build inlines.
  - **Lighthouse scores are out of 100**: the last milestone compared them with 0.9, so they never held it back; now 90.
  - **Translations as typed modules**: the standard card asked for JSON files in the shared look, which the layer rules
    read as configuration; the security card now also says the policy lets the app load what its own build makes.
  - **A shape too small to hold a rule is not a copy**: `() => x.y()` in a few files was refused as copied code; the
    copy gate now asks the same 30 tokens of shared shape a claim does.

## 0.0.55 (2026-10-21)

- **The blueprint plans a complete product by itself**: HungerLab's blueprint had a card per module, feature and
  journey only; an assistant added about 50 cards by hand (languages, offline, security, accessibility, speed, release)
  and measured by hand that every requirement of the plan was covered. The generator collected the spec's
  `nonfunctional` facts and ignored them. Now the cards every product needs are data (`eaos/data/product-standard.json`),
  chosen by those facts and the integrations: languages and right-to-left, privacy, offline, one adapter per
  integration, security and errors in the foundations; accessibility, speed, load and release in a last milestone,
  "Ready to release".
- **Every requirement of the plan is built**: the spec lists them with what builds each (`requirements[].covered_by`);
  one nothing builds stops the blueprint, each card names the requirements it builds, and the last milestone is not
  delivered while a requirement has no kept card (a card skipped earlier may be built then) or while its running
  screens have serious accessibility problems (axe, touch targets, Lighthouse accessibility or best practices under
  0.9; the copy's speed, in development mode, is the release card's to prove).
- **One press builds the whole product**: "Build the whole product" in the Studio builds every milestone in order,
  fixing what each milestone's screen review found before the next one, and stops when the last branch waits for the
  person. The blueprint's page for people moved to `eaos/blueprint_view.py`; an import cycle 0.0.54 brought is gone.

## 0.0.54 (2026-10-21)

- **A project built from its plan is followed in the Studio, wherever its blueprint was drawn**: HungerLab's blueprint
  was drawn from the person's own assistant session, and the Studio showed none of its 68 build cards, none of its four
  questions, and "check the project" with "no score". The Studio read only a check's plan and inbox. Now it reads the
  blueprint folder (`eaos/studio/build_plan.py`): the Plan page lists the milestones and each card with its acceptance,
  files, tests and state; the spec's open questions wait in "Waiting for you" (a check's share of questions never
  answers them for the person); Status says where the build stands and offers its one next step.
- **An answer to the blueprint acts**: it goes into the spec at once (`blueprint_answer`), with no assistant run to
  review it, and a blueprint not built yet is drawn again with it (the journeys, when the person says yes, are one per
  role through the features it can use).
- **"Build the next milestone" builds it**: from the Studio it only opened the milestone and stopped, with no one to
  build its cards. Now it starts the person's assistant, which opens the milestone, builds every card through its gates
  and hands the milestone over as its branch, then stops for the person.

## 0.0.53 (2026-10-21)

- **An answer acts; the same question never comes back**: after the assistant's connection dropped, chief-ops' check
  stopped on "Claude Code is not answering", and every answer brought the same question back. "I fixed it: check
  again" checked the assistant first, found it as before and asked again; an answer in words went to an assistant,
  the very one not answering. Now "I fixed it" starts the check (`fixed`): a stage the assistant still fails says so in
  the report. An answer in words to a step's own question takes the option it names, else the recommended one. Only
  running the app takes an explicit yes, as before.

## 0.0.52 (2026-10-21)

- **The views and the sign-in are worked out by an assistant that reads the code itself**: chief-ops' check found the
  program owner's view but never made a session that opened its pages, and a local trial of the same shape stopped at
  setup. The assistant of the views, the setup and the sessions answered blind, every tool off, from excerpts. Now
  those three calls read and search the project (or its isolated copy) themselves, read only (Read, Grep, Glob; Codex
  in its read-only sandbox), and the views and the sessions think as long as they need. Every other call is as it was.
- **The reading of the code says the way in**: how a person signs in, and whether one account may hold every view
  (`one_account`: one test account granted every profile, switched between) or each account enters one view
  (`account_per_view`: one account of each kind, its own role only). The run's own session is always granted
  everything in the copy's database, so every page opens once.
- **A lack goes back to the node that owns it**: the sessions are made in up to three rounds of five minutes (fifteen
  at most, as before); a round that ends with pages no session opens asks the reading of the views again with them,
  which adds views and never drops one, and the next round goes on with its answer.
- **A working app is not refused**: a first page of more than forty words is the app, whatever "no ... yet" it shows
  (chief-ops' command center was taken for an empty state), and a chooser in front of the app is picked by the seed,
  its browser state saved.
- **One rule of a page seen**: the sessions and the pictures judge a page the same way, and a page sent on is seen only
  when it lands under its own address (/settings to /settings/profile, never /admin to /dashboard).

## 0.0.51 (2026-10-21)

- **A new check starts from nothing; going on with a stopped one is a choice**: the owner stopped a check of chief-ops
  and started a new one, which opened at "31 of 37 stages done": any check found the checkpoint of one stopped midway
  and went on from it, whether asked or not. Now "Check the project" always starts a new check and drops that
  checkpoint; Retry on the stopped check goes on from where it stopped (`go_on`), and the Stop window says which does
  what. Pause and resume are as they were: the same check, frozen and going on.
- **Stop stops the check**: a check stopped in its first seconds, before the Studio knew its job (a tool call waits up
  to 50 seconds for it), was marked stopped while it went on to its end. Stop now ends the project's running job then,
  and a job that comes back to a run already stopped is ended at once.
- **The Studio's assistant does what the person asks**: asked to start a new check, it could only propose it, and the
  proposal waited for a press, or for an hour of direct control turned on by hand; and it never knew which run to stop.
  Now direct control is on unless the person turns it off, and runs every action and control at once; only accepting a
  branch and throwing one away, which cannot be undone, wait for a press. Each turn names the runs going on with their
  ids. A real turn, "start a new check from nothing now, even if one is running": it stopped the running check and
  started a new one, which began from nothing.

## 0.0.50 (2026-10-21)

- **An app that signs in by itself still gets its views**: the third check of chief-ops pictured the support pages
  alone again, and its sign-in record said `"needed": false`. In development the app signs every request in as a
  support account, with no sign-in page, so no sign-in was seen and the whole making of the views (0.0.49's, too)
  was skipped. Now, with no sign-in asked for, the pages of the code are still opened: when the code has views, or
  some pages open as none of themselves (the program's pages a "not found"), the assistant makes the sessions as for
  any app, the session of the app as it opens included, and the person is never asked to sign in. The record names
  the pages that opened with no session (`unreached`).
- **No page is left without an answer**: a page of the code that no session opens goes back to the assistant until it
  has one of two answers: the view that opens it, with its session, or the line of the code that proves no person
  reaches it (a removed feature, a route that refuses every user), kept in `roles.json` (`unreachable`), never
  pictured and named in the report with its reason. A verdict without a real line is refused. Every page of the code
  is tried (150 at most, not 24), for fifteen minutes (not five). And a page a view's session opened, and no session
  before it, becomes that view's own, so the pictures open it with that session, not with one that shows a "not found".

## 0.0.49 (2026-10-20)

- **A "not found" inside the app's menus is a page not seen**: the second check of chief-ops still asked whether to
  redirect /rota, /schedule, /settings and other pages that "now end at a not found page". The app draws its "not
  found" inside its menus, and the page of an address it does not have without them, so the whole pages were too
  unlike (62% against the 90% needed) for the "not found" to be told; and an app may have two "not found" pages of
  different words. A page is now not seen when it shows every line of that page the first page lacks, whatever menus
  are around them, or when its own few lines, the menus left out, open with "not found", "404", "no access" and the
  like (in English or Arabic). The screens' reviewer is told such a picture is never a finding.
- **The views of a big project reach the assistant, and the running app tells those it missed**: chief-ops pictured the
  support pages alone. The assistant read the fifteen files with most words about users, which in a big project are a
  folder of near-alike policies or fixtures: the sign-in, the accounts and the program chooser never reached it. Now the
  files that serve the app's routes come first, two of any other folder at most. And once the test users are made,
  the pages of the code are opened with every session: those no session opens (a "not found", a refusal, the sign-in)
  go back to the assistant with their files, which say what they need, until it adds the view that opens them, or two
  tries change nothing. A trial project grown with eighteen policy files: before, no view found and nobody signed in;
  now the manager, support and the program views, every page pictured from its own session.
- **A page that shows anything only once a record is chosen** (an active program, clinic or project) is a view entered
  by a switch: the test users' script chooses one, making it in the copy's database when none is there. A trial app
  whose rota and schedule show only in a chosen program: the program view found, its pages pictured with a program
  chosen.

## 0.0.48 (2026-10-20)

- **An answer in the person's own words is their answer**: every answer written instead of picking an option was taken
  for a clarification, the assistant was told to change nothing, and the same question came back until one of its
  options was picked: the owner answered some questions three or four times. Now the words go to the assistant's own
  session as the answer, and it goes on from them. Only a question whose option EAOS carries out itself (a direct
  step's: the branch, the agreement to run the app; or closing a batch) still needs an option, its words a
  clarification, and the Studio says which, under the answer box.

## 0.0.47 (2026-10-20)

- **Every view of an app is found and seen from its own session**: a check of an app whose manager switches between
  an administration and a programs profile within one sign-in named one kind of user, opened the programs pages with
  the administration's session, pictured the app's "not found" page (answered 200) as those pages, and its assistant
  asked whether to delete or build them. Now:
  - the roles stage names every view (up to ten: a clinic's reception, doctor, nurse, pharmacy...), each entered by an
    account of its own or by a switch within one sign-in, with the line of the code that switches;
  - the test users' script makes a session in each view, switched into it the way the app switches; when the person
    signed in themselves, it switches a copy of their session and never touches theirs;
  - each view's pages are opened with its own session, and the person's one session never opens a view another
    session holds;
  - a page that does not open as itself (a sign-in, a refusal, or the app's own page for an address it does not have,
    told by opening one such address, even when it answers 200) is not seen: it never reaches the review of the
    screens, the target's plan never deletes, rebuilds or adds it nor asks about it, the report says it was not seen,
    and it is no breach of another view.
  A clinic signing in a manager with two profiles and a nurse: three views found (one a switch), every page of each
  pictured from its own session, the programs pages with the programs profile switched on.

## 0.0.46 (2026-10-20)

- **A check runs the project's own tests beside the pages**: the tests ran in a copy of their own but shared the
  check's database, and stopping their run stopped the server under the app the page stages were opening, so they
  were chained in the app's order: seven minutes beside nothing in a check of EAOS. Every run on the server now holds
  it and the last one leaving stops it, and the tests get a database and a data folder of their own. On the last
  check's own times, 22 minutes become 16; what still runs one after the other waits for what it reads.
- **Speed mode for fixes**: most of a card's time is the assistant's thinking (a minute and a half a card, against
  seconds for EAOS to check its change, in 498 recorded changes), so in speed mode the batch's cards are dealt into
  lanes and the Studio starts an assistant for each beside the first one, as many as this computer holds (five at
  most): one copy, one branch, the cards sharing a file or waiting for one another in one lane. A change to a file
  another assistant holds is never tried: its card is left for the end, when the first assistant fixes it. EAOS checks
  the changes one at a time, as with one assistant; an assistant that stops for good hands its cards back; the batch
  is handed over once every lane is done, through the same checks. The switch is the check's speed mode, kept for the
  project, and says that the usage limit goes faster.
- **Work sent while other work runs waits its turn** instead of answering "busy", and the project's state is written
  whole, under a lock where several assistants write it.
- **A sheet's blocks keep their own height**: in a sheet taller than the screen, a block with a minimum height got
  that height alone and its text ran over the blocks around it (a running stage's programs); each program is now
  named once, with its count.

## 0.0.45 (2026-10-19)

- **The check of EAOS itself pictures its app again**: the setup's probe opens a few routes of the code, and EAOS's
  /api/ routes answer 401 without a token; a 401 counted as the app not working, so the setup failed after five
  attempts and seven minutes and no page stage ran. A page asking for a sign-in or a token (401), like one refusing
  the user (403), is the app answering. The check of EAOS from this branch: set up, 13 pages crawled, 22 pictures,
  5 journeys walked without a failure.
- **Two steps named for what they do**: "Pin the libraries" writes a test of what each feature does today ("Write
  what your app does today"), and "Check that your app runs" runs the project's own tests ("Run your project's
  tests"), which read like a second setup. "Prepares a test sign-in" carries the assistant's mark.

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
