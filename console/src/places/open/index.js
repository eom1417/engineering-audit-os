// Opening states and old links (builder A): S-53. PJS-02..04, OFF-04, OFF-06, PRJ-12, LNK-01, ACT-05. ?kind=
// folder (the projects on this computer, GET /api/projects), switch (that project's own Studio started and opened,
// POST /api/projects/open), export (the read-only copy), nokey, readonly, oldlink (?what=), partial (the parts of the
// report the check could not write), contract (data of another contract) and connection (the live feed's state).
import { said, t, tn, num, esc, icon, code, href, fmtWhen, fmtTime, screen, refresh, data, live, client, model, rowWords, facts, pageHead } from 'eaos';

const KINDS = ['folder', 'switch', 'export', 'nokey', 'readonly', 'oldlink', 'partial', 'contract', 'connection'];
let projects = null, switching = null;

function folder() {
  if (client && !projects) client.projects().then(list => { projects = list; refresh(); }, () => { projects = []; refresh(); });
  if (!client) return pageHead(t('ac.op.folder.offline'), t('ac.op.folder.guide'));
  if (!projects) return `<h1 class="lede" aria-busy="true">${t('st.loading')}</h1>`;
  return `${pageHead(esc(tn('ac.op.folder.n', projects.length)), t('ac.op.folder.guide'))}
    <ul class="panel rows section">${projects.map(p => `<li><a class="row" href="${href(p.current ? '/status' : '/open', p.current ? {} : { kind: 'switch', p: p.workspace })}"><span class="project-btn__mark" aria-hidden="true">${esc((p.name || '?')[0].toUpperCase())}</span>
      ${rowWords(code(p.name) + (p.current ? ` <span class="tag tag--state">${t('proj.current')}</span>` : ''), (p.score != null ? esc(t('proj.score', { score: num(Math.round(p.score * 100)) })) + ', ' : '') + esc(p.checked ? t('ac.op.checked', { when: fmtWhen(p.checked) }) : t('ac.op.never')))}${icon('chev', 'icon--dir muted')}</a></li>`).join('')}</ul>
    <p class="small muted mt-3">${t('ac.op.folder.later')}</p>`;
}

function switchTo(q) {
  const p = q.p || '';
  if (client && p && (!switching || switching.p !== p)) {
    switching = { p, late: false };
    client.openProject(p).then(r => { location.assign(r.studio); }, e => { switching.late = true; switching.why = said(e); refresh(); });
  }
  const late = q.late === '1' || (switching && switching.late) || !client;
  return pageHead(esc(t(late ? 'ac.op.switch.late' : 'ac.op.switch', { p })), late && switching && switching.why ? esc(switching.why) : t(late ? 'ac.op.switch.late.guide' : 'ac.op.switch.guide'), `${late ? `<button class="btn btn--primary" data-act="go" data-href="${href('/open', { kind: 'switch', p, t: Date.now() })}">${icon('retry')}${t('ac.op.try')}</button>` : `<span class="state ac-state"><span class="dot dot--live" aria-hidden="true"></span>${t('ac.op.starting')}</span>`}
      <a class="btn btn--quiet" href="${href('/status')}">${t('ac.op.stay')}</a>`);
}

function partial() {
  const m = data.manifest();
  const missing = m ? m.sections.filter(s => data.isMissing(s.name)).map(s => s.name) : [];
  const unread = m ? m.sections.filter(s => s.missing || s.error).map(s => s.name) : [];
  const names = [...new Set(missing.concat(unread))];
  if (!names.length) return pageHead(t('ac.op.partial.none'), t('ac.op.partial.none.guide'), `<a class="btn btn--primary" href="${href('/status')}">${t('ac.op.partial.see')}</a>`);
  return `${pageHead(esc(tn('ac.op.partial.n', names.length)), t('ac.op.partial.guide'))}
    <ul class="panel rows section">${names.map(n => `<li class="row">${rowWords(code(n), t('ac.op.partial.row'))}</li>`).join('')}</ul>
    <div class="actions"><a class="btn btn--primary" href="${href('/activity', { sheet: 'check' })}">${t('stale.act')}</a><a class="btn btn--quiet" href="${href('/status')}">${t('ac.op.partial.see')}</a></div>`;
}

const STATES = ['reconnecting', 'quiet', 'refused', 'reset'];
// the words for the live feed's state now
const feedKey = now => (live.feed === 'open' || live.feed === 'connected' ? 'ac.op.c.now.ok' : now ? 'ac.op.c.short.' + now : client ? 'ac.op.c.now.ok' : 'live.copy');
function connection(q) {
  const now = live.feed === 'refused' ? 'refused' : live.feed === 'reconnecting' ? 'reconnecting' : null;
  const state = STATES.includes(q.c) ? q.c : now || 'reconnecting';
  const at = fmtTime(new Date(live.heard || Date.now()).toISOString());
  return `<div class="banner ${state === 'refused' ? 'banner--caution' : ''} ac-banner-inline" role="status">${icon(state === 'refused' ? 'warn' : 'offline')}<span>${esc(t('ac.op.c.' + state, { time: at }))}</span></div>
    ${pageHead(t('ac.op.c.lede.' + state), t('ac.op.c.guide.' + state))}
    <p class="small ink-2">${esc(t('ac.op.c.now', { state: t(feedKey(now)) }))}</p>
    <div class="actions">${state === 'refused' ? `<button class="btn btn--primary" data-act="copy" data-text="eaos studio">${icon('copy')}${t('ac.op.c.reopen')}</button>` : state === 'reset' ? `<a class="btn btn--primary" href="${href('/status')}">${t('ac.op.c.reload')}</a>` : ''}</div>
    <nav class="seg section" aria-label="${esc(t('ac.op.c.which'))}">${STATES.map(s => `<a href="${href('/open', { kind: 'connection', c: s })}" aria-current="${s === state}">${t('ac.op.c.short.' + s)}</a>`).join('')}</nav>`;
}

// the read-only copy
function exported() {
  return pageHead(esc(t('ac.op.export.v', { when: fmtWhen(model.project().checked_at) })), t('ac.op.export.guide'), `<a class="btn btn--primary" href="${href('/status', client ? { state: 'offline' } : {})}">${t('ac.op.readonly.see')}</a><button class="btn btn--quiet" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button>`);
}
// opened without its key
function nokey() {
  return `${pageHead(t('ac.op.nokey'), t('ac.op.nokey.guide'))}
      <div class="panel panel__pad section ac-stack"><div class="code pad-3-4">eaos studio</div>
        <div><button class="btn btn--primary" data-act="copy" data-text="eaos studio">${icon('copy')}${t('copy')}</button></div><p class="small muted">${t('ac.op.nokey.why')}</p></div>`;
}
// read-only
function readonly() {
  return `<div class="banner ac-banner-inline" role="note">${icon('lock')}<span>${t('ac.op.readonly.banner')}</span></div>
      ${pageHead(t('ac.op.readonly'), t('ac.op.readonly.guide'), `<a class="btn btn--primary" href="${href('/status')}">${t('ac.op.readonly.see')}</a><button class="btn btn--quiet" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button>`)}`;
}
// an old link to something no longer there
function oldlink(q) {
  const what = q.what || '';
  return `${pageHead(esc(t('ac.op.old', { what })), t('ac.op.old.guide'))}
      <div class="panel panel__pad section">${facts([[t('ac.op.old.missing'), code(what)], [t('ac.op.old.why'), t('ac.op.old.why.v')]])}</div>
      <div class="actions"><a class="btn btn--primary" href="${href('/problems')}">${t('ac.op.old.back')}</a></div>`;
}
// data of another contract
function contract() {
  const seen = data.contractSeen();
  return pageHead(t(seen != null ? 'ac.op.contract' : 'ac.op.contract.same'), esc(t('ac.op.contract.guide.v', { data: seen != null ? num(seen) : num(1), this: num(1) })), `<button class="btn btn--primary" data-act="copy" data-text="eaos report --rebuild">${icon('copy')}${t('ac.op.contract.rebuild')}</button>`);
}
const BODIES = new Map(Object.entries({ folder: () => folder(), switch: switchTo, export: exported, nokey, readonly, oldlink, partial: () => partial(), contract, connection }));

function openPage(ctx) {
  const q = ctx.query;
  const kind = KINDS.includes(q.kind) ? q.kind : 'folder';
  const body = BODIES.get(kind)(q);
  return `<div class="page">${body}
    <p class="list-foot">${t('ac.op.others')} ${KINDS.map(k => k === kind ? `<b>${t('ac.op.k.' + k)}</b>` : `<a href="${href('/open', { kind: k })}">${t('ac.op.k.' + k)}</a>`).join(t('list.sep'))}</p></div>`;
}
screen({ id: 'S-53', path: '/open', place: 'open', title: () => t('ac.op.title'), render: openPage });
