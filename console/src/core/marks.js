// Builder A's shared marks (EAOS.ac): the glyph and word of a state, times, durations, money and tokens, folds, and
// the runs as the person reads them (the live action API's runs without the quick answers). Activity, the project
// pages, Ask and Waiting's sign-in and questions draw with them, so they live in the core once.
import { t, tn, L, num, has } from './i18n.js';
import { esc, icon, fmtWhen, fmtTime, exactTime } from './format.js';
import { href } from './address.js';
import { act } from './events.js';
import { toast } from './notices.js';
import { prefs } from './prefs.js';
import { live, active } from '../data/store.js';
import { assistantName } from '../data/model.js';
import { labelOf, seconds } from '../data/derive.js';
import { actionOf } from '../data/contract.js';
import { TERMINAL } from '../data/actions.js';

const GLYPH = {
  queued: ['circle', 'muted'], waiting: ['circle', 'muted'], paused: ['pause', 'ink-2'], done: ['check', 'ok'], ok: ['check', 'ok'],
  unchanged: ['dash', 'ink-2'], stopped: ['stop', 'ink-2'], failed: ['fail', 'danger'], skipped: ['dash', 'muted'], notin: ['dash', 'muted'],
  notreached: ['dash', 'muted'], partial: ['warn', 'caution'], handoff: ['terminal', 'ink-2'], error: ['fail', 'danger'], ready: ['check', 'ok'],
  unavailable: ['dash', 'muted'], downloading: [null, 'live'], notneeded: ['dash', 'muted'],
};
export function glyph(st) {
  if (st === 'running' || st === 'downloading') return '<span class="dot dot--live" aria-hidden="true"></span>';
  if (st === 'you') return '<span class="dot dot--you" aria-hidden="true"></span>';
  if (st === 'stalled') return '<span class="dot ac-dot--caution" aria-hidden="true"></span>';
  const g = GLYPH[st] || ['circle', 'muted'];
  return icon(g[0], 'icon--sm ac-c-' + g[1]);
}
export const stateWord = st => (has('ac.st.' + st) ? t('ac.st.' + st) : st);
export function mark(st, word) { return `<span class="state ac-state">${glyph(st)}<span>${word || esc(stateWord(st))}</span></span>`; }
export function back(path, label, query) { return `<a class="back" href="${href(path, query)}">${icon('back', 'icon--dir')}${esc(label)}</a>`; }
export function fold(id, title, sum, body, open, cls) {
  return `<details class="fold ${cls || ''}" id="fold-${id}" ${open ? 'open' : ''}><summary><span class="row__main"><span class="row__title">${title}</span>${sum ? `<span class="row__meta" style="display:block">${sum}</span>` : ''}</span>${icon('chev', 'chev')}</summary>
    <div class="fold__body">${body}</div></details>`;
}
export function when(iso) { return iso ? `<button class="ac-time" data-act="ac-time" data-iso="${esc(iso)}" title="${esc(exactTime(iso))}">${esc(fmtWhen(iso))}</button>` : ''; }
export function clock(iso) { return iso ? `<button class="ac-time num" data-act="ac-time" data-iso="${esc(iso)}" title="${esc(exactTime(iso))}">${esc(fmtTime(iso))}</button>` : ''; }
act('ac-time', el => toast(exactTime(el.dataset.iso)));
export function secs(s) {
  if (s == null) return '';
  if (s < 60) return t('ac.sec', { n: num(Math.round(s)) });
  return minutes(Math.round(s / 60));
}
/** A stopwatch: m:ss, h:mm:ss past the hour, in Western digits read left to right. */
export function stopwatch(s) {
  const n = Math.max(0, Math.floor(s || 0)), h = Math.floor(n / 3600), m = Math.floor(n / 60) % 60, x = n % 60;
  return (h ? h + ':' + String(m).padStart(2, '0') : String(m)) + ':' + String(x).padStart(2, '0');
}
/** The seconds since `iso` on the server's clock (live.skew: how far it runs ahead of this browser's). */
export const since = iso => Math.max(0, (Date.now() + (live.skew || 0) - Date.parse(iso)) / 1000);
/** A live time: counting up from `from` each second while `upTo` is unset (the ticker below rewrites only these marks,
 *  the screen is never drawn again for it); `took` seconds once it ended. Empty when neither is known. */
export function ticker(from, took, cls) {
  if (took != null) return `<bdi class="num ac-tick ${cls || ''}" dir="ltr">${stopwatch(took)}</bdi>`;
  if (!from || isNaN(Date.parse(from))) return '';
  return `<bdi class="num ac-tick ac-tick--live ${cls || ''}" dir="ltr" data-since="${esc(from)}" aria-live="off">${stopwatch(since(from))}</bdi>`;
}
/* the one ticker: a querySelectorAll a second, idle when no live time is on screen */
setInterval(() => document.querySelectorAll('[data-since]').forEach(el => {
  const v = stopwatch(since(el.dataset.since));
  if (el.textContent !== v) el.textContent = v;
}), 1000);
export function minutes(m) { return m >= 120 ? t('ac.hm', { h: num(Math.floor(m / 60)), m: num(m % 60) }) : tn('pl.minute', m); }
/** A cost, isolated left to right inside Arabic. */
export function money(v) { return v == null ? null : '⁦$' + Number(v).toFixed(2) + '⁩'; }
export function tokens(n) { return n == null ? null : n >= 1e6 ? t('ac.tok.m', { n: (n / 1e6).toFixed(1) }) : t('ac.tok.k', { n: num(Math.round(n / 1000)) }); }
export function nmTag(reason) { return `<span class="tag tag--nm">${t('nm')}</span>${reason ? ` <span class="small muted">${reason}</span>` : ''}`; }
export function progressBar(share, label) {
  const s = Math.max(0, Math.min(1, share || 0));
  return `<div class="ac-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(s * 100)}" aria-label="${esc(label || t('a11y.progress'))}"><i style="transform:scaleX(${s})"></i></div>`;
}
/** Every token a usage record counts. */
export const usedTokens = u => (u ? ['input', 'cache_write', 'cache_read', 'output', 'thinking'].reduce((a, k) => a + (u[k] || 0), 0) : null);

/* ---------- the runs ---------- */
/** The runs the person follows: every run but the quick answers (read-only tools answered at once), newest first. */
export const runs = () => live.runs.filter(r => !r.read);
export const quickAnswers = () => live.runs.filter(r => r.read);
export const runOf = id => live.runs.find(r => r.id === id) || null;
/** The queue, in its order: the runs waiting their turn. */
export const queue = () => live.queue.map(runOf).filter(r => r && r.state === 'queued');
export const liveRun = () => active();
/** A run's state as its glyph and word name it: waiting for the person is "you". */
export const runState = r => (r.state === 'waiting_for_person' ? 'you' : r.state);
export const ended = r => TERMINAL.includes(r.state);
/** The kind of a run: check, fix, verify, explain, plan, record, run_try, extend, or action. */
export function kindOf(r) {
  if (r.action === 'audit') return 'check';
  if (r.verb) return r.verb;
  return { safety_net: 'record', run_try: 'run_try', extend_start: 'extend', blueprint_start: 'extend' }[r.action] || 'action';
}
export function kindWord(r) {
  const k = kindOf(r);
  if (k !== 'action') return t('ac.kind.' + k);
  if (has('ac.kind.' + r.action)) return t('ac.kind.' + r.action);
  const a = actionOf(r.action);
  return a ? L(a.label) : r.action;
}
export const runLabel = r => labelOf(r.label, prefs.lang) || r.action;
export function whoWord(r) {
  if (r.mode === 'handoff') return t('ac.who.handoff');
  if (r.mode === 'direct' || !r.assistant) return 'EAOS';
  return assistantName(r.assistant);
}
/** Whole minutes a run took (or has taken so far). */
export function took(r) {
  const flow = flowOfRun(r);
  const s = flow && flow.seconds != null ? flow.seconds : seconds(r.started || r.created, r.ended);
  return s == null ? null : Math.max(1, Math.round(s / 60));
}
/** The check flow of /api/progress, with its stages. */
export const checkFlow = () => (live.progress && live.progress.flows && live.progress.flows.check) || null;
/** The check run /api/progress's check flow is of: the newest one that started no later than the flow did. A check
 *  that stopped before it began its stages (no assistant, a refusal) never owns the stages of the one before it. */
export const lastCheck = () => {
  const flow = checkFlow(), began = flow && Date.parse(flow.started_at);
  return runs().find(r => r.action === 'audit' && r.started && (!began || Date.parse(r.started) <= began)) || null;
};
/** The check flow belongs to this run when it is the newest check. */
export const flowOfRun = r => (r && r.action === 'audit' && lastCheck() && lastCheck().id === r.id ? checkFlow() : null);

/** What a tool answered (a run's result.answer): the assistant's words, or the facts of a reading tool, its scalars
 *  first and the whole answer one press away. */
export function answerHTML(answer) {
  if (answer == null || answer === '') return '';
  if (typeof answer !== 'object') return `<div class="ai-block"><span class="ai-block__label">${icon('ai', 'icon--sm')}${t('ai.label')}</span><p class="small" style="margin-top:4px;white-space:pre-wrap">${esc(answer)}</p></div>`;
  const plain = v => v != null && typeof v !== 'object' && !/^\//.test(String(v));
  const rows = Object.entries(answer).filter(([, v]) => plain(v) || (Array.isArray(v) && v.every(plain))).slice(0, 14);
  return `${rows.length ? `<dl class="facts">${rows.map(([k, v]) => `<dt>${esc(k.replace(/_/g, ' '))}</dt><dd><bdi dir="auto">${esc(Array.isArray(v) ? v.slice(0, 12).join(', ') : typeof v === 'number' ? num(v) : v)}</bdi></dd>`).join('')}</dl>` : ''}
    <details class="ac-ev-fold"><summary>${t('ac.run.answer')}${icon('chev-down', 'icon--sm muted')}</summary><div class="code" style="padding:8px 12px;white-space:pre-wrap;max-height:320px;overflow:auto">${esc(JSON.stringify(answer, null, 2).slice(0, 20000))}</div></details>`;
}
/** The branch a run's delivered branch was merged into. */
export const mergedInto = r => (r.result && (r.result.target || r.result.landed_on)) || (r.where && r.where.merge_into) || (r.context && r.context.analysis_branch) || '';
