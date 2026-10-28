// What the branch pages and their confirm sheets share (builder A): what git says, read once per base and again after
// any change (GET /api/branches, GET /api/branches/detail, the free merge preview), and the marks they draw a branch
// and a confirm sheet with.
import { t, L, num, esc, icon, code, href, refresh, rerenderSheet, local, act, chk, expiresAt, store, client, ActionError, ac, skeletonRows } from 'eaos';

export const enc = encodeURIComponent;
export const said = e => (e instanceof ActionError ? e.message : String(e));
export const reasonsOf = list => (list || []).map(r => L(r)).join(' ');
export const projBack = () => `<a class="back" href="${href('/status', { sheet: 'project' })}">${icon('back', 'icon--dir')}${t('proj.title')}</a>`;

/* ---------- what git says, read once per base and again after any change ---------- */
export const inv = { base: null, data: null, reading: false, problem: null, details: {} };
const sameBase = base => inv.data && inv.base === (base || null);
export function inventory(base) {
  if (!client) return null;
  if (sameBase(base)) return inv.data;
  if (!inv.reading) {
    inv.reading = true;
    client.branches.inventory(base || undefined).then(d => { Object.assign(inv, { data: d, base: base || null, reading: false, problem: null }); refresh(); },
      e => { Object.assign(inv, { reading: false, problem: e }); refresh(); });
  }
  return sameBase(base) ? inv.data : null;
}
const keyOf = (name, kind, remote) => `${kind || 'local'}:${remote || ''}:${name}`;
export function detail(name, kind, remote) {
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
export function mergeTry(b) {
  const k = b.name + '@' + b.tip;
  if (k in tried) return tried[k];
  tried[k] = null;
  client.branches.previewMerge(b.name).then(p => { tried[k] = p; refresh(); }, () => {});
  return null;
}
export const problemOf = (name, kind, remote) => (inv.details[keyOf(name, kind, remote)] || {}).problem;
/** The local branches protected now (null while git is asked). */
export function protectedNames() { const d = inventory(inv.base); return d ? d.branches.filter(b => b.kind === 'local' && b.protected).map(b => b.name) : null; }
/** After a change to the branches: everything read again, the runs too. */
export function changed() { inv.data = null; inv.details = {}; store.refresh(); store.refreshFreshness(); refresh(); }

const sameRow = (b, name, kind, remote) => b.name === name && b.kind === (kind || 'local') && (!remote || b.remote === remote);
export const rowOf = (d, name, kind, remote) => (d ? d.branches.find(b => sameRow(b, name, kind, remote)) : null);
export const brUrl = b => href('/project/branches/' + enc(b.name), b.kind === 'remote' ? { kind: 'remote', remote: b.remote } : {});
export const liveName = b => (b.kind === 'remote' ? `${b.remote}/${b.name}` : b.name);
export const waitingRun = name => store.awaiting().find(r => r.result && r.result.branch === name) || null;
export function aheadBehind(b) {
  const c = b.compare;
  if (!c) return '';
  if (b.name === c.base && b.kind === 'local') return esc(t('ac.br.is_base'));
  if (c.merged && !c.ahead) return t('ac.br.merged_into', { b: code(c.base) });
  if (!c.ahead && !c.behind) return t('ac.br.same_as', { b: code(c.base) });
  return esc(t('ac.br.ab', { a: num(c.ahead), b: num(c.behind) })) + ' ' + code(c.base);
}
export function whoLine(b) {
  const o = b.ownership || {};
  if (o.owner === 'eaos' || o.owner === 'shared') {
    const waits = waitingRun(b.name);
    const base = o.kind === 'wave' ? t(waits ? 'ac.br.who.eaos.waits' : 'ac.br.who.eaos', { n: num(o.wave) }) : t('ac.br.who.eaos.run');
    return esc(o.owner === 'shared' ? base + ' ' + t('ac.br.who.shared', { n: num(o.foreign_commits || 0) }) : base);
  }
  return esc(t('ac.br.who.unknown'));
}
/* a branch's role tags, in this order */
const ROLE_TAGS = [
  ['checkout', () => `<span class="tag tag--state">${icon('folder')}${t('ac.br.r.folder')}</span>`],
  ['analysis', () => `<span class="tag tag--live">${t('ac.br.r.analysed')}</span>`],
  ['report', () => `<span class="tag tag--state">${t('ac.br.r.report')}</span>`],
  ['default', () => `<span class="tag tag--state">${t('ac.br.r.default')}</span>`],
];
export function roleTags(b) {
  const r = b.roles || [];
  const tags = ROLE_TAGS.filter(([role]) => r.includes(role)).map(([, tag]) => tag());
  if (b.protected) tags.push(`<span class="tag tag--owner">${icon('lock')}${t('ac.br.r.protected')}</span>`);
  if (waitingRun(b.name)) tags.push(`<span class="tag tag--you">${t('who.you')}</span>`);
  if (b.kind === 'remote') tags.push(`<span class="tag tag--eaos">${esc(t('ac.br.r.remote', { r: b.remote }))}</span>`);
  return tags.join('');
}
export const conflictOf = cmd => cmd && (cmd.blocked || []).some(r => r.code === 'conflict');
export function checksLine(ch) {
  if (!ch || ch.status === 'not_recorded') return ac.nmTag(t('ac.br.checks.none'));
  return ac.mark(ch.status === 'passed' ? 'ok' : ch.status === 'failed' ? 'failed' : 'skipped', esc(ch.summary || ch.status));
}
/** The branch a sheet's argument names: `<name>` or `<remote>/<name>` for a remote copy. */
export function sheetBranch(arg, remote) {
  if (!remote) return { name: arg, kind: 'local', remote: null };
  const i = arg.indexOf('/');
  return { name: arg.slice(i + 1), kind: 'remote', remote: arg.slice(0, i) };
}

/* ---------- the confirm sheets' parts ---------- */
export function owner() { return `<div class="owner-band">${icon('seal')}<span><b>${t('owner.only')}</b>${t('cf.band')}</span></div>`; }
export function ack(kind, text, on) { return `<label class="ack">${chk(`data-change="ac-ack" data-kind="${kind}" data-fk="ack-${kind}"`, !!on, text)}<span class="ack__text">${text}</span></label>`; }
act('ac-ack', el => { local()['ack_' + el.dataset.kind] = el.checked; rerenderSheet(); });
export const valid = c => (c ? `<p class="sheet__fine">${esc(t('cf.valid', { time: expiresAt(c.expires) }))}</p>` : '');
export const alert = text => (text ? `<p class="small" role="alert" style="color:var(--danger)">${icon('warn', 'icon--sm')} ${esc(text)}</p>` : '');
export const loadingRows = () => skeletonRows(3, [45, 70], { cls: 'section' });
/** A sheet's one closing button: `word` is close or cancel. */
export const closeFoot = word => `<button class="btn btn--secondary btn--block" data-act="sheet-close" data-autofocus>${t(word)}</button>`;
/** While the free preview is asked: why it could not be, or that it is being asked. */
export const previewing = own => (own.problem ? alert(own.problem) : `<p class="small muted" aria-busy="true">${t('cf.previewing')}</p>`);
/** A confirm sheet's free preview, asked once: `own.preview`, or `own.problem` when it could not be made. */
export function previewOnce(own, ask) {
  if (own.preview || own.asking || own.problem || !client) return;
  own.asking = true;
  ask().then(p => { own.preview = p; own.asking = false; rerenderSheet(); }, e => { own.asking = false; own.problem = said(e); rerenderSheet(); });
}
/** What the run an act started answered (empty when it did not). */
export const answerOf = r => (r.run && r.run.result && r.run.result.answer) || {};
/** Throws why the run an act started did not finish (`fallback` when it does not say). */
export function mustBeDone(r, fallback) {
  if (r.run && r.run.state !== 'done') throw new Error(L(r.run.result && r.run.result.answer && r.run.result.answer.reason) || t(fallback));
}
