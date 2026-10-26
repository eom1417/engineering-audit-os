// The frame around every screen: the phone's top bar and tab bar, the desktop's sidebar (places, the live card, language and theme, the version), the one banner (read-only copy, stale, reconnecting, loading), the
// live strip while something runs or waits for the owner, and the selection bar.
import { prefs } from './prefs.js';
import { t, tn, num } from './i18n.js';
import { esc, icon, fmtWhen, fmtTime } from './format.js';
import { href, parseHash } from './address.js';
import { picked } from '../data/selection.js';
import { listed, manifest, mode, pendingOf } from '../data/source.js';
import { active, live } from '../data/store.js';
import { labelOf } from '../data/derive.js';
import { project, waitingCount } from '../data/model.js';

const PLACES = [
  { id: 'status', path: '/status', icon: 'status' },
  { id: 'waiting', path: '/waiting', icon: 'waiting' },
  { id: 'problems', path: '/problems', icon: 'problems' },
  { id: 'activity', path: '/activity', icon: 'activity' },
  { id: 'report', path: '/report', icon: 'understand' },
];

/** What runs or waits now, for the live strip, the sidebar's card and Status: {kind: check | fix | run | signin,
 *  text, href, share (0..1 or null), you (it waits for the owner), run}; null when nothing does. */
const DONE_STATES = ['ok', 'skipped', 'unavailable', 'failed'];
const finishedOf = stages => stages.filter(s => DONE_STATES.includes(s.state)).length;
// what the sidebar says about a run in progress
function runText(run, isCheck, stages, check) {
  const label = labelOf(run.label, prefs.lang);
  if (run.state === 'waiting_for_person') return t('live.you', { label });
  if (run.state === 'paused') return t('live.paused', { label });
  if (isCheck && stages.length) return t('live.check', { done: num(finishedOf(stages)), total: num(stages.length) }) + left(check);
  return t(run.verb === 'fix' || /^fix/.test(run.action) ? 'live.fixing' : 'live.run', { label });
}
// the live line for a run in progress
function runNow(run, check) {
  const isCheck = run.action === 'audit';
  const stages = isCheck && check ? check.stages || [] : [];
  const share = stages.length ? finishedOf(stages) / stages.length : null;
  const text = runText(run, isCheck, stages, check);
  return { kind: isCheck ? 'check' : run.verb === 'fix' ? 'fix' : 'run', you: run.state === 'waiting_for_person', href: `/activity/run/${encodeURIComponent(run.id)}`, share, text, run };
}
export function liveNow() {
  if (live.signIn && live.signIn.asked) return { kind: 'signin', you: true, href: '/waiting/sign-in', share: null, text: t('live.signin') };
  const run = active();
  const check = live.progress && live.progress.flows && live.progress.flows.check;
  if (run) return runNow(run, check);
  if (check && check.state === 'running') {
    const stages = check.stages || [];
    const finished = finishedOf(stages);
    return { kind: 'check', you: false, href: '/activity', share: stages.length ? finished / stages.length : null,
      text: t('live.check', { done: num(finished), total: num(stages.length) }) + left(check) };
  }
  return null;
}
function left(check) {
  const e = check && check.estimate;
  return e && e.low != null && e.high != null ? t('live.left', { lo: num(Math.max(1, Math.round(e.low / 60))), hi: num(Math.max(1, Math.round(e.high / 60))) }) : '';
}

function projectButton() {
  const p = project();
  return `<button class="project-btn" data-act="sheet" data-sheet="project" aria-label="${esc(t('project.menu'))}" aria-haspopup="dialog">
    <span class="project-btn__mark" aria-hidden="true">${esc((p.name || 'E').slice(0, 1).toUpperCase())}</span>
    <span class="project-btn__text"><span class="project-btn__name">${esc(p.name || 'EAOS')}</span><span class="project-btn__branch">${esc(p.branch)}</span></span>
    ${icon('chev-down', 'icon--sm muted')}
  </button>`;
}

function connection() {
  if (mode !== 'live') return t('live.copy');
  return live.feed === 'reconnecting' || live.feed === 'refused' ? t('live.lost') : t('live.ok');
}

/** A place's link attributes: the current one, and Waiting's spoken count. */
function placeAttrs(p, place, wc) {
  const label = p.id === 'waiting' ? `aria-label="${esc(wc ? `${t('nav.waiting')}, ${tn('pl.thing_waits', wc)}` : t('nav.waiting'))}"` : '';
  return `${place === p.id ? 'aria-current="page"' : ''} ${label}`;
}
const placeCount = (p, wc) => (p.id === 'waiting' && wc ? `<span class="count" aria-hidden="true">${num(wc)}</span>` : '');

/** The sidebar's card of what runs or waits now. */
function liveCard() {
  const now = liveNow();
  return now ? `<a class="side-live ${now.you ? 'side-live--you' : ''}" href="${href(now.href)}">
      <span class="side-live__top"><span class="dot ${now.you ? 'dot--you' : 'dot--live'}"></span>${esc(now.text)}</span>
      ${now.share != null ? `<span class="side-live__bar"><i style="transform:scaleX(${now.share})"></i></span>` : ''}</a>` : '';
}

function sidePrefs() {
  const dark = prefs.theme === 'dark';
  return `<div class="side-prefs">
        <div class="seg" role="group" aria-label="${esc(t('lang.label'))}">
          <button type="button" data-act="lang" data-lang="ar" aria-pressed="${prefs.lang === 'ar'}" lang="ar">${t('lang.ar')}</button>
          <button type="button" data-act="lang" data-lang="en" aria-pressed="${prefs.lang === 'en'}" lang="en">${t('lang.en')}</button>
        </div>
        <button class="btn btn--icon" data-act="theme" aria-label="${esc(t('theme.switch'))}: ${esc(t(dark ? 'theme.light' : 'theme.dark'))}">${icon(dark ? 'sun' : 'moon')}</button>
      </div>`;
}

export function renderShell(place) {
  document.querySelector('.skip').textContent = t('skip');
  const wc = waitingCount();
  document.getElementById('topbar').innerHTML = `${projectButton()}
    <div class="topbar__end"><button class="btn btn--icon" data-act="sheet" data-sheet="search" aria-label="${esc(t('search.open'))}">${icon('search', 'icon--lg')}</button></div>`;
  const tabbar = document.getElementById('tabbar');
  tabbar.setAttribute('aria-label', t('nav.label'));
  tabbar.innerHTML = PLACES.map(p => `<a class="tab" href="${href(p.path)}" ${placeAttrs(p, place, wc)}>
      <span class="tab__icon">${icon(p.icon, 'icon--lg')}${placeCount(p, wc)}</span>
      <span>${t('nav.' + p.id)}</span></a>`).join('');
  document.getElementById('sidebar').innerHTML = `${projectButton()}
    <button class="side-search" data-act="sheet" data-sheet="search">${icon('search')}<span>${t('search.open')}</span><kbd>${t('search.kbd')}</kbd></button>
    <nav class="side-nav" aria-label="${esc(t('nav.label'))}">
      ${PLACES.map(p => `<a href="${href(p.path)}" ${placeAttrs(p, place, wc)}>${icon(p.icon)}<span>${t(p.id === 'waiting' ? 'nav.waiting.long' : 'nav.' + p.id)}</span>${placeCount(p, wc)}</a>`).join('')}
    </nav>
    <div class="side-foot">
      ${liveCard()}
      ${sidePrefs()}
      <div class="side-ver"><span class="dot" aria-hidden="true"></span>${esc(connection())}<span>${esc(t('version', { v: live.version || project().eaos_version || '' }))}</span></div>
    </div>`;
  document.body.classList.toggle('has-selection', picked.ids.size > 0);
}

export function renderStrip() {
  const el = document.getElementById('strip');
  const now = liveNow();
  // no strip on a page that already shows the same work (its run, Activity's Now, the sign-in under Waiting)
  const here = parseHash().path;
  const shown = now && (here === now.href || (here === '/activity' && now.kind !== 'signin') || (now.kind === 'signin' && here.startsWith('/waiting')));
  document.body.classList.toggle('has-strip', !!now && !picked.ids.size && !shown);
  if (!now || shown) { el.innerHTML = ''; return; }
  el.innerHTML = `<a class="live-strip ${now.you ? 'live-strip--you' : ''}" href="${href(now.href)}">
    <span class="dot ${now.you ? 'dot--you' : 'dot--live'}" aria-hidden="true"></span>
    <span class="live-strip__text">${esc(now.text)}</span>
    <span class="link">${t('live.follow')}</span>${icon('chev', 'icon--sm icon--dir muted')}</a>`;
}

/** The freshness the banner and Status say: the live answer of git when there is one, else the report's own. */
export function freshness() {
  const f = live.freshness;
  if (f) return { state: f.state, behind: f.behind, branch: f.branch || f.scanned_branch, reason: f.reason };
  const p = project();
  return { state: p.freshness === 'eaos_updated' ? 'fresh' : p.freshness, behind: p.freshness_detail && p.freshness_detail.behind, branch: p.branch, reason: null };
}

export function renderBanner(ctx) {
  const el = document.getElementById('banner');
  const f = freshness();
  if (ctx.offline) {
    el.innerHTML = `<div class="banner banner--offline" role="note">${icon('lock')}<span>${esc(project().checked_at ? t('offline.banner', { when: fmtWhen(project().checked_at) }) : t('offline.banner.bare'))}</span>
      <button class="btn btn--quiet btn--sm banner__act" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button></div>`;
  } else if (ctx.query.state === 'reconnecting' || live.feed === 'reconnecting') {
    el.innerHTML = `<div class="banner banner--caution" role="status">${icon('offline')}<span>${esc(t('reconnect.banner', { time: fmtTime(new Date(live.heard || Date.now()).toISOString()) }))}</span></div>`;
  } else if (ctx.state === 'loading') {
    const all = ((manifest() && manifest().sections) || []).filter(s => listed(s.name)).length;
    el.innerHTML = `<div class="banner" role="status">${icon('clock')}<span>${esc(t('loading.banner', { n: num(pendingOf(ctx.needs.concat(['head', 'decisions'])).length), total: num(all) }))}</span></div>`;
  } else if (ctx.state !== 'empty' && (f.state === 'behind' || f.state === 'rewritten' || f.state === 'dirty')) {
    const b = f.behind || {};
    const said = f.state === 'behind' ? t('stale.banner', { commits: tn('pl.commit', b.commits || 0), files: tn('pl.file', b.files || 0), branch: f.branch || '' })
      : t('stale.' + f.state, { branch: f.branch || '' });
    el.innerHTML = `<div class="banner banner--caution" role="note">${icon('warn')}<span>${esc(said)}</span>
      <a class="btn btn--quiet btn--sm banner__act" href="${href('/activity', { sheet: 'check' })}">${t('stale.act')}</a></div>`;
  } else el.innerHTML = '';
}

/** The selection bar of the screen that selects (Problems, the plan), which names the action that clears its picks:
 *  the count, the group picked whole, and the four verbs (offline, the verb's sheet gives the command instead). */
let selbarClear = null;
export function setSelbar(clearAct) { selbarClear = clearAct; }
const selbarHTML = () => `<div class="selbar__top"><span class="selbar__count">${esc(tn('pl.selected', picked.ids.size))}</span>
    ${picked.group ? `<span class="tag tag--state">${esc(t('sel.group', { name: picked.group.label }))}</span>` : ''}
    <button class="btn btn--plain btn--sm" data-act="${selbarClear}">${icon('x', 'icon--sm')}${t('sel.clear')}</button></div>
  <div class="selbar__verbs">${['fix', 'verify', 'explain', 'plan'].map((v, i) => `<button class="btn ${i ? 'btn--secondary' : 'btn--primary'}" data-act="sheet" data-sheet="verb:${v}">${t('verb.' + v)}</button>`).join('')}</div>`;
export function renderSelbar() {
  const el = document.getElementById('selbar');
  if (picked.ids.size && selbarClear) { el.innerHTML = selbarHTML(); el.setAttribute('aria-label', tn('pl.selected', picked.ids.size)); }
  else el.innerHTML = '';
  document.body.classList.toggle('has-selection', picked.ids.size > 0);
}
