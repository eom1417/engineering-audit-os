// The floating assistant (CHT-01..07 from every screen): a button on every screen opens the conversation in place, a
// side panel on the desktop (the page stays usable beside it) and a bottom sheet on the phone. It is the SAME
// conversation as the full Ask view: the panel draws it through EAOS.askAPI, which the Ask place provides
// (src/places/ask: {chat(), turnHTML(turn), control(), send(text, context)}), read when the panel first opens. The
// panel carries the page it was opened from as a removable chip and suggests questions for it.
// States: ready, thinking and failed (from the conversation), no ready assistant (none logged in), the read-only copy.
// Address: ?ask=1 opens it. Keyboard: Ctrl/Cmd+I toggles it, Esc closes it.
import { t, tn, L } from './i18n.js';
import { esc, icon, code } from './format.js';
import { afterRender, refresh, offline } from './router.js';
import { href, parseHash, setQuery } from './address.js';
import { a11yRegions, hold } from './a11y.js';
import { act } from './events.js';
import { announce } from './notices.js';
import { closeSheetThen } from './sheets.js';
import { loadBundle, isLoaded } from './places.js';
import { S } from './state.js';
import { live } from '../data/store.js';
import { decisions, problem } from '../data/model.js';

const api = () => window.EAOS && window.EAOS.askAPI;
const desk = () => matchMedia('(min-width: 1024px)').matches;
const path = () => parseHash().path;

/** The context of the page the panel was opened from. */
function routeCtx() {
  const p = path(), m = re => p.match(re);
  let x;
  if ((x = m(/^\/problems\/([^/]+)$/)) && x[1] !== 'plan') { const pr = problem(decodeURIComponent(x[1])); return { kind: 'problem', id: x[1], label: x[1] + (pr ? ' ' + L(pr.title) : '') }; }
  if ((x = m(/^\/activity\/run\/([^/]+)$/))) { const id = decodeURIComponent(x[1]); const r = live.runs.find(y => y.id === id); return { kind: 'run', id, label: id + (r ? ' ' + L(r.label) : '') }; }
  if ((x = m(/^\/project\/branches\/(.+)$/))) { const n = decodeURIComponent(x[1]); return { kind: 'branch', id: n, label: n }; }
  if ((x = m(/^\/understand\/(components|functions|gaps|paths|data|screens|library|history)\/(.+)$/)) && x[2] !== 'all' && x[2] !== 'compare') {
    const id = decodeURIComponent(x[2]); return { kind: 'thing', id: id.split('#').pop(), label: id };
  }
  if ((x = m(/^\/problems\/plan\/([^/]+)$/)) && x[1] !== 'waves') return { kind: 'thing', id: x[1], label: x[1] };
  if ((x = m(/^\/waiting\/(.+)$/)) && !['sign-in', 'questions', 'decided'].includes(x[1])) {
    const id = decodeURIComponent(x[1]);
    const d = decisions().find(y => y.id === id);
    const run = live.runs.find(y => y.id === id);
    const label = d ? L(d.question) : run && run.result ? run.result.branch : id;
    return { kind: run ? 'branch' : 'thing', id: d ? label.slice(0, 40) : label, label };
  }
  const title = (document.title || '').split(' - ')[0];
  return { kind: 'place', id: title, label: title };
}
const ctx = () => (S.assist.ctxOff === path() ? null : routeCtx());

/** No ready assistant: none is installed and logged in (live.assistants, read at start). */
const noAssistant = () => parseHash().query.state === 'noasst' || (live.assistants && !live.assistants.some(a => a.installed && a.logged_in));
const hidden = () => path() === '/ask' || path().startsWith('/open');

function fabHTML() {
  if (hidden() || S.assist.open) return '';
  return `<button class="fab" id="fab" data-act="assist-open" aria-label="${esc(t('as.fab.sr'))}" title="${esc(t('as.fab'))} (${esc(t('as.fab.kbd'))})"
    aria-controls="assist" aria-expanded="false">${icon('ai', 'icon--lg')}<span class="fab__label">${t('as.fab')}</span></button>`;
}

function bodyHTML() {
  if (offline()) {
    return `<div class="assist__state"><p class="h2">${t('as.offline')}</p><p class="small ink-2">${t('as.offline.guide')}</p>
      <div class="actions"><button class="btn btn--primary" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button></div></div>`;
  }
  if (noAssistant()) {
    return `<div class="assist__state"><p class="h2">${t('as.noasst')}</p><p class="small ink-2">${t('as.noasst.why', { cmd: code('claude login') })}</p>
      <div class="actions"><button class="btn btn--primary" data-act="copy" data-text="claude login">${icon('copy')}${t('copy')}</button>
        <a class="btn btn--quiet" href="${href('/project/assistants')}">${t('as.noasst.open')}</a></div></div>`;
  }
  const a = api();
  if (!a && !isLoaded('ask')) return `<div class="assist__state" aria-busy="true"><p class="small muted">${t('st.loading')}</p></div>`;
  if (!a) return `<div class="assist__state"><p class="small ink-2">${t('todo.next')}</p></div>`;
  const turns = a.chat();
  const answers = turns.filter(x => x.who === 'ai' && x.cost != null);
  const cost = answers.reduce((sum, x) => sum + x.cost, 0);
  return `<ol class="ac-chat assist__chat" id="assist-chat" aria-live="polite">${turns.map(a.turnHTML).join('')}</ol>
    ${a.control()}
    <p class="small muted">${esc(t('as.cost', { answers: tn('pl.answer', answers.length), cost: '$' + cost.toFixed(2) }))}
      <a class="link" href="${href('/project/assistants')}">${t('proj.assistants')}</a></p>`;
}

function chipHTML(c) {
  return c ? `<span class="chip assist__ctx">${icon(c.kind === 'problem' ? 'problems' : c.kind === 'run' ? 'activity' : c.kind === 'branch' ? 'branch' : c.kind === 'place' ? 'status' : 'map')}
      <span class="assist__ctxtext">${esc(t('as.ctx', { label: c.label }))}</span>
      <button class="ac-chip-x" data-act="assist-ctx-off" aria-label="${esc(t('as.ctx.remove'))}">${icon('x', 'icon--sm')}</button></span>`
    : `<span class="chip assist__ctx">${icon('status')}${t('as.ctx.project')}</span>`;
}

function composerHTML() {
  if (offline() || noAssistant() || !api()) return '';
  const thinking = api().chat().some(x => x.pending);
  const depth = S.assist.depth || 'quick';
  const draft = S.assist.draft || '';
  const c = ctx();
  const sug = [1, 2, 3].map(i => t(`as.sug.${c ? c.kind : 'place'}.${i}`, { id: c ? c.id : '' }));
  return `<div class="assist__composer">
    <div class="assist__ctxrow">${chipHTML(c)}</div>
    <div class="assist__sug" role="group" aria-label="${esc(t('as.sug'))}">${sug.map(x => `<button class="assist__q" data-act="assist-q" data-q="${esc(x)}" ${thinking ? 'disabled' : ''}>${esc(x)}</button>`).join('')}</div>
    <label class="sr-only" for="as-in">${t('as.ph')}</label>
    <textarea class="input" id="as-in" data-fk="as-in" data-input="assist-draft" rows="2" maxlength="8000" placeholder="${esc(t('as.ph'))}">${esc(draft)}</textarea>
    <div class="assist__row">
      <div class="seg" role="group" aria-label="${esc(t('as.depth'))}">${['quick', 'balanced', 'deep'].map(d => `<button type="button" data-act="assist-depth" data-d="${d}" data-fk="as-depth-${d}" aria-pressed="${depth === d}">${t('as.depth.' + d)}</button>`).join('')}</div>
      <button class="btn btn--primary" data-act="assist-send" data-fk="as-send" ${draft.trim() && !thinking ? '' : 'disabled'}>${thinking ? `<span class="dot dot--live" aria-hidden="true"></span>${t('as.thinking')}` : t('as.send')}</button>
    </div></div>`;
}

function readyWho() {
  const ready = (live.assistants || []).find(a => a.installed && a.logged_in);
  return ready ? ready.name : '';
}

function panelHTML() {
  const who = readyWho();
  const c = ctx();
  return `<div class="assist__head">
      <div class="assist__titles"><h2 class="sheet__title" id="assist-title">${icon('ai', 'icon--sm')} ${t('as.title')}</h2>
        ${who && !offline() ? `<p class="sheet__sub">${esc(t('as.ready', { who }))}</p>` : ''}</div>
      <a class="btn btn--quiet btn--sm" href="${href('/ask', c && c.kind === 'run' ? { run: c.id } : {})}" data-act="assist-full">${t('as.full')}</a>
      <button class="btn btn--icon" data-act="assist-close" aria-label="${esc(t('as.close'))}" data-fk="as-x">${icon('x')}</button>
    </div>
    <div class="assist__body" id="assist-body">${bodyHTML()}</div>
    ${composerHTML()}`;
}

function draw() {
  if (parseHash().query.ask === '1' && !S.assist.open && !hidden()) S.assist.open = true;
  if (hidden()) S.assist.open = false;
  const open = S.assist.open;
  if (open && !isLoaded('ask') && !offline()) loadBundle('ask').then(ok => { if (ok) draw(); });
  document.body.classList.toggle('has-assist', open);
  const host = document.getElementById('assist-host');
  const back = hold(document.getElementById('assist'));
  const sb = document.getElementById('assist-body');
  const keepBottom = sb ? sb.scrollHeight - sb.scrollTop - sb.clientHeight < 40 : true;
  host.innerHTML = `${fabHTML()}
    ${open ? `${desk() ? '' : '<div class="assist-scrim" data-act="assist-close"></div>'}
    <aside class="assist" id="assist" tabindex="-1" role="dialog" aria-modal="${desk() ? 'false' : 'true'}" aria-labelledby="assist-title">${panelHTML()}</aside>` : ''}`;
  if (open) {
    a11yRegions(host);
    const body = document.getElementById('assist-body');
    if (body && keepBottom) body.scrollTop = body.scrollHeight;
    back();
  }
}
afterRender(draw);
/** Redraws the panel alone (the conversation moved on). */
export const redrawAssist = draw;

function open() {
  S.assist.open = true;
  refresh();
  const i = desk() ? (document.getElementById('as-in') || document.querySelector('#assist [data-act="assist-close"]')) : document.getElementById('assist');
  if (i) i.focus({ preventScroll: true });
  announce(t('as.title'));
}
function close() {
  S.assist.open = false;
  if (parseHash().query.ask) setQuery({ ask: null }); else refresh();
  const f = document.getElementById('fab');
  if (f) f.focus({ preventScroll: true });
}
function ask(text) {
  if (!text || !text.trim() || !api()) return;
  S.assist.draft = '';
  api().send(text.trim(), ctx() || null, S.assist.depth || 'quick');
  draw();
  const b = document.getElementById('assist-body'); if (b) b.scrollTop = b.scrollHeight;
}

act('assist-open', () => open());
act('assist-close', () => close());
act('assist-full', el => { S.assist.open = false; location.hash = el.getAttribute('href'); });
act('assist-ctx-off', () => { S.assist.ctxOff = path(); draw(); const f = document.getElementById('as-in'); if (f) f.focus(); });
act('assist-q', el => { if (!el.disabled) ask(el.dataset.q); });
act('assist-send', el => { if (!el.disabled) ask(S.assist.draft || ''); });
act('assist-depth', el => { S.assist.depth = el.dataset.d; draw(); });
act('assist-draft', el => {
  S.assist.draft = el.value;
  const b = document.querySelector('#assist [data-act="assist-send"]');
  if (b) b.disabled = !el.value.trim() || !api() || api().chat().some(x => x.pending);
});
// "Ask your assistant: …" in Search or ask opens this panel with the question (one home: the same conversation)
act('assist-ask', el => {
  const text = el.dataset.q;
  closeSheetThen(() => {
    if (hidden()) { location.hash = href('/ask', { q: text }); return; }
    S.assist.open = true; refresh();
    loadBundle('ask').then(() => { draw(); ask(text); });
  });
});

document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && (e.key === 'i' || e.key === 'I')) {
    if (hidden()) return;
    e.preventDefault();
    if (S.assist.open) close(); else open();
    return;
  }
  if (e.key === 'Escape' && S.assist.open && !document.querySelector('.sheet.is-open')) {
    const inside = document.activeElement && document.activeElement.closest('#assist');
    if (inside || !desk()) { e.preventDefault(); e.stopPropagation(); close(); }
  }
  // the phone sheet is modal: Tab stays inside it
  if (e.key === 'Tab' && S.assist.open && !desk() && !document.querySelector('.sheet.is-open')) {
    const f = Array.from(document.querySelectorAll('#assist a[href], #assist button:not([disabled]), #assist textarea, #assist input, #assist summary')).filter(x => x.offsetParent !== null);
    if (!f.length) return;
    if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
    else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
  }
}, true);
matchMedia('(min-width: 1024px)').addEventListener('change', () => draw());
