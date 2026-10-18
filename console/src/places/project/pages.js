// The project's other pages (builder A): S-48 Your app (APP-01, APP-03, SGN-02, SGN-06, SGN-07, DEC-04), S-49
// Assistants and cost (AST-01..05, CHK-06), S-50 Tools (CHK-05), S-51 Settings (SET-03, SET-05..07, OFF-05). What they
// say comes from the live API: the `status` and `assistant_check` reading tools (free, answered at once), the check's
// offer (the audit preview), /api/progress's setup, safety and tools flows, /api/sign-in, /api/usage, /api/session.
import {
  t, L, num, esc, icon, code, href, has, fmtWhen, exactTime, screen, sheet, act, refresh, toast, closeSheetThen, setTimeZone, offline,
  prefs, live, store, model, client, contract, ActionError, ac,
} from 'eaos';
import { projBack, protectedNames } from './branches.js';

const said = e => (e instanceof ActionError ? e.message : String(e));
const flows = () => (live.progress && live.progress.flows) || {};
const offlinePage = (lede, guide) => `<div class="page">${projBack()}<h1 class="lede">${t(lede)}</h1><p class="guide">${t(guide)}</p><div class="actions"><button class="btn btn--primary" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button></div></div>`;
const busyPage = lede => `<div class="page" aria-busy="true">${projBack()}<h1 class="lede">${t(lede)}</h1><div class="panel rows section">${[1, 2].map(() => `<div class="row"><span style="flex:1;display:grid;gap:8px"><span class="skel-line" style="width:40%"></span><span class="skel-line" style="width:70%"></span></span></div>`).join('')}</div></div>`;

/** A reading tool's answer, asked once per visit (and again on demand). */
const answers = {};
function answer(action, inputs, again) {
  if (!client) return null;
  const k = action;
  if (answers[k] && !again) return answers[k].data;
  if (!answers[k] || again) {
    answers[k] = Object.assign({}, answers[k], { asking: true });
    client.start({ action, inputs: inputs || {} }).then(run => { answers[k] = { data: (run.result && run.result.answer) || {} }; refresh(); },
      e => { answers[k] = { data: answers[k] && answers[k].data, problem: said(e) }; refresh(); });
  }
  return answers[k].data || null;
}
const asking = action => !!(answers[action] && answers[action].asking);
/** What the start of a check offers and keeps (the free audit preview). */
let offer = null, offering = false;
function checkOffer() {
  if (!client || offer || offering) return offer;
  offering = true;
  client.preview('audit', { inputs: {} }).then(p => { offer = p.check || {}; offering = false; refresh(); }, () => { offering = false; offer = {}; refresh(); });
  return offer;
}

/* =================================================================================================================
   S-48 YOUR APP
   ================================================================================================================= */
const flowState = f => (!f || f.state === 'none' ? null : f.state === 'done' ? (f.status === 'COMPLETE' ? 'ok' : 'partial') : f.state);
function appPage(ctx) {
  if (ctx.offline) return offlinePage('ac.app.offline', 'ac.app.offline.guide');
  const st = answer('status');
  const o = checkOffer();
  if (!st) return busyPage('ac.app.loading');
  const consent = (((st.handover || {}).person_already_answered) || []).some(a => a.question === 'run_and_fix' && a.answer === true);
  const setup = flowState(flows().setup), safety = flowState(flows().safety);
  const runs = st.app_runs === true ? 'ok' : st.app_runs === false ? 'failed' : null;
  const lede = runs === 'ok' ? 'ac.app.lede' : runs === 'failed' ? 'ac.app.lede.failed' : 'ac.app.lede.notsetup';
  const way = (o && o.sign_in) || null;
  const seen = o && o.sign_in_seen && o.sign_in_seen[0] ? o.sign_in_seen[0].split(':')[0] : null;
  const kept = live.signIn && live.signIn.kept;
  const lastRun = action => ac.runs().find(r => r.action === action);
  const runLink = action => { const r = lastRun(action); return r ? ` <a class="link" href="${href('/activity/run/' + encodeURIComponent(r.id))}">${t('ac.app.how')}</a>` : ''; };
  return `<div class="page">
    ${projBack()}
    <h1 class="lede">${t(lede)}</h1>
    <p class="guide">${t(runs ? 'ac.app.guide' : 'ac.app.guide.notsetup')}</p>
    <div class="actions">${runs === 'failed' ? `<button class="btn btn--primary" data-act="sheet" data-sheet="action:run_try">${t('ac.run.get_running')}</button>`
      : runs === 'ok' ? `<button class="btn btn--primary" data-act="sheet" data-sheet="action:safety_net">${t('ac.app.record')}</button>` : `<button class="btn btn--primary" data-act="sheet" data-sheet="action:run_setup">${t('ac.app.run')}</button>`}
      ${runs ? `<button class="btn btn--quiet" data-act="sheet" data-sheet="action:run_setup">${t('ac.app.run')}</button>` : ''}
      <p class="actions__note">${t('ac.app.consent.ask')}</p></div>
    <section class="section" aria-labelledby="app-h"><div class="section-head"><h2 id="app-h">${t('ac.app.state')}</h2></div><div class="panel panel__pad"><dl class="facts ac-facts">
      <dt>${t('ac.app.runs')}</dt><dd>${runs ? ac.mark(runs, t(runs === 'ok' ? 'ac.app.runs.yes' : 'ac.app.runs.no')) : ac.nmTag(t('ac.app.runs.notyet'))}${runLink('run_setup')}</dd>
      <dt>${t('ac.app.setup')}</dt><dd>${setup ? ac.mark(setup, esc(t('ac.flow.ended', { when: fmtWhen(flows().setup.ended_at) }))) : esc(t('ac.app.never'))}</dd>
      <dt>${t('ac.app.screens')}</dt><dd>${st.safety_net ? ac.mark('ok', t('ac.app.screens.match')) : safety ? ac.mark(safety, esc(t('ac.flow.ended', { when: fmtWhen(flows().safety.ended_at) }))) + ` <span class="small muted">${t('ac.app.screens.other')}</span>` : ac.nmTag(t('ac.app.screens.nm'))}${runLink('safety_net')}</dd>
      <dt>${t('ac.app.copy')}</dt><dd>${t('ac.app.copy.v')}</dd></dl></div></section>
    <section class="section" aria-labelledby="cons-h"><div class="section-head"><h2 id="cons-h">${t('ac.app.consent')}</h2></div>
      <div class="panel panel__pad ac-stack"><div class="ac-note">${ac.glyph(consent ? 'ok' : 'notin')}<span class="small">${t(consent ? 'ac.app.consent.yes' : 'ac.app.consent.no')}</span></div>
        <p class="small ink-2">${t('ac.app.consent.what')}</p></div></section>
    <section class="section" aria-labelledby="si-h"><div class="section-head"><h2 id="si-h">${t('ac.chk.si')}</h2></div>
      <div class="panel panel__pad ac-stack">
        <p class="small ink-2">${seen ? t('ac.chk.si.found', { path: code(seen) }) : t('ac.app.si.none')}</p>
        <dl class="facts"><dt>${t('ac.app.si.way')}</dt><dd>${way ? t('ac.chk.si.' + (way === 'test_user' ? 'test' : way)) : t('ac.app.si.notyet')}</dd></dl>
        <p class="small ink-2">${t('ac.app.si.kept')} <a class="link" href="${href('/activity', { sheet: 'check' })}">${t('ac.app.si.change')}</a></p></div></section>
    <section class="section" aria-labelledby="sess-h"><div class="section-head"><h2 id="sess-h">${t('ac.app.session')}</h2></div>
      <div class="panel panel__pad ac-stack">
        <div class="ac-note">${ac.glyph(kept ? 'ok' : 'notin')}<span class="small">${t(kept ? 'ac.app.session.kept' : 'ac.app.session.forgot')}</span></div>
        <p class="small ink-2">${t('ac.app.session.private')}</p>
        <p class="small ink-2">${t('ac.app.session.again')}</p>
        ${kept ? `<div><button class="btn btn--secondary btn--sm" data-act="sheet" data-sheet="forget">${t('ac.app.forget')}</button></div>` : ''}</div></section>
  </div>`;
}
screen({ id: 'S-48', path: '/project/app', place: 'project', title: () => t('proj.app'), render: appPage });
sheet('forget', {
  kind: 'dialog', confirm: true,
  render(arg, query, own) {
    return { title: esc(t('ac.fg.title')), body: `<p>${t('ac.fg.lede')}</p><p class="small ink-2">${t('ac.fg.after')}</p>${own.refused ? `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(own.refused)}</p>` : ''}`,
      foot: `<div class="sheet__foot-row"><button class="btn btn--secondary" data-act="sheet-close" data-autofocus>${t('cancel')}</button><button class="btn btn--danger" data-act="ac-forget" data-fk="forget-do" ${offline() ? 'disabled' : ''}>${t('ac.fg.do')}</button></div>` };
  },
});
act('ac-forget', async () => {
  if (!client) return;
  try {
    const st = await client.signIn.forget();
    live.signIn = Object.assign({}, live.signIn, st);
    closeSheetThen(() => { toast(t('ac.fg.done', { n: num(st.forgotten || 0) })); store.refresh(); refresh(); });
  } catch (e) { toast(said(e), { refusal: true }); }
});

/* =================================================================================================================
   S-49 ASSISTANTS AND COST ("a measure, not a bill")
   ================================================================================================================= */
let usage = null, usageReading = false;
function readUsage(again) {
  if (!client || usageReading || (usage && !again)) return usage;
  usageReading = true;
  client.usage().then(u => { usage = u; usageReading = false; refresh(); }, () => { usage = { runs: [], check: null, chat: null }; usageReading = false; refresh(); });
  return usage;
}
const all = u => ac.usedTokens(u) || 0;
function asstPage(ctx) {
  if (ctx.offline) return offlinePage('ac.as.offline', 'ac.as.offline.guide');
  const check = answer('assistant_check');
  const u = readUsage();
  if (!live.assistants || !u) return busyPage('ac.as.loading');
  const rows = (check && check.assistants) || live.assistants.map(a => Object.assign({ ready: a.installed && a.logged_in }, a));
  const ready = rows.filter(a => a.ready);
  if (!rows.some(a => a.installed)) {
    return `<div class="page">${projBack()}<h1 class="lede">${t('ac.as.none')}</h1><p class="guide">${t('ac.as.none.guide')}</p>
      <div class="actions"><button class="btn btn--secondary" data-act="copy" data-text="npm install -g @anthropic-ai/claude-code">${icon('copy')}${t('ac.as.none.copy')}</button></div></div>`;
  }
  const lede = ready.length ? t('ac.as.lede.ready', { names: ready.map(a => a.name).join(t('list.sep')) }) : t('ac.as.lede.none');
  const checkedAt = rows.find(a => a.checked_at);
  const stages = u.check ? Object.entries(u.check.stages || {}).sort((a, b) => (b[1].cost_usd || 0) - (a[1].cost_usd || 0)) : [];
  const stageName = id => (has('ac.stage.' + id) ? t('ac.stage.' + id) : id);
  const tok = n => ac.tokens(n) || '0';
  const mins = ms => (ms ? ac.secs(ms / 1000) : '');
  const stageRows = stages.map(([id, s]) => `<li class="row ac-urow"><span class="row__main"><span class="row__title small">${esc(stageName(id))}</span>
      <span class="row__meta ac-meta"><span>${esc(tok(all(s)))}</span><span>${esc(t('ac.as.turns', { n: num(s.turns || 0) }))}</span><span>${esc(mins(s.duration_ms))}</span></span></span><span class="num ac-urow__cost">${s.cost_usd != null ? ac.money(s.cost_usd) : ''}</span></li>`).join('');
  const table = stages.length ? `<div class="ac-table-wrap only-desk"><table class="ac-table"><thead><tr><th scope="col">${t('ac.as.col.stage')}</th><th scope="col">${t('ac.as.col.in')}</th><th scope="col">${t('ac.as.col.cw')}</th><th scope="col">${t('ac.as.col.cr')}</th><th scope="col">${t('ac.as.col.out')}</th><th scope="col">${t('ac.as.col.think')}</th><th scope="col">${t('ac.as.col.time')}</th><th scope="col">${t('ac.as.col.cost')}</th></tr></thead>
    <tbody>${stages.map(([id, s]) => `<tr><th scope="row">${esc(stageName(id))}</th>${['input', 'cache_write', 'cache_read', 'output', 'thinking'].map(k => `<td class="num">${esc(tok(s[k] || 0))}</td>`).join('')}<td class="num">${esc(mins(s.duration_ms))}</td><td class="num">${s.cost_usd != null ? ac.money(s.cost_usd) : '—'}</td></tr>`).join('')}</tbody>
    <tfoot><tr><th scope="row">${t('ac.as.total')}</th><td colspan="5" class="num">${esc(tok(all(u.check.total)))}</td><td class="num">${esc(mins(u.check.total.duration_ms))}</td><td class="num">${u.check.total.cost_usd != null ? ac.money(u.check.total.cost_usd) : '—'}</td></tr></tfoot></table></div>` : '';
  const used = u.runs.filter(r => r.usage);
  const runRows = used.slice(0, 10).map(r => `<li><a class="row" href="${href('/activity/run/' + encodeURIComponent(r.id))}">${ac.glyph(r.state === 'waiting_for_person' ? 'you' : r.state)}<span class="row__main"><span class="row__title small">${esc(L(r.label))}</span>
      <span class="row__meta ac-meta"><span>${esc(tok(all(r.usage)))}</span><span>${esc(model.assistantName(r.assistant) || 'EAOS')}</span>${r.verb === 'fix' ? `<span>${esc(t('ac.as.closed', { n: num(r.cards) }))}</span>` : ''}<span>${esc(fmtWhen(r.created))}</span></span></span>
      <span class="num ac-urow__cost">${r.usage.cost_usd != null ? ac.money(r.usage.cost_usd) : ''}</span></a></li>`).join('');
  const fixes = u.runs.filter(r => r.verb === 'fix' && r.usage && r.usage.cost_usd != null);
  const closed = fixes.reduce((a, r) => a + (r.cards || 0), 0), fixCost = fixes.reduce((a, r) => a + r.usage.cost_usd, 0);
  const T = u.check && u.check.total;
  const readAgain = T && all(T) ? Math.round((T.cache_read || 0) / ((T.input || 0) + (T.cache_write || 0) + (T.cache_read || 0) || 1) * 100) : null;
  const think = T && (T.output || T.thinking) ? Math.round((T.thinking || 0) / ((T.output || 0) + (T.thinking || 0)) * 100) : null;
  const chat = u.chat;
  const k = asking('assistant_check');
  return `<div class="page">
    ${projBack()}
    <h1 class="lede">${esc(lede)}</h1>
    <p class="guide">${t('ac.as.guide')}</p>
    <div class="actions"><button class="btn btn--primary" data-act="ac-asst-again" data-fk="asst-again" ${k ? 'disabled' : ''}>${k ? t('ac.as.asking') : t('ac.asst.again')}</button>
      ${checkedAt ? `<p class="actions__note">${esc(t('ac.as.checked', { when: fmtWhen(checkedAt.checked_at) }))}</p>` : ''}</div>
    <section class="section" aria-labelledby="as-h"><div class="section-head"><h2 id="as-h">${t('ac.as.here')}</h2></div>
      <ul class="panel rows">${rows.map(a => `<li class="row ac-arow">${ac.glyph(a.ready ? 'ok' : a.installed ? 'notin' : 'unavailable')}<span class="row__main"><span class="row__title">${esc(a.name)} ${a.ready ? `<span class="tag tag--ok">${icon('check')}${t('pv.ready')}</span>` : `<span class="tag tag--caution">${t(a.installed ? 'pv.notsigned' : 'pv.notinstalled')}</span>`}</span>
          <span class="row__meta" style="display:block">${esc([a.version, a.model || (a.ready ? t('ac.as.model.default') : ''), a.seconds != null && a.ready ? t('ac.as.answered', { s: num(a.seconds) }) : ''].filter(Boolean).join(' · '))}${a.reason ? ` ${esc(L(a.reason))}` : ''}</span>
          <span style="display:block;margin-top:8px"><button class="btn btn--secondary btn--sm" data-act="ac-asst-one" data-id="${esc(a.id)}" ${k ? 'disabled' : ''}>${esc(t('ac.as.one.v', { name: a.name }))}</button></span></span></li>`).join('')}</ul></section>
    <section class="section" aria-labelledby="lc-h2"><div class="section-head"><h2 id="lc-h2">${t('ac.as.last')}</h2>${T ? `<span class="small muted num">${esc(t('ac.as.last.sum', { cost: T.cost_usd != null ? ac.money(T.cost_usd) : t('nm'), tokens: tok(all(T)) }))}</span>` : ''}</div>
      ${stages.length ? `<p class="small ink-2" style="margin-bottom:12px">${t('ac.as.bill')}</p><ul class="panel rows only-phone">${stageRows}</ul>${table}` : `<div class="panel panel__pad"><p class="small ink-2">${t('ac.as.last.none.v')}</p></div>`}</section>
    <section class="section" aria-labelledby="ru-h"><div class="section-head"><h2 id="ru-h">${t('ac.as.runs')}</h2></div>
      ${runRows ? `<ul class="panel rows">${runRows}</ul>` : `<p class="small muted">${t('ac.as.runs.none')}</p>`}<p class="small muted" style="margin-top:8px">${t('ac.as.runs.note')}</p></section>
    <section class="section" aria-labelledby="im-h"><div class="section-head"><h2 id="im-h">${t('ac.as.improve')}</h2></div>
      <div class="panel panel__pad"><dl class="facts">
        <dt>${t('ac.as.i.perfix')}</dt><dd>${closed ? ac.money(fixCost / closed) : ac.nmTag()} <span class="small muted">${t('ac.as.i.perfix.v')}</span></dd>
        <dt>${t('ac.as.i.check')}</dt><dd>${T && T.cost_usd != null ? ac.money(T.cost_usd) : ac.nmTag()}</dd>
        <dt>${t('ac.as.i.again')}</dt><dd>${readAgain != null ? num(readAgain) + '%' : ac.nmTag()} <span class="small muted">${t('ac.as.i.again.v')}</span></dd>
        <dt>${t('ac.as.i.think')}</dt><dd>${think != null ? num(think) + '%' : ac.nmTag()} <span class="small muted">${t('ac.as.i.think.v')}</span></dd>
        <dt>${t('ac.as.i.chat')}</dt><dd>${chat && chat.cost_usd != null ? ac.money(chat.cost_usd) : ac.nmTag()}</dd></dl></div></section>
    <section class="section panel">${ac.fold('chat', t('ac.as.chat'), esc(t('ac.as.chat.sum', { n: num((chat && chat.turns) || 0), cost: chat && chat.cost_usd != null ? ac.money(chat.cost_usd) : t('nm') })),
      `<p class="small muted">${t('ac.as.chat.note')}</p><a class="link" href="${href('/ask')}">${t('ac.ask.title')}</a>`)}</section>
  </div>`;
}
screen({ id: 'S-49', path: '/project/assistants', place: 'project', title: () => t('proj.assistants'), render: asstPage });
async function askAgain(inputs) {
  answer('assistant_check', Object.assign({ fresh: true }, inputs), true);
  refresh();
  await store.refreshAssistants();
  readUsage(true);
}
act('ac-asst-again', el => { if (!el.disabled) { askAgain({}); toast(t('ac.as.asked')); } });
act('ac-asst-one', el => { if (!el.disabled) { askAgain({ assistant: el.dataset.id }); toast(t('ac.as.asked')); } });

/* =================================================================================================================
   S-50 TOOLS
   ================================================================================================================= */
const toolState = s => ({ ok: 'ready', running: 'downloading', waiting: 'waiting', failed: 'failed', skipped: 'notneeded', unavailable: 'notneeded' }[s.state] || s.state);
function toolsPage(ctx) {
  if (ctx.offline) return offlinePage('ac.tl.offline', 'ac.tl.offline.guide');
  const f = flows().tools;
  if (!live.progress) return busyPage('ac.tl.loading');
  const list = (f && f.stages) || [];
  const needed = list.filter(s => s.requested !== false);
  const ready = needed.filter(s => s.state === 'ok').length;
  const failed = needed.filter(s => s.state === 'failed'), coming = needed.filter(s => ['running', 'waiting'].includes(s.state));
  const installing = f && f.state === 'running';
  const lede = !list.length ? t('ac.tl.lede.none') : installing ? t('ac.tl.lede.installing', { n: num(ready), t: num(needed.length) })
    : failed.length ? t('ac.tl.lede.failed.v', { n: num(ready), t: num(needed.length), names: failed.map(s => s.name).join(t('list.sep')) }) : t('ac.tl.lede', { n: num(ready), all: num(needed.length) });
  const row = s => {
    const st = toolState(s);
    const step = (s.steps || []).find(x => x.total);
    const share = step ? step.done / step.total : null;
    const meta = st === 'failed' ? `<span class="ac-c-danger">${esc(s.reason || t('ac.tl.failed.v'))}</span>` : st === 'downloading' ? `${t('ac.tl.downloading')}${share != null ? ` <span class="num">${num(Math.round(share * 100))}%</span>` : ''}` : st === 'waiting' ? t('ac.tl.waiting') : esc(s.reason || '');
    return `<li class="row ac-trow">${ac.glyph(st)}<span class="row__main"><span class="row__title small"><bdi class="mono">${esc(s.name)}</bdi>${s.description && st === 'ready' ? ` <span class="muted num small">${esc(String(s.description).slice(0, 14))}</span>` : ''}</span>
      ${meta ? `<span class="row__meta" style="display:block">${meta}</span>` : ''}${st === 'downloading' && share != null ? `<span class="ac-bar ac-bar--thin" aria-hidden="true"><i style="transform:scaleX(${share})"></i></span>` : ''}</span><span class="small muted">${t('ac.tl.st.' + (['ready', 'downloading', 'waiting', 'failed', 'notneeded'].includes(st) ? st : 'waiting'))}</span></li>`;
  };
  const attention = failed.concat(coming);
  return `<div class="page">
    ${projBack()}
    <h1 class="lede">${esc(lede)}</h1>
    <p class="guide">${t(failed.length ? 'ac.tl.guide.failed.v' : installing ? 'ac.tl.guide.installing.v' : 'ac.tl.guide')}</p>
    <div class="actions">${failed.length ? `<button class="btn btn--primary" data-act="sheet" data-sheet="action:tools_check" data-fk="reinstall">${icon('retry')}${t('ac.tl.again')}</button><a class="btn btn--secondary" href="${href('/activity', { sheet: 'check' })}">${t('ac.tl.without')}</a>`
      : `<a class="btn btn--primary" href="${href('/activity', { sheet: 'check' })}">${t('st.empty.act')}</a><button class="btn btn--quiet" data-act="sheet" data-sheet="action:tools_check">${t('ac.tl.again')}</button>`}
      <p class="actions__note">${t(failed.length ? 'ac.tl.without.note' : 'ac.tl.auto')}</p></div>
    <section class="section" aria-labelledby="tw-h"><div class="section-head"><h2 id="tw-h">${t('ac.tl.waits')}</h2></div>
      <div class="panel panel__pad"><dl class="facts">
        <dt>${t('ac.tl.for_check')}</dt><dd>${esc(t('ac.tl.of', { n: num(ready), t: num(needed.length) }))}&ensp;${!failed.length && !coming.length ? ac.mark('ok', t('ac.tl.can_start')) : ac.mark(failed.length ? 'failed' : 'running', t(failed.length ? 'ac.tl.cannot' : 'ac.tl.coming'))}</dd>
        ${installing && f.estimate && f.estimate.low != null ? `<dt>${t('ac.tl.left')}</dt><dd>${esc(t('live.left', { lo: num(Math.max(1, Math.round(f.estimate.low / 60))), hi: num(Math.max(1, Math.round(f.estimate.high / 60))) }))}</dd>` : ''}
        <dt>${t('ac.tl.eaos')}</dt><dd>${code('EAOS ' + model.project().eaos_version)}</dd>
        ${f && f.ended_at ? `<dt>${t('ac.tl.last')}</dt><dd>${esc(fmtWhen(f.ended_at))}</dd>` : ''}</dl></div></section>
    ${attention.length ? `<section class="section" aria-labelledby="ta-h"><div class="section-head"><h2 id="ta-h">${t('ac.tl.attention')}</h2></div><ul class="panel rows">${attention.map(row).join('')}</ul></section>` : ''}
    <div class="section panel">
      ${ac.fold('check', t('ac.tl.g.all'), esc(t('ac.tl.of', { n: num(ready), t: num(needed.length) })) + ' ' + t('ac.tl.ready_word'), list.length ? `<ul class="rows" style="margin:0 -16px">${needed.map(row).join('')}</ul>` : `<p class="small muted">${t('ac.tl.lede.none')}</p>`)}
      ${list.length > needed.length ? ac.fold('other', t('ac.tl.g.other'), esc(t('ac.tl.g.other.sum', { n: num(list.length - needed.length) })), `<ul class="rows" style="margin:0 -16px">${list.filter(s => s.requested === false).map(row).join('')}</ul>`) : ''}
    </div>
  </div>`;
}
screen({ id: 'S-50', path: '/project/tools', place: 'project', title: () => t('proj.tools'), render: toolsPage });

/* =================================================================================================================
   S-51 SETTINGS
   ================================================================================================================= */
let session = null;
function settingsPage(ctx) {
  if (client && !session) client.session().then(s => { session = s; refresh(); }, () => { session = {}; });
  const o = ctx.offline ? null : checkOffer();
  const st = ctx.offline ? null : answer('status');
  const device = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  const zones = [...new Set([device, 'UTC', prefs.tz, 'Asia/Riyadh', 'Asia/Dubai', 'Europe/London', 'America/New_York'])];
  const tzOpts = zones.map(z => `<label class="opt"><input type="radio" name="tz" value="${esc(z)}" data-change="ac-tz" data-fk="tz-${esc(z)}" ${prefs.tz === z ? 'checked' : ''}><span class="opt__dot" aria-hidden="true"></span>
    <span class="opt__text">${z === device ? t('ac.set.tz.device') : z === 'UTC' ? t('ac.set.tz.utc') : t('ac.set.tz.other')} <bdi class="mono muted">${esc(z)}</bdi></span></label>`).join('');
  const sample = model.project().checked_at || new Date().toISOString();
  const answered = (st && st.handover && st.handover.person_already_answered) || [];
  const consent = answered.some(a => a.question === 'run_and_fix' && a.answer === true);
  const useAi = answered.find(a => a.question === 'use_assistant');
  const protectedList = ctx.offline ? [] : protectedNames();
  const ln = l => t(l === 'ar' ? 'lang.ar' : 'lang.en');
  const kept = [
    [t('ac.set.k.mode'), o ? t(o.mode === 'speed' ? 'ac.set.k.mode.speed' : 'ac.set.k.mode.normal') : '…', '/activity', { sheet: 'check' }],
    [t('ac.set.k.ai'), useAi ? t(useAi.answer ? 'ac.set.k.ai.on' : 'ac.set.k.ai.off') : '…', '/activity', { sheet: 'check' }],
    [t('ac.chk.si'), o ? (o.sign_in ? t('ac.chk.si.' + (o.sign_in === 'test_user' ? 'test' : o.sign_in)) : t('ac.app.si.notyet')) : '…', '/project/app'],
    [t('ac.app.consent'), st ? t(consent ? 'ac.set.k.consent.given' : 'ac.set.k.consent.no') : '…', '/project/app'],
    [t('ac.set.k.protected'), protectedList ? (protectedList.length ? protectedList.map(code).join(' ') : t('ac.set.k.protected.none')) : '…', '/project/branches'],
    [t('lang.label'), ln(prefs.lang) + (session && session.lang && session.lang !== prefs.lang ? ` (${t('ac.set.k.report_lang', { lang: ln(session.lang) })})` : ''), null],
  ];
  const keys = [['Ctrl/Cmd K', 'ac.set.kb.k'], ['Ctrl/Cmd I', 'ac.set.kb.i'], ['Esc', 'ac.set.kb.esc'], ['↑ ↓ Enter', 'ac.set.kb.arrows'], ['Shift + click', 'ac.set.kb.shift'], ['Tab', 'ac.set.kb.tab']];
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const remote = location.hostname !== '127.0.0.1' && location.hostname !== 'localhost' && /^https?:$/.test(location.protocol);
  const made = model.project().eaos_version;
  return `<div class="page">
    ${projBack()}
    <h1 class="lede">${t('ac.set.lede')}</h1>
    <p class="guide">${t('ac.set.guide')}</p>
    <section class="section" aria-labelledby="tz-h"><div class="section-head"><h2 id="tz-h">${t('ac.set.tz')}</h2></div>
      <p class="small ink-2" style="margin-bottom:12px">${esc(t('ac.set.tz.example', { rel: fmtWhen(sample), exact: exactTime(sample) }))}</p>
      <div class="opts" role="radiogroup" aria-labelledby="tz-h">${tzOpts}</div></section>
    <section class="section" aria-labelledby="lg-h"><div class="section-head"><h2 id="lg-h">${t('ac.set.display')}</h2></div>
      <div class="panel panel__pad toggles">
        <div class="toggle-row"><span>${t('lang.label')}</span><div class="seg" role="group" aria-label="${esc(t('lang.label'))}" style="min-width:180px">
          <button type="button" data-act="lang" data-lang="ar" data-fk="s-lang-ar" aria-pressed="${prefs.lang === 'ar'}" lang="ar">${t('lang.ar')}</button><button type="button" data-act="lang" data-lang="en" data-fk="s-lang-en" aria-pressed="${prefs.lang === 'en'}" lang="en">${t('lang.en')}</button></div></div>
        <p class="muted small">${t('lang.note')}</p>
        <div class="toggle-row"><span>${t('theme.label')}</span><div class="seg" role="group" aria-label="${esc(t('theme.label'))}" style="min-width:180px">
          <button type="button" data-act="theme-set" data-theme="light" data-fk="s-th-l" aria-pressed="${prefs.theme === 'light'}">${icon('sun', 'icon--sm')}${t('theme.light')}</button><button type="button" data-act="theme-set" data-theme="dark" data-fk="s-th-d" aria-pressed="${prefs.theme === 'dark'}">${icon('moon', 'icon--sm')}${t('theme.dark')}</button></div></div>
      </div></section>
    ${ctx.offline ? '' : `<section class="section" aria-labelledby="kp-h"><div class="section-head"><h2 id="kp-h">${t('ac.set.kept')}</h2></div>
      <p class="small ink-2" style="margin-bottom:12px">${t('ac.set.kept.sub')}</p>
      <ul class="panel rows">${kept.map(([label, v, path, q]) => `<li>${path ? `<a class="row" href="${href(path, q)}">` : '<div class="row">'}<span class="row__main"><span class="row__title small">${label}</span><span class="row__meta" style="display:block">${v}</span></span>${path ? `<span class="small link">${t('ac.set.change')}</span>${icon('chev', 'icon--sm icon--dir muted')}</a>` : '</div>'}</li>`).join('')}</ul></section>`}
    <section class="section" aria-labelledby="vr-h"><div class="section-head"><h2 id="vr-h">${t('ac.set.version')}</h2></div>
      <div class="panel panel__pad"><dl class="facts"><dt>${t('ac.set.v.eaos')}</dt><dd>${code('EAOS ' + (made || ''))}</dd>
        <dt>${t('ac.set.v.contract')}</dt><dd class="num">${esc(num(session && session.contract != null ? session.contract : contract.ACTIONS.length && 1))}</dd>
        <dt>${t('ac.set.v.same')}</dt><dd>${st && st.report ? (st.report.version === made ? ac.mark('ok', t('ac.set.v.same.v')) : ac.mark('partial', esc(t('ac.set.v.differs', { v: st.report.version })))) : '…'}</dd></dl></div></section>
    <section class="section" aria-labelledby="kb-h"><div class="section-head"><h2 id="kb-h">${t('ac.set.kb')}</h2></div>
      <div class="panel panel__pad"><dl class="facts ac-keys">${keys.map(([k2, w]) => `<dt><kbd class="ac-kbd">${esc(k2)}</kbd></dt><dd>${t(w)}</dd>`).join('')}</dl>
        <p class="small ink-2" style="margin-top:12px">${t('ac.set.kb.more')} ${t(reduce ? 'ac.set.kb.reduce.on' : 'ac.set.kb.reduce.off')}</p></div></section>
    <section class="section" aria-labelledby="ax-h"><div class="section-head"><h2 id="ax-h">${t('ac.set.access')}</h2></div>
      <div class="panel panel__pad ac-stack">
        <div class="ac-note">${ac.glyph('ok')}<span class="small">${ctx.offline ? t('ac.set.access.copy') : t(remote ? 'ac.set.access.remote' : 'ac.set.access.local', { addr: code(location.origin + '/') })}</span></div>
        <p class="small ink-2">${t('ac.set.access.rules')}</p>
        <p class="small ink-2">${t('ac.set.access.idle')}</p></div></section>
  </div>`;
}
screen({ id: 'S-51', path: '/project/settings', place: 'project', title: () => t('proj.settings'), render: settingsPage });
act('ac-tz', el => { setTimeZone(el.value === (Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC') ? null : el.value); toast(t('ac.set.tz.done', { z: el.value })); });
