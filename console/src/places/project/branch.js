// S-47 one branch (builder A): PRJ-05, BRN-04, BRN-06..08, BRN-10. One branch's commits, files, diff, recorded checks,
// runs and every command with why it is blocked (GET /api/branches/detail); its owner-only confirm sheets, each opened
// on its own free preview whose confirm token the act spends: merge, delete here or on the remote, protect, unprotect,
// propose a conflict's resolution. What it shares with S-46: git.js.
import {
  t, tn, L, num, esc, icon, code, rich, diffLines, href, fmtWhen, screen, sheet, act, rerenderSheet, local, toast, closeSheetThen,
  live, store, client, ActionError, ac,
  rowWords,
  lockLine, radio,
  facts,
  titledBlock, titledSection,
  notFound, refusal,
  openLiveButton, pageHead,
} from 'eaos';
import {
  enc, said, reasonsOf, inv, inventory, detail, mergeTry, problemOf, changed, liveName, waitingRun, aheadBehind, whoLine, roleTags,
  conflictOf, checksLine, sheetBranch, owner, ack, valid, alert, loadingRows, closeFoot, previewing, previewOnce, mustBeDone,
} from './git.js';

/* =================================================================================================================
   S-47 ONE BRANCH (BRN-04, BRN-06, BRN-07, BRN-08, BRN-10)
   ================================================================================================================= */
const targetOf = det => (det.destination && det.destination.recommended) || '';
function protectCommand(b) {
  if (b.protected) return ['unprotect', !['default', 'eaos_main'].includes(b.protected.code), L(b.protected)];
  return b.work ? ['protect', false, t('ac.cmd.protect.eaos')] : ['protect', true, ''];
}
/** Every command of the branch: [id, available, why not]; EAOS's own waiting branch is decided on its waiting page. */
function commands(b, det) {
  const c = det.commands || {};
  const out = [];
  const offer = (id, cmd) => [id, cmd.available, reasonsOf(cmd.blocked)];
  const waits = waitingRun(b.name);
  const held = (id, cmd, why) => (waits ? [id, false, t(why)] : offer(id, cmd));
  if (c.select_analysis) out.push(offer('check', c.select_analysis));
  if (c.merge) out.push(held('merge', c.merge, 'ac.cmd.merge.eaos'));
  if (b.kind === 'local' && conflictOf(c.merge) && !waits) out.push(['resolve', true, '']);
  if (c.delete_local) out.push(held('delete', c.delete_local, 'ac.cmd.del.eaos'));
  if (c.delete_remote) out.push(offer('delete-remote', c.delete_remote));
  if (b.kind === 'local') out.push(protectCommand(b));
  return out;
}
const CMD_ICON = { protect: 'seal', unprotect: 'seal', merge: 'branch', resolve: 'ai', check: 'retry' };
function cmdButton(b, cmd, det) {
  const [id, ok, why] = cmd;
  const target = targetOf(det);
  const label = t('ac.cmd.' + id, { t: target, r: b.remote || '' });
  const ic = CMD_ICON[id] || 'minus';
  if (!ok) return `<li class="row ac-cmd">${icon(ic === 'seal' ? 'lock' : ic, 'muted')}${rowWords(esc(label), esc(t('ac.cmd.not', { why })), { title: 'ac-c-muted' })}</li>`;
  const arg = b.kind === 'remote' ? `${b.remote}/${b.name}` : b.name;
  const attrs = id === 'check' ? `data-act="ac-analyse" data-name="${esc(b.name)}"` : `data-act="sheet" data-sheet="${esc(id + ':' + arg)}"`;
  return `<li><button class="row ac-cmd" ${attrs}>${icon(ic, id.startsWith('delete') ? 'ac-c-danger' : 'ac-c-accent')}
    ${rowWords(esc(label), esc(t('ac.cmd.' + id + '.sub', { t: target, r: b.remote || '' })))}${icon('chev', 'icon--sm icon--dir muted')}</button></li>`;
}
const branchLede = (b, det, waits) => (waits ? t('ac.br1.lede.eaos', { b: code(b.name) }) : b.protected ? t('ac.br1.lede.protected', { b: code(liveName(b)) })
  : (b.roles || []).includes('analysis') ? t('ac.br1.lede.analysed', { b: code(b.name) }) : b.compare && b.compare.merged && !b.compare.ahead ? t('ac.br1.lede.merged', { b: code(liveName(b)), t: code(b.compare.base) })
    : t('ac.br1.lede', { b: code(liveName(b)), a: num(b.compare ? b.compare.ahead : 0), base: code(det.base || '') }));
const mainAction = (b, waits, primary, target) => (waits ? `<div class="actions"><a class="btn btn--primary" href="${href('/waiting/' + enc(waits.id))}">${icon('seal')}${t('ac.run.r12.decide')}</a><p class="actions__note">${t('ac.br1.eaos.note')}</p></div>`
  : primary ? `<div class="actions"><button class="btn btn--primary" data-act="sheet" data-sheet="merge:${esc(b.name)}">${icon('seal')}${esc(t('ac.cmd.merge', { t: target }))}</button><p class="actions__note">${t('ac.br1.merge.note')}</p></div>` : '');
/** The conflicts a trial merge found, when the merge is the page's press (`tries`). */
function clashNote(b, tries, target) {
  const trial = tries && b.kind === 'local' ? mergeTry(b) : null;
  const clash = trial && (trial.conflicts || []).length ? trial.conflicts : null;
  return clash ? `<div class="ac-note ac-note--caution mt-4">${icon('warn', 'icon--sm ac-c-caution')}<span class="small">${esc(tn('ac.br1.clash', clash.length, { t: trial.target || target }))}</span>
      <button class="btn btn--secondary btn--sm" data-act="sheet" data-sheet="resolve:${esc(b.name)}">${icon('ai')}${t('ac.cmd.resolve')}</button></div>` : '';
}
/** The merge's warnings: the conflicts a trial merge found (`tries`: the merge is the page's press), or why it is blocked. */
function mergeNotes(b, det, merge, tries, target) {
  const conflict = merge && conflictOf({ blocked: (det.commands.merge || {}).blocked });
  return `${clashNote(b, tries, target)}
    ${conflict ? `<div class="mt-4"><div class="ac-note ac-note--caution">${icon('warn', 'icon--sm ac-c-caution')}<span class="small">${esc(reasonsOf(det.commands.merge.blocked))}</span></div></div>` : ''}`;
}
function whereFact(b) {
  if (b.kind !== 'local') return t('ac.br1.remote_only', { r: code(b.remote) });
  return t('ac.br1.local') + (b.upstream ? `, ${t('ac.br1.tracks', { u: code(b.upstream) })}${b.tracking ? ` <span class="small muted">${esc(b.tracking)}</span>` : ''}` : '');
}
function branchFacts(b, det, target) {
  return titledSection('bf-h', t('ac.br1.facts'), `
      <div class="panel panel__pad">${facts([[t('ac.br1.tip'), `${code(String(b.tip).slice(0, 7))} <span class="small ink-2">${rich(b.subject || '')}</span> <span class="small muted">${esc(fmtWhen(b.last_commit))}</span>`], [t('ac.br1.where'), whereFact(b)], [t('ac.br1.vs'), aheadBehind(b)], [t('ac.br1.who'), whoLine(b)], b.protected ? `<dt>${t('ac.br.r.protected')}</dt><dd>${esc(L(b.protected))}</dd>` : '', [t('ac.br1.wt'), b.worktree ? `${code(b.worktree.path)} ${t(b.worktree.current ? 'ac.br.wt.here' : 'ac.br.wt.other')}` : t('ac.br1.wt.none')], [t('ac.br1.checks'), checksLine(det.checks)], det.lineage && det.lineage.parent ? `<dt>${t('ac.br1.lineage')}</dt><dd>${t('ac.br1.lineage.v', { p: code(det.lineage.parent), c: code(String(det.lineage.parent_commit || '').slice(0, 7)) })}</dd>` : '', [t('ac.br1.dest'), target ? t('ac.br1.dest.v', { t: code(target) }) : '—']], 'ac-facts')}</div>`);
}
function branchPage(ctx) {
  const name = ctx.params.name, kind = ctx.query.kind || 'local', remote = ctx.query.remote || null;
  const back = `<a class="back" href="${href('/project/branches')}">${icon('back', 'icon--dir')}${t('proj.branches')}</a>`;
  if (ctx.offline) return `<div class="page">${back}${pageHead(t('ac.br.offline.lede'), null, openLiveButton())}</div>`;
  const det = client && detail(name, kind, remote);
  const problem = problemOf(name, kind, remote);
  if (problem) {
    return `<div class="page">${back}${notFound(esc(t('ac.br.notfound', { name })), t('ac.br.notfound.guide'), `<a class="btn btn--secondary" href="${href('/project/branches')}">${t('proj.branches')}</a>`)}</div>`;
  }
  if (!det) return `<div class="page" aria-busy="true">${back}<h1 class="lede">${t('ac.br.loading')}</h1>${loadingRows()}</div>`;
  return branchHTML(det, back);
}
function branchHTML(det, back) {
  const b = det.branch, cmds = commands(b, det);
  const target = targetOf(det), waits = waitingRun(b.name);
  const merge = cmds.find(c => c[0] === 'merge'), primary = merge && merge[1] ? merge : null;
  return `<div class="page">
    ${back}
    <div class="context"><bdi class="mono" style="align-self:center;font-weight:500">${esc(liveName(b))}</bdi>${roleTags(b)}</div>
    ${pageHead(branchLede(b, det, waits), t(waits ? 'ac.br1.guide.eaos' : 'ac.br1.guide'))}
    ${mainAction(b, waits, primary, target)}
    ${mergeNotes(b, det, merge, primary && !waits, target)}
    ${titledSection('cmd-h', t('ac.br1.cmds'), `<ul class="panel rows">${cmds.filter(c => c !== primary).map(c => cmdButton(b, c, det)).join('')}</ul>`)}
    ${branchFacts(b, det, target)}
    ${branchFolds(det)}
  </div>`;
}
function commitsFold(det) {
  const commits = det.commits || [];
  return ac.fold('commits', t('ac.br1.commits', { base: det.base || '' }), esc(commits.length ? tn('ac.pl.commit', commits.length) : t('ac.br1.commits.none')),
        commits.length ? `<ul class="rows">${commits.map(c => `<li class="row" style="padding-inline:0;min-height:48px">${code(String(c.commit).slice(0, 7))}<span class="row__main small">${rich(c.subject)}<span class="row__meta" style="display:block">${esc(c.author || '')}, ${esc(fmtWhen(c.at))}</span></span></li>`).join('')}</ul>
          ${det.commits_truncated ? `<p class="small muted">${t('ac.br1.more.cut')}</p>` : ''}` : `<p class="small muted">${t('ac.br1.commits.none')}</p>`);
}
const fileStatus = f => (['M', 'A', 'D'].includes(f.status[0]) ? f.status[0] : 'M');
function filesFold(det) {
  const files = det.files || [];
  return ac.fold('files', t('ac.br1.files'), esc(files.length ? tn('pl.file', det.files_total || files.length) : t('ac.br1.files.none')),
        files.length ? `<ul class="rows">${files.map(f => `<li class="row" style="padding-inline:0;min-height:44px"><span class="tag tag--state">${esc(t('ac.br1.fs.' + fileStatus(f)))}</span><bdi class="mono">${esc(f.path)}</bdi></li>`).join('')}</ul>` : `<p class="small muted">${t('ac.br1.files.none')}</p>`);
}
const diffFold = det => ac.fold('diff', t('ac.br1.diff'), t('ac.br1.diff.sum'), det.diff ? `<div class="code diff">${diffLines(det.diff.split('\n').slice(0, 400))}</div>${det.diff_cut ? `<p class="small muted">${t('wt.fix.cut')}</p>` : ''}` : `<p class="small muted">${t('ac.br1.diff.none')}</p>`);
function runsFold(det) {
  const runs = det.runs || [];
  return ac.fold('runs', t('ac.br1.runs'), esc(runs.length ? tn('ac.pl.run', runs.length) : t('ac.br1.runs.none')),
        runs.length ? `<ul class="rows">${runs.map(r => `<li><a class="row" style="padding-inline:0" href="${href('/activity/run/' + enc(r.id))}">${ac.glyph(r.state === 'waiting_for_person' ? 'you' : r.state)}<span class="row__main small">${esc(L(r.label))}</span><span class="small muted">${esc(fmtWhen(r.created))}</span></a></li>`).join('')}</ul>` : `<p class="small muted">${t('ac.br1.runs.none')}</p>`);
}
function branchFolds(det) {
  return `<div class="section panel">
      ${commitsFold(det)}
      ${filesFold(det)}
      ${diffFold(det)}
      ${runsFold(det)}
    </div>`;
}
screen({ id: 'S-47', path: '/project/branches/:name', place: 'project', title: ctx => ctx.params.name + ' - ' + t('proj.branches'), render: branchPage });

/* merge, its preview inside the confirm sheet (BRN-06; G1, G2, G4, G8, G11) */
function mergeInto(name, p) {
  const d = inventory(inv.base);
  const targets = d ? d.branches.filter(b => b.kind === 'local' && b.name !== name) : [];
  return `<div class="opts" role="radiogroup" aria-labelledby="mg-into">${targets.slice(0, 12).map(b => radio({ name: 'mg-into', value: b.name, 'data-change': 'ac-mg-into', 'data-fk': `mg-${b.name}`, checked: b.name === p.target, disabled: !!b.protected },
      lockLine(code(b.name), b.protected), esc(b.protected ? L(b.protected) : b.name === p.recommended_target ? t('ac.mg.recommended') : ''))).join('')}</div>`;
}
function mergeBody(name, p, into) {
  return `${owner()}<p>${t('ac.mg.lede', { b: code(name), t: code(p.target) })}</p>
        ${p.blocked.length ? refusal(t('ac.mg.refused'), [esc(reasonsOf(p.blocked)), p.conflicts.length && p.conflicts.map(code).join(' ')]) : ''}
        <div><div class="block-title" id="mg-into">${t('cf.into')}</div>${into}</div>
        ${facts([[t('ac.mg.how'), t(p.path === 'accept' ? 'ac.mg.how.accept' : 'ac.mg.how.v')], [t('ac.mg.ff'), t(p.fast_forward ? 'ac.mg.ff.yes' : 'ac.mg.ff.merge')], [t('ac.mg.heads'), `${code(String(p.source_head).slice(0, 7))} → ${code(String(p.target_head).slice(0, 7))}`], [t('ac.mg.commits'), esc(tn('ac.pl.commit', p.commits.length))], [t('cf.files'), esc(tn('pl.file', p.files.length))], [t('ac.mg.conflicts'), p.conflicts.length ? ac.mark('failed', esc(tn('pl.file', p.conflicts.length))) : ac.mark('ok', t('ac.mg.conflicts.none'))], [t('cf.checks'), checksLine(p.checks)]])}`;
}
const mergeReady = (p, own) => !p.blocked.length && p.confirm && own.ack_merge && (!p.needs_unchecked_ack || own.ack_merge2) && !own.busy;
function mergeFoot(name, p, own) {
  const blocked = p.blocked.length;
  return `${alert(own.refused)}${blocked ? '' : ack('merge', t('cf.ack.accept'), own.ack_merge) + (p.needs_unchecked_ack ? ack('merge2', t('ac.mg.ack.unchecked'), own.ack_merge2) : '')}<div class="sheet__foot-row">
          <button class="btn btn--secondary" data-act="sheet-close" data-autofocus>${t('cancel')}</button>
          ${p.conflicts.length ? `<button class="btn btn--primary" data-act="sheet" data-sheet="resolve:${esc(name)}">${icon('ai')}${t('ac.cmd.resolve')}</button>`
            : blocked ? `<button class="btn btn--primary" data-act="ac-mg-again">${t('ac.mg.preview_again')}</button>`
              : `<button class="btn btn--primary" data-act="ac-merge" data-fk="mg-do" ${mergeReady(p, own) ? '' : 'disabled'} title="${esc(own.ack_merge ? '' : t('cf.need_ack'))}">${icon('seal')}${esc(t('ac.mg.do', { t: p.target }))}</button>`}</div>${valid(p.confirm)}`;
}
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
    if (!p) return { title, body: `${owner()}${previewing(own)}`, foot: closeFoot('cancel') };
    const into = mergeInto(name, p);
    return { title, body: mergeBody(name, p, into), foot: mergeFoot(name, p, own) };
  },
});
act('ac-mg-into', el => { const own = local(); own.ack_merge = own.ack_merge2 = false; own.ask(el.value); rerenderSheet(); });
act('ac-mg-again', () => { const own = local(); own.ask(own.target); rerenderSheet(); });
function mergeRefused(own, e) {
  Object.assign(own, { busy: false, ack_merge: false, ack_merge2: false, refused: said(e) });
  if (e instanceof ActionError && ['refresh', 'confirm'].includes(e.needs)) own.ask(own.target);
  rerenderSheet();
}
act('ac-merge', async el => {
  const own = local(), p = own.preview;
  if (el.disabled || !p) return;
  own.busy = true; rerenderSheet();
  try {
    const r = await client.branches.merge(p, !!own.ack_merge2);
    mustBeDone(r, 'ac.mg.failed');
    closeSheetThen(() => { toast(t('ac.mg.done', { b: p.source, t: p.target })); changed(); });
  } catch (e) { mergeRefused(own, e); }
});

/* delete here or on the remote (BRN-08; G10: a recovery point first, a second consent for commits only it holds) */
function localLoss(p, lost) {
  return `<dt>${t('ac.dl.lost')}</dt><dd>${p.unmerged ? esc(t('ac.dl.only', { n: tn('ac.pl.commit', lost.length) })) : t('ac.dl.nothing', { b: (p.merged_into || []).slice(0, 3).map(code).join(' ') })}</dd>
              ${p.worktree ? `<dt>${t('ac.br1.wt')}</dt><dd>${t('ac.dl.wt', { p: code(p.worktree) })}</dd>` : ''}`;
}
function deleteBody(remote, br, p, lost) {
  return `${owner()}<p>${t(remote ? 'ac.dl.lede.remote' : 'ac.dl.lede', { b: code(br.name), r: code(br.remote || 'origin') })}</p>
          ${facts([[t('ac.br1.who'), esc(L(p.whose))], remote ? `<dt>${t('ac.dl.other')}</dt><dd>${t(p.local_kept ? 'ac.dl.other.local' : 'ac.dl.other.nolocal')}</dd>`
              : localLoss(p, lost)])}
          ${lost.length ? titledBlock(t('ac.dl.only.list'), `<ul class="panel rows">${lost.map(c => `<li class="row small" style="min-height:44px">${code(String(c.commit).slice(0, 7))}<span class="row__main">${rich(c.subject || '')}</span></li>`).join('')}</ul>`) : ''}
          <p class="small ink-2">${t('ac.dl.recovery')}</p>`;
}
const deleteReady = (p, own) => p.confirm && own.ack_del && (!p.unmerged || own.ack_del2) && !own.busy;
function deleteFoot(remote, br, p, own, lost) {
  return `${alert(own.refused)}${ack('del', esc(t('ac.dl.ack', { b: br.name })), own.ack_del)}${p.unmerged ? ack('del2', esc(t('ac.dl.ack2', { n: tn('ac.pl.commit', lost.length) })), own.ack_del2) : ''}<div class="sheet__foot-row">
            <button class="btn btn--secondary" data-act="sheet-close" data-autofocus>${t('cancel')}</button>
            <button class="btn btn--danger" data-act="ac-delete" data-fk="del-do" ${deleteReady(p, own) ? '' : 'disabled'} title="${esc(own.ack_del ? '' : t('cf.need_ack'))}">${esc(t(remote ? 'ac.dl.do.remote' : 'ac.dl.do', { b: br.name, r: br.remote || '' }))}</button></div>${valid(p.confirm)}`;
}
function deleteSheet(remote) {
  return {
    kind: 'dialog', confirm: true,
    render(arg, query, own) {
      const br = sheetBranch(arg, remote);
      previewOnce(own, () => client.branches.previewDelete(br.name, remote ? 'remote' : 'local', br.remote));
      const p = own.preview;
      const title = esc(t(remote ? 'ac.dl.title.remote' : 'ac.dl.title', { b: br.name, r: br.remote || '' }));
      if (!p) return { title, body: `${owner()}${previewing(own)}`, foot: closeFoot('cancel') };
      if (p.blocked.length) return { title, body: owner() + refusal(t('ac.dl.refused'), [esc(reasonsOf(p.blocked))]), foot: closeFoot('close') };
      const lost = p.lost_commits || [];
      return { title, body: deleteBody(remote, br, p, lost), foot: deleteFoot(remote, br, p, own, lost) };
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
    mustBeDone(r, 'ac.dl.failed');
    closeSheetThen(() => { toast(t(p.where === 'remote' ? 'ac.dl.done.remote' : 'ac.dl.done', { b: p.branch, r: p.remote || '' })); changed(); if (p.where !== 'remote') location.hash = href('/project/branches'); });
  } catch (e) { Object.assign(own, { busy: false, preview: null, asking: false, ack_del: false, ack_del2: false, refused: said(e) }); rerenderSheet(); }
});

/* protect, remove the protection (BRN-10) */
const protectBody = (name, on, own) => `${owner()}<p>${t(on ? 'ac.pr.lede' : 'ac.up.lede', { b: code(name) })}</p>${on ? `<p class="small ink-2">${t('ac.pr.undo')}</p>` : ''}${own.problem ? alert(own.problem) : ''}`;
function protectFoot(name, on, own, p) {
  const ready = p && (on || own.ack_unprot) && !own.busy;
  return `${alert(own.refused)}${on ? '' : ack('unprot', t('ac.up.ack'), own.ack_unprot)}<div class="sheet__foot-row"><button class="btn btn--secondary" data-act="sheet-close" data-autofocus>${t('cancel')}</button>
          <button class="btn btn--primary" data-act="ac-protect" data-on="${on ? 1 : ''}" data-name="${esc(name)}" data-fk="prot-do" ${ready ? '' : 'disabled'}>${icon('seal')}${esc(t(on ? 'ac.pr.do' : 'ac.up.do', { b: name }))}</button></div>${p ? valid(p.confirm) : ''}`;
}
function protectSheet(on) {
  return {
    kind: 'dialog', confirm: true,
    render(name, query, own) {
      previewOnce(own, () => client.branches.previewProtect(name, on));
      return {
        title: esc(t(on ? 'ac.pr.title' : 'ac.up.title', { b: name })),
        body: protectBody(name, on, own),
        foot: protectFoot(name, on, own, own.preview),
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
function pickOf(own, assistants) {
  const ready = assistants.filter(a => a.installed && a.logged_in);
  return own.asst || (ready[0] && ready[0].id) || 'handoff';
}
function asstOption(a, pick) {
  const ok = a.installed && a.logged_in;
  return radio({ name: 'rv-asst', value: a.id, 'data-change': 'ac-rv-asst', 'data-fk': `rv-${a.id}`, checked: pick === a.id, disabled: !ok }, esc(a.name), t(ok ? 'pv.ready' : a.installed ? 'pv.notsigned' : 'pv.notinstalled'));
}
function resolveFiles(p, own, conflicts) {
  if (!p) return previewing(own);
  return conflicts.length ? titledBlock(t('ac.rv.files'), `<ul class="panel rows">${conflicts.map(f => `<li class="row small" style="min-height:44px">${icon('file', 'icon--sm muted')}<bdi class="mono">${esc(f)}</bdi></li>`).join('')}</ul>`) : `<p class="small ink-2" role="note">${t('ac.rv.none')}</p>`;
}
sheet('resolve', {
  kind: 'drawer',
  render(name, query, own) {
    previewOnce(own, () => client.branches.previewMerge(name));
    const p = own.preview;
    const assistants = live.assistants || [];
    const pick = pickOf(own, assistants);
    const conflicts = p ? p.conflicts : [];
    return {
      title: esc(t('ac.rv.title', { b: name })),
      sub: `<span class="free-band">${icon('check', 'icon--sm')}${t('free')}</span>`,
      body: `<p>${t('ac.rv.does', { t: code(p ? p.target : '') })}</p>
        ${resolveFiles(p, own, conflicts)}
        ${facts([[t('pv.risk'), `<span class="tag tag--state">${t('pv.risk.low')}</span> <span class="small ink-2">${t('ac.rv.risk')}</span>`]])}
        ${titledBlock(t('pv.who'), `<div class="opts">${assistants.map(a => asstOption(a, pick)).join('')}
          ${radio({ name: 'rv-asst', value: 'handoff', 'data-change': 'ac-rv-asst', 'data-fk': 'rv-handoff', checked: pick === 'handoff' }, t('ac.who.handoff'), t('pv.handoff'))}</div>`)}
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
