// Ask your assistant (builder A): S-52, and EAOS.askAPI, the one conversation the floating assistant shows too
// (src/core/assist.js). CHT-01..07, PRB-13, PRB-15, AST-05. A turn goes to the person's own assistant (POST /api/chat:
// it may only read; eaos/interfaces/studio/chat.py) and is followed as it is written (GET /api/chat/<turn>: what it reads
// now and the answer so far); what it proposes comes back as cards the person confirms in the action's usual preview,
// or a run's control they send. Direct control for an hour (owner) on /api/chat/control. The conversation goes on in
// the assistant's own session and is kept for the tab. Also ?q= (asks at once), ?run=<id> (about a run),
// ?records=1&q= (the check's records, the free `ask` tool) and ?note=project (a note, the `note` action).
import {
  t, num, L, esc, rich, icon, code, href, fmtTime, screen, act, refresh, refreshSoon, redrawAssist, toast, announce, parseHash, setQuery, searchTyped, openSheet, offline,
  S, live, store, client, contract, ActionError, prefs, ac, md,
} from 'eaos';

const KEY = 'eaos.chat';
const said = e => (e instanceof ActionError ? e.message : String(e));
function load() { try { return JSON.parse(sessionStorage.getItem(KEY)) || null; } catch (e) { return null; } }
const conv = load() || { session: null, turns: [] };
// a turn that was being written when the page was reloaded is followed again
conv.turns.filter(x => x.pending && x.turn).forEach(x => setTimeout(() => poll(x), 0));
function save() { try { sessionStorage.setItem(KEY, JSON.stringify(conv)); } catch (e) { /* private mode: this page only */ } }
const draw = () => { if (parseHash().path === '/ask') refreshSoon(); redrawAssist(); };
S.ac = S.ac || { prefill: {} };
S.ac.prefill = S.ac.prefill || {};
const dc = { on: false, until: null, read: false };
const ready = () => (live.assistants || []).find(a => a.installed && a.logged_in);

/* ---------- one turn ---------- */
const cost = x => (x.usage && x.usage.cost_usd != null ? x.usage.cost_usd : null);
function proposalHTML(p, i, k) {
  const a = p.kind === 'action' ? contract.actionOf(p.action) : null;
  const title = p.kind === 'action' ? (a ? L(a.label) : p.action) : t('ac.ask.ctl.' + p.action, { run: p.run });
  const sent = p.sent ? `<span class="tag tag--ok">${icon('check')}${t('ac.ask.sent')}</span>` : '';
  const btn = sent || (p.kind === 'action'
    ? `<button class="btn btn--secondary btn--sm" data-act="ac-ask-prop" data-i="${i}" data-k="${k}">${t('ac.ask.preview')}</button>`
    : `<button class="btn btn--secondary btn--sm" data-act="ac-ask-control" data-i="${i}" data-k="${k}">${t('ac.ask.send_control')}</button>`);
  return `<li class="ac-prop"><span class="row__main"><span class="row__title small">${esc(title)}</span><span class="row__meta" style="display:block">${rich(p.why || '')}</span></span>${btn}</li>`;
}
// the owner's own question
function youTurn(x) {
  return `<li class="ac-turn ac-turn--you"><div class="ac-bubble"><p>${rich(x.text)}</p></div>
      <span class="ac-turn__meta small muted">${esc(fmtTime(x.at))}${x.about ? `, ${esc(t('ac.ask.about', { id: x.about }))}` : ''}</span></li>`;
}
// an answer still coming: what the assistant reads, and what it wrote so far
function pendingTurn(x, i, who) {
  return `<li class="ac-turn ac-turn--ai" id="ac-pending-${i}" aria-busy="true"><div class="ai-block"><span class="ai-block__label">${icon('ai', 'icon--sm')}${esc(who)}</span>
      <p class="small muted ac-reading"><span class="dot dot--live" aria-hidden="true"></span>${esc(x.reading && x.reading.length ? t('ac.ask.reading', { tools: x.reading.join(t('list.sep')) }) : t('ac.ask.thinking'))}</p>
      ${x.partial ? `${md(x.partial)}<span class="ac-caret" aria-hidden="true"></span>` : ''}</div></li>`;
}
// an answer that failed, with a retry
function failedTurn(x, i) {
  return `<li class="ac-turn ac-turn--ai"><div class="ac-note ac-note--fail">${icon('fail', 'icon--sm ac-c-danger')}<span class="small">${esc(t('ac.ask.failed', { why: x.error }))}</span></div>
      <div class="actions" style="margin-top:8px"><button class="btn btn--secondary btn--sm" data-act="ac-ask-retry" data-i="${i}">${icon('retry')}${t('ac.ctl.retry')}</button></div></li>`;
}
function turnHTML(x, i) {
  if (x.who === 'you') return youTurn(x);
  const who = x.assistant || (ready() ? ready().name : t('ai.label'));
  if (x.pending) return pendingTurn(x, i, who);
  if (x.error) return failedTurn(x, i);
  return answerTurn(x, i, who);
}
// a finished answer: what it read, the answer, what it started and what it proposes
function answerTurn(x, i, who) {
  const props = (x.proposals || []).map((p, k) => proposalHTML(p, i, k)).join('');
  const done = (x.done || []).map(d => d.run ? `<a class="tag tag--state" href="${href('/activity/run/' + encodeURIComponent(d.run))}">${icon('play')}${esc(t('ac.ask.done.run', { run: d.run }))}</a>` : `<span class="tag tag--caution">${esc(t('ac.ask.done.not', { why: d.error || '' }))}</span>`).join(' ');
  const c = cost(x);
  return `<li class="ac-turn ac-turn--ai"><div class="ai-block"><span class="ai-block__label">${icon('ai', 'icon--sm')}${esc(who)}</span>
      ${(x.reading || []).length ? `<details class="ac-ev-fold"><summary class="small muted">${esc(t('ac.ask.read', { n: num(x.reading.length) }))}${icon('chev-down', 'icon--sm muted')}</summary><p class="small muted">${x.reading.map(code).join(' ')}</p></details>` : ''}
      ${md(x.answer)}
      ${done ? `<p class="small" style="margin-top:8px">${done}</p>` : ''}
      ${props ? `<div class="block-title" style="margin-top:12px">${t('ac.ask.props')}</div><ul class="ac-props">${props}</ul>` : ''}</div>
    <span class="ac-turn__meta small muted">${esc(fmtTime(x.at))}, ${t('as.depth.' + (x.depth || 'quick'))}${c != null ? `, ${ac.money(c)}` : ''}</span></li>`;
}

/* ---------- asking ---------- */
async function poll(x) {
  if (!client) return;
  try {
    const p = await client.chatProgress(x.turn);
    x.reading = p.reading || x.reading; x.partial = p.partial || x.partial;
    if (p.done) {
      x.pending = false;
      if (p.error || !p.result) x.error = p.error || t('ac.ask.noanswer');
      else {
        Object.assign(x, { answer: p.result.answer, proposals: p.result.proposals || [], done: p.result.done || [], assistant: p.result.assistant, usage: p.result.usage });
        if (p.result.session) conv.session = p.result.session;
        if ((p.result.done || []).length) store.refresh();
      }
      save(); draw(); announce(t('ac.ask.answered'));
      return;
    }
    draw();
  } catch (e) { x.pending = false; x.error = said(e); save(); draw(); return; }
  setTimeout(() => poll(x), 800);
}
/** One question to the assistant; `about` the page it was asked from ({kind, id, label}), `depth` quick, balanced or deep. */
async function send(text, about, depth) {
  if (!client || !text) return;
  const mine = { who: 'you', at: new Date().toISOString(), text, about: about && about.kind !== 'place' ? about.label || about.id : null };
  const answer = { who: 'ai', at: new Date().toISOString(), pending: true, depth: depth || 'quick', reading: [], partial: '' };
  conv.turns.push(mine, answer);
  save(); draw();
  const context = Object.assign({ page: parseHash().path, lang: prefs.lang }, about || {}, about && about.kind === 'run' ? { run: about.id } : {});
  try {
    const r = await client.chat(text, conv.session, context, depth || 'quick');
    answer.turn = r.turn; save();
    poll(answer);
  } catch (e) { answer.pending = false; answer.error = said(e); save(); draw(); }
}

/* ---------- direct control (CHT-04) ---------- */
function readControl() {
  if (!client || dc.read) return;
  dc.read = true;
  client.chatControl().then(c => { Object.assign(dc, c); draw(); }, () => {});
}
function control() {
  readControl();
  const on = dc.on;
  return `<details class="panel fold" ${on ? 'open' : ''}><summary>${icon('seal', 'muted')}<span class="row__main"><span class="row__title">${t('ac.ask.dc')}</span>
      <span class="row__meta" style="display:block">${on ? t('ac.ask.dc.on') : t('ac.ask.dc.off')}</span></span>${icon('chev', 'chev')}</summary>
    <div class="fold__body ac-stack">
      <div class="toggle-row"><span><span style="display:flex;gap:8px;align-items:center">${icon('seal', 'icon--sm')}${t('ac.ask.dc.switch')}</span><span class="small muted">${t('owner.only')}</span></span>
        <span class="switch"><input type="checkbox" data-change="ac-direct" data-fk="direct" ${on ? 'checked' : ''} ${offline() ? 'disabled' : ''} aria-label="${esc(t('ac.ask.dc.switch'))}"><span class="switch__track"></span><span class="switch__thumb"></span></span></div>
      <p class="small ink-2">${t('ac.ask.dc.may')}</p>
      <p class="small ink-2"><b>${t('ac.ask.dc.never.t')}</b> ${t('ac.ask.dc.never')}</p>
      <p class="small muted">${t('ac.ask.dc.note')}</p></div></details>`;
}
/** The one conversation, for the floating assistant (src/core/assist.js). Its cost comes from each answer's usage. */
self.EAOS.askAPI = { chat: () => conv.turns.map(x => Object.assign({}, x, { cost: x.who === 'ai' ? cost(x) : null })), turnHTML, control, send };

/* ---------- S-52 ---------- */
function composer(q) {
  const depth = S.ac.depth || 'quick';
  const v = S.ac.draft || '';
  const run = q.run && ac.runOf(q.run);
  const thinking = conv.turns.some(x => x.pending);
  const chip = run ? `<span class="chip">${icon('activity')}${esc(t('ac.ask.ctx.run', { id: run.id, label: ac.runLabel(run) }))}
      <a class="ac-chip-x" href="${href('/ask')}" aria-label="${esc(t('ac.ask.ctx.remove'))}">${icon('x', 'icon--sm')}</a></span>` : `<span class="chip">${icon('status')}${t('ac.ask.ctx.project')}</span>`;
  return `<div class="panel ac-composer">
    <div class="context" style="margin:0">${chip}</div>
    <label class="sr-only" for="ask-in">${t('as.ph')}</label>
    <textarea class="input" id="ask-in" data-fk="ask-in" data-input="ac-draft" maxlength="8000" placeholder="${esc(t('as.ph'))}">${esc(v)}</textarea>
    <div class="ac-composer__row">
      <div class="seg" role="group" aria-label="${esc(t('as.depth'))}">${['quick', 'balanced', 'deep'].map(d => `<button type="button" data-act="ac-depth" data-d="${d}" data-fk="depth-${d}" aria-pressed="${depth === d}">${t('as.depth.' + d)}</button>`).join('')}</div>
      <span class="small muted num" id="ask-count">${esc(t('ac.ask.count', { n: num(v.length) }))}</span>
    </div>
    <p class="small muted">${t('ac.ask.depth.note.' + depth)}</p>
    <div class="ac-composer__row"><button class="btn btn--primary" data-act="ac-send" data-fk="ask-send" ${v.trim() && !thinking ? '' : 'disabled'} aria-describedby="ask-why">${thinking ? t('as.thinking') : t('ac.ask.send')}</button>
      <button class="btn btn--quiet" data-act="ac-new">${t('ac.ask.new')}</button><span class="sr-only" id="ask-why">${t('ac.ask.empty')}</span></div>
  </div>`;
}

const records = { q: null, answer: null, busy: false, problem: null };
function recordsPage(q) {
  const qq = (q.q || '').trim();
  if (qq && records.q !== qq && client) {
    Object.assign(records, { q: qq, answer: null, busy: true, problem: null });
    client.start({ action: 'ask', inputs: { question: qq } }).then(run => { records.busy = false; records.answer = (run.result && run.result.answer) || {}; refresh(); },
      e => { records.busy = false; records.problem = said(e); refresh(); });
  }
  const hits = (records.answer && records.answer.answers) || [];
  return `<div class="page">
    <h1 class="lede">${esc(qq ? t('ac.rec.lede', { q: qq }) : t('ac.rec.search'))}</h1>
    <p class="guide">${t('ac.rec.guide')}</p>
    <div class="ptools"><label class="field">${icon('search')}<span class="sr-only">${t('ac.rec.search')}</span><input type="search" id="rec-q" data-fk="rec-q" data-input="ac-rec-q" value="${esc(q.q || '')}" placeholder="${esc(t('ac.rec.search'))}" autocomplete="off"></label></div>
    ${offline() ? `<div class="panel empty"><p class="small ink-2">${t('ac.ask.offline.guide')}</p></div>`
      : !qq ? `<div class="panel empty"><p class="small ink-2">${t('ac.rec.empty')}</p></div>`
        : records.problem ? `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(records.problem)}</p>`
          : records.busy ? `<p class="small muted" aria-busy="true">${t('st.loading')}</p>`
            : `<div class="listhead"><span class="listhead__count" aria-live="polite">${esc(t('ac.rec.count', { n: num(hits.length) }))}</span></div>
        ${hits.length ? `<ul class="panel rows">${hits.slice(0, 40).map(h => `<li class="row" style="align-items:flex-start">${icon('book', 'muted')}<span class="row__main"><span class="row__title small">${rich(h.text || h.id)}</span><span class="row__meta" style="display:block">${esc(h.kind || '')}${h.citation ? ' · ' : ''}<bdi class="mono">${esc(h.citation || '')}</bdi></span></span></li>`).join('')}</ul>`
          : `<div class="panel empty"><p class="small ink-2">${t('ac.rec.none')}</p></div>`}`}
    <div class="actions"><a class="btn btn--secondary" href="${href('/ask', qq ? { q: qq } : {})}">${icon('ask')}${t('ac.rec.ask')}</a></div>
  </div>`;
}

let noteSaved = null;
function notePage() {
  return `<div class="page">
    <a class="back" href="${href('/status')}">${icon('back', 'icon--dir')}${t('st.place')}</a>
    <h1 class="lede">${t('ac.note.lede')}</h1>
    <p class="guide">${t('ac.note.guide')}</p>
    ${noteSaved ? `<div class="saved section" role="status"><b>${icon('check', 'icon--sm')} ${esc(noteSaved)}</b><span>${t('pd.note.kept')}</span></div>
      <div class="actions"><a class="btn btn--secondary" href="${href('/status')}">${t('st.place')}</a><button class="btn btn--quiet" data-act="ac-note-again">${t('ac.note.another')}</button></div>`
    : offline() ? `<div class="actions"><button class="btn btn--primary" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button></div>`
      : `<div class="section ac-stack"><label class="sr-only" for="pnote">${t('st.stand.note')}</label><textarea class="input" id="pnote" data-fk="pnote" maxlength="4000" placeholder="${esc(t('ac.note.ph'))}"></textarea>
      <div><button class="btn btn--primary" data-act="ac-pnote">${t('pd.note.save')}</button></div></div>`}
  </div>`;
}

let asked = null;
function askPage(ctx) {
  const q = ctx.query;
  if (q.note) return notePage();
  if (q.records) return recordsPage(q);
  if (ctx.offline) {
    return `<div class="page"><h1 class="lede">${t('ac.ask.offline')}</h1><p class="guide">${t('ac.ask.offline.guide')}</p>
      <div class="actions"><button class="btn btn--primary" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button></div></div>`;
  }
  if (q.state === 'noasst' || (live.assistants && !ready())) {
    return `<div class="page"><h1 class="lede">${t('ac.ask.noasst')}</h1><p class="guide">${t('ac.ask.noasst.guide', { cmd: code('claude login') })}</p>
      <div class="actions"><button class="btn btn--primary" data-act="copy" data-text="claude login">${icon('copy')}${t('copy')}</button><a class="btn btn--quiet" href="${href('/project/assistants')}">${t('proj.assistants')}</a></div></div>`;
  }
  // a question from Search or ask is asked at once (CHT-01)
  if (q.q && asked !== q.q && live.assistants) { asked = q.q; const run = q.run && ac.runOf(q.run); setTimeout(() => send(q.q, run ? { kind: 'run', id: run.id, label: run.id } : null, S.ac.depth || 'quick'), 0); }
  const turns = conv.turns;
  const answers = turns.filter(x => x.who === 'ai' && cost(x) != null);
  const total = answers.reduce((a, x) => a + cost(x), 0);
  const busy = ac.liveRun() && ac.liveRun().verb === 'fix';
  return `<div class="page">
    <h1 class="lede">${t('ac.ask.lede')}</h1>
    <p class="guide">${t('ac.ask.guide')}</p>
    ${busy ? `<div class="ac-note section">${icon('info', 'icon--sm')}<span class="small">${t('ac.ask.busy')}</span></div>` : ''}
    <section class="section" aria-labelledby="conv-h"><div class="section-head"><h2 id="conv-h">${t('ac.ask.conv')}</h2><span class="small muted">${esc(t('ac.ask.conv.sum', { n: num(turns.filter(x => x.who === 'you').length) }))}</span></div>
      ${turns.length ? `<ol class="ac-chat" aria-live="polite">${turns.map(turnHTML).join('')}</ol>` : `<div class="panel empty"><p class="small ink-2">${t('ac.ask.empty.conv')}</p></div>`}</section>
    <section class="section" aria-label="${esc(t('as.ph'))}">${composer(q)}</section>
    <div class="section">${control()}</div>
    <p class="list-foot">${esc(t('ac.ask.cost', { n: num(answers.length), cost: ac.money(total) }))} <a href="${href('/project/assistants')}">${t('proj.assistants')}</a></p>
  </div>`;
}
screen({ id: 'S-52', path: '/ask', place: 'ask', title: () => t('ac.ask.title'), render: askPage });

act('ac-draft', el => {
  S.ac.draft = el.value;
  const c = document.getElementById('ask-count'); if (c) c.textContent = t('ac.ask.count', { n: num(el.value.length) });
  const b = document.querySelector('[data-act="ac-send"]'); if (b) b.disabled = !el.value.trim() || conv.turns.some(x => x.pending);
});
act('ac-send', el => {
  if (el.disabled) return;
  const v = (S.ac.draft || '').trim(), run = parseHash().query.run && ac.runOf(parseHash().query.run);
  if (!v) return;
  S.ac.draft = '';
  send(v, run ? { kind: 'run', id: run.id, label: run.id } : null, S.ac.depth || 'quick');
});
act('ac-depth', el => { S.ac.depth = el.dataset.d; refresh(); });
act('ac-new', () => { conv.session = null; conv.turns = []; save(); refresh(); toast(t('ac.ask.new.done')); });
act('ac-direct', async el => {
  if (!client) return;
  try { Object.assign(dc, await client.chatControl(el.checked)); toast(dc.on ? t('ac.ask.dc.on') : t('ac.ask.dc.turned_off')); }
  catch (e) { toast(said(e), { refusal: true }); }
  draw();
});
const propOf = el => { const x = conv.turns[Number(el.dataset.i)]; return x && x.proposals ? x.proposals[Number(el.dataset.k)] : null; };
act('ac-ask-prop', el => {
  const p = propOf(el);
  if (!p) return;
  if (p.action === 'audit') { openSheet('check'); return; }
  S.ac.prefill[p.action] = Object.fromEntries(Object.entries(p.inputs || {}).map(([k, v]) => [k, v != null && typeof v === 'object' && !Array.isArray(v) ? JSON.stringify(v) : v]));
  openSheet('action:' + p.action);
});
act('ac-ask-control', async el => {
  const p = propOf(el);
  if (!p || !client) return;
  try {
    const run = await client.control(p.run, p.action);
    p.sent = true; save();
    store.patchRun(run.id, run);
    toast(t('ac.ask.control.done', { label: ac.runLabel(run) }), { link: { href: href('/activity/run/' + encodeURIComponent(run.id)), text: t('toast.follow') } });
  } catch (e) { toast(said(e), { refusal: true }); }
  draw();
});
act('ac-ask-retry', el => {
  const i = Number(el.dataset.i), prev = conv.turns[i - 1];
  conv.turns.splice(i - 1, 2); save();
  if (q0().state) setQuery({ state: null });
  if (prev) send(prev.text, null, S.ac.depth || 'quick');
});
const q0 = () => parseHash().query;
act('ac-rec-q', el => searchTyped(el, 400));
act('ac-pnote', async () => {
  const ta = document.getElementById('pnote');
  if (!ta || !ta.value.trim() || !client) return;
  try { await client.start({ action: 'note', inputs: { text: ta.value.trim() } }); noteSaved = ta.value.trim(); refresh(); toast(t('pd.note.kept')); }
  catch (e) { toast(said(e), { refusal: true }); }
});
act('ac-note-again', () => { noteSaved = null; refresh(); });
