// The frame around every screen: the phone's top bar and tab bar, the desktop's sidebar (places, Understand's groups,
// the live card, language and theme, the version), the one banner (read-only copy, stale, reconnecting, loading), the
// live strip while something runs or waits for the owner, and the selection bar.
import { prefs } from './prefs.js';
import { t, tn, num } from './i18n.js';
import { esc, icon, fmtWhen, fmtTime } from './format.js';
import { href, parseHash } from './router.js';
import { UGROUPS, ugroupOf } from './places.js';
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
  { id: 'understand', path: '/understand', icon: 'understand' },
];

/** What runs or waits now, for the live strip, the sidebar's card and Status: {kind: check | fix | run | signin,
 *  text, href, share (0..1 or null), you (it waits for the owner), run}; null when nothing does. */
export function liveNow() {
  if (live.signIn && live.signIn.asked) return { kind: 'signin', you: true, href: '/waiting/sign-in', share: null, text: t('live.signin') };
  const run = active();
  const check = live.progress && live.progress.flows && live.progress.flows.check;
  if (run) {
    const isCheck = run.action === 'audit';
    const you = run.state === 'waiting_for_person';
    const stages = isCheck && check ? check.stages || [] : [];
    const finished = stages.filter(s => ['ok', 'skipped', 'unavailable', 'failed'].includes(s.state)).length;
    const share = stages.length ? finished / stages.length : null;
    const label = labelOf(run.label, prefs.lang);
    const text = you ? t('live.you', { label }) : run.state === 'paused' ? t('live.paused', { label })
      : isCheck && stages.length ? t('live.check', { stage: num(Math.min(finished + 1, stages.length)), total: num(stages.length) }) + left(check)
        : t(run.verb === 'fix' || /^fix/.test(run.action) ? 'live.fixing' : 'live.run', { label });
    return { kind: isCheck ? 'check' : run.verb === 'fix' ? 'fix' : 'run', you, href: `/activity/run/${encodeURIComponent(run.id)}`, share, text, run };
  }
  if (check && check.state === 'running') {
    const stages = check.stages || [];
    const finished = stages.filter(s => ['ok', 'skipped', 'unavailable', 'failed'].includes(s.state)).length;
    return { kind: 'check', you: false, href: '/activity', share: stages.length ? finished / stages.length : null,
      text: t('live.check', { stage: num(Math.min(finished + 1, stages.length)), total: num(stages.length) }) + left(check) };
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

export function renderShell(place, path) {
  document.querySelector('.skip').textContent = t('skip');
  const wc = waitingCount();
  const wLabel = wc ? `${t('nav.waiting')}, ${tn('pl.thing_waits', wc)}` : t('nav.waiting');
  document.getElementById('topbar').innerHTML = `${projectButton()}
    <div class="topbar__end"><button class="btn btn--icon" data-act="sheet" data-sheet="search" aria-label="${esc(t('search.open'))}">${icon('search', 'icon--lg')}</button></div>`;
  const tabbar = document.getElementById('tabbar');
  tabbar.setAttribute('aria-label', t('nav.label'));
  tabbar.innerHTML = PLACES.map(p => `<a class="tab" href="${href(p.path)}" ${place === p.id ? 'aria-current="page"' : ''} ${p.id === 'waiting' ? `aria-label="${esc(wLabel)}"` : ''}>
      <span class="tab__icon">${icon(p.icon, 'icon--lg')}${p.id === 'waiting' && wc ? `<span class="count" aria-hidden="true">${num(wc)}</span>` : ''}</span>
      <span>${t('nav.' + p.id)}</span></a>`).join('');
  const ug = place === 'understand' ? ugroupOf(path) : null;
  const sub = place === 'understand' ? `<div class="side-sub">${UGROUPS.map(g => `<a href="${href('/understand/' + g.views[0])}" ${ug === g ? 'aria-current="true"' : ''}>${t('nav.u.' + g.id)}</a>`).join('')}</div>` : '';
  const now = liveNow();
  const card = now ? `<a class="side-live ${now.you ? 'side-live--you' : ''}" href="${href(now.href)}">
      <span class="side-live__top"><span class="dot ${now.you ? 'dot--you' : 'dot--live'}"></span>${esc(now.text)}</span>
      ${now.share != null ? `<span class="side-live__bar"><i style="transform:scaleX(${now.share})"></i></span>` : ''}</a>` : '';
  document.getElementById('sidebar').innerHTML = `${projectButton()}
    <button class="side-search" data-act="sheet" data-sheet="search">${icon('search')}<span>${t('search.open')}</span><kbd>${t('search.kbd')}</kbd></button>
    <nav class="side-nav" aria-label="${esc(t('nav.label'))}">
      ${PLACES.map(p => `<a href="${href(p.path)}" ${place === p.id ? 'aria-current="page"' : ''} ${p.id === 'waiting' ? `aria-label="${esc(wLabel)}"` : ''}>${icon(p.icon)}<span>${t(p.id === 'waiting' ? 'nav.waiting.long' : 'nav.' + p.id)}</span>${p.id === 'waiting' && wc ? `<span class="count" aria-hidden="true">${num(wc)}</span>` : ''}</a>${p.id === 'understand' ? sub : ''}`).join('')}
    </nav>
    <div class="side-foot">
      ${card}
      <div class="side-prefs">
        <div class="seg" role="group" aria-label="${esc(t('lang.label'))}">
          <button type="button" data-act="lang" data-lang="ar" aria-pressed="${prefs.lang === 'ar'}" lang="ar">${t('lang.ar')}</button>
          <button type="button" data-act="lang" data-lang="en" aria-pressed="${prefs.lang === 'en'}" lang="en">${t('lang.en')}</button>
        </div>
        <button class="btn btn--icon" data-act="theme" aria-label="${esc(t('theme.switch'))}: ${esc(t(prefs.theme === 'dark' ? 'theme.light' : 'theme.dark'))}">${icon(prefs.theme === 'dark' ? 'sun' : 'moon')}</button>
      </div>
      <div class="side-ver"><span class="dot" aria-hidden="true"></span>${esc(connection())}<span>${esc(t('version', { v: project().eaos_version || '' }))}</span></div>
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
    el.innerHTML = `<div class="banner banner--offline" role="note">${icon('lock')}<span>${esc(t('offline.banner', { when: fmtWhen(project().checked_at) }))}</span>
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

/** The selection bar is drawn by the screen that selects (Problems, the plan) through this hook. */
let selbarRenderer = null;
export function setSelbar(fn) { selbarRenderer = fn; }
export function renderSelbar() {
  const el = document.getElementById('selbar');
  if (picked.ids.size && selbarRenderer) { el.innerHTML = selbarRenderer(); el.setAttribute('aria-label', tn('pl.selected', picked.ids.size)); }
  else el.innerHTML = '';
  document.body.classList.toggle('has-selection', picked.ids.size > 0);
}
