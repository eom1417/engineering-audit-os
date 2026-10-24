// What a run's page shows, derived from the run's events alone (studio/src/data/actions/derive.ts, ported): its state,
// the sentence of what happens now, the problems a fix tried, the open question, the result or the error, the
// before/after screens, and the timeline with consecutive reads folded into one line. Pure, so a replayed stream and a
// live one look the same.

const NOW_KINDS = new Set(['step', 'read', 'edit', 'check', 'say', 'question', 'answer', 'result', 'error']);
/** Kinds the timeline leaves out: progress is drawn as bars, screenshots as pairs. */
const HIDDEN = new Set(['progress', 'screenshot']);

function onState(f, event) {
  const to = event.data.to;
  f.view.state = to;
  // a retry starts again: the last attempt's error and what was happening then are not what happens now
  if (to === 'running' || to === 'queued') { f.view.error = null; f.view.now = null; }
  if (to !== 'waiting_for_person') f.view.question = null;
  // the cards tried stay: the server counts on from them after a retry (its progress events)
  if (to === 'queued') { f.view.result = null; f.view.screens = []; }
}
// the batch now running: its before/after screens pair under it; the server's own count (done of total), the one
// count of the run, which survives a retry (a Fix run counts the cards its batch tried, whichever attempt tried them)
function onProgress(f, event) {
  const data = event.data;
  f.batch = typeof data.batch === 'number' ? data.batch || null : null;
  if (typeof data.done === 'number' && typeof data.total === 'number') f.view.progress = { done: data.done, total: data.total, stage: data.stage || null };
}
function onError(f, event) {
  const data = event.data;
  const what = data.what_now;
  f.view.error = { text: event.text, reason: String(data.reason || ''), what_now: what && (what.en || what.ar) ? what : null,
    recoverable: data.recoverable !== false, detail: event.detail || null };
}
function onScreenshot(f, event) {
  const data = event.data;
  const key = typeof data.batch === 'number' ? data.batch : f.batch;
  const before = data.when === 'before';
  let pair = f.view.screens.find(s => s.batch === key && !(before ? s.before : s.after));
  if (!pair) { pair = { batch: key }; f.view.screens.push(pair); }
  if (before) pair.before = event; else pair.after = event;
}
const APPLY = {
  state: onState,
  progress: onProgress,
  question: (f, e) => { f.view.question = e.data; },
  answer: f => { f.view.question = null; },
  // accept or undo recorded on a done run: the handed-over result stays
  result: (f, e) => { if (!('outcome' in e.data)) f.view.result = e.data; },
  error: onError,
  // each problem of a batch an edit tried, kept or taken back: the one count of what was tried
  edit: (f, e) => { if (e.data && e.data.card) f.view.cards[e.data.card] = e.data.kept; },
  check: (f, e) => { f.view.checks[e.data.passed === false ? 'failed' : 'passed'] += 1; },
  screenshot: onScreenshot,
};
function addItem(items, event) {
  if (HIDDEN.has(event.kind)) return;
  const previous = items[items.length - 1];
  if (event.kind !== 'read') items.push({ kind: 'event', event });
  else if (previous && previous.kind === 'reads') previous.events.push(event);
  else items.push({ kind: 'reads', events: [event] });
}

export function deriveRun(events, run) {
  const view = { state: run ? run.state : null, now: null, question: run ? run.question || null : null, result: run ? run.result || null : null,
    error: null, screens: [], items: [], cards: {}, checks: { passed: 0, failed: 0 }, progress: null, last: 0 };
  const fold = { view, batch: null };
  for (const event of events) {
    view.last = Math.max(view.last, event.seq);
    if (NOW_KINDS.has(event.kind)) view.now = event.text;
    const apply = APPLY[event.kind];
    if (apply) apply(fold, event);
    addItem(view.items, event);
  }
  return view;
}

/** A Fix run's count of cards tried: the server's last progress of its cards (whichever attempt tried them), else the
 *  cards this page saw edited. A retry starts a new attempt, never a new count. */
export function fixCount(view, run) {
  const total = ((run && run.cards) || []).length;
  const p = view.progress;
  return p && p.total === total ? p.done : Object.keys(view.cards).length;
}

/** Where a run's page follows its events from now, or null: its first look from the start; a stream that ended with
 *  an attempt, after the last event seen once the run runs again (a retry is the same run, and its page stood still
 *  until opened again); never while one is open or the run has ended. */
export function followFrom(follow, ended) {
  if (!follow.stop) return 0;
  if (follow.open || ended) return null;
  return follow.events.length ? follow.events[follow.events.length - 1].seq : 0;
}

/** A run's label in the language: an Arabic list takes the Arabic comma, so its ids read in order. */
export function labelOf(label, lang) {
  if (!label) return '';
  return lang === 'ar' ? String(label.ar || label.en || '').replaceAll(', ', '، ') : String(label.en || label.ar || '');
}

/** Whole seconds between two instants (to: now when absent); null when either cannot be read. */
export function seconds(from, to, now = Date.now()) {
  if (!from) return null;
  const start = Date.parse(from), end = to ? Date.parse(to) : now;
  return Number.isNaN(start) || Number.isNaN(end) ? null : Math.max(0, Math.round((end - start) / 1000));
}
