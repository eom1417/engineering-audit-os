// S-46 Branches (builder A): PRJ-04, BRN-01..03, BRN-05, BRN-09, BRN-11. Every branch as git tells it now
// (GET /api/branches: roles, ownership, protection, ahead and behind the base, worktrees, recovery points) and the
// owner-only confirm sheets of the whole list, each opened on its own free preview whose confirm token the act spends:
// choose the branch EAOS checks, clean up the merged branches, restore a deleted one, compare with another base, fetch.
// One branch and its own sheets: branch.js; what both share: git.js.
import {
  t, tn, L, num, esc, icon, code, href, fmtWhen, screen, sheet, act, rerenderSheet, local, toast, closeSheetThen, openSheet,
  parseHash, setQuery, searchTyped, freshness, store, client, ActionError, normalize, ac, refresh,
} from 'eaos';
import {
  enc, said, reasonsOf, projBack, inv, inventory, changed, rowOf, brUrl, liveName, aheadBehind, whoLine, roleTags, owner, ack, valid, alert,
  loadingRows, closeFoot, previewing, previewOnce, answerOf, mustBeDone,
} from './git.js';

/* =================================================================================================================
   S-46 BRANCHES
   ================================================================================================================= */
function branchRow(b) {
  return `<li><a class="row ac-brow" href="${brUrl(b)}">${icon('branch', 'muted')}
    <span class="row__main"><span class="ac-brow__top"><bdi class="mono ac-brow__name">${esc(liveName(b))}</bdi>${roleTags(b)}</span>
      <span class="row__meta ac-meta"><span>${aheadBehind(b)}</span><span>${whoLine(b)}</span>${b.last_commit ? `<span>${esc(t('ac.br.last', { when: fmtWhen(b.last_commit) }))}</span>` : ''}</span></span>${icon('chev', 'icon--dir muted')}</a></li>`;
}
const offlinePage = () => `<div class="page">${projBack()}<h1 class="lede">${t('ac.br.offline.lede')}</h1><p class="guide">${t('ac.br.offline')}</p><div class="actions"><button class="btn btn--primary" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button></div></div>`;
function failedPage(problem) {
  const nogit = /not a git repository/.test(said(problem));
  return `<div class="page">${projBack()}<h1 class="lede">${t(nogit ? 'ac.br.nogit' : 'ac.br.failed')}</h1><p class="guide">${nogit ? t('ac.br.nogit.guide') : esc(said(problem))}</p>
      <div class="actions">${nogit ? `<button class="btn btn--secondary" data-act="copy" data-text="git init">${icon('copy')}${t('ac.br.nogit.copy')}</button>` : `<button class="btn btn--secondary" data-act="ac-br-reload">${icon('retry')}${t('ac.op.try')}</button>`}</div></div>`;
}
function branchesPage(ctx) {
  if (ctx.offline) return offlinePage();
  const d = inventory(ctx.query.base);
  if (inv.problem && !d) return failedPage(inv.problem);
  if (!d) return `<div class="page" aria-busy="true">${projBack()}<h1 class="lede">${t('ac.br.loading')}</h1>${loadingRows()}</div>`;
  return branchesHTML(ctx.query, d);
}
/** The folder's branch, the branch analysed and whether they differ. */
function whereOf(c) {
  const folder = (c.checkout && c.checkout.branch) || t('ac.br.detached'), analysed = (c.analysis && c.analysis.branch) || folder;
  return { folder, analysed, differ: folder !== analysed };
}
const unsaved = c => (c.dirty ? (c.dirty.tracked || 0) + (c.dirty.untracked || 0) : 0);
const headOf = x => `${code(x.branch || '')} ${code(String(x.commit || '').slice(0, 7))}`;
/** The four places a branch matters: the folder, the analysis, the report, the last scan. */
function fourPanel(c, w, f) {
  const dirty = unsaved(c), none = esc(t('ac.br.four.none'));
  return `<div class="panel panel__pad ac-four"><dl class="facts">
      <dt>${t('ac.br.four.folder')}</dt><dd>${code(w.folder)} <span class="small muted">${dirty ? esc(t('ac.br.four.unsaved.v', { n: num(dirty) })) : t('ac.br.four.clean')}</span></dd>
      <dt>${t('ac.br.four.analysed')}</dt><dd>${code(w.analysed)}${c.analysis && c.analysis.selected ? ` <span class="small muted">${t('ac.br.four.chosen')}</span>` : ''}</dd>
      <dt>${t('ac.br.four.report')}</dt><dd>${c.report ? `${headOf(c.report)} <span class="small muted">${esc(fmtWhen(c.report.at))}</span>` : none}</dd>
      <dt>${t('ac.br.four.scan')}</dt><dd>${c.scan ? headOf(c.scan) : none}</dd></dl>
      ${w.differ ? `<p class="ac-note ac-note--caution small mt-3">${icon('warn', 'icon--sm ac-c-caution')}<span>${t('ac.br.four.differ.todo', { folder: code(w.folder), analysed: code(w.analysed) })}</span></p>`
        : `<p class="small ink-2 mt-3">${t(f.state === 'fresh' ? 'ac.br.four.agree' : 'ac.br.four.agree.stale')}</p>`}</div>`;
}
const isYours = b => b.work || (b.roles || []).some(r => r === 'checkout' || r === 'analysis');
const found = (b, q) => normalize.matches([b.name, b.remote || '', b.upstream || '', b.subject || ''].join(' '), q);
const shownBranches = (all, q, yours) => all.filter(b => (!yours || isYours(b)) && (!q.q || found(b, q.q)));
function freshChip(f) {
  const ok = f.state === 'fresh';
  return `<a class="chip ${ok ? 'chip--ok' : 'chip--caution'}" href="${href('/status', { sheet: 'freshness' })}">${icon(ok ? 'check' : 'warn')}${esc(ok ? t('ac.br.fresh.ok') : t('ac.br.fresh.stale'))}</a>`;
}
function fetchLine(d) {
  const button = `<button class="link ac-inline" data-act="ac-fetch" ${inv.fetching ? 'disabled' : ''}>${t(inv.fetching ? 'ac.br.fetching' : 'ac.br.refresh')}</button>`;
  return `${esc(d.last_fetch ? t('ac.br.fetched', { when: fmtWhen(d.last_fetch) }) : t('ac.br.fetched.never'))} ${(d.remotes || []).length ? button : ''}`;
}
function recoveryFold(d) {
  const recovery = (d.recovery || []).filter(r => !r.restored);
  return ac.fold('deleted', t('ac.br.deleted'), esc(tn('ac.pl.branch', recovery.length)), recovery.length ? `<ul class="rows">${recovery.map(r => `<li class="row" style="padding-inline:0">${icon('branch', 'muted')}<span class="row__main"><bdi class="mono">${esc(r.branch)}</bdi>
          <span class="row__meta" style="display:block">${esc(t(r.where === 'remote' ? 'ac.br.deleted.remote' : 'ac.br.deleted.local', { r: r.remote || '' }))}, ${esc(fmtWhen(r.at))}. ${t('ac.br.deleted.tip', { tip: code(String(r.tip).slice(0, 7)) })}</span></span>
          <button class="btn btn--secondary btn--sm" data-act="sheet" data-sheet="restore:${esc(r.id)}">${t('ac.br.restore')}</button></li>`).join('')}</ul>` : `<p class="small muted">${t('ac.br.deleted.none')}</p>`);
}
const defaultFact = def => (def && def.name ? `${code(def.name)} <span class="small muted">${esc(def.source || '')}</span>` : '—');
function remotesFold(d) {
  const remotes = d.remotes || [], worktrees = d.worktrees || [], missing = d.missing_linked || [];
  return ac.fold('remotes', t('ac.br.remotes'), esc(t('ac.br.remotes.sum.v', { remotes: remotes.join(t('list.sep')) || t('ac.br.remotes.none'), n: num(worktrees.length) })), `<dl class="facts">
          <dt>${t('ac.br.remote')}</dt><dd>${remotes.map(code).join(' ') || esc(t('ac.br.remotes.none'))}</dd>
          <dt>${t('ac.br.remote.default')}</dt><dd>${defaultFact(d.default)}</dd>
          <dt>${t('ac.br.remote.fetched')}</dt><dd>${esc(d.last_fetch ? fmtWhen(d.last_fetch) : t('ac.br.fetched.never'))}</dd>
          <dt>${t('ac.br.wt')}</dt><dd>${worktrees.map(w => `<div>${code(w.path)} ${code(w.branch || String(w.head).slice(0, 7))} <span class="small muted">${t(w.current ? 'ac.br.wt.here' : 'ac.br.wt.other')}</span></div>`).join('')}</dd>
          <dt>${t('ac.br.orphans')}</dt><dd>${missing.length ? missing.map(m => code(m.name)).join(' ') : t('ac.br.orphans.none')}</dd></dl>`);
}
function branchesHTML(q, d) {
  const w = whereOf(d.context || {});
  const f = freshness();
  const lede = w.differ ? t('ac.br.lede.differ', { folder: code(w.folder), analysed: code(w.analysed) }) : t('ac.br.lede', { b: code(w.folder) });
  const yours = q.show === 'yours';
  const all = d.branches;
  const list = shownBranches(all, q, yours);
  return `<div class="page">
    ${projBack()}
    <div class="context">${freshChip(f)}</div>
    <h1 class="lede">${lede}</h1>
    <p class="guide">${t('ac.br.guide')}</p>
    <div class="actions">
      <button class="btn btn--primary" data-act="sheet" data-sheet="choose-branch" data-fk="br-choose">${t('ac.br.choose', { b: code(w.analysed) })}</button>
      ${w.differ ? `<a class="btn btn--secondary" href="${href('/activity', { sheet: 'check' })}">${t('ac.br.check_now')}</a>` : ''}
      <button class="btn btn--quiet" data-act="sheet" data-sheet="cleanup">${t('ac.br.cleanup')}</button>
      <p class="actions__note">${t('ac.br.note')}</p>
    </div>
    <section class="section" aria-labelledby="four-h"><div class="section-head"><h2 id="four-h">${t('ac.br.four')}</h2></div>${fourPanel(d.context || {}, w, f)}</section>
    <section class="section" aria-labelledby="all-h">
      <div class="section-head"><h2 id="all-h">${t('ac.br.all')}</h2><span class="small muted ac-fetch">${fetchLine(d)}</span></div>
      <div class="ptools" style="margin-top:0">
        <label class="field">${icon('search')}<span class="sr-only">${t('ac.br.search')}</span><input type="search" id="bq" data-fk="bq" data-input="ac-bq" value="${esc(q.q || '')}" placeholder="${esc(t('ac.br.search'))}" autocomplete="off"></label>
        <div class="ptools__row ac-brtools">
          <nav class="seg" aria-label="${esc(t('ac.br.all'))}"><a href="${href('/project/branches', Object.assign({}, q, { show: null }))}" aria-current="${!yours}">${t('ac.br.show.all', { n: num(all.length) })}</a><a href="${href('/project/branches', Object.assign({}, q, { show: 'yours' }))}" aria-current="${yours}">${t('ac.br.show.yours')}</a></nav>
          <button class="btn btn--secondary" data-act="sheet" data-sheet="compare" data-fk="br-compare">${t('ac.br.compare', { b: code(d.base || w.analysed) })}</button>
        </div>
      </div>
      <div class="listhead"><span class="listhead__count" aria-live="polite">${esc(t('ac.br.count', { shown: num(list.length), total: num(all.length) }))}</span></div>
      ${list.length ? `<ul class="panel rows">${list.map(branchRow).join('')}</ul>` : `<div class="panel empty"><p class="empty__title">${t('ac.br.none')}</p><a class="btn btn--secondary" href="${href('/project/branches')}">${t('pb.clear')}</a></div>`}
      ${d.truncated ? `<p class="list-foot">${t('ac.br.truncated')}</p>` : ''}
    </section>
    <div class="section panel">
      ${recoveryFold(d)}
      ${remotesFold(d)}
    </div>
  </div>`;
}
screen({ id: 'S-46', path: '/project/branches', place: 'project', title: () => t('proj.branches'), render: branchesPage });
act('ac-bq', el => searchTyped(el));
act('ac-br-reload', () => { inv.problem = null; changed(); });
/** What a fetch's run says: done, or why not. */
function fetchToast(run) {
  const done = run && run.state === 'done';
  toast(done ? t('ac.br.fetched.done') : L(answerOf({ run }).reason || t('ac.br.fetched.failed')), done ? undefined : { refusal: true });
}
act('ac-fetch', async el => {
  if (el.disabled || !client || !inv.data) return;
  inv.fetching = true; refresh();
  try { const r = await client.branches.fetch((inv.data.remotes || [])[0]); fetchToast(r.run); }
  catch (e) { toast(said(e), { refusal: true }); }
  inv.fetching = false; changed();
});

/* choose the branch EAOS checks (BRN-05; G1, G9; the same choice answers DEC-03) */
function blockedRow(r) {
  const run = ac.runOf(r.id);
  return `<li class="row">${ac.glyph(run ? ac.runState(run) : 'queued')}<span class="row__main"><span class="row__title small">${esc(L(r.label))}</span></span>
            ${run && run.state === 'queued' ? `<button class="btn btn--secondary btn--sm" data-act="ac-remove" data-id="${esc(r.id)}">${t('ac.line.remove')}</button>` : `<button class="btn btn--secondary btn--sm" data-act="sheet" data-sheet="stop:${esc(r.id)}">${t('ac.ctl.stop')}</button>`}</li>`;
}
/** The choice refused while runs are in flight: each of them, to remove or stop. */
const chooseBlocked = blocked => ({
  title: esc(t('ac.br.choose.title')),
  body: `${owner()}<div class="ac-refuse" role="alert"><p><b>${t('ac.br.choose.refused')}</b></p><p class="small ink-2">${esc(L(blocked))}</p></div>
          <ul class="panel rows">${(blocked.runs || []).map(blockedRow).join('')}</ul>`,
  foot: closeFoot('close'),
});
function chooseOption(b, cur, pick) {
  const prot = !!b.protected;
  const note = prot ? L(b.protected) : b.name === cur ? t('ac.br.choose.now') : b.compare ? t('ac.br.choose.vs', { a: num(b.compare.ahead), b: num(b.compare.behind), base: b.compare.base }) : '';
  return `<label class="opt ${prot ? 'opt--off' : ''}"><input type="radio" name="ac-pick" value="${esc(b.name)}" data-change="ac-pick" data-fk="pick-${esc(b.name)}" ${pick === b.name ? 'checked' : ''} ${prot ? 'disabled' : ''}><span class="opt__dot" aria-hidden="true"></span>
        <span class="opt__text"><span class="opt__line">${code(b.name)}${prot ? icon('lock', 'icon--sm muted') : ''}</span><span class="opt__note">${esc(note)}</span></span></label>`;
}
function waitsNote() {
  const waits = store.awaiting()[0];
  return waits ? `<p class="small ink-2">${t('ac.br.choose.waiting', { b: code(waits.result.branch) })} <a class="link" href="${href('/waiting/' + enc(waits.id))}" data-act="go" data-href="${href('/waiting/' + enc(waits.id))}">${t('ac.run.r12.decide')}</a></p>` : '';
}
sheet('choose-branch', {
  kind: 'dialog',
  render(arg, query, own) {
    const d = inventory(inv.base);
    if (!d) return { title: esc(t('ac.br.choose.title')), body: `<p class="small muted" aria-busy="true">${t('st.loading')}</p>` };
    const cur = (d.context.analysis && d.context.analysis.branch) || '';
    const pick = own.pick || arg || cur;
    if (own.blocked) return chooseBlocked(own.blocked);
    const opts = d.branches.filter(b => b.kind === 'local' && !b.work).map(b => chooseOption(b, cur, pick)).join('');
    return {
      title: esc(t('ac.br.choose.title')),
      body: `${owner()}<p>${t('ac.br.choose.lede')}</p>
        <div class="opts" role="radiogroup" aria-label="${esc(t('ac.br.choose.title'))}">${opts}</div>
        <div class="toggle-row"><span><span style="display:block">${t('ac.br.choose.check')}</span><span class="small muted">${t('ac.br.choose.check.note')}</span></span>
          <span class="switch"><input type="checkbox" data-change="ac-pick-scan" data-fk="pick-check" ${own.scan !== false ? 'checked' : ''} aria-label="${esc(t('ac.br.choose.check'))}"><span class="switch__track"></span><span class="switch__thumb"></span></span></div>
        ${waitsNote()}`,
      foot: `${alert(own.refused)}<div class="sheet__foot-row"><button class="btn btn--secondary" data-act="sheet-close" data-autofocus>${t('cancel')}</button>
        <button class="btn btn--primary" data-act="ac-choose" data-fk="choose-do" ${pick === cur || own.busy ? `disabled title="${esc(t('ac.br.choose.same'))}"` : ''}>${icon('seal')}${esc(t('ac.br.choose.do', { b: pick }))}</button></div>`,
    };
  },
});
act('ac-pick', el => { local().pick = el.value; rerenderSheet(); });
act('ac-pick-scan', el => { local().scan = el.checked; });
act('ac-analyse', el => openSheet('choose-branch:' + el.dataset.name));
const sheetArg = () => (parseHash().query.sheet || '').split(':').slice(1).join(':');
function chooseRefused(own, e) {
  own.busy = false;
  if (e instanceof ActionError && e.needs === 'in_flight') own.blocked = e.reasons[0]; else own.refused = said(e);
  rerenderSheet();
}
act('ac-choose', async el => {
  const own = local(), d = inv.data;
  const pick = own.pick || sheetArg();
  if (el.disabled || !client || !d || !pick) return;
  const row = rowOf(d, pick);
  own.busy = true; rerenderSheet();
  try {
    const r = await client.branches.select(pick, own.scan !== false, row ? row.tip : null);
    closeSheetThen(() => { toast(t('ac.br.choose.done', { b: pick, folder: (d.context.checkout && d.context.checkout.branch) || '' }), r.scan ? { link: { href: href('/activity/run/' + enc(r.scan.id)), text: t('toast.follow') } } : undefined); changed(); });
  } catch (e) { chooseRefused(own, e); }
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
const keptRows = p => `<ul class="panel rows">${p.kept.map(k => `<li class="row small" style="min-height:48px">${code(k.branch)}<span class="row__main muted">${esc(reasonsOf(k.reasons))}</span></li>`).join('')}${p.kept_branches.map(n => `<li class="row small" style="min-height:48px">${code(n)}<span class="row__main muted">${t('ac.cl.why.keeper')}</span></li>`).join('')}</ul>`;
sheet('cleanup', {
  kind: 'dialog', confirm: true,
  render(arg, query, own) {
    previewOnce(own, () => client.branches.previewCleanup());
    const p = own.preview;
    if (!p) return { title: esc(t('ac.cl.title')), body: previewing(own), foot: closeFoot('close') };
    const stays = keptRows(p);
    const goes = p.branches.length + p.worktrees.length;
    if (!goes) return { title: esc(t('ac.cl.title')), body: `<p class="h2">${t('ac.cl.nothing')}</p>${stays}`, foot: closeFoot('close') };
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
    const done = answerOf(r).deleted || [];
    closeSheetThen(() => { toast(t('ac.cl.done', { n: num(done.length) })); changed(); });
  } catch (e) { Object.assign(own, { busy: false, preview: null, asking: false, ack_cleanup: false, refused: said(e) }); rerenderSheet(); }
});

/* restore a deleted branch (BRN-09) */
const restoreBody = (r, v, taken) => `<p>${t('ac.rs.lede')}</p><dl class="facts"><dt>${t('ac.rs.tip')}</dt><dd>${code(String(r.tip).slice(0, 12))}</dd><dt>${t('ac.rs.when')}</dt><dd>${esc(fmtWhen(r.at))}</dd>
        <dt>${t('ac.rs.by')}</dt><dd>${r.run ? `<a class="link" href="${href('/activity/run/' + enc(r.run))}">${code(r.run)}</a>` : '—'}</dd></dl>
        <label class="ac-label" for="rs-name">${t('ac.rs.name')}</label><div class="field"><input id="rs-name" dir="ltr" data-fk="rs-name" data-input="ac-rs-name" value="${esc(v)}" autocomplete="off" aria-describedby="rs-note"></div>
        <p class="small ${taken ? 'ac-c-danger' : 'muted'}" id="rs-note">${t(taken ? 'ac.rs.taken' : 'ac.rs.note')}</p>`;
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
      body: restoreBody(r, v, taken),
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
    const name = answerOf(r).branch || own.name;
    mustBeDone(r, 'ac.rs.failed');
    closeSheetThen(() => { toast(t('ac.rs.done', { name })); changed(); });
  } catch (e) { Object.assign(own, { busy: false, refused: said(e) }); rerenderSheet(); }
});
