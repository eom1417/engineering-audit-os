// What a run's page shows, derived from the run's events alone (studio/src/data/actions/derive.ts, ported): its state,
// the sentence of what happens now, every batch's progress, the open question, the result or the error, the
// before/after screens, and the timeline with consecutive reads folded into one line. Pure, so a replayed stream and a
// live one look the same.

const NOW_KINDS = new Set(['step', 'read', 'edit', 'check', 'say', 'question', 'answer', 'result', 'error']);
/** Kinds the timeline leaves out: progress is drawn as bars, screenshots as pairs. */
const HIDDEN = new Set(['progress', 'screenshot']);

function onState(f, event) {
  const to = event.data.to;
  f.view.state = to;
  if (to === 'running' || to === 'queued') f.view.error = null;
  if (to !== 'waiting_for_person') f.view.question = null;
  if (to === 'queued') { f.view.result = null; f.batches.clear(); f.view.screens = []; }
}
function onProgress(f, event) {
  const data = event.data;
  const number = typeof data.batch === 'number' ? data.batch : 0;
  f.batch = number || null;
  f.batches.set(number, { number, done: Number(data.done) || 0, total: Number(data.total) || 0 });
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
  edit: f => { f.view.edits += 1; },
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
  const view = { state: run ? run.state : null, now: null, batches: [], question: run ? run.question || null : null, result: run ? run.result || null : null,
    error: null, screens: [], items: [], edits: 0, checks: { passed: 0, failed: 0 }, last: 0 };
  const fold = { view, batches: new Map(), batch: null };
  for (const event of events) {
    view.last = Math.max(view.last, event.seq);
    if (NOW_KINDS.has(event.kind)) view.now = event.text;
    const apply = APPLY[event.kind];
    if (apply) apply(fold, event);
    addItem(view.items, event);
  }
  view.batches = [...fold.batches.values()].sort((a, b) => a.number - b.number);
  return view;
}

/** The overall share done, 0..1, from the batches (each weighs its cards); null before any progress. */
export function share(batches) {
  const total = batches.reduce((sum, b) => sum + b.total, 0);
  if (!total) return null;
  return Math.min(1, batches.reduce((sum, b) => sum + Math.min(b.done, b.total), 0) / total);
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
