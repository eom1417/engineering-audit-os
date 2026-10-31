// S-12 the check preview (CHK-01..06, SGN-01, SGN-02, SGN-08, DEC-05) on POST /api/actions/audit/preview: what it
// looks at, with or without AI and which assistant, the sign-in way, the speed mode, the published address, the time
// from this project's last check; Start sends exactly those inputs (POST /api/runs). S-13 what EAOS can do now
// (PRJ-08: composed from the data), then every action of the contract (RUN-13), then the expert steps (FIX-16); each
// action opens its own preview with its form (action.js).
import {
  said, t, tn, L, num, esc, rich, icon, code, href, sheet, act, rerenderSheet, local, closeSheetThen, toast, refresh, offline, S, live, store, model,
  client, contract, normalize, ac, rowWords, toggleRow, radio, facts, titledBlock,
} from 'eaos';

const enc = encodeURIComponent;
S.ac = S.ac || { prefill: {} };
/** The refusal or problem line above a preview's start button, when there is one. */
export const alertLine = text => (text ? `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(text)}</p>` : '');

/* ---------- S-12 the check preview ---------- */
const readyOnes = () => (live.assistants || []).filter(a => a.installed && a.logged_in);
function assistantInputs(c) {
  if (c.asst !== 'rules') return { use_assistant: true, assistant: c.asst };
  return !readyOnes().length && c.kept ? { without_ai: true } : { use_assistant: false };
}
function checkInputs(c) {
  return Object.assign({ fresh: true, mode: c.speed ? 'speed' : 'normal' }, c.paths.length ? { paths: c.paths } : {},
    assistantInputs(c),
    c.signinAsked ? { sign_in: c.signin } : {}, c.signin === 'hand' && c.published ? { published: c.published } : {},
    c.runAppAsked && c.runApp ? { run_app: true } : {},
    c.withoutTools ? { without_tools: true } : {});
}
function askCheck(c) {
  if (!client || c.asking) return;
  const mine = c.ticket = (c.ticket || 0) + 1;
  c.asking = true;
  client.preview('audit', { inputs: checkInputs(c) }).then(p => {
    if (mine !== c.ticket) return;
    c.preview = p; c.asking = false;
    if (!c.offer) {
      c.offer = p.check || { paths: [], mode: 'normal', sign_in: null, sign_in_seen: [] };
      c.speed = c.offer.mode === 'speed';
      c.signin = c.offer.sign_in === 'test_user' ? 'test_user' : c.offer.sign_in || 'hand';
      c.runApp = true;      // a check of the app's pages runs it unless the person turns it off
    }
    rerenderSheet();
  }, e => { if (mine !== c.ticket) return; c.asking = false; c.problem = said(e); rerenderSheet(); });
}
function againCheck(change) { const c = local(); Object.assign(c, change, { problem: null }); askCheck(c); rerenderSheet(); }
const pathName = (c, id) => { const p = c.offer && c.offer.paths.find(x => x.id === id); return p ? L(p.name) : id; };
function publishedProblem(v) {
  if (!v) return null;
  return !/^https?:\/\/[^\s/]+\.[^\s]+/i.test(v) || /^https?:\/\/(localhost|127\.|0\.0\.0\.0|\[::1\])/i.test(v) ? t('ac.chk.pub.bad') : null;
}
function toolsLine() {
  const f = live.progress && live.progress.flows && live.progress.flows.tools;
  const list = (f && f.stages) || [];
  const ready = list.filter(s => s.state === 'ok').length, failed = list.filter(s => s.state === 'failed');
  return { ready, total: list.length, failed };
}

function initCheck(c, q) {
  const ready = readyOnes();
  Object.assign(c, { init: true, paths: q.path && q.path !== 'complete' ? [q.path] : [], published: '', kept: true, asst: ready.length ? ready[0].id : 'rules' });
}
function checkFacts(p) {
  const first = !ac.lastCheck();
  const est = p && p.estimate && p.estimate.minutes_low != null ? t('pv.estimate.v', { lo: num(p.estimate.minutes_low), hi: num(p.estimate.minutes_high) }) : t('ac.chk.est.none');
  return facts([
      [t('pv.estimate'), `${p ? esc(est) : `<span class="muted" aria-busy="true">${t('pv.updating')}</span>`}<span class="small muted" style="display:block">${p && p.estimate ? esc(L(p.estimate.basis)) : t(first ? 'ac.chk.est.basis.none' : 'ac.chk.est.basis.wait')}</span>`],
      [t('pv.risk'), `<span class="tag tag--state">${t('pv.risk.low')}</span> <span class="small ink-2">${t('ac.chk.risk')}</span>`],
      [t('pv.fail'), p ? esc(L(p.on_failure)) : t('ac.chk.fail'), 'small'],
    ]);
}
function pathsHTML(c) {
  const pathCard = (id, on, name, looks) => `<label class="opt ac-path"><input type="checkbox" data-change="ac-path" value="${esc(id)}" data-fk="path-${esc(id)}" ${on ? 'checked' : ''}><span class="ac-path__box" aria-hidden="true">${icon('tick')}</span>
      <span class="opt__text"><b class="ac-path__name">${esc(name)}</b><span class="opt__note">${rich(looks)}</span></span></label>`;
  return c.offer ? c.offer.paths.map(x => pathCard(x.id, x.id === 'complete' ? !c.paths.length : c.paths.includes(x.id), L(x.name), L(x.looks_at))).join('') : `<p class="small muted" aria-busy="true">${t('pv.updating')}</p>`;
}
/** The assistants to choose from, the rules alone, and the question when none is ready (DEC-05). */
function assistantsHTML(c) {
  const ready = readyOnes();
  const asst = (live.assistants || []).map(a => {
    const ok = a.installed && a.logged_in;
    return radio({ name: 'ac-asst', value: a.id, 'data-change': 'ac-asst', 'data-fk': `asst-${a.id}`, checked: c.asst === a.id, disabled: !ok },
      esc(a.name) + (ok ? `<span class="tag tag--ok">${icon('check')}${t('pv.ready')}</span>` : ''),
      esc(ok ? t('ac.chk.asst.ready', { version: a.version || '' }) : !a.installed ? t('pv.notinstalled') : t('ac.chk.asst.notsigned', { cmd: a.id + ' login' })));
  }).join('') + radio({ name: 'ac-asst', value: 'rules', 'data-change': 'ac-asst', 'data-fk': 'asst-rules', checked: c.asst === 'rules' }, t('ac.chk.rules'), t('ac.chk.rules.note'));
  const dec5 = live.assistants && live.assistants.length && !ready.length ? `<div class="ac-refuse" role="note"><p class="small"><b>${esc(t('ac.chk.dec5.q', { name: live.assistants.map(a => a.name).join(t('list.sep')) }))}</b> ${t('ac.chk.dec5.why', { cmd: code('claude login') })}</p>
      <div class="actions mt-2"><button class="btn btn--secondary btn--sm" data-act="ac-ask-again" data-fk="ask-again" ${c.asking2 ? 'disabled' : ''}>${c.asking2 ? t('ac.as.asking') : t('ac.chk.dec5.fixed')}</button></div>
      <p class="small ink-2">${t('ac.chk.dec5.noai.v')}</p></div>` : '';
  return `${dec5}<div class="opts">${asst}</div>`;
}
function runAppHTML(c) {
  if (!c.runAppAsked) return '';
  return toggleRow(t('ac.chk.run'), t(c.runApp ? 'ac.chk.run.note' : 'ac.chk.run.off'), { 'data-change': 'ac-run', 'data-fk': 'run-app', checked: c.runApp });
}
function signinHTML(c, needed) {
  if (!needed) return `<p class="small muted">${t('ac.chk.si.notneeded')}</p>`;
  const offer = c.offer;
  const seen = offer && offer.sign_in_seen && offer.sign_in_seen[0] ? offer.sign_in_seen[0].split(':')[0] : null;
  return `${seen ? `<p class="small ink-2 mb-2">${t('ac.chk.si.found', { path: code(seen) })}</p>` : ''}
      <div class="opts">${[['hand', 'ac.chk.si.hand'], ['test_user', 'ac.chk.si.test'], ['none', 'ac.chk.si.none']].map(([id, k]) => radio({ name: 'ac-si', value: id, 'data-change': 'ac-si', 'data-fk': `si-${id}`, checked: c.signin === id }, t(k), t(k + '.note'))).join('')}</div>
      ${c.signin === 'hand' && live.signIn && live.signIn.kept ? `<p class="small ink-2 ac-iline">${icon('check', 'icon--sm ac-c-ok')}<span>${t('ac.chk.si.kept')}</span></p>` : ''}`;
}
function toolsHTML(c) {
  const tools = toolsLine();
  return `<a class="row panel" href="${href('/project/tools')}" data-act="go" data-href="${href('/project/tools')}" style="min-height:52px">${ac.glyph(tools.failed.length ? 'failed' : 'ok')}<span class="row__main small">${esc(tools.total ? t(tools.failed.length ? 'ac.chk.tools.failed' : 'ac.chk.tools', { n: num(tools.ready), total: num(tools.total), failed: tools.failed.map(s => s.name).join(t('list.sep')) }) : t('ac.chk.tools.none'))}</span>${icon('chev', 'icon--sm icon--dir muted')}</a>
        ${tools.failed.length ? toggleRow(t('ac.chk.without'), null, { 'data-change': 'ac-without', 'data-fk': 'without', checked: c.withoutTools }) : ''}`;
}
function optionsHTML(c, pubErr) {
  return `<details class="panel fold" ${c.speed || c.published ? 'open' : ''}><summary>${rowWords(t('ac.chk.options'), t('ac.chk.options.sum'))}${icon('chev', 'chev')}</summary>
          <div class="fold__body ac-stack">
            ${toggleRow(t('ac.chk.speed'), t('ac.chk.speed.note'), { 'data-change': 'ac-speed', 'data-fk': 'speed', checked: c.speed })}
            ${c.speed ? `<p class="ac-note ac-note--caution small">${icon('warn', 'icon--sm ac-c-caution')}<span>${t('ac.chk.speed.warn')}</span></p>` : ''}
            <label class="ac-label" for="ac-pub">${t('ac.chk.pub')}</label>
            <div class="field">${icon('globe')}<input id="ac-pub" type="url" inputmode="url" dir="ltr" data-fk="ac-pub" data-input="ac-pub" value="${esc(c.published)}" placeholder="app.example.com" autocomplete="off" aria-describedby="ac-pub-note"></div>
            <p class="small ${pubErr ? 'ac-c-danger' : 'muted'}" id="ac-pub-note">${pubErr ? esc(pubErr) : t('ac.chk.pub.note')}</p>
          </div></details>`;
}
function checkStartLabel(c, lr) {
  if (c.busy) return t('pv.starting');
  if (lr) return t('ac.chk.queue');
  if (c.asst === 'rules' && !readyOnes().length) return t('ac.chk.start.noai');
  return c.paths.length ? t('ac.chk.start.paths', { paths: c.paths.map(id => pathName(c, id)).join(t('ac.and')) }) : t('ac.chk.start');
}
function checkFoot(c, p, pubErr) {
  const lr = ac.liveRun();
  return `${alertLine(c.problem || c.refused)}
        ${lr ? `<p class="small ink-2 ac-iline">${icon('clock', 'icon--sm')}<span>${esc(t('ac.chk.busy', { label: ac.runLabel(lr) }))}</span></p>` : ''}
        <button class="btn btn--primary btn--block" data-act="ac-start-check" data-fk="chk-start" ${pubErr || !p || c.busy ? 'disabled' : ''}>${esc(checkStartLabel(c, lr))}</button>
        <button class="btn btn--quiet btn--block" data-act="copy" data-text="${esc(checkCmd(c))}">${icon('copy')}${t('pv.copy')}</button>`;
}
/** The questions the chosen paths ask: the sign-in (returned), and running the app. */
function askedOf(c) {
  const offer = c.offer;
  const needsSignin = !c.paths.length || c.paths.some(id => ['look', 'experience'].includes(id));
  c.signinAsked = needsSignin;
  // without the person's yes to run the app, its pages, sign-in and speed are never checked: asked here, once
  c.runAppAsked = !!offer && offer.run_app === false && (!c.paths.length || c.paths.some(id => ['look', 'speed', 'experience'].includes(id)));
  return needsSignin;
}

sheet('check', {
  kind: 'drawer',
  render(arg, q, c) {
    if (offline()) return { title: esc(t('ac.chk.title')), body: `<p>${t('ac.chk.does')}</p>`, foot: `<button class="btn btn--primary btn--block" data-act="sheet" data-sheet="open-live">${t('ac.chk.start')}</button>` };
    if (!c.init) initCheck(c, q);
    if (!c.preview && !c.asking && !c.problem) askCheck(c);
    const p = c.preview;
    const needsSignin = askedOf(c);
    const pubErr = publishedProblem(c.published);
    return {
      title: esc(t('ac.chk.title')),
      sub: `<span class="free-band">${icon('check', 'icon--sm')}${t('free')}</span>`,
      body: `<p>${t('ac.chk.does')}</p>
        ${checkFacts(p)}
        <fieldset class="ac-fs"><legend class="block-title">${t('ac.chk.paths')}</legend><div class="opts">${pathsHTML(c)}</div>
          <p class="small muted mt-2">${t('ac.chk.paths.note')}</p></fieldset>
        <fieldset class="ac-fs"><legend class="block-title">${t('ac.chk.asst')}</legend>${assistantsHTML(c)}
          <p class="small muted mt-2">${t('ac.chk.asst.checked')} <button class="link ac-inline" data-act="ac-ask-again">${t('ac.asst.again')}</button></p></fieldset>
        ${runAppHTML(c)}
        ${c.runAppAsked && !c.runApp ? '' : `<fieldset class="ac-fs"><legend class="block-title">${t('ac.chk.si')}</legend>${signinHTML(c, needsSignin)}</fieldset>`}
        ${toolsHTML(c)}
        ${optionsHTML(c, pubErr)}
        <p class="small muted">${t('ac.chk.kept')}</p>`,
      foot: checkFoot(c, p, pubErr),
    };
  },
});
function checkCmd(c) {
  const i = checkInputs(c);
  return `eaos check${i.paths ? ' --paths ' + i.paths.join(',') : ''}${i.assistant ? ' --assistant ' + i.assistant : ' --without-ai'}${i.sign_in ? ' --sign-in ' + i.sign_in : ''}${c.speed ? ' --mode speed' : ''}${i.published ? ' --published ' + i.published : ''}`;
}
act('ac-path', el => {
  const c = local();
  let paths = c.paths;
  if (el.value === 'complete') paths = [];
  else if (el.checked) paths = [...new Set(paths.concat([el.value]))];
  else paths = paths.filter(x => x !== el.value);
  if (c.offer && paths.length === c.offer.paths.filter(x => x.id !== 'complete').length) paths = [];
  againCheck({ paths });
});
act('ac-asst', el => againCheck({ asst: el.value }));
act('ac-si', el => againCheck({ signin: el.value }));
act('ac-speed', el => againCheck({ speed: el.checked }));
act('ac-run', el => againCheck({ runApp: el.checked }));
act('ac-without', el => againCheck({ withoutTools: el.checked }));
let pubTimer = null;
act('ac-pub', el => { const c = local(); c.published = el.value.trim(); clearTimeout(pubTimer); pubTimer = setTimeout(() => rerenderSheet(), 400); });
/** "Ask again" (CHK-06): the assistants asked now, not the answer of the last minutes. */
act('ac-ask-again', async el => {
  if (el.disabled || !client) return;
  const c = local(); c.asking2 = true; rerenderSheet();
  try { await client.start({ action: 'assistant_check', inputs: { fresh: true } }); } catch (e) { /* the readiness is read below either way */ }
  const list = await store.refreshAssistants();
  c.asking2 = false;
  const ready = (list || []).filter(a => a.installed && a.logged_in);
  if (ready.length && c.asst === 'rules') c.asst = ready[0].id;
  toast(ready.length ? t('ac.asst.again.ready', { names: ready.map(a => a.name).join(t('list.sep')) }) : t('ac.asst.again.none'));
  rerenderSheet();
});
act('ac-start-check', async el => {
  const c = local();
  if (el.disabled || !client || c.busy) return;
  c.busy = true; rerenderSheet();
  try {
    const run = await client.start({ action: 'audit', inputs: checkInputs(c) });
    closeSheetThen(() => {
      store.refresh(); store.refreshProgress(); refresh();
      toast(run.state === 'queued' && ac.liveRun() ? t('ac.chk.queued', { n: num(run.position || 1) }) : t('toast.started', { title: t('ac.chk.title') }),
        { link: { href: href('/activity/run/' + enc(run.id)), text: t('toast.follow') } });
    });
  } catch (e) { Object.assign(c, { busy: false, refused: said(e) }); rerenderSheet(); }
});

/* ---------- S-13 the launcher ---------- */
/** Where each action of the contract sits in the launcher, its icon, and the one place it lives when it has a page. */
const META = {
  audit: { group: 'check', icon: 'retry', opens: 'check' }, tools_check: { group: 'check', icon: 'tool' }, assistant_check: { group: 'check', icon: 'ai' },
  choose_branch: { group: 'check', icon: 'branch', opens: 'choose-branch' }, accept: { group: 'check', icon: 'seal', link: '/waiting' }, undo: { group: 'check', icon: 'seal', link: '/waiting' },
  design_propose: { group: 'answers', icon: 'layers' }, design_make: { group: 'build', icon: 'layers' }, context_propose: { group: 'answers', icon: 'book' }, context_make: { group: 'build', icon: 'book' }, project_map: { group: 'build', icon: 'layers' },
  run_setup: { group: 'app', icon: 'app' }, run_try: { group: 'app', icon: 'ai' }, safety_net: { group: 'app', icon: 'screen' },
  blueprint_start: { group: 'build', icon: 'folder' }, extend_start: { group: 'build', icon: 'plus' }, build_start: { group: 'build', icon: 'layers' },
  replan_ideal: { group: 'plan', icon: 'ai' }, run_nodes: { group: 'plan', icon: 'ai' },
  design: { group: 'answers', icon: 'layers', link: '/report' }, status: { group: 'answers', icon: 'status' }, overview: { group: 'answers', icon: 'status' }, menu: { group: 'answers', icon: 'activity' },
  findings: { group: 'answers', icon: 'problems', link: '/problems' }, finding: { group: 'answers', icon: 'problems' }, impact: { group: 'answers', icon: 'map' },
  ask: { group: 'answers', icon: 'book' }, branches: { group: 'answers', icon: 'branch', link: '/project/branches' }, structure: { group: 'answers', icon: 'layers', link: '/report' },
  design_brief: { group: 'answers', icon: 'book' }, design_choose: { group: 'expert' }, plan: { group: 'answers', icon: 'layers', link: '/problems/plan' },
  report_file: { group: 'answers', icon: 'file', link: '/report?part=files' }, open_report: { group: 'answers', icon: 'external', link: '/report?part=files' },
  note: { group: 'answers', icon: 'note' },
};
const GROUPS = ['check', 'app', 'build', 'plan', 'answers'];
export const metaOf = a => META[a.id] || { group: 'expert' };
const HIDDEN = ['open_studio'];
/** Every action of the contract the person may start here, with the pointer to the verbs (Problems). */
function actions() { return contract.ACTIONS.filter(a => !HIDDEN.includes(a.id)); }
export const reading = a => metaOf(a).group === 'answers' || a.id === 'assistant_check';

function actionRow(a) {
  const m = metaOf(a);
  const attrs = m.opens ? `data-act="go" data-href="${href('/activity', { sheet: m.opens })}"` : m.link && !contract.personInputs(a).some(([, v]) => v) ? `data-act="go" data-href="${href(m.link)}"` : `data-act="sheet" data-sheet="action:${esc(a.id)}"`;
  const sub = m.link && !m.opens ? t('ac.lc.goes') : reading(a) ? t('ac.lc.answers_now') : t('ac.lc.preview_first');
  return `<button class="row" ${m.link && m.link.startsWith('/waiting') ? `data-act="go" data-href="${href(m.link)}"` : attrs} data-fk="a-${esc(a.id)}">${icon(m.icon || 'dash', 'muted')}${rowWords(esc(L(a.label)), esc(sub))}${icon('chev', 'icon--sm icon--dir muted')}</button>`;
}
function launcherList(qv) {
  const all = actions().filter(a => !qv || normalize.matches([a.id, a.label.ar, a.label.en, a.description.ar, a.description.en].join(' '), qv));
  const verbs = !qv || normalize.matches([t('ac.lc.x.verbs'), 'fix verify explain plan'].join(' '), qv);
  if (qv && !all.length && !verbs) return `<p class="small muted">${t('ac.lc.none')}</p>`;
  const verbRow = `<button class="row" data-act="go" data-href="${href('/problems')}" data-fk="a-verbs">${icon('problems', 'muted')}${rowWords(t('ac.lc.x.verbs'), t('ac.lc.x.verbs.sub'))}${icon('chev', 'icon--sm icon--dir muted')}</button>`;
  const groups = GROUPS.map(g => {
    const items = all.filter(a => metaOf(a).group === g);
    const extra = g === 'check' && verbs ? verbRow : '';
    return items.length || extra ? titledBlock(t('ac.lc.g.' + g), `<div class="panel rows">${extra}${items.map(actionRow).join('')}</div>`) : '';
  }).join('');
  const ex = all.filter(a => metaOf(a).group === 'expert');
  const expert = ex.length ? `<details class="panel fold" ${qv ? 'open' : ''}><summary>${rowWords(t('ac.lc.g.expert'), esc(t('ac.lc.expert.sum', { n: num(ex.length) })))}${icon('chev', 'chev')}</summary>
    <div class="rows" style="border-top:1px solid var(--line)">${ex.map(actionRow).join('')}</div></details>` : '';
  return groups + expert;
}
/** PRJ-08: what EAOS can do now, from the data: the fixes it makes by itself, what waits for the owner, the branch
 *  it delivered, the high problems, a new check. */
function recommended() {
  const o = a => (offline() ? 'data-act="sheet" data-sheet="open-live"' : a);
  const opt = (ic, title, sub, attrs, primary) => `<button class="row" ${attrs}>${icon(ic, primary ? 'ac-c-accent' : 'muted')}${rowWords(esc(title), esc(sub))}${icon('chev', 'icon--dir muted')}</button>`;
  const tot = model.totals(), wc = model.waitingCount(), branch = store.awaiting()[0];
  const high = (tot.by_severity.critical || 0) + (tot.by_severity.high || 0);
  const rows = [];
  if (branch) rows.push(opt('branch', t('ac.lc.r.branch', { branch: branch.result.branch }), t('ac.lc.r.branch.sub'), `data-act="go" data-href="${href('/waiting/' + enc(branch.id))}"`, true));
  if (tot.fixable) rows.push(opt('tool', t('ac.lc.r.fix', { problems: tn('pl.problem', tot.fixable) }), t('ac.lc.r.fix.sub'), o('data-act="sheet" data-sheet="verb:fix:fixable"'), !branch));
  if (wc) rows.push(opt('waiting', tn('pl.thing_waits', wc), t('ac.lc.r.wait.sub'), `data-act="go" data-href="${href('/waiting')}"`));
  if (high) rows.push(opt('problems', t('ac.lc.r.high', { problems: tn('pl.problem', high) }), t('ac.lc.r.high.sub'), `data-act="go" data-href="${href('/problems', { sev: 'high' })}"`));
  rows.push(opt('retry', t('ac.lc.r.check'), t('ac.lc.r.check.sub'), o(`data-act="go" data-href="${href('/activity', { sheet: 'check' })}"`), !rows.length));
  return rows.join('');
}
sheet('launcher', {
  kind: 'drawer', needs: ['cards'],
  render() {
    return {
      title: esc(t('st.opt.title')),
      sub: esc(t('st.opt.sub')),
      body: `${titledBlock(t('ac.lc.reco'), `<div class="panel rows">${recommended()}</div>`)}
        <div class="ac-lc-search"><div class="block-title" id="lc-h">${t('ac.lc.all')}</div>
          <label class="field">${icon('search')}<span class="sr-only">${t('ac.lc.search')}</span><input type="search" id="lc-q" data-fk="lc-q" placeholder="${esc(t('ac.lc.search'))}" autocomplete="off" aria-describedby="lc-h"></label></div>
        <div id="lc-list" class="ac-stack">${launcherList('')}</div>`,
    };
  },
  after(el) {
    const input = el.querySelector('#lc-q');
    if (input) input.addEventListener('input', () => { el.querySelector('#lc-list').innerHTML = launcherList(input.value); });  // nosemgrep: javascript.browser.security.insecure-document-method, javascript.browser.security.insecure-innerhtml -- the query only filters; every text is a word or escaped
  },
});
