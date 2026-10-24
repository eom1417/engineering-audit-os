// The live action API of `eaos studio` (docs/studio-actions.json `endpoints`, eaos/interfaces/studio/, eaos/interfaces/api/): every
// call carries the launch token (X-EAOS-Token), every POST also the CSRF token GET /api/session returned for this
// launch, and the browser adds the Origin the server checks. Previews never change anything; a run that changes code or
// cannot be undone needs the confirm token its preview returned. The read-only copy has no client (`client` is null):
// its screens lock every action and explain how to open the console live.
import { prefs } from '../core/prefs.js';
import { mode, token } from './source.js';
import { follow } from './sse.js';

export const TERMINAL = ['done', 'failed', 'stopped', 'unchanged'];
export const ACTIVE = ['running', 'paused', 'waiting_for_person'];
export const RETRYABLE = ['failed', 'stopped', 'unchanged'];

/** A refused call: its status, the message in the person's language when the server gave reasons, what it needs
 *  (`confirm`, `preview`, `refresh`, `in_flight`…) and the reasons themselves. */
export class ActionError extends Error {
  constructor(status, message, needs, reasons) { super(message); this.status = status; this.needs = needs; this.reasons = reasons || []; }
}

function refused(answer, payload) {
  const reasons = payload.reasons || [];
  const message = reasons.length ? reasons.map(r => r[prefs.lang] || r.en).join(' ') : String(payload.message || payload.error || answer.statusText);
  return new ActionError(answer.status, message, payload.needs, reasons);
}

const enc = encodeURIComponent;
const query = values => Object.entries(values).filter(([, v]) => v != null && v !== '').map(([k, v]) => `${k}=${enc(v)}`).join('&');

function liveClient() {
  let csrf = null, session = null;
  const readSession = () => (session = session || request('GET', '/api/session'));

  async function request(method, path, body, retried) {
    const headers = { 'X-EAOS-Token': token, Accept: 'application/json' };
    if (method === 'POST') {
      headers['Content-Type'] = 'application/json';
      headers['X-EAOS-CSRF'] = await (csrf = csrf || readSession().then(s => String(s.csrf)));
    }
    const answer = await fetch(path, { method, headers, body: method === 'POST' ? JSON.stringify(body || {}) : undefined, cache: 'no-store', credentials: 'same-origin' });
    let payload = {};
    try { payload = await answer.json(); } catch (e) { payload = {}; }
    if (answer.status === 403 && /csrf/i.test(String(payload.error)) && !retried) {
      csrf = null; session = null; // a new launch: this page's CSRF token went stale
      return request(method, path, body, true);
    }
    if (!answer.ok) throw refused(answer, payload);
    return payload;
  }
  const get = path => request('GET', path);
  const post = (path, body) => request('POST', path, body);
  const run = p => p.then(r => r.run);

  return {
    mode: 'live',
    /** The server's session: mode, version, project, the assistants found and whether the action API is mounted. */
    session: () => readSession(),
    preview: (id, body) => post(`/api/actions/${enc(id)}/preview`, body || {}),
    // the run, and the check or fix it starts, write in the language the person reads
    start: body => run(post('/api/runs', Object.assign({}, body, { lang: prefs.lang }))),
    runs: () => get('/api/runs?all=1'),
    run: id => run(get(`/api/runs/${enc(id)}`)),
    control: (id, op) => run(post(`/api/runs/${enc(id)}/${op}`)),
    reorder: order => post('/api/runs/reorder', { order }).then(r => r.queue),
    decide: (id, op, confirm, choice) => run(post(`/api/runs/${enc(id)}/${op}`, Object.assign({ confirm }, choice || {}))),
    /** Every event of a run after `after`, then live until it ends; returns the stop. */
    follow: (id, after, onEvent, onStatus) => {
      let last = after || 0;
      return follow(`/api/runs/${enc(id)}/events`, {
        last: last || null, onStatus,
        onFrame: frame => {
          let event;
          try { event = JSON.parse(frame.data); } catch (e) { return; }
          if (typeof event.seq !== 'number' || event.seq <= last) return; // a replayed event already shown
          last = event.seq;
          onEvent(event);
          return event.kind === 'state' && TERMINAL.includes(event.data && event.data.to) ? 'end' : undefined;
        },
      });
    },
    questions: () => get('/api/questions').then(r => r.questions),
    answer: (question, option, text) => run(post(`/api/questions/${enc(question)}/answer`, { option, text: text || null })),
    decisions: () => get('/api/decisions').then(r => r.decisions),
    answerDecision: (id, scope, option, text) => post(`/api/decisions/${enc(id)}/answer`, { scope, option, text: text || null }).then(r => r.decision),
    assistants: () => get('/api/assistants').then(r => r.assistants),
    usage: () => get('/api/usage'),
    chat: (message, session, context, model) => post('/api/chat', { message, session, context, model }),
    chatProgress: turn => get(`/api/chat/${enc(turn)}`),
    chatControl: on => (on === undefined ? get('/api/chat/control') : post('/api/chat/control', { on })),
    plan: body => run(post('/api/plan', body)),
    progress: () => get('/api/progress'),
    projects: () => get('/api/projects').then(r => r.projects),
    openProject: workspace => post('/api/projects/open', { workspace }),
    branches: {
      freshness: () => get('/api/freshness').then(r => r.freshness),
      context: () => get('/api/context').then(r => r.context),
      inventory: base => get(`/api/branches?${query({ base })}`),
      detail: (name, kind, remote, base) => get(`/api/branches/detail?${query({ name, kind, remote, base })}`),
      select: (branch, scan, expectedTip) => post('/api/branches/analysis', { branch, scan, expected_tip: expectedTip || null }),
      previewMerge: (source, target) => post('/api/branches/merge/preview', { source, target: target || null }),
      merge: (p, uncheckedAck) => post('/api/branches/merge', { source: p.source, target: p.target, source_head: p.source_head, target_head: p.target_head,
        unchecked: p.needs_unchecked_ack, unchecked_ack: uncheckedAck, confirm: p.confirm ? p.confirm.token : null }),
      proposeResolution: (source, target, assistant) => post('/api/branches/conflict', { source, target, assistant: assistant || null }),
      previewDelete: (branch, where, remote) => post('/api/branches/delete/preview', { branch, where, remote: remote || null }),
      remove: (p, second) => post('/api/branches/delete', { branch: p.branch, where: p.where, remote: p.remote || null, tip: p.tip, unmerged: !!p.unmerged,
        worktree: !!p.worktree, confirm: p.confirm ? p.confirm.token : null, confirm_unmerged: second && p.confirm_unmerged ? p.confirm_unmerged.token : null }),
      restore: (recovery, as) => post('/api/branches/restore', { recovery, as: as || null }),
      previewProtect: (branch, on) => post('/api/branches/protect/preview', { branch, protected: on }),
      protect: (branch, on, confirm) => post('/api/branches/protect', { branch, protected: on, confirm: confirm || null }),
      previewCleanup: () => post('/api/branches/cleanup/preview', {}),
      cleanup: p => post('/api/branches/cleanup', { digest: p.digest, confirm: p.confirm ? p.confirm.token : null }),
      fetch: remote => post('/api/branches/fetch', { remote: remote || 'origin' }),
    },
    signIn: {
      status: () => get('/api/sign-in'),
      open: () => post('/api/sign-in/open'),
      input: command => post('/api/sign-in/input', command),
      done: () => post('/api/sign-in/done'),
      skip: () => post('/api/sign-in/skip'),
      forget: () => post('/api/sign-in/forget'),
    },
  };
}

/** The live client, or null in the read-only copy. */
export const client = mode === 'live' ? liveClient() : null;
