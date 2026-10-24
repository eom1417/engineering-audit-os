// What happens now, shared by every screen (live only): the runs with the queue's order, the questions runs ask, the
// owner's answers to the report's decisions, the sign-in a check waits for, the assistants, the progress of every
// flow and the freshness of the check. Polled (every 3 s while the tab is seen, 15 s otherwise, and at once when it is
// seen again) and pushed by the live feed (/api/events: a new check, a delivered batch, a merge, a decision; the
// progress of the work), which also tells the report's sections to reload. Listeners hear only real changes.
import { ACTIVE, TERMINAL, client } from './actions.js';
import { follow } from './sse.js';
import { mode, reload } from './source.js';

export const live = {
  loaded: false, runs: [], queue: [], questions: [], decisions: [], signIn: null, assistants: null, progress: null,
  freshness: null, context: null, feed: mode === 'live' ? 'connecting' : null, heard: null, last: null, version: null,
};
const listeners = new Set();
/** `fn(what)` after a change: 'runs', 'progress', 'feed', 'assistants', 'freshness' or 'event' (live.last). */
export function onLive(fn) { listeners.add(fn); return () => listeners.delete(fn); }
const tell = what => listeners.forEach(fn => fn(what));

/** The run holding the project's one slot (running, paused or waiting for the person), if any. */
export const active = () => live.runs.find(r => ACTIVE.includes(r.state)) || null;
/** A run whose branch waits for the person's Accept or Reject: it ended well, handed a branch over, nobody decided. */
export const awaitsApproval = run => run.state === 'done' && !!(run.result && run.result.branch) && !run.outcome;
export const awaiting = () => live.runs.filter(awaitsApproval);
/** The owner's saved answer to a report decision (GET /api/decisions), or null. */
export const answerOf = id => { const row = live.decisions.find(d => d.id === id); return row ? row.response : null; };
export const scopeOf = id => { const row = live.decisions.find(d => d.id === id); return row ? row.scope : null; };

let ticket = 0;
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/** Reads the runs, the questions, the decisions' answers and the sign-in again. */
export async function refresh() {
  if (!client) return;
  const mine = ++ticket;
  try {
    const [listed, asked, answered, signing] = await Promise.all([client.runs(), client.questions(), client.decisions().catch(() => []),
      client.signIn.status().catch(() => null)]);
    if (mine !== ticket) return; // a newer refresh has the newer truth
    const next = { runs: listed.runs, queue: listed.queue, questions: asked, decisions: answered, signIn: signing };
    const was = { runs: live.runs, queue: live.queue, questions: live.questions, decisions: live.decisions, signIn: live.signIn };
    Object.assign(live, next);
    const first = !live.loaded;
    live.loaded = true;
    if (first || !same(was, next)) tell('runs');
    if (!first && ended(was.runs, next.runs)) catchUp();
  } catch (e) {
    if (!live.loaded) { live.loaded = true; tell('runs'); }
  }
}

/** Whether a run that was going (queued, running, paused, waiting) has ended since the last read: a check that ended
 *  rebuilt the report, a merge moved the branch. */
function ended(before, after) {
  const going = new Set((before || []).filter(r => !TERMINAL.includes(r.state)).map(r => r.id));
  return (after || []).some(r => going.has(r.id) && TERMINAL.includes(r.state));
}

/** The report's changed sections, whether it still matches the code and every flow's progress, read again: after a run
 *  ended, and when the tab is seen again or the feed comes back (a phone's tab sleeps and misses the feed's events). */
export function catchUp() {
  reload(false).then(refreshFreshness, refreshFreshness);
  refreshProgress();
}

/** Shows a change at once (pause, an answer…); the next refresh replaces it with the server's truth. */
export function patchRun(id, change) {
  live.runs = live.runs.map(r => (r.id === id ? Object.assign({}, r, change) : r));
  tell('runs');
}
export function rememberDecision(row) {
  ticket++;
  live.decisions = live.decisions.some(d => d.id === row.id) ? live.decisions.map(d => (d.id === row.id ? row : d)) : live.decisions.concat([row]);
  tell('runs');
}

let progressTimer = 0;
/** The progress of every flow (/api/progress), at most once a second however many progress events arrive (a stage's
 *  counted steps are written up to four times a second, eaos/core/progress/log.py); its `now` sets the server's clock. */
export function refreshProgress() {
  if (!client || progressTimer) return;
  progressTimer = setTimeout(async () => {
    try {
      const asked = Date.now();
      const next = await client.progress();
      progressTimer = 0;
      if (next.now && !isNaN(Date.parse(next.now))) live.skew = Date.parse(next.now) - (asked + Date.now()) / 2;
      if (!same(next.flows, live.progress && live.progress.flows)) { live.progress = next; tell('progress'); } else live.progress = next;
    } catch (e) { progressTimer = 0; }
  }, live.progress ? 1000 : 0);
}

/** The assistants on this computer (read once, and again on demand). */
export async function refreshAssistants() {
  if (!client) return null;
  try { live.assistants = await client.assistants(); } catch (e) { live.assistants = live.assistants || []; }
  tell('assistants');
  return live.assistants;
}

/** Whether the check still matches the code, asked of git now, and the branches in play (the checkout, the branch
 *  EAOS works on, the report's). */
export async function refreshFreshness() {
  if (!client) return null;
  try {
    const [freshness, context] = await Promise.all([client.branches.freshness(), client.branches.context().catch(() => null)]);
    Object.assign(live, { freshness, context });
    tell('freshness');
  } catch (e) { /* the report's own word stays */ }
  return live.freshness;
}

function onFeed(frame) {
  live.heard = Date.now();
  if (frame.event === 'reset') { reload(true); refresh(); refreshProgress(); return; }
  if (frame.event !== 'studio') return;
  let event;
  try { event = JSON.parse(frame.data); } catch (e) { reload(true); return; }
  if (event.kind === 'progress') { refreshProgress(); return; }
  live.last = event;
  if (event.sections && event.sections.length) reload(false).then(refreshFreshness);
  refresh();
  tell('event');
}

/** Starts following (live only): the runs' poll, the feed, the first progress, assistants and freshness. */
export function begin() {
  if (!client) return;
  client.session().then(s => {
    live.version = s.version || null;      // the EAOS running now; the report says which one made it
    if (s.actions === false) { live.loaded = true; tell('runs'); return; }
    refresh();
    const loop = () => setTimeout(async () => { if (document.visibilityState === 'visible') await refresh(); loop(); }, document.visibilityState === 'visible' ? 3000 : 15000);
    loop();
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') { refresh(); catchUp(); } });
  }, () => { live.loaded = true; tell('runs'); });
  refreshProgress();
  refreshAssistants();
  refreshFreshness();
  follow('/api/events', {
    onFrame: onFeed,
    onBeat: () => { live.heard = Date.now(); },
    onStatus: status => {
      if (status === live.feed) return;
      const back = live.feed === 'reconnecting' && status === 'open';
      live.feed = status; tell('feed');
      if (back) catchUp();
    },
  });
}
