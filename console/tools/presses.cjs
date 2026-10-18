/* The MEASURED press table (D46), against a served console on its real report: for every feature ID of
   brief/FEATURES.md, a recipe presses from Status in a real headless browser, at 390 and 1440, in Arabic and in English,
   counts the presses and asserts the end state (ported from the prototype's tools/presses.cjs).
   Counting rule (D46): start on Status (a page that opens instead of Status starts there); one press = one click on a
   visible tab, row, button, chip, toggle or fold; typing is free; the press that opens a preview counts; the governance
   tick and the act button after it are not pressed (marked "+c"). The lead's recipes use the report's own ids (the
   first problem with evidence, its first fact, the first waiting decision, the delivered branch waiting); the builders
   replace the prototype's sample ids in theirs (R-12, M04, feature/login-by-hand…) as they port, and a recipe that
   needs a live state (a running check, a sign-in) starts one for real or is checked in the end-to-end gate.
   Results: EAOS_PRESSES_OUT (default /workspace/eaos-work/studio-design/presses-results.json); FEATURES.md:
   EAOS_FEATURES (default /workspace/eaos-work/studio-design/brief/FEATURES.md).
   Usage: node console/tools/presses.cjs [ID-or-prefix] */
const fs = require('fs');
const Lib = require('./lib.cjs');

const OUT = process.env.EAOS_PRESSES_OUT || '/workspace/eaos-work/studio-design/presses-results.json';
const FEATURES = process.env.EAOS_FEATURES || '/workspace/eaos-work/studio-design/brief/FEATURES.md';
const CSS_ID = s => String(s).replace(/[^\w-]/g, c => '\\' + c);

/** The report's own ids the lead's recipes press. */
async function discover(page) {
  await Lib.open(page, '/status', 'ar');
  return page.evaluate(async () => {
    const E = window.EAOS;
    await E.data.need(['cards', 'decisions', 'evidence']);
    const problems = E.model.problems();
    const p = problems.find(x => (x.evidence || []).some(id => E.model.fact(id) && E.model.fact(id).code)) || problems[0];
    const d = E.model.decisions().find(x => x.state === 'waiting');
    const run = E.store.awaiting()[0];
    /* builder A's: the last check, a run that ended badly, a run that handed a branch over, a branch to merge or
       delete, one in conflict, a deleted one to restore (the scratch home makes them; a recipe without one fails) */
    const runs = E.ac.runs(), check = E.ac.lastCheck();
    const failedStage = check && E.ac.checkFlow() ? (E.ac.checkFlow().stages.find(s => s.state === 'ok') || {}).name : null;
    const inv = E.client ? await E.client.branches.inventory().catch(() => null) : null;
    const locals = inv ? inv.branches.filter(b => b.kind === 'local' && !b.protected && !b.work && !(b.roles || []).includes('analysis')) : [];
    let branch = null, conflict = null;
    for (const b of locals) {
      const det = await E.client.branches.detail(b.name).catch(() => null);
      const m = det && det.commands.merge;
      if (m && m.available && !conflict) { const pv = await E.client.branches.previewMerge(b.name).catch(() => null); if (pv && pv.conflicts.length) conflict = b.name; else if (!branch) branch = b.name; }
    }
    const restore = inv && (inv.recovery || []).find(r => !r.restored);
    // builder B's: a plan step, a step that waits for another, a gap with problems, a component, a code path, a data
    // store, a screen, a document read first and the last check (the report's own ids)
    await E.data.need(['plans', 'paths', 'gaps', 'system', 'data_paths', 'screens', 'docs', 'history']);
    const sec = E.data.section, steps = E.model.plan().steps, tl = (sec('paths') || {}).timeline;
    const waiting = tl && tl.tasks.find(x => x.waits.some(w => { const o = tl.tasks.find(y => y.id === w.task); return o && o.step !== x.step; }));
    const scans = (sec('history') || {}).scans || [];
    const doc = ((sec('docs') || {}).docs || []).filter(x => x.order != null).sort((a, b) => a.order - b.order)[0];
    return { problem: p && p.id, fact: p && p.evidence[0], decision: d && d.id, run: run && run.id, first: problems[0] && problems[0].id,
      total: E.model.totals().problems, version: E.model.project().eaos_version,
      check: check && check.id, stage: failedStage, ended: (runs.find(r => ['failed', 'stopped', 'unchanged'].includes(r.state)) || {}).id,
      branchRun: (run || runs.find(r => r.result && r.result.branch) || {}).id, handoff: (runs.find(r => r.mode === 'handoff') || {}).id,
      branch, conflict, restore: restore && restore.id,
      step: (steps.find(x => x.tasks.length > 1) || steps[0] || {}).id, stepWaits: waiting && waiting.step,
      gap: (((sec('gaps') || {}).gaps || []).find(g => g.cards.length) || {}).id, comp: (((sec('system') || {}).current || {}).nodes || [])[0].id,
      path: (((sec('paths') || {}).paths || [])[0] || {}).id, store: (((sec('data_paths') || {}).stores || [])[0] || {}).id,
      screen: ((((sec('screens') || {}).screens || []).find(x => (x.shots || []).length)) || {}).id, doc: doc && doc.path,
      lastScan: (scans[scans.length - 1] || {}).id };
  });
}

function recipes(ids) {
  /* ---- selectors shared by the recipes ---- */
  const NAV = p => `:is(.tab, .side-nav a)[href="#/${p}"]`;   /* a place: tab bar (phone) or sidebar (desktop) */
  const PM = '.project-btn';                                    /* the project menu */
  const SRCH = '[data-act="sheet"][data-sheet="search"]';       /* Search or ask */
  const SH = '.sheet.is-open';
  const MORE = '#main .actions [data-sheet="launcher"]';        /* Status: More work... */
  const CHECK = '#main [data-sheet="check"]';                   /* Activity: Check the project... */
  const PMROW = p => `${SH} a[href^="#${p}"]`;
  const UV = v => `#main a[href="#/understand/${v}"]`;
  const T6 = `#main a[href^="#/problems/${ids.problem}"]`;
  const BR = '#main .context a[href="#/project/branches"]';
  const enc = encodeURIComponent;
  const FEAT = `#main a[href="#/project/branches/${enc(ids.branch || '')}"]`;
  const RUN = id => `#main a[href="#/activity/run/${id}"]`;
  const R12 = RUN(ids.branchRun);
  const ALL = '#main a[href="#/activity/runs"]';
  const LIVE = { ph: { steps: ['.live-strip'] }, dk: { steps: ['.side-live'] }, note: 'live: needs a run holding the slot (checked in the end-to-end gate)' };
  const L = (id, steps, expect, more) => Object.assign({ steps, expect }, more || {});

  const R = {
    /* ---- PRJ ---- */
    'PRJ-01': L(0, [], ['vis:#main h1.lede a[href^="#/problems"]', 'vis:#main .actions .btn--primary']),
    'PRJ-02': L(0, [], [], { ph: { steps: ['#main button[data-sheet="health"]'], expect: ['sheet:health', 'vis:.sheet.is-open .figure'] }, dk: { steps: [], expect: ['vis:.status-aside .figure', 'vis:.status-aside .meter'] } }),
    'PRJ-03': L(0, [], ['vis:#main .sevbar', 'vis:#main .split-line a[href*="who=you"]', 'vis:#main .split-line a[href*="who=eaos"]']),
    'PRJ-04': L(0, ['#main .context [data-sheet="freshness"]'], ['sheet:freshness', 'vis:.sheet.is-open .facts']),
    'PRJ-05': L(0, [BR], ['hash:/project/branches', 'vis:#main h1']),
    'PRJ-06': L(0, ['#fold-stand > summary'], ['vis:#fold-stand[open] .facts']),
    'PRJ-07': L(0, ['#fold-journey > summary'], ['vis:#fold-journey[open] li']),
    'PRJ-08': L(0, [MORE], ['sheet:launcher']),
    'PRJ-09': L(0, ['#fold-about > summary'], ['vis:#fold-about[open] .facts']),
    'PRJ-10': L(0, ['#fold-measured > summary'], ['vis:#fold-measured[open] .nm']),
    'PRJ-11': L(0, [], ['txt:st.empty.lede', 'vis:#main .actions .btn--primary'], { start: '/status?state=empty' }),
    'PRJ-12': L(0, [], ['vis:#banner .banner', 'vis:#main [aria-busy="true"]'], { start: '/status?state=loading' }),
    /* ---- CHK ---- */
    'CHK-01': L(0, [NAV('activity'), CHECK], ['sheet:check', 'vis:.sheet.is-open [data-act="ac-start-check"]']),
    'CHK-02': L(0, [NAV('activity'), CHECK], ['sheet:check', 'vis:.sheet.is-open label:has(input[value="security"])', 'vis:.sheet.is-open label:has(input[value="speed"])']),
    'CHK-03': L(0, [NAV('activity'), CHECK, `${SH} details.fold > summary`], ['vis:.sheet.is-open details.fold[open]']),
    'CHK-04': L(0, [NAV('activity'), CHECK], ['vis:.sheet.is-open label:has(input[value="claude"])', 'vis:.sheet.is-open label:has(input[value="rules"])']),
    'CHK-05': L(0, [PM, PMROW('/project/tools')], ['hash:/project/tools', 'vis:#main h1']),
    'CHK-06': L(0, [PM, PMROW('/project/assistants')], ['hash:/project/assistants', 'vis:#main [data-act="ac-asst-again"]']),
    'CHK-07': L(0, [], ['hash:/activity/run/'], LIVE),
    'CHK-08': L(0, ['#fold-about > summary', `#fold-about a[href="#/activity/run/${ids.check}"]`], [`hash:/activity/run/${ids.check}`, 'vis:#main [data-sheet^="stage:"]']),
    'CHK-09': L(0, ['#fold-about > summary', `#fold-about a[href="#/activity/run/${ids.check}"]`, `#main [data-sheet="stage:${ids.stage}"]`], ['sheet:stage:']),
    'CHK-10': L(0, [NAV('activity'), RUN(ids.check), `#main [data-sheet="stage:${ids.stage}"]`, `${SH} [data-sheet^="redo:"]`], ['sheet:redo']),
    'CHK-11': L(0, [NAV('activity'), RUN(ids.check), '#main a[href*="replay=10"]'], ['hash:replay=10', 'vis:#main .ac-stamp']),
    'CHK-12': L(0, [NAV('activity')], ['txt:ac.flow.tools']),
    /* ---- APP ---- */
    'APP-01': L(0, [MORE, `${SH} [data-sheet="action:run_setup"]`], ['sheet:action:run_setup']),
    'APP-02': L(0, [MORE, `${SH} [data-sheet="action:run_try"]`], ['sheet:action:run_try']),
    'APP-03': L(0, [MORE, `${SH} [data-sheet="action:safety_net"]`], ['sheet:action:safety_net']),
    /* ---- RUN ---- */
    'RUN-01': L(0, [], ['vis:.live-strip, .side-live'], { note: 'live: visible on every screen while a run holds the slot (checked in the end-to-end gate)' }),
    'RUN-02': L(0, [NAV('activity')], ['txt:ac.act.line'], { note: 'up, down and remove show on each queued run (end-to-end gate)' }),
    'RUN-03': L(0, [NAV('activity'), ALL], ['hash:/activity/runs', 'vis:#main #rq']),
    'RUN-04': L(0, [NAV('activity'), R12, '#fold-facts > summary'], ['vis:#fold-facts .facts'], { dk: { steps: [NAV('activity'), R12], expect: ['vis:#main .ac-run-aside .facts'] } }),
    'RUN-05': L(0, [NAV('activity'), R12], [`hash:/activity/run/${ids.branchRun}`, 'vis:#main .ac-time']),
    'RUN-06': L(0, [NAV('activity'), R12], ['vis:#main .ac-tl']),
    'RUN-07': L(0, [NAV('activity'), R12], ['vis:#main .ac-result']),
    'RUN-08': L(0, [NAV('activity'), '#main [data-act="ac-ctl"]'], ['vis:#main [data-act="ac-ctl"]'], { note: 'live: pause and stop on the running run (end-to-end gate)' }),
    'RUN-09': L(0, [NAV('activity'), ALL, RUN(ids.handoff)], ['vis:#main .ac-req [data-act="copy"]'], { note: 'needs a run handed off to an assistant elsewhere' }),
    'RUN-10': L(0, [NAV('activity'), ALL, RUN(ids.ended)], ['vis:#main [data-op="retry"]']),
    'RUN-11': L(0, [NAV('activity'), R12, '#fold-facts > summary'], ['vis:#fold-facts .facts'], { dk: { steps: [NAV('activity'), R12], expect: ['vis:#main .ac-run-aside .facts'] } }),
    'RUN-12': L(0, [NAV('activity'), ALL, RUN(ids.ended), `#main a[href^="#/ask?run=${ids.ended}"]`], ['hash:/ask', `hash:run=${ids.ended}`]),
    'RUN-13': L(0, [MORE, `${SH} [data-sheet="action:status"]`], ['sheet:action:status']),
    /* ---- PRB ---- */
    'PRB-01': L(0, [NAV('problems')], ['vis:#main .prow']),
    'PRB-02': L(0, [NAV('problems')], ['vis:#main #pq']),
    'PRB-03': L(0, [NAV('problems'), '#main .seg a[href*="who=you"]'], ['hash:who=you']),
    'PRB-04': L(0, [NAV('problems'), '#main [data-sheet="filters"]'], ['sheet:filters', 'vis:.sheet.is-open [data-change="facet"], .sheet.is-open label.check']),
    'PRB-05': L(0, [NAV('problems'), '#main [data-sheet="filters"]', `${SH} [data-act="group"][data-group="area"]`], ['hash:group=area']),
    'PRB-06': L(0, [NAV('problems'), T6], [`hash:/problems/${ids.problem}`, 'vis:#pd-title']),
    'PRB-07': L(0, [NAV('problems'), T6], ['vis:#pd-decision']),
    'PRB-08': L(0, [NAV('problems'), T6], ['vis:#main .fact .code']),
    'PRB-09': L(0, [NAV('problems'), T6, `#main [data-sheet="fact:${ids.fact}"]`], ['sheet:fact']),
    'PRB-10': L(0, [NAV('problems'), T6], ['vis:#main .planline']),
    'PRB-11': L(0, [NAV('problems')], ['txt:pb.newcheck'], { start: '/status?state=newcheck' }),
    'PRB-12': L(0, [NAV('problems')], ['vis:#main .band [data-sheet="verb:fix:assistant"]']),
    'PRB-13': L(0, [SRCH, { type: ['#search-input', 'toolchain'] }, '#search-results [data-href*="records=1"]'], ['hash:records=1']),
    'PRB-14': L(0, [NAV('problems'), T6, '#main [data-sheet^="impact:"]'], ['sheet:impact']),
    'PRB-15': L(0, [NAV('problems'), T6, '#main .pdetail details:has(textarea) > summary'], ['vis:#main .pdetail textarea']),
    /* ---- FIX ---- */
    'FIX-01': L(0, [NAV('problems'), T6, `#main .verbs [data-sheet="verb:fix:${ids.problem}"]`], ['sheet:verb:fix']),
    'FIX-02': L(0, ['#main .actions .btn--primary'], ['sheet:verb:fix', 'txt:free']),
    'FIX-03': L(0, ['#main .actions .btn--primary'], ['sheet:verb:fix', 'txt:pv.where', 'txt:pv.merge']),
    'FIX-04': L(0, ['#main .actions .btn--primary'], ['txt:pv.who', 'vis:.sheet.is-open label:has(input[name="asst"])']),
    'FIX-05': L(0, ['#main .actions .btn--primary'], ['txt:pv.auto', 'vis:.sheet.is-open .switch']),
    'FIX-06': L(0, ['#main .actions .btn--primary'], ['vis:.sheet.is-open [data-act="verb-start"]']),
    'FIX-07': L(0, [], ['txt:ac.fix.progress'], Object.assign({}, LIVE, { note: 'live: a fix running (end-to-end gate)' })),
    'FIX-08': L(0, [NAV('waiting'), '#main a[href="#/waiting/questions"]'], ['hash:/waiting/questions', 'txt:ac.q.lede']),
    'FIX-09': L(0, [NAV('waiting')], [`vis:#w-${ids.run}`]),
    'FIX-10': L(0, [NAV('activity'), ALL, RUN(ids.ended)], [`hash:/activity/run/${ids.ended}`, 'vis:#main [data-op="retry"]']),
    'FIX-11': L(0, [NAV('waiting'), `#main [data-sheet="accept:${ids.run}"]`], ['sheet:accept', 'vis:.sheet.is-open .owner-band', 'vis:.sheet.is-open [data-needs-ack]'], { c: true }),
    'FIX-12': L(0, [NAV('waiting'), `#main [data-sheet="reject:${ids.run}"]`], ['sheet:reject', 'vis:.sheet.is-open .owner-band'], { c: true }),
    'FIX-13': L(0, [NAV('waiting')], ['vis:#g-fixes']),
    'FIX-14': L(0, [MORE, `${SH} details.fold > summary`, `${SH} [data-sheet="action:fix_abandon"]`], ['sheet:action:fix_abandon']),
    'FIX-15': L(0, [NAV('problems'), '#main a[href="#/problems/plan"]', '#main .actions [data-sheet^="verb:fix:step:"]'], ['sheet:verb:fix']),
    'FIX-16': L(0, [MORE, `${SH} details.fold > summary`, `${SH} [data-sheet="action:fix_start"]`], ['sheet:action:fix_start']),
    /* ---- DEC ---- */
    'DEC-01': L(0, [NAV('waiting')], ['hash:/waiting', 'vis:#main h1']),
    'DEC-02': L(0, [NAV('waiting'), '#main a[href="#/waiting/questions"]'], ['txt:ac.q.guide'], { note: 'live: the cards show while a run asks (end-to-end gate)' }),
    'DEC-03': L(0, [NAV('waiting'), '#main a[href="#/waiting/questions"]'], ['txt:wt.g.questions'], { note: 'live: asked when the project has several live branches' }),
    'DEC-04': L(0, [NAV('waiting'), '#main a[href="#/waiting/questions"]'], ['txt:wt.g.questions'], { note: 'live: asked once per project before the app runs' }),
    'DEC-05': L(0, [NAV('activity'), CHECK], ['vis:.sheet.is-open label:has(input[value="rules"])'], { note: 'with no assistant ready the check says so in place and starts with the rules; a run asks it (end-to-end gate)' }),
    'DEC-06': L(0, [NAV('waiting'), '#main [data-act="own-open"]'], ['vis:#main textarea']),
    'DEC-07': L(0, [NAV('waiting')], ['vis:#g-dec', 'vis:#main .wcard label.opt']),
    'DEC-08': L(0, [NAV('waiting'), '#main .wcard details > summary'], ['vis:#main .wcard details[open]']),
    'DEC-09': L(0, [NAV('waiting'), `#main #w-${CSS_ID(ids.decision)} label.opt`], ['vis:#main [data-act="send"]:not([disabled])']),
    'DEC-10': L(0, [NAV('waiting'), '#decided > summary'], ['vis:#decided[open] li']),
    'DEC-11': L(0, [NAV('waiting'), '#decided > summary', '#decided [data-act="copy"]'], ['vis:#toasts .toast']),
    /* ---- BRN ---- */
    'BRN-01': L(0, [BR], ['hash:/project/branches', 'vis:#main a[href^="#/project/branches/"]']),
    'BRN-02': L(0, [BR, '#main a[href*="show=yours"]'], ['hash:show=yours']),
    'BRN-03': L(0, [BR, '#main [data-sheet="compare"]'], ['sheet:compare']),
    'BRN-04': L(0, [BR, FEAT], ['hash:/project/branches/', 'vis:#main h1']),
    'BRN-05': L(0, [BR, '#main [data-sheet="choose-branch"]'], ['sheet:choose-branch']),
    'BRN-06': L(0, [BR, FEAT, '#main [data-sheet^="merge:"]'], ['sheet:merge', 'vis:.sheet.is-open .owner-band, .sheet.is-open [class*="owner"]'], { c: true }),
    'BRN-07': L(0, [BR, `#main a[href="#/project/branches/${enc(ids.conflict || '')}"]`, '#main [data-sheet^="merge:"]', `${SH} [data-sheet^="resolve:"]`], ['sheet:resolve']),
    'BRN-08': L(0, [BR, FEAT, '#main [data-sheet^="delete:"]'], ['sheet:delete'], { c: true }),
    'BRN-09': L(0, [BR, '#fold-deleted > summary', `#fold-deleted [data-sheet="restore:${ids.restore}"]`], ['sheet:restore']),
    'BRN-10': L(0, [BR, FEAT, '#main [data-sheet^="protect:"]'], ['sheet:protect']),
    'BRN-11': L(0, [BR, '#main [data-sheet="cleanup"]'], ['sheet:cleanup'], { c: true }),
    'BRN-12': L(0, [BR, '#main [data-act="ac-fetch"]'], ['vis:#toasts .toast']),
    /* ---- PLN ---- */
    'PLN-01': L(0, [NAV('understand'), UV('story')], ['hash:/understand/story', 'vis:#main h1']),
    'PLN-02': L(0, [NAV('problems'), '#main a[href="#/problems/plan"]'], ['hash:/problems/plan', `vis:#main a[href="#/problems/plan/${ids.step}"]`]),
    'PLN-03': L(0, [NAV('problems'), '#main a[href="#/problems/plan"]', `#main .un-steps a[href="#/problems/plan/${ids.step}"]`], [`hash:/problems/plan/${ids.step}`]),
    'PLN-04': L(0, [NAV('problems'), '#main a[href="#/problems/plan"]'], ['vis:#main .un-deplist li']),
    'PLN-05': L(0, [NAV('problems'), T6], ['vis:#main .planline']),
    'PLN-06': L(0, [NAV('problems'), '#main a[href="#/problems/plan"]', '#main a[href="#/problems/plan/waves"]'], ['hash:/problems/plan/waves']),
    'PLN-07': L(0, [NAV('understand'), UV('gaps')], ['hash:/understand/gaps']),
    'PLN-08': L(0, [NAV('understand'), UV('gaps'), `#main a[href="#/understand/gaps/${enc(ids.gap)}"]`], [`hash:/understand/gaps/${enc(ids.gap)}`]),
    'PLN-09': L(0, [NAV('understand'), UV('operations')], ['hash:/understand/operations']),
    'PLN-10': L(0, [NAV('understand'), UV('story'), '#main a[href*="tab=bridge"]'], ['hash:tab=bridge']),
    'PLN-11': L(0, [NAV('understand'), UV('ideal')], ['hash:/understand/ideal']),
    'PLN-12': L(0, [NAV('understand'), UV('ideal'), '#main [data-sheet="replan"]'], ['sheet:replan']),
    'PLN-13': L(0, [NAV('understand'), UV('story'), '#main .un-prov > summary'], ['vis:#main .un-prov[open]']),
    /* ---- SYS ---- */
    'SYS-01': L(0, [NAV('understand'), UV('components')], ['hash:/understand/components']),
    'SYS-02': L(0, [NAV('understand'), UV('components'), `#main .un-split :is(.only-desk .un-map__a, .only-phone a.row)[href^="#/understand/components/${enc(ids.comp)}"]`], [`hash:/understand/components/${enc(ids.comp)}`]),
    'SYS-03': L(0, [], [], { ph: { steps: [NAV('understand'), UV('components')], expect: ['vis:#main .only-phone a.row[href^="#/understand/components/"]'] }, dk: { steps: [NAV('understand'), UV('components'), '#main a[href*="view=list"]'], expect: ['hash:view=list'] } }),
    'SYS-04': L(0, [NAV('understand'), UV('components'), '#main a[href*="lens=unseen"]'], ['hash:lens=unseen']),
    'SYS-05': L(0, [NAV('understand'), UV('functions')], ['hash:/understand/functions', 'vis:#main a.un-fnrow']),
    'SYS-06': L(0, [NAV('understand'), UV('functions'), '#main a.un-fnrow'], ['hash:/understand/functions/']),
    'SYS-07': L(0, [NAV('understand'), UV('paths')], ['hash:/understand/paths']),
    'SYS-08': L(0, [NAV('understand'), UV('paths'), `#main a[href="#/understand/paths/${enc(ids.path)}"]`], [`hash:/understand/paths/${enc(ids.path)}`]),
    'SYS-09': L(0, [NAV('understand'), UV('data')], ['hash:/understand/data']),
    'SYS-10': L(0, [NAV('understand'), UV('data'), `#main a[href="#/understand/data/${enc(ids.store)}"]`], [`hash:/understand/data/${enc(ids.store)}`]),
    'SYS-11': L(0, [NAV('understand'), UV('unseen')], ['hash:/understand/unseen']),
    'SYS-12': L(0, [NAV('understand'), UV('journeys')], ['hash:/understand/journeys']),
    'SYS-13': L(0, [NAV('understand'), UV('infra')], ['hash:/understand/infra']),
    'SYS-14': L(0, [NAV('understand'), UV('pipelines')], ['hash:/understand/pipelines']),
    'SYS-15': L(0, [NAV('understand'), UV('pipelines'), '#main [data-sheet^="pstage:"]'], ['sheet:pstage']),
    'SYS-16': L(0, [NAV('understand'), UV('ai-decisions')], ['hash:/understand/ai-decisions']),
    'SYS-17': L(0, [NAV('understand'), UV('architecture')], ['hash:/understand/architecture']),
    'SYS-18': L(0, [], [], { ph: { steps: [NAV('understand'), UV('components'), '#main [data-sheet="map:today"]'], expect: ['sheet:map'] }, dk: { steps: [NAV('understand'), UV('components')], expect: ['vis:#main svg', 'vis:#main a[href*="view=list"]'] } }),
    /* ---- SCR ---- */
    'SCR-01': L(0, [NAV('understand'), UV('screens')], ['hash:/understand/screens']),
    'SCR-02': L(0, [NAV('understand'), UV('screens/all')], ['hash:/understand/screens/all']),
    'SCR-03': L(0, [NAV('understand'), UV('screens/all'), `#main a[href="#/understand/screens/${enc(ids.screen)}"]`], [`hash:/understand/screens/${enc(ids.screen)}`, 'vis:#main .un-picfig']),
    'SCR-04': L(0, [NAV('activity'), R12], ['vis:#main .ac-tl'], { note: 'the before and after screens show in a fix run that recorded them' }),
    /* ---- LIB ---- */
    'LIB-01': L(0, [NAV('understand'), UV('library')], ['hash:/understand/library']),
    'LIB-02': L(0, [NAV('understand'), UV('library')], ['vis:#main input']),
    'LIB-03': L(0, [NAV('understand'), UV('library'), `#main a[href="#/understand/library/${enc(ids.doc)}"]`], [`hash:/understand/library/${enc(ids.doc)}`, 'vis:#main .un-doc__body p']),
    'LIB-04': L(0, [NAV('understand'), UV('library'), '#main a[href="#/understand/library/START-HERE.md"]'], ['vis:#main .un-doc__body a']),
    'LIB-05': L(0, [NAV('understand'), UV('library'), '#main a[href="#/understand/library/CURRENT-STATE.md"]'], ['vis:#main .un-doc__body svg.un-dg']),
    'LIB-06': L(0, [NAV('understand'), UV('library'), '#main a[href*="tab=images"]'], ['hash:tab=images']),
    'LIB-07': L(0, [NAV('understand'), UV('report-files'), '#main [data-sheet^="file:"]'], ['sheet:file']),
    /* ---- HIS ---- */
    'HIS-01': L(0, [NAV('understand'), UV('history')], ['hash:/understand/history', `vis:#main a[href="#/understand/history/${ids.lastScan}"]`]),
    'HIS-02': L(0, [], [], { ph: { steps: ['#main button[data-sheet="health"]'], expect: ['txt:st.health.trend'] }, dk: { steps: [], expect: ['txt:st.health.trend'] } }),
    'HIS-03': L(0, [NAV('understand'), UV('history')], ['vis:#main a[href="#/problems?sev=high"]']),
    'HIS-04': L(0, [NAV('understand'), UV('history')], ['vis:#main svg']),
    'HIS-05': L(0, [NAV('understand'), UV('history'), '#events > summary'], ['vis:#events[open]']),
    'HIS-06': L(0, [NAV('understand'), UV('history'), `#main a[href="#/understand/history/${ids.lastScan}"]`], [`hash:/understand/history/${ids.lastScan}`]),
    'HIS-07': L(0, [NAV('understand'), UV('history'), '#main a[href="#/understand/history/compare"]'], ['hash:/understand/history/compare']),
    /* ---- AST ---- */
    'AST-01': L(0, [PM, PMROW('/project/assistants')], ['hash:/project/assistants', 'vis:#main .ac-arow']),
    'AST-02': L(0, [PM, PMROW('/project/assistants')], ['txt:ac.as.last']),
    'AST-03': L(0, [PM, PMROW('/project/assistants')], ['txt:ac.as.runs']),
    'AST-04': L(0, [PM, PMROW('/project/assistants')], ['txt:ac.as.improve']),
    'AST-05': L(0, [PM, PMROW('/project/assistants'), '#fold-chat > summary'], ['vis:#fold-chat[open] a[href="#/ask"]']),
    /* ---- CHT ---- */
    /* the floating assistant button opens the same conversation in place, on every screen */
    'CHT-01': L(0, ['#fab'], ['vis:#assist']),
    'CHT-02': L(0, ['#fab'], ['vis:#assist'], { note: 'the answer as it is written needs a signed-in assistant (end-to-end gate)' }),
    'CHT-03': L(0, ['#fab'], ['vis:#assist'], { note: 'proposals need a signed-in assistant (end-to-end gate)' }),
    'CHT-04': L(0, [NAV('activity'), ALL, RUN(ids.ended), `#main a[href^="#/ask?run="]`], ['hash:/ask'], { note: 'direct control shows on Ask with a signed-in assistant' }),
    'CHT-05': L(0, [NAV('activity'), R12, '#fab'], ['vis:#assist .assist__ctx, #assist .assist__state']),
    'CHT-06': L(0, ['#fab'], ['vis:#assist'], { note: 'depth shows with a signed-in assistant' }),
    'CHT-07': L(0, ['#fab'], ['vis:#assist']),
    /* ---- BLD ---- */
    'BLD-01': L(0, [MORE, `${SH} [data-sheet="action:blueprint_start"]`], ['sheet:action:blueprint_start']),
    'BLD-02': L(0, [MORE, `${SH} [data-sheet="action:extend_start"]`], ['sheet:action:extend_start']),
    'BLD-03': L(0, [MORE, `${SH} [data-sheet="action:build_start"]`], ['sheet:action:build_start']),
    'BLD-04': L(0, ['#fold-journey > summary'], ['vis:#fold-journey[open] li']),
    /* ---- PJS ---- */
    'PJS-01': L(0, [PM], ['sheet:project', 'txt:proj.others']),
    'PJS-02': L(0, [PM, `${SH} a[href*="kind=switch"]`], ['hash:kind=switch']),
    'PJS-03': L(0, [], ['vis:#main h1', 'vis:#main a[href*="kind=switch"]'], { start: '/open?kind=folder', note: 'the chooser opens instead of Status' }),
    'PJS-04': L(0, [], ['vis:#main h1'], { start: '/open?kind=export', note: 'the report chooser opens instead of Status' }),
    /* ---- SGN ---- */
    'SGN-01': L(0, [NAV('activity'), CHECK], ['txt:ac.chk.si']),
    'SGN-02': L(0, [NAV('activity'), CHECK, `${SH} label:has(input[value="test_user"])`], ['vis:.sheet.is-open label:has(input[value="test_user"]:checked)']),
    'SGN-03': L(0, [NAV('waiting')], ['hash:/waiting'], { note: 'live: the sign-in card shows while a check waits for it (end-to-end gate)' }),
    'SGN-04': L(0, [PM, PMROW('/project/app')], ['txt:ac.app.session'], { note: 'live: the browser picture shows while a check waits for the sign-in (end-to-end gate)' }),
    'SGN-05': L(0, [PM, PMROW('/project/app')], ['txt:ac.app.session'], { note: 'live: what the app sent shows beside the picture (end-to-end gate)' }),
    'SGN-06': L(0, [PM, PMROW('/project/app')], ['txt:ac.app.session.private']),
    'SGN-07': L(0, [PM, PMROW('/project/app')], ['hash:/project/app', 'txt:ac.app.session.again']),
    'SGN-08': L(0, [NAV('activity'), CHECK, `${SH} details.fold > summary`], ['vis:.sheet.is-open details.fold[open] input']),
    /* ---- ACT ---- */
    'ACT-01': L(0, [], ['vis:.count'], { note: 'the live strip shows while a run holds the slot (end-to-end gate)' }),
    'ACT-02': L(0, [], ['exists:#toasts[aria-live="polite"]'], { note: 'behaviour on every screen' }),
    'ACT-03': L(0, [], ['exists:#main[data-screen]'], { note: 'behaviour on every screen' }),
    'ACT-04': L(0, [], ['title:EAOS']),
    'ACT-05': L(0, [], ['vis:#banner .banner'], { start: '/status?state=reconnecting' }),
    'ACT-06': L(0, [], ['exists:#announce[aria-live="polite"]'], { note: 'behaviour on every screen' }),
    /* ---- SRC ---- */
    'SRC-01': L(0, [SRCH], ['sheet:search', 'vis:#search-input']),
    'SRC-02': L(0, [SRCH, { type: ['#search-input', 'الامان'] }], ['vis:#search-results .result']),
    'SRC-03': L(0, [NAV('problems')], ['vis:#main #pq']),
    /* ---- SEL ---- */
    'SEL-01': L(0, [NAV('problems'), `#main input[value="${ids.first}"]`], ['vis:.selbar .selbar__count']),
    'SEL-02': L(0, [NAV('problems'), '#main [data-sheet="groups"]', `${SH} [data-act="select-group"]`], ['vis:.selbar .selbar__count']),
    'SEL-03': L(0, [NAV('problems'), `#main input[value="${ids.first}"]`], ['vis:.selbar [data-act="sel-clear"]']),
    'SEL-04': L(0, [NAV('problems'), `#main input[value="${ids.first}"]`, '.selbar [data-sheet="verb:fix"]'], ['sheet:verb:fix']),
    /* ---- LNK ---- */
    'LNK-01': L(0, [], ['hash:/status'], { note: 'every state is its address; behaviour on every screen' }),
    /* ---- SET ---- */
    'SET-01': L(0, [], ['lang:{other}'], { ph: { steps: [PM, `${SH} [data-act="lang"][data-lang="{other}"]`] }, dk: { steps: ['.side-prefs [data-act="lang"][data-lang="{other}"]'] } }),
    'SET-02': L(0, [], ['theme:dark'], { ph: { steps: [PM, `${SH} [data-act="theme-set"][data-theme="dark"]`] }, dk: { steps: ['.side-prefs [data-act="theme"]'] } }),
    'SET-03': L(0, [PM, PMROW('/project/settings'), '#main label:has(input[value="UTC"])'], ['vis:#main label:has(input[value="UTC"]:checked)']),
    'SET-04': L(0, [], [`has:${ids.total}`]),
    'SET-05': L(0, [PM, PMROW('/project/settings')], ['vis:#main a[href="#/project/branches"]']),
    'SET-06': L(0, ['#fold-about > summary'], [`has:EAOS ${ids.version}`]),
    'SET-07': L(0, [], ['exists:.skip[href="#main"]']),
    /* ---- OFF ---- */
    'OFF-01': L(0, [], ['vis:.banner--offline'], { start: '/status?state=offline' }),
    'OFF-02': L(0, ['#banner [data-sheet="open-live"]'], ['sheet:open-live'], { start: '/status?state=offline' }),
    'OFF-03': L(0, ['#main .actions .btn--primary'], ['sheet:open-live', 'vis:.sheet.is-open [data-act="copy"]'], { start: '/status?state=offline' }),
    'OFF-04': L(0, [], ['vis:#main h1'], { start: '/open?kind=nokey', note: 'the page opens instead of Status' }),
    'OFF-05': L(0, [PM, PMROW('/project/settings')], ['txt:ac.set.access']),
    'OFF-06': L(0, [], ['vis:#main h1'], { start: '/open?kind=readonly', note: 'the page opens instead of Status' })
  };
  return R;
}

async function runOne(page, id, rec, w, lang) {
  const r = Object.assign({}, rec, rec[w === 390 ? 'ph' : 'dk'] || {});
  const other = lang === 'ar' ? 'en' : 'ar';
  const sub = s => s.replace(/\{other\}/g, other);
  const start = r.start || '/status';
  await Lib.open(page, start, lang, 'light');
  let presses = 0; const labels = [];
  try {
    for (const st of r.steps) {
      if (typeof st === 'string') {
        const loc = page.locator(`${sub(st)} >> visible=true`).first();
        labels.push(await loc.evaluate(e => (e.getAttribute('aria-label') || (e.innerText || '').split('\n').map(x => x.trim()).filter(Boolean)[0] || e.value || '').replace(/\s+/g, ' ').trim().slice(0, 48), null, { timeout: 2500 }));
        await loc.click({ timeout: 2500 });
        presses++;
        await page.waitForTimeout(260);
      } else if (st.type) {
        await page.locator(st.type[0]).first().fill(st.type[1]);
        labels.push(`(type "${st.type[1]}")`);
        await page.waitForTimeout(260);
      }
    }
  } catch (e) { return { presses, labels, ok: false, why: 'press failed: ' + String(e.message).split('\n')[0].slice(0, 160) }; }
  const fails = await page.evaluate(exp => {
    const bad = [];
    const vis = css => [...document.querySelectorAll(css)].some(e => e.checkVisibility && e.checkVisibility());
    const hash = decodeURIComponent(location.hash);
    const text = document.body.innerText;
    for (const x of exp) {
      const i = x.indexOf(':'); const k = x.slice(0, i), v = x.slice(i + 1);
      let ok = true;
      if (k === 'vis') ok = vis(v);
      else if (k === 'exists') ok = !!document.querySelector(v);
      else if (k === 'hash') ok = hash.includes(v);
      else if (k === 'sheet') ok = !!document.querySelector('.sheet.is-open') && hash.includes('sheet=' + v);
      else if (k === 'txt') { const w = String(EAOS.t(v)).split('{')[0].trim(); ok = text.includes(w); }
      else if (k === 'has') ok = text.includes(v);
      else if (k === 'title') ok = document.title.includes(v);
      else if (k === 'lang') ok = document.documentElement.lang === v;
      else if (k === 'theme') ok = document.documentElement.dataset.theme === v;
      if (!ok) bad.push(x);
    }
    return bad;
  }, r.expect.map(sub));
  return { presses, labels, ok: !fails.length, why: fails.length ? 'not reached: ' + fails.join(', ') : '' };
}

(async () => {
  const filter = process.argv[2];
  const feats = [...fs.readFileSync(FEATURES, 'utf8').matchAll(/^#### ([A-Z]{3}-\d{2})/gm)].map(m => m[1]);
  const browser = await Lib.chromium.launch();
  const first = await Lib.context(browser, 1440);
  const R = recipes(await discover(await first.newPage()));
  await first.close();
  const missing = feats.filter(f => !R[f]);
  if (missing.length) { console.log('no recipe for', missing.join(' ')); process.exit(1); }
  const prev = fs.existsSync(OUT) && filter ? JSON.parse(fs.readFileSync(OUT, 'utf8')) : { results: {} };
  const results = prev.results;
  for (const w of [390, 1440]) for (const lang of ['ar', 'en']) {
    const ctx = await Lib.context(browser, w, 'light');
    const page = await ctx.newPage();
    for (const id of feats) {
      if (filter && !id.startsWith(filter) && id !== filter) continue;
      const res = await runOne(page, id, R[id], w, lang);
      const e = results[id] || (results[id] = { c: !!R[id].c, start: R[id].start || '/status', note: R[id].note || '', runs: {} });
      e.c = !!R[id].c; e.start = R[id].start || '/status'; e.note = R[id].note || '';
      e.runs[`${w}-${lang}`] = res;
      if (!res.ok) console.log(`FAIL ${id} ${w}-${lang}: ${res.why}`);
    }
    await ctx.close();
  }
  await browser.close();
  for (const id of Object.keys(results)) {
    const r = results[id].runs;
    results[id].phone = Math.max(...['390-ar', '390-en'].map(k => r[k] ? r[k].presses : 99));
    results[id].desktop = Math.max(...['1440-ar', '1440-en'].map(k => r[k] ? r[k].presses : 99));
    results[id].ok = Object.values(r).length === 4 && Object.values(r).every(x => x.ok);
  }
  fs.writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString(), rule: 'D46: from Status; one press = one click; typing free; the press that opens a preview counts; the governance tick and act are not pressed (+c)', results }, null, 1));
  const all = Object.values(results);
  console.log(`features: ${all.length}; passed at 390/1440 in ar/en: ${all.filter(x => x.ok).length}; above 3: ${all.filter(x => x.phone > 3 || x.desktop > 3).length}`);
})();
