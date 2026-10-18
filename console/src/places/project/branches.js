// S-46 Branches and S-47 one branch (builder A): PRJ-04, PRJ-05, BRN-01..12. Every branch as git tells it now
// (GET /api/branches: roles, ownership, protection, ahead and behind the base, worktrees, recovery points), one
// branch's commits, files, diff, recorded checks, runs and every command with why it is blocked (GET
// /api/branches/detail); the owner-only confirm sheets, each opened on its own free preview whose confirm token the
// act spends: choose the branch EAOS checks, merge, delete here or on the remote, protect, unprotect, clean up the
// merged branches, restore a deleted one, propose a conflict's resolution, compare with another base, fetch.
import {
  t, tn, L, num, esc, rich, icon, code, href, fmtWhen, expiresAt, screen, sheet, act, refresh, rerenderSheet, local, toast, closeSheetThen, openSheet,
  parseHash, setQuery, offline, freshness, chk, live, store, client, ActionError, normalize, ac,
} from 'eaos';

const enc = encodeURIComponent;
const said = e => (e instanceof ActionError ? e.message : String(e));
const reasonsOf = list => (list || []).map(r => L(r)).join(' ');
export const projBack = () => `<a class="back" href="${href('/status', { sheet: 'project' })}">${icon('back', 'icon--dir')}${t('proj.title')}</a>`;

/* ---------- what git says, read once per base and again after any change ---------- */
const inv = { base: null, data: null, reading: false, problem: null, details: {} };
function inventory(base) {
  if (!client) return null;
  if (inv.data && inv.base === (base || null)) return inv.data;
  if (!inv.reading) {
    inv.reading = true;
    client.branches.inventory(base || undefined).then(d => { Object.assign(inv, { data: d, base: base || null, reading: false, problem: null }); refresh(); },
      e => { Object.assign(inv, { reading: false, problem: e }); refresh(); });
  }
  return inv.data && inv.base === (base || null) ? inv.data : null;
}
const keyOf = (name, kind, remote) => `${kind || 'local'}:${remote || ''}:${name}`;
function detail(name, kind, remote) {
  const k = keyOf(name, kind, remote), d = inv.details[k];
  if (d) return d.data || null;
  inv.details[k] = { reading: true };
  client.branches.detail(name, kind || 'local', remote || undefined, inv.base || undefined)
    .then(data => { inv.details[k] = { data }; refresh(); rerenderSheet(); }, e => { inv.details[k] = { problem: said(e) }; refresh(); });
  return null;
}
/* The free merge preview a mergeable branch's page reads once per tip, so a conflict shows (with its proposed
   resolution, BRN-07) before the person asks to merge; null while git is asked or when it could not tell. */
const tried = {};
function mergeTry(b) {
  const k = b.name + '@' + b.tip;
  if (k in tried) return tried[k];
  tried[k] = null;
  client.branches.previewMerge(b.name).then(p => { tried[k] = p; refresh(); }, () => {});
  return null;
}
const problemOf = (name, kind, remote) => (inv.details[keyOf(name, kind, remote)] || {}).problem;
/** The local branches protected now (null while git is asked). */
export function protectedNames() { const d = inventory(inv.base); return d ? d.branches.filter(b => b.kind === 'local' && b.protected).map(b => b.name) : null; }
/** After a change to the branches: everything read again, the runs too. */
export function changed() { inv.data = null; inv.details = {}; store.refresh(); store.refreshFreshness(); refresh(); }

const rowOf = (d, name, kind, remote) => (d ? d.branches.find(b => b.name === name && b.kind === (kind || 'local') && (!remote || b.remote === remote)) : null);
const brUrl = b => href('/project/branches/' + enc(b.name), b.kind === 'remote' ? { kind: 'remote', remote: b.remote } : {});
const liveName = b => (b.kind === 'remote' ? `${b.remote}/${b.name}` : b.name);
const waitingRun = name => store.awaiting().find(r => r.result && r.result.branch === name) || null;
function aheadBehind(b) {
  const c = b.compare;
  if (!c) return '';
  if (b.name === c.base && b.kind === 'local') return esc(t('ac.br.is_base'));
  if (c.merged && !c.ahead) return t('ac.br.merged_into', { b: code(c.base) });
  if (!c.ahead && !c.behind) return t('ac.br.same_as', { b: code(c.base) });
  return esc(t('ac.br.ab', { a: num(c.ahead), b: num(c.behind) })) + ' ' + code(c.base);
}
function whoLine(b) {
  const o = b.ownership || {};
  if (o.owner === 'eaos' || o.owner === 'shared') {
    const waits = waitingRun(b.name);
    const base = o.kind === 'wave' ? t(waits ? 'ac.br.who.eaos.waits' : 'ac.br.who.eaos', { n: num(o.wave) }) : t('ac.br.who.eaos.run');
    return esc(o.owner === 'shared' ? base + ' ' + t('ac.br.who.shared', { n: num(o.foreign_commits || 0) }) : base);
  }
  return esc(t('ac.br.who.unknown'));
}
function roleTags(b) {
  const r = b.roles || [], tags = [];
  if (r.includes('checkout')) tags.push(`<span class="tag tag--state">${icon('folder')}${t('ac.br.r.folder')}</span>`);
  if (r.includes('analysis')) tags.push(`<span class="tag tag--live">${t('ac.br.r.analysed')}</span>`);
  if (r.includes('report')) tags.push(`<span class="tag tag--state">${t('ac.br.r.report')}</span>`);
  if (r.includes('default')) tags.push(`<span class="tag tag--state">${t('ac.br.r.default')}</span>`);
  if (b.protected) tags.push(`<span class="tag tag--owner">${icon('lock')}${t('ac.br.r.protected')}</span>`);
  if (waitingRun(b.name)) tags.push(`<span class="tag tag--you">${t('who.you')}</span>`);
  if (b.kind === 'remote') tags.push(`<span class="tag tag--eaos">${esc(t('ac.br.r.remote', { r: b.remote }))}</span>`);
  return tags.join('');
}
function owner() { return `<div class="owner-band">${icon('seal')}<span><b>${t('owner.only')}</b>${t('cf.band')}</span></div>`; }
function ack(kind, text, on) { return `<label class="ack">${chk(`data-change="ac-ack" data-kind="${kind}" data-fk="ack-${kind}"`, !!on, text)}<span class="ack__text">${text}</span></label>`; }
act('ac-ack', el => { local()['ack_' + el.dataset.kind] = el.checked; rerenderSheet(); });
const valid = c => (c ? `<p class="sheet__fine">${esc(t('cf.valid', { time: expiresAt(c.expires) }))}</p>` : '');
const alert = text => (text ? `<p class="small" role="alert" style="color:var(--danger)">${icon('warn', 'icon--sm')} ${esc(text)}</p>` : '');
const loadingRows = () => `<ul class="panel rows section">${[1, 2, 3].map(() => `<li class="row"><span style="flex:1;display:grid;gap:8px"><span class="skel-line" style="width:45%"></span><span class="skel-line" style="width:70%"></span></span></li>`).join('')}</ul>`;

/* =================================================================================================================
   S-46 BRANCHES
   ================================================================================================================= */
function branchRow(b) {
  return `<li><a class="row ac-brow" href="${brUrl(b)}">${icon('branch', 'muted')}
    <span class="row__main"><span class="ac-brow__top"><bdi class="mono ac-brow__name">${esc(liveName(b))}</bdi>${roleTags(b)}</span>
      <span class="row__meta ac-meta"><span>${aheadBehind(b)}</span><span>${whoLine(b)}</span>${b.last_commit ? `<span>${esc(t('ac.br.last', { when: fmtWhen(b.last_commit) }))}</span>` : ''}</span></span>${icon('chev', 'icon--dir muted')}</a></li>`;
}
function branchesPage(ctx) {
  if (ctx.offline) return `<div class="page">${projBack()}<h1 class="lede">${t('ac.br.offline.lede')}</h1><p class="guide">${t('ac.br.offline')}</p><div class="actions"><button class="btn btn--primary" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button></div></div>`;
  const q = ctx.query;
  const d = inventory(q.base);
  if (inv.problem && !d) {
    const nogit = /not a git repository/.test(said(inv.problem));
    return `<div class="page">${projBack()}<h1 class="lede">${t(nogit ? 'ac.br.nogit' : 'ac.br.failed')}</h1><p class="guide">${nogit ? t('ac.br.nogit.guide') : esc(said(inv.problem))}</p>
      <div class="actions">${nogit ? `<button class="btn btn--secondary" data-act="copy" data-text="git init">${icon('copy')}${t('ac.br.nogit.copy')}</button>` : `<button class="btn btn--secondary" data-act="ac-br-reload">${icon('retry')}${t('ac.op.try')}</button>`}</div></div>`;
  }
  if (!d) return `<div class="page" aria-busy="true">${projBack()}<h1 class="lede">${t('ac.br.loading')}</h1>${loadingRows()}</div>`;
  const c = d.context || {};
  const folder = (c.checkout && c.checkout.branch) || t('ac.br.detached'), analysed = (c.analysis && c.analysis.branch) || folder;
  const differ = folder !== analysed;
  const dirty = c.dirty ? (c.dirty.tracked || 0) + (c.dirty.untracked || 0) : 0;
  const f = freshness();
  const lede = differ ? t('ac.br.lede.differ', { folder: code(folder), analysed: code(analysed) }) : t('ac.br.lede', { b: code(folder) });
  const four = `<div class="panel panel__pad ac-four"><dl class="facts">
      <dt>${t('ac.br.four.folder')}</dt><dd>${code(folder)} <span class="small muted">${dirty ? esc(t('ac.br.four.unsaved.v', { n: num(dirty) })) : t('ac.br.four.clean')}</span></dd>
      <dt>${t('ac.br.four.analysed')}</dt><dd>${code(analysed)}${c.analysis && c.analysis.selected ? ` <span class="small muted">${t('ac.br.four.chosen')}</span>` : ''}</dd>
      <dt>${t('ac.br.four.report')}</dt><dd>${c.report ? `${code(c.report.branch || '')} ${code(String(c.report.commit || '').slice(0, 7))} <span class="small muted">${esc(fmtWhen(c.report.at))}</span>` : esc(t('ac.br.four.none'))}</dd>
      <dt>${t('ac.br.four.scan')}</dt><dd>${c.scan ? `${code(c.scan.branch || '')} ${code(String(c.scan.commit || '').slice(0, 7))}` : esc(t('ac.br.four.none'))}</dd></dl>
      ${differ ? `<p class="ac-note ac-note--caution small" style="margin-top:12px">${icon('warn', 'icon--sm ac-c-caution')}<span>${t('ac.br.four.differ.todo', { folder: code(folder), analysed: code(analysed) })}</span></p>`
        : `<p class="small ink-2" style="margin-top:12px">${t(f.state === 'fresh' ? 'ac.br.four.agree' : 'ac.br.four.agree.stale')}</p>`}</div>`;
  const yours = q.show === 'yours';
  const all = d.branches;
  const list = all.filter(b => (!yours || b.work || (b.roles || []).some(r => r === 'checkout' || r === 'analysis'))
    && (!q.q || normalize.matches([b.name, b.remote || '', b.upstream || '', b.subject || ''].join(' '), q.q)));
  const fresh = `<a class="chip ${f.state === 'fresh' ? 'chip--ok' : 'chip--caution'}" href="${href('/status', { sheet: 'freshness' })}">${icon(f.state === 'fresh' ? 'check' : 'warn')}${esc(f.state === 'fresh' ? t('ac.br.fresh.ok') : t('ac.br.fresh.stale'))}</a>`;
  const recovery = (d.recovery || []).filter(r => !r.restored);
  return `<div class="page">
    ${projBack()}
    <div class="context">${fresh}</div>
    <h1 class="lede">${lede}</h1>
    <p class="guide">${t('ac.br.guide')}</p>
    <div class="actions">
      <button class="btn btn--primary" data-act="sheet" data-sheet="choose-branch" data-fk="br-choose">${t('ac.br.choose', { b: code(analysed) })}</button>
      ${differ ? `<a class="btn btn--secondary" href="${href('/activity', { sheet: 'check' })}">${t('ac.br.check_now')}</a>` : ''}
      <button class="btn btn--quiet" data-act="sheet" data-sheet="cleanup">${t('ac.br.cleanup')}</button>
      <p class="actions__note">${t('ac.br.note')}</p>
    </div>
    <section class="section" aria-labelledby="four-h"><div class="section-head"><h2 id="four-h">${t('ac.br.four')}</h2></div>${four}</section>
    <section class="section" aria-labelledby="all-h">
      <div class="section-head"><h2 id="all-h">${t('ac.br.all')}</h2><span class="small muted ac-fetch">${esc(d.last_fetch ? t('ac.br.fetched', { when: fmtWhen(d.last_fetch) }) : t('ac.br.fetched.never'))} ${(d.remotes || []).length ? `<button class="link ac-inline" data-act="ac-fetch" ${inv.fetching ? 'disabled' : ''}>${t(inv.fetching ? 'ac.br.fetching' : 'ac.br.refresh')}</button>` : ''}</span></div>
      <div class="ptools" style="margin-top:0">
        <label class="field">${icon('search')}<span class="sr-only">${t('ac.br.search')}</span><input type="search" id="bq" data-fk="bq" data-input="ac-bq" value="${esc(q.q || '')}" placeholder="${esc(t('ac.br.search'))}" autocomplete="off"></label>
        <div class="ptools__row ac-brtools">
          <nav class="seg" aria-label="${esc(t('ac.br.all'))}"><a href="${href('/project/branches', Object.assign({}, q, { show: null }))}" aria-current="${!yours}">${t('ac.br.show.all', { n: num(all.length) })}</a><a href="${href('/project/branches', Object.assign({}, q, { show: 'yours' }))}" aria-current="${yours}">${t('ac.br.show.yours')}</a></nav>
          <button class="btn btn--secondary" data-act="sheet" data-sheet="compare" data-fk="br-compare">${t('ac.br.compare', { b: code(d.base || analysed) })}</button>
        </div>
      </div>
      <div class="listhead"><span class="listhead__count" aria-live="polite">${esc(t('ac.br.count', { shown: num(list.length), total: num(all.length) }))}</span></div>
      ${list.length ? `<ul class="panel rows">${list.map(branchRow).join('')}</ul>` : `<div class="panel empty"><p class="empty__title">${t('ac.br.none')}</p><a class="btn btn--secondary" href="${href('/project/branches')}">${t('pb.clear')}</a></div>`}
      ${d.truncated ? `<p class="list-foot">${t('ac.br.truncated')}</p>` : ''}
    </section>
    <div class="section panel">
      ${ac.fold('deleted', t('ac.br.deleted'), esc(tn('ac.pl.branch', recovery.length)), recovery.length ? `<ul class="rows">${recovery.map(r => `<li class="row" style="padding-inline:0">${icon('branch', 'muted')}<span class="row__main"><bdi class="mono">${esc(r.branch)}</bdi>
          <span class="row__meta" style="display:block">${esc(t(r.where === 'remote' ? 'ac.br.deleted.remote' : 'ac.br.deleted.local', { r: r.remote || '' }))}, ${esc(fmtWhen(r.at))}. ${t('ac.br.deleted.tip', { tip: code(String(r.tip).slice(0, 7)) })}</span></span>
          <button class="btn btn--secondary btn--sm" data-act="sheet" data-sheet="restore:${esc(r.id)}">${t('ac.br.restore')}</button></li>`).join('')}</ul>` : `<p class="small muted">${t('ac.br.deleted.none')}</p>`)}
      ${ac.fold('remotes', t('ac.br.remotes'), esc(t('ac.br.remotes.sum.v', { remotes: (d.remotes || []).join(t('list.sep')) || t('ac.br.remotes.none'), n: num((d.worktrees || []).length) })), `<dl class="facts">
          <dt>${t('ac.br.remote')}</dt><dd>${(d.remotes || []).map(code).join(' ') || esc(t('ac.br.remotes.none'))}</dd>
          <dt>${t('ac.br.remote.default')}</dt><dd>${d.default && d.default.name ? `${code(d.default.name)} <span class="small muted">${esc(d.default.source || '')}</span>` : '—'}</dd>
          <dt>${t('ac.br.remote.fetched')}</dt><dd>${esc(d.last_fetch ? fmtWhen(d.last_fetch) : t('ac.br.fetched.never'))}</dd>
          <dt>${t('ac.br.wt')}</dt><dd>${(d.worktrees || []).map(w => `<div>${code(w.path)} ${code(w.branch || String(w.head).slice(0, 7))} <span class="small muted">${t(w.current ? 'ac.br.wt.here' : 'ac.br.wt.other')}</span></div>`).join('')}</dd>
          <dt>${t('ac.br.orphans')}</dt><dd>${(d.missing_linked || []).length ? d.missing_linked.map(m => code(m.name)).join(' ') : t('ac.br.orphans.none')}</dd></dl>`)}
    </div>
  </div>`;
}
screen({ id: 'S-46', path: '/project/branches', place: 'project', title: () => t('proj.branches'), render: branchesPage });
let bqTimer = null;
act('ac-bq', el => { clearTimeout(bqTimer); const v = el.value; bqTimer = setTimeout(() => { setQuery({ q: v || null }); const i = document.getElementById('bq'); if (i) { i.focus(); i.setSelectionRange(i.value.length, i.value.length); } }, 180); });
act('ac-br-reload', () => { inv.problem = null; changed(); });
act('ac-fetch', async el => {
  if (el.disabled || !client || !inv.data) return;
  inv.fetching = true; refresh();
  try { const r = await client.branches.fetch((inv.data.remotes || [])[0]); toast(r.run && r.run.state === 'done' ? t('ac.br.fetched.done') : L((r.run && r.run.result && r.run.result.answer && r.run.result.answer.reason) || t('ac.br.fetched.failed')), r.run && r.run.state === 'done' ? undefined : { refusal: true }); }
  catch (e) { toast(said(e), { refusal: true }); }
  inv.fetching = false; changed();
});

/* choose the branch EAOS checks (BRN-05; G1, G9; the same choice answers DEC-03) */
sheet('choose-branch', {
  kind: 'dialog',
  render(arg, query, own) {
    const d = inventory(inv.base);
    if (!d) return { title: esc(t('ac.br.choose.title')), body: `<p class="small muted" aria-busy="true">${t('st.loading')}</p>` };
    const cur = (d.context.analysis && d.context.analysis.branch) || '';
    const pick = own.pick || arg || cur;
    if (own.blocked) {
      const runs = own.blocked.runs || [];
      return {
        title: esc(t('ac.br.choose.title')),
        body: `${owner()}<div class="ac-refuse" role="alert"><p><b>${t('ac.br.choose.refused')}</b></p><p class="small ink-2">${esc(L(own.blocked))}</p></div>
          <ul class="panel rows">${runs.map(r => { const run = ac.runOf(r.id); return `<li class="row">${ac.glyph(run ? ac.runState(run) : 'queued')}<span class="row__main"><span class="row__title small">${esc(L(r.label))}</span></span>
            ${run && run.state === 'queued' ? `<button class="btn btn--secondary btn--sm" data-act="ac-remove" data-id="${esc(r.id)}">${t('ac.line.remove')}</button>` : `<button class="btn btn--secondary btn--sm" data-act="sheet" data-sheet="stop:${esc(r.id)}">${t('ac.ctl.stop')}</button>`}</li>`; }).join('')}</ul>`,
        foot: `<button class="btn btn--secondary btn--block" data-act="sheet-close" data-autofocus>${t('close')}</button>`,
      };
    }
    const opts = d.branches.filter(b => b.kind === 'local' && !b.work).map(b => {
      const prot = !!b.protected;
      const note = prot ? L(b.protected) : b.name === cur ? t('ac.br.choose.now') : b.compare ? t('ac.br.choose.vs', { a: num(b.compare.ahead), b: num(b.compare.behind), base: b.compare.base }) : '';
      return `<label class="opt ${prot ? 'opt--off' : ''}"><input type="radio" name="ac-pick" value="${esc(b.name)}" data-change="ac-pick" data-fk="pick-${esc(b.name)}" ${pick === b.name ? 'checked' : ''} ${prot ? 'disabled' : ''}><span class="opt__dot" aria-hidden="true"></span>
        <span class="opt__text"><span class="opt__line">${code(b.name)}${prot ? icon('lock', 'icon--sm muted') : ''}</span><span class="opt__note">${esc(note)}</span></span></label>`;
    }).join('');
    const waits = store.awaiting()[0];
    return {
      title: esc(t('ac.br.choose.title')),
      body: `${owner()}<p>${t('ac.br.choose.lede')}</p>
        <div class="opts" role="radiogroup" aria-label="${esc(t('ac.br.choose.title'))}">${opts}</div>
        <div class="toggle-row"><span><span style="display:block">${t('ac.br.choose.check')}</span><span class="small muted">${t('ac.br.choose.check.note')}</span></span>
          <span class="switch"><input type="checkbox" data-change="ac-pick-scan" data-fk="pick-check" ${own.scan !== false ? 'checked' : ''} aria-label="${esc(t('ac.br.choose.check'))}"><span class="switch__track"></span><span class="switch__thumb"></span></span></div>
        ${waits ? `<p class="small ink-2">${t('ac.br.choose.waiting', { b: code(waits.result.branch) })} <a class="link" href="${href('/waiting/' + enc(waits.id))}" data-act="go" data-href="${href('/waiting/' + enc(waits.id))}">${t('ac.run.r12.decide')}</a></p>` : ''}`,
      foot: `${alert(own.refused)}<div class="sheet__foot-row"><button class="btn btn--secondary" data-act="sheet-close" data-autofocus>${t('cancel')}</button>
        <button class="btn btn--primary" data-act="ac-choose" data-fk="choose-do" ${pick === cur || own.busy ? `disabled title="${esc(t('ac.br.choose.same'))}"` : ''}>${icon('seal')}${esc(t('ac.br.choose.do', { b: pick }))}</button></div>`,
    };
  },
});
act('ac-pick', el => { local().pick = el.value; rerenderSheet(); });
act('ac-pick-scan', el => { local().scan = el.checked; });
act('ac-analyse', el => openSheet('choose-branch:' + el.dataset.name));
act('ac-choose', async el => {
  const own = local(), d = inv.data;
  const pick = own.pick || (parseHash().query.sheet || '').split(':').slice(1).join(':');
  if (el.disabled || !client || !d || !pick) return;
  const row = rowOf(d, pick);
  own.busy = true; rerenderSheet();
  try {
    const r = await client.branches.select(pick, own.scan !== false, row ? row.tip : null);
    closeSheetThen(() => { toast(t('ac.br.choose.done', { b: pick, folder: (d.context.checkout && d.context.checkout.branch) || '' }), r.scan ? { link: { href: href('/activity/run/' + enc(r.scan.id)), text: t('toast.follow') } } : undefined); changed(); });
  } catch (e) {
    own.busy = false;
    if (e instanceof ActionError && e.needs === 'in_flight') own.blocked = e.reasons[0]; else own.refused = said(e);
    rerenderSheet();
  }
});

/* compare with another base (BRN-03) */
sheet('compare', {
  kind: 'drawer',
  render() {
    const d = inv.data;
    const bases = d ? [...new Set([d.context.analysis && d.context.analysis.branch, d.default && d.default.name].concat(d.branches.filter(b => b.kind === 'local' && (b.roles || []).includes('checkout')).map(b => b.name)).filter(Boolean))] : [];
    const opts = bases.map(b => `<label class="opt"><input type="radio" name="ac-base" value="${esc(b)}" data-change="ac-base" data-fk="base-${esc(b)}" ${(d.base || '') === b ? 'checked' : ''}><span class="opt__dot" aria-hidden="true"></span>
      <span class="opt__text">${code(b)}<span class="opt__note">${t(b === (d.context.analysis && d.context.analysis.branch) ? 'ac.br.cmp.develop' : b === (d.default && d.default.name) ? 'ac.br.cmp.main' : 'ac.br.cmp.folder')}</span></span></label>`).join('');
    return { title: esc(t('ac.br.cmp.title')), sub: esc(t('ac.br.cmp.sub')), body: `<div class="opts">${opts}</div><p class="small muted">${t('ac.br.cmp.note')}</p>`,
      foot: `<button class="btn btn--primary btn--block" data-act="sheet-close">${t('done')}</button>` };
  },
});
act('ac-base', el => { inv.data = null; inv.details = {}; setQuery({ base: el.value, sheet: null }); });

/* clean up the merged branches (BRN-11; G10) */
sheet('cleanup', {
  kind: 'dialog', confirm: true,
  render(arg, query, own) {
    if (!own.preview && !own.asking && !own.problem && client) {
      own.asking = true;
      client.branches.previewCleanup().then(p => { own.preview = p; own.asking = false; rerenderSheet(); }, e => { own.asking = false; own.problem = said(e); rerenderSheet(); });
    }
    const p = own.preview;
    if (!p) return { title: esc(t('ac.cl.title')), body: own.problem ? alert(own.problem) : `<p class="small muted" aria-busy="true">${t('cf.previewing')}</p>`, foot: `<button class="btn btn--secondary btn--block" data-act="sheet-close" data-autofocus>${t('close')}</button>` };
    const stays = `<ul class="panel rows">${p.kept.map(k => `<li class="row small" style="min-height:48px">${code(k.branch)}<span class="row__main muted">${esc(reasonsOf(k.reasons))}</span></li>`).join('')}${p.kept_branches.map(n => `<li class="row small" style="min-height:48px">${code(n)}<span class="row__main muted">${t('ac.cl.why.keeper')}</span></li>`).join('')}</ul>`;
    const goes = p.branches.length + p.worktrees.length;
    if (!goes) return { title: esc(t('ac.cl.title')), body: `<p class="h2">${t('ac.cl.nothing')}</p>${stays}`, foot: `<button class="btn btn--secondary btn--block" data-act="sheet-close" data-autofocus>${t('close')}</button>` };
    return {
      title: esc(t('ac.cl.title')),
      body: `${owner()}<p>${esc(t('ac.cl.lede', { branches: tn('ac.pl.branch', p.branches.length) }))}</p>
        ${p.blocked.length ? `<div class="ac-refuse" role="alert"><p class="small">${esc(reasonsOf(p.blocked))}</p></div>` : ''}
        <div><div class="block-title">${t('ac.cl.goes')} (${num(p.branches.length)})</div><ul class="panel rows">${p.branches.map(b => `<li class="row">${icon('branch', 'muted')}<span class="row__main"><bdi class="mono">${esc(b.branch)}</bdi>
          <span class="row__meta" style="display:block">${t('ac.br.merged_into', { b: code(b.merged_into) })}. ${esc(L(b.whose))}</span></span></li>`).join('')}</ul></div>
        <div><div class="block-title">${t('ac.cl.wt')}</div>${p.worktrees.length ? `<ul class="panel rows">${p.worktrees.map(w => `<li class="row small">${code(w.path)}</li>`).join('')}</ul>` : `<p class="small ink-2">${t('ac.cl.wt.none')}</p>`}</div>
        <div><div class="block-title">${t('ac.cl.stays')}</div>${stays}</div>
        <p class="small ink-2">${t('ac.cl.rules')}</p>`,
      foot: `${alert(own.refused)}${ack('cleanup', esc(t('ac.cl.ack', { n: num(p.branches.length) })), own.ack_cleanup)}<div class="sheet__foot-row">
          <button class="btn btn--secondary" data-act="sheet-close" data-autofocus>${t('cancel')}</button>
          <button class="btn btn--danger" data-act="ac-cleanup" data-fk="cleanup-do" ${own.ack_cleanup && p.confirm && !own.busy ? '' : 'disabled'} title="${esc(own.ack_cleanup ? '' : t('cf.need_ack'))}">${esc(t('ac.cl.do', { branches: tn('ac.pl.branch', p.branches.length) }))}</button></div>${valid(p.confirm)}`,
    };
  },
});
act('ac-cleanup', async el => {
  const own = local();
  if (el.disabled || !own.preview) return;
  own.busy = true; rerenderSheet();
  try {
    const r = await client.branches.cleanup(own.preview);
    const done = (r.run && r.run.result && r.run.result.answer && r.run.result.answer.deleted) || [];
    closeSheetThen(() => { toast(t('ac.cl.done', { n: num(done.length) })); changed(); });
  } catch (e) { Object.assign(own, { busy: false, preview: null, asking: false, ack_cleanup: false, refused: said(e) }); rerenderSheet(); }
});

/* restore a deleted branch (BRN-09) */
sheet('restore', {
  kind: 'drawer',
  render(id, query, own) {
    const d = inv.data || inventory(inv.base);
    const r = d && (d.recovery || []).find(x => x.id === id);
    if (!r) return { title: esc(d ? t('ac.br.notfound', { name: id }) : t('st.loading')), body: '' };
    const v = own.name != null ? own.name : r.branch;
    const taken = d.branches.some(b => b.kind === 'local' && b.name === v);
    return {
      title: esc(t('ac.rs.title', { name: r.branch })),
      body: `<p>${t('ac.rs.lede')}</p><dl class="facts"><dt>${t('ac.rs.tip')}</dt><dd>${code(String(r.tip).slice(0, 12))}</dd><dt>${t('ac.rs.when')}</dt><dd>${esc(fmtWhen(r.at))}</dd>
        <dt>${t('ac.rs.by')}</dt><dd>${r.run ? `<a class="link" href="${href('/activity/run/' + enc(r.run))}">${code(r.run)}</a>` : '—'}</dd></dl>
        <label class="ac-label" for="rs-name">${t('ac.rs.name')}</label><div class="field"><input id="rs-name" dir="ltr" data-fk="rs-name" data-input="ac-rs-name" value="${esc(v)}" autocomplete="off" aria-describedby="rs-note"></div>
        <p class="small ${taken ? 'ac-c-danger' : 'muted'}" id="rs-note">${t(taken ? 'ac.rs.taken' : 'ac.rs.note')}</p>`,
      foot: `${alert(own.refused)}<button class="btn btn--primary btn--block" data-act="ac-restore" data-id="${esc(r.id)}" data-fk="rs-do" ${taken || !v.trim() || own.busy ? 'disabled' : ''}>${esc(t('ac.rs.do', { name: v }))}</button>`,
    };
  },
});
let rsTimer = null;
act('ac-rs-name', el => { local().name = el.value; clearTimeout(rsTimer); rsTimer = setTimeout(() => { rerenderSheet(); const i = document.getElementById('rs-name'); if (i) i.setSelectionRange(i.value.length, i.value.length); }, 400); });
act('ac-restore', async el => {
  const own = local();
  if (el.disabled || !client) return;
  own.busy = true; rerenderSheet();
  try {
    const r = await client.branches.restore(el.dataset.id, own.name || undefined);
    const name = (r.run && r.run.result && r.run.result.answer && r.run.result.answer.branch) || own.name;
    if (r.run && r.run.state !== 'done') throw new Error(L(r.run.result && r.run.result.answer && r.run.result.answer.reason) || t('ac.rs.failed'));
    closeSheetThen(() => { toast(t('ac.rs.done', { name })); changed(); });
  } catch (e) { Object.assign(own, { busy: false, refused: said(e) }); rerenderSheet(); }
});

/* =================================================================================================================
   S-47 ONE BRANCH (BRN-04, BRN-06, BRN-07, BRN-08, BRN-10)
   ================================================================================================================= */
const conflictOf = cmd => cmd && (cmd.blocked || []).some(r => r.code === 'conflict');
function commands(b, det) {
  const c = det.commands || {};
  const out = [];
  const why = cmd => reasonsOf(cmd.blocked);
  if (c.select_analysis) out.push(['check', c.select_analysis.available, why(c.select_analysis)]);
  const waits = waitingRun(b.name);
  if (c.merge) out.push(waits ? ['merge', false, t('ac.cmd.merge.eaos')] : ['merge', c.merge.available, why(c.merge)]);
  if (b.kind === 'local' && conflictOf(c.merge) && !waits) out.push(['resolve', true, '']);
  if (c.delete_local) out.push(waits ? ['delete', false, t('ac.cmd.del.eaos')] : ['delete', c.delete_local.available, why(c.delete_local)]);
  if (c.delete_remote) out.push(['delete-remote', c.delete_remote.available, why(c.delete_remote)]);
  if (b.kind === 'local') {
    if (b.protected) out.push(['unprotect', !['default', 'eaos_main'].includes(b.protected.code), L(b.protected)]);
    else out.push(b.work ? ['protect', false, t('ac.cmd.protect.eaos')] : ['protect', true, '']);
  }
  return out;
}
function cmdButton(b, cmd, det) {
  const [id, ok, why] = cmd;
  const target = (det.destination && det.destination.recommended) || '';
  const label = t('ac.cmd.' + id, { t: target, r: b.remote || '' });
  const ic = id === 'protect' || id === 'unprotect' ? 'seal' : id === 'merge' ? 'branch' : id === 'resolve' ? 'ai' : id === 'check' ? 'retry' : 'minus';
  if (!ok) return `<li class="row ac-cmd">${icon(ic === 'seal' ? 'lock' : ic, 'muted')}<span class="row__main"><span class="row__title ac-c-muted">${esc(label)}</span><span class="row__meta" style="display:block">${esc(t('ac.cmd.not', { why }))}</span></span></li>`;
  const arg = b.kind === 'remote' ? `${b.remote}/${b.name}` : b.name;
  const attrs = id === 'check' ? `data-act="ac-analyse" data-name="${esc(b.name)}"` : `data-act="sheet" data-sheet="${esc(id + ':' + arg)}"`;
  return `<li><button class="row ac-cmd" ${attrs}>${icon(ic, id.startsWith('delete') ? 'ac-c-danger' : 'ac-c-accent')}
    <span class="row__main"><span class="row__title">${esc(label)}</span><span class="row__meta" style="display:block">${esc(t('ac.cmd.' + id + '.sub', { t: target, r: b.remote || '' }))}</span></span>${icon('chev', 'icon--sm icon--dir muted')}</button></li>`;
}
function checksLine(ch) {
  if (!ch || ch.status === 'not_recorded') return ac.nmTag(t('ac.br.checks.none'));
  return ac.mark(ch.status === 'passed' ? 'ok' : ch.status === 'failed' ? 'failed' : 'skipped', esc(ch.summary || ch.status));
}
function branchPage(ctx) {
  const name = ctx.params.name, kind = ctx.query.kind || 'local', remote = ctx.query.remote || null;
  const back = `<a class="back" href="${href('/project/branches')}">${icon('back', 'icon--dir')}${t('proj.branches')}</a>`;
  if (ctx.offline) return `<div class="page">${back}<h1 class="lede">${t('ac.br.offline.lede')}</h1><div class="actions"><button class="btn btn--primary" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button></div></div>`;
  const det = client && detail(name, kind, remote);
  const problem = problemOf(name, kind, remote);
  if (problem) {
    return `<div class="page">${back}<div class="panel empty" style="margin-top:12px"><h1 class="empty__title">${esc(t('ac.br.notfound', { name }))}</h1>
      <p class="small ink-2">${t('ac.br.notfound.guide')}</p><a class="btn btn--secondary" href="${href('/project/branches')}">${t('proj.branches')}</a></div></div>`;
  }
  if (!det) return `<div class="page" aria-busy="true">${back}<h1 class="lede">${t('ac.br.loading')}</h1>${loadingRows()}</div>`;
  const b = det.branch;
  const cmds = commands(b, det);
  const target = (det.destination && det.destination.recommended) || '';
  const waits = waitingRun(b.name);
  const merge = cmds.find(c => c[0] === 'merge');
  const primary = merge && merge[1] ? merge : null;
  let lede;
  if (waits) lede = t('ac.br1.lede.eaos', { b: code(b.name) });
  else if (b.protected) lede = t('ac.br1.lede.protected', { b: code(liveName(b)) });
  else if ((b.roles || []).includes('analysis')) lede = t('ac.br1.lede.analysed', { b: code(b.name) });
  else if (b.compare && b.compare.merged && !b.compare.ahead) lede = t('ac.br1.lede.merged', { b: code(liveName(b)), t: code(b.compare.base) });
  else lede = t('ac.br1.lede', { b: code(liveName(b)), a: num(b.compare ? b.compare.ahead : 0), base: code(det.base || '') });
  const conflict = merge && conflictOf({ blocked: (det.commands.merge || {}).blocked });
  const tryMerge = primary && !waits && b.kind === 'local' ? mergeTry(b) : null;
  const clash = tryMerge && (tryMerge.conflicts || []).length ? tryMerge.conflicts : null;
  const commits = det.commits || [], files = det.files || [];
  const runs = det.runs || [];
  return `<div class="page">
    ${back}
    <div class="context"><bdi class="mono" style="align-self:center;font-weight:500">${esc(liveName(b))}</bdi>${roleTags(b)}</div>
    <h1 class="lede">${lede}</h1>
    <p class="guide">${t(waits ? 'ac.br1.guide.eaos' : 'ac.br1.guide')}</p>
    ${waits ? `<div class="actions"><a class="btn btn--primary" href="${href('/waiting/' + enc(waits.id))}">${icon('seal')}${t('ac.run.r12.decide')}</a><p class="actions__note">${t('ac.br1.eaos.note')}</p></div>`
      : primary ? `<div class="actions"><button class="btn btn--primary" data-act="sheet" data-sheet="merge:${esc(b.name)}">${icon('seal')}${esc(t('ac.cmd.merge', { t: target }))}</button><p class="actions__note">${t('ac.br1.merge.note')}</p></div>` : ''}
    ${clash ? `<div class="ac-note ac-note--caution" style="margin-top:16px">${icon('warn', 'icon--sm ac-c-caution')}<span class="small">${esc(tn('ac.br1.clash', clash.length, { t: tryMerge.target || target }))}</span>
      <button class="btn btn--secondary btn--sm" data-act="sheet" data-sheet="resolve:${esc(b.name)}">${icon('ai')}${t('ac.cmd.resolve')}</button></div>` : ''}
    ${conflict ? `<div style="margin-top:16px"><div class="ac-note ac-note--caution">${icon('warn', 'icon--sm ac-c-caution')}<span class="small">${esc(reasonsOf(det.commands.merge.blocked))}</span></div></div>` : ''}
    <section class="section" aria-labelledby="cmd-h"><div class="section-head"><h2 id="cmd-h">${t('ac.br1.cmds')}</h2></div><ul class="panel rows">${cmds.filter(c => c !== primary).map(c => cmdButton(b, c, det)).join('')}</ul></section>
    <section class="section" aria-labelledby="bf-h"><div class="section-head"><h2 id="bf-h">${t('ac.br1.facts')}</h2></div>
      <div class="panel panel__pad"><dl class="facts ac-facts">
        <dt>${t('ac.br1.tip')}</dt><dd>${code(String(b.tip).slice(0, 7))} <span class="small ink-2">${rich(b.subject || '')}</span> <span class="small muted">${esc(fmtWhen(b.last_commit))}</span></dd>
        <dt>${t('ac.br1.where')}</dt><dd>${b.kind === 'local' ? t('ac.br1.local') + (b.upstream ? `, ${t('ac.br1.tracks', { u: code(b.upstream) })}${b.tracking ? ` <span class="small muted">${esc(b.tracking)}</span>` : ''}` : '') : t('ac.br1.remote_only', { r: code(b.remote) })}</dd>
        <dt>${t('ac.br1.vs')}</dt><dd>${aheadBehind(b)}</dd>
        <dt>${t('ac.br1.who')}</dt><dd>${whoLine(b)}</dd>
        ${b.protected ? `<dt>${t('ac.br.r.protected')}</dt><dd>${esc(L(b.protected))}</dd>` : ''}
        <dt>${t('ac.br1.wt')}</dt><dd>${b.worktree ? `${code(b.worktree.path)} ${t(b.worktree.current ? 'ac.br.wt.here' : 'ac.br.wt.other')}` : t('ac.br1.wt.none')}</dd>
        <dt>${t('ac.br1.checks')}</dt><dd>${checksLine(det.checks)}</dd>
        ${det.lineage && det.lineage.parent ? `<dt>${t('ac.br1.lineage')}</dt><dd>${t('ac.br1.lineage.v', { p: code(det.lineage.parent), c: code(String(det.lineage.parent_commit || '').slice(0, 7)) })}</dd>` : ''}
        <dt>${t('ac.br1.dest')}</dt><dd>${target ? t('ac.br1.dest.v', { t: code(target) }) : '—'}</dd>
      </dl></div></section>
    <div class="section panel">
      ${ac.fold('commits', t('ac.br1.commits', { base: det.base || '' }), esc(commits.length ? tn('ac.pl.commit', commits.length) : t('ac.br1.commits.none')),
        commits.length ? `<ul class="rows">${commits.map(c => `<li class="row" style="padding-inline:0;min-height:48px">${code(String(c.commit).slice(0, 7))}<span class="row__main small">${rich(c.subject)}<span class="row__meta" style="display:block">${esc(c.author || '')}, ${esc(fmtWhen(c.at))}</span></span></li>`).join('')}</ul>
          ${det.commits_truncated ? `<p class="small muted">${t('ac.br1.more.cut')}</p>` : ''}` : `<p class="small muted">${t('ac.br1.commits.none')}</p>`)}
      ${ac.fold('files', t('ac.br1.files'), esc(files.length ? tn('pl.file', det.files_total || files.length) : t('ac.br1.files.none')),
        files.length ? `<ul class="rows">${files.map(f => `<li class="row" style="padding-inline:0;min-height:44px"><span class="tag tag--state">${esc(t('ac.br1.fs.' + (['M', 'A', 'D'].includes(f.status[0]) ? f.status[0] : 'M')))}</span><bdi class="mono">${esc(f.path)}</bdi></li>`).join('')}</ul>` : `<p class="small muted">${t('ac.br1.files.none')}</p>`)}
      ${ac.fold('diff', t('ac.br1.diff'), t('ac.br1.diff.sum'), det.diff ? `<div class="code diff">${det.diff.split('\n').slice(0, 400).map((l, i) => `<div class="code__line ${l.startsWith('+') && !l.startsWith('+++') ? 'code__line--add' : l.startsWith('-') && !l.startsWith('---') ? 'code__line--del' : ''}"><span class="code__ln">${i + 1}</span><span>${esc(l)}</span></div>`).join('')}</div>${det.diff_cut ? `<p class="small muted">${t('wt.fix.cut')}</p>` : ''}` : `<p class="small muted">${t('ac.br1.diff.none')}</p>`)}
      ${ac.fold('runs', t('ac.br1.runs'), esc(runs.length ? tn('ac.pl.run', runs.length) : t('ac.br1.runs.none')),
        runs.length ? `<ul class="rows">${runs.map(r => `<li><a class="row" style="padding-inline:0" href="${href('/activity/run/' + enc(r.id))}">${ac.glyph(r.state === 'waiting_for_person' ? 'you' : r.state)}<span class="row__main small">${esc(L(r.label))}</span><span class="small muted">${esc(fmtWhen(r.created))}</span></a></li>`).join('')}</ul>` : `<p class="small muted">${t('ac.br1.runs.none')}</p>`)}
    </div>
  </div>`;
}
screen({ id: 'S-47', path: '/project/branches/:name', place: 'project', title: ctx => ctx.params.name + ' - ' + t('proj.branches'), render: branchPage });

/** The branch a sheet's argument names: `<name>` or `<remote>/<name>` for a remote copy. */
function sheetBranch(arg, remote) {
  if (!remote) return { name: arg, kind: 'local', remote: null };
  const i = arg.indexOf('/');
  return { name: arg.slice(i + 1), kind: 'remote', remote: arg.slice(0, i) };
}

/* merge, its preview inside the confirm sheet (BRN-06; G1, G2, G4, G8, G11) */
sheet('merge', {
  kind: 'dialog', confirm: true,
  render(name, query, own) {
    const ask = target => {
      own.asking = true; own.preview = null; own.problem = null;
      client.branches.previewMerge(name, target).then(p => { own.preview = p; own.asking = false; own.target = p.target; rerenderSheet(); }, e => { own.asking = false; own.problem = said(e); rerenderSheet(); });
    };
    if (!own.preview && !own.asking && !own.problem && client) ask(own.target);
    own.ask = ask;
    const p = own.preview;
    const title = esc(t('ac.mg.title', { b: name, t: (p && p.target) || own.target || '' }));
    if (!p) return { title, body: `${owner()}${own.problem ? alert(own.problem) : `<p class="small muted" aria-busy="true">${t('cf.previewing')}</p>`}`, foot: `<button class="btn btn--secondary btn--block" data-act="sheet-close" data-autofocus>${t('cancel')}</button>` };
    const d = inventory(inv.base);
    const targets = d ? d.branches.filter(b => b.kind === 'local' && b.name !== name) : [];
    const into = `<div class="opts" role="radiogroup" aria-labelledby="mg-into">${targets.slice(0, 12).map(b => `<label class="opt ${b.protected ? 'opt--off' : ''}"><input type="radio" name="mg-into" value="${esc(b.name)}" data-change="ac-mg-into" data-fk="mg-${esc(b.name)}" ${b.name === p.target ? 'checked' : ''} ${b.protected ? 'disabled' : ''}><span class="opt__dot" aria-hidden="true"></span>
      <span class="opt__text"><span class="opt__line">${code(b.name)}${b.protected ? icon('lock', 'icon--sm muted') : ''}</span><span class="opt__note">${esc(b.protected ? L(b.protected) : b.name === p.recommended_target ? t('ac.mg.recommended') : '')}</span></span></label>`).join('')}</div>`;
    const blocked = p.blocked.length;
    const ready = !blocked && p.confirm && own.ack_merge && (!p.needs_unchecked_ack || own.ack_merge2) && !own.busy;
    return {
      title,
      body: `${owner()}<p>${t('ac.mg.lede', { b: code(name), t: code(p.target) })}</p>
        ${blocked ? `<div class="ac-refuse" role="alert"><p><b>${t('ac.mg.refused')}</b></p><p class="small">${esc(reasonsOf(p.blocked))}</p>${p.conflicts.length ? `<p class="small">${p.conflicts.map(code).join(' ')}</p>` : ''}</div>` : ''}
        <div><div class="block-title" id="mg-into">${t('cf.into')}</div>${into}</div>
        <dl class="facts">
          <dt>${t('ac.mg.how')}</dt><dd>${t(p.path === 'accept' ? 'ac.mg.how.accept' : 'ac.mg.how.v')}</dd>
          <dt>${t('ac.mg.ff')}</dt><dd>${t(p.fast_forward ? 'ac.mg.ff.yes' : 'ac.mg.ff.merge')}</dd>
          <dt>${t('ac.mg.heads')}</dt><dd>${code(String(p.source_head).slice(0, 7))} → ${code(String(p.target_head).slice(0, 7))}</dd>
          <dt>${t('ac.mg.commits')}</dt><dd>${esc(tn('ac.pl.commit', p.commits.length))}</dd>
          <dt>${t('cf.files')}</dt><dd>${esc(tn('pl.file', p.files.length))}</dd>
          <dt>${t('ac.mg.conflicts')}</dt><dd>${p.conflicts.length ? ac.mark('failed', esc(tn('pl.file', p.conflicts.length))) : ac.mark('ok', t('ac.mg.conflicts.none'))}</dd>
          <dt>${t('cf.checks')}</dt><dd>${checksLine(p.checks)}</dd>
        </dl>`,
      foot: `${alert(own.refused)}${blocked ? '' : ack('merge', t('cf.ack.accept'), own.ack_merge) + (p.needs_unchecked_ack ? ack('merge2', t('ac.mg.ack.unchecked'), own.ack_merge2) : '')}<div class="sheet__foot-row">
          <button class="btn btn--secondary" data-act="sheet-close" data-autofocus>${t('cancel')}</button>
          ${p.conflicts.length ? `<button class="btn btn--primary" data-act="sheet" data-sheet="resolve:${esc(name)}">${icon('ai')}${t('ac.cmd.resolve')}</button>`
            : blocked ? `<button class="btn btn--primary" data-act="ac-mg-again">${t('ac.mg.preview_again')}</button>`
              : `<button class="btn btn--primary" data-act="ac-merge" data-fk="mg-do" ${ready ? '' : 'disabled'} title="${esc(own.ack_merge ? '' : t('cf.need_ack'))}">${icon('seal')}${esc(t('ac.mg.do', { t: p.target }))}</button>`}</div>${valid(p.confirm)}`,
    };
  },
});
act('ac-mg-into', el => { const own = local(); own.ack_merge = own.ack_merge2 = false; own.ask(el.value); rerenderSheet(); });
act('ac-mg-again', () => { const own = local(); own.ask(own.target); rerenderSheet(); });
act('ac-merge', async el => {
  const own = local(), p = own.preview;
  if (el.disabled || !p) return;
  own.busy = true; rerenderSheet();
  try {
    const r = await client.branches.merge(p, !!own.ack_merge2);
    if (r.run && r.run.state !== 'done') throw new Error(L(r.run.result && r.run.result.answer && r.run.result.answer.reason) || t('ac.mg.failed'));
    closeSheetThen(() => { toast(t('ac.mg.done', { b: p.source, t: p.target })); changed(); });
  } catch (e) { Object.assign(own, { busy: false, ack_merge: false, ack_merge2: false, refused: said(e) }); if (e instanceof ActionError && ['refresh', 'confirm'].includes(e.needs)) own.ask(own.target); rerenderSheet(); }
});

/* delete here or on the remote (BRN-08; G10: a recovery point first, a second consent for commits only it holds) */
function deleteSheet(remote) {
  return {
    kind: 'dialog', confirm: true,
    render(arg, query, own) {
      const br = sheetBranch(arg, remote);
      if (!own.preview && !own.asking && !own.problem && client) {
        own.asking = true;
        client.branches.previewDelete(br.name, remote ? 'remote' : 'local', br.remote).then(p => { own.preview = p; own.asking = false; rerenderSheet(); }, e => { own.asking = false; own.problem = said(e); rerenderSheet(); });
      }
      const p = own.preview;
      const title = esc(t(remote ? 'ac.dl.title.remote' : 'ac.dl.title', { b: br.name, r: br.remote || '' }));
      if (!p) return { title, body: `${owner()}${own.problem ? alert(own.problem) : `<p class="small muted" aria-busy="true">${t('cf.previewing')}</p>`}`, foot: `<button class="btn btn--secondary btn--block" data-act="sheet-close" data-autofocus>${t('cancel')}</button>` };
      if (p.blocked.length) return { title, body: `${owner()}<div class="ac-refuse" role="alert"><p><b>${t('ac.dl.refused')}</b></p><p class="small">${esc(reasonsOf(p.blocked))}</p></div>`, foot: `<button class="btn btn--secondary btn--block" data-act="sheet-close" data-autofocus>${t('close')}</button>` };
      const lost = p.lost_commits || [];
      const ready = p.confirm && own.ack_del && (!p.unmerged || own.ack_del2) && !own.busy;
      return {
        title,
        body: `${owner()}<p>${t(remote ? 'ac.dl.lede.remote' : 'ac.dl.lede', { b: code(br.name), r: code(br.remote || 'origin') })}</p>
          <dl class="facts"><dt>${t('ac.br1.who')}</dt><dd>${esc(L(p.whose))}</dd>
            ${remote ? `<dt>${t('ac.dl.other')}</dt><dd>${t(p.local_kept ? 'ac.dl.other.local' : 'ac.dl.other.nolocal')}</dd>`
              : `<dt>${t('ac.dl.lost')}</dt><dd>${p.unmerged ? esc(t('ac.dl.only', { n: tn('ac.pl.commit', lost.length) })) : t('ac.dl.nothing', { b: (p.merged_into || []).slice(0, 3).map(code).join(' ') })}</dd>
              ${p.worktree ? `<dt>${t('ac.br1.wt')}</dt><dd>${t('ac.dl.wt', { p: code(p.worktree) })}</dd>` : ''}`}</dl>
          ${lost.length ? `<div><div class="block-title">${t('ac.dl.only.list')}</div><ul class="panel rows">${lost.map(c => `<li class="row small" style="min-height:44px">${code(String(c.commit).slice(0, 7))}<span class="row__main">${rich(c.subject || '')}</span></li>`).join('')}</ul></div>` : ''}
          <p class="small ink-2">${t('ac.dl.recovery')}</p>`,
        foot: `${alert(own.refused)}${ack('del', esc(t('ac.dl.ack', { b: br.name })), own.ack_del)}${p.unmerged ? ack('del2', esc(t('ac.dl.ack2', { n: tn('ac.pl.commit', lost.length) })), own.ack_del2) : ''}<div class="sheet__foot-row">
            <button class="btn btn--secondary" data-act="sheet-close" data-autofocus>${t('cancel')}</button>
            <button class="btn btn--danger" data-act="ac-delete" data-fk="del-do" ${ready ? '' : 'disabled'} title="${esc(own.ack_del ? '' : t('cf.need_ack'))}">${esc(t(remote ? 'ac.dl.do.remote' : 'ac.dl.do', { b: br.name, r: br.remote || '' }))}</button></div>${valid(p.confirm)}`,
      };
    },
  };
}
sheet('delete', deleteSheet(false));
sheet('delete-remote', deleteSheet(true));
act('ac-delete', async el => {
  const own = local(), p = own.preview;
  if (el.disabled || !p) return;
  own.busy = true; rerenderSheet();
  try {
    const r = await client.branches.remove(p, !!p.unmerged);
    if (r.run && r.run.state !== 'done') throw new Error(L(r.run.result && r.run.result.answer && r.run.result.answer.reason) || t('ac.dl.failed'));
    closeSheetThen(() => { toast(t(p.where === 'remote' ? 'ac.dl.done.remote' : 'ac.dl.done', { b: p.branch, r: p.remote || '' })); changed(); if (p.where !== 'remote') location.hash = href('/project/branches'); });
  } catch (e) { Object.assign(own, { busy: false, preview: null, asking: false, ack_del: false, ack_del2: false, refused: said(e) }); rerenderSheet(); }
});

/* protect, remove the protection (BRN-10) */
function protectSheet(on) {
  return {
    kind: 'dialog', confirm: true,
    render(name, query, own) {
      if (!own.preview && !own.asking && !own.problem && client) {
        own.asking = true;
        client.branches.previewProtect(name, on).then(p => { own.preview = p; own.asking = false; rerenderSheet(); }, e => { own.asking = false; own.problem = said(e); rerenderSheet(); });
      }
      const p = own.preview;
      const ready = p && (on || own.ack_unprot) && !own.busy;
      return {
        title: esc(t(on ? 'ac.pr.title' : 'ac.up.title', { b: name })),
        body: `${owner()}<p>${t(on ? 'ac.pr.lede' : 'ac.up.lede', { b: code(name) })}</p>${on ? `<p class="small ink-2">${t('ac.pr.undo')}</p>` : ''}${own.problem ? alert(own.problem) : ''}`,
        foot: `${alert(own.refused)}${on ? '' : ack('unprot', t('ac.up.ack'), own.ack_unprot)}<div class="sheet__foot-row"><button class="btn btn--secondary" data-act="sheet-close" data-autofocus>${t('cancel')}</button>
          <button class="btn btn--primary" data-act="ac-protect" data-on="${on ? 1 : ''}" data-name="${esc(name)}" data-fk="prot-do" ${ready ? '' : 'disabled'}>${icon('seal')}${esc(t(on ? 'ac.pr.do' : 'ac.up.do', { b: name }))}</button></div>${p ? valid(p.confirm) : ''}`,
      };
    },
  };
}
sheet('protect', protectSheet(true));
sheet('unprotect', protectSheet(false));
act('ac-protect', async el => {
  const own = local(), on = !!el.dataset.on, name = el.dataset.name;
  if (el.disabled || !own.preview) return;
  own.busy = true; rerenderSheet();
  try {
    await client.branches.protect(name, on, own.preview.confirm ? own.preview.confirm.token : null);
    closeSheetThen(() => { toast(t(on ? 'ac.pr.done' : 'ac.up.done', { b: name })); changed(); });
  } catch (e) { Object.assign(own, { busy: false, preview: null, asking: false, refused: said(e) }); rerenderSheet(); }
});

/* propose a conflict's resolution (BRN-07): a read-only assistant run, previewed for free */
sheet('resolve', {
  kind: 'drawer',
  render(name, query, own) {
    if (!own.preview && !own.asking && !own.problem && client) {
      own.asking = true;
      client.branches.previewMerge(name).then(p => { own.preview = p; own.asking = false; rerenderSheet(); }, e => { own.asking = false; own.problem = said(e); rerenderSheet(); });
    }
    const p = own.preview;
    const assistants = live.assistants || [];
    const ready = assistants.filter(a => a.installed && a.logged_in);
    const pick = own.asst || (ready[0] && ready[0].id) || 'handoff';
    const conflicts = p ? p.conflicts : [];
    return {
      title: esc(t('ac.rv.title', { b: name })),
      sub: `<span class="free-band">${icon('check', 'icon--sm')}${t('free')}</span>`,
      body: `<p>${t('ac.rv.does', { t: code(p ? p.target : '') })}</p>
        ${!p ? (own.problem ? alert(own.problem) : `<p class="small muted" aria-busy="true">${t('cf.previewing')}</p>`) : conflicts.length ? `<div><div class="block-title">${t('ac.rv.files')}</div><ul class="panel rows">${conflicts.map(f => `<li class="row small" style="min-height:44px">${icon('file', 'icon--sm muted')}<bdi class="mono">${esc(f)}</bdi></li>`).join('')}</ul></div>` : `<p class="small ink-2" role="note">${t('ac.rv.none')}</p>`}
        <dl class="facts"><dt>${t('pv.risk')}</dt><dd><span class="tag tag--state">${t('pv.risk.low')}</span> <span class="small ink-2">${t('ac.rv.risk')}</span></dd></dl>
        <div><div class="block-title">${t('pv.who')}</div><div class="opts">${assistants.map(a => { const ok = a.installed && a.logged_in; return `<label class="opt ${ok ? '' : 'opt--off'}"><input type="radio" name="rv-asst" value="${esc(a.id)}" data-change="ac-rv-asst" data-fk="rv-${esc(a.id)}" ${pick === a.id ? 'checked' : ''} ${ok ? '' : 'disabled'}><span class="opt__dot"></span><span class="opt__text">${esc(a.name)}<span class="opt__note">${t(ok ? 'pv.ready' : a.installed ? 'pv.notsigned' : 'pv.notinstalled')}</span></span></label>`; }).join('')}
          <label class="opt"><input type="radio" name="rv-asst" value="handoff" data-change="ac-rv-asst" data-fk="rv-handoff" ${pick === 'handoff' ? 'checked' : ''}><span class="opt__dot"></span><span class="opt__text">${t('ac.who.handoff')}<span class="opt__note">${t('pv.handoff')}</span></span></label></div></div>
        ${pick !== 'handoff' ? `<p class="small ink-2">${t('pv.cost')}</p>` : ''}`,
      foot: `${alert(own.refused)}<button class="btn btn--primary btn--block" data-act="ac-resolve" data-name="${esc(name)}" data-fk="rv-do" ${p && conflicts.length && !own.busy ? '' : 'disabled'}>${esc(t('pv.start', { title: t('ac.cmd.resolve') }))}</button>`,
    };
  },
});
act('ac-rv-asst', el => { local().asst = el.value; rerenderSheet(); });
act('ac-resolve', async el => {
  const own = local(), p = own.preview;
  if (el.disabled || !p) return;
  own.busy = true; rerenderSheet();
  try {
    const r = await client.branches.proposeResolution(p.source, p.target, own.asst || undefined);
    closeSheetThen(() => { toast(t('ac.rv.started'), { link: { href: href('/activity/run/' + enc(r.run.id)), text: t('toast.follow') } }); store.refresh(); });
  } catch (e) { Object.assign(own, { busy: false, refused: said(e) }); rerenderSheet(); }
});
