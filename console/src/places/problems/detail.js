// S-07 One problem with its evidence (PRB-06..10, PRB-15, PLN-05, FIX-01): why it matters, what the assistant
// decided, where it is, the facts it rests on with their lines of code, its place in the plan, the other problems of the
// same file and a note for whoever goes on after. Its sheet: one evidence fact (PRB-09).
import { ac, said, t, tn, L, num, esc, rich, icon, code, sev, chk, href, fmtWhen, sheet, act, refresh, toast, parseHash, offline, S, md, model, selection, client, rowWords, facts, titledBlock } from 'eaos';
import { component, who, keepQuery, kindWord } from './shared.js';

const enc = encodeURIComponent;
const confidence = c => (c == null ? null : c >= 0.9 ? 'confirmed' : c >= 0.6 ? 'likely' : 'hypothesis');
S.notes = S.notes || {};

function codeBlock(c) {
  const hidden = new Set(c.hidden || []);
  return `<div class="code">${c.lines.map((l, i) => {
    const n = c.start + i;
    if (hidden.has(n)) return `<div class="code__line"><span class="code__ln">${n}</span><span class="code__hidden">${t('pd.ev.hidden')}</span></div>`;
    return `<div class="code__line ${n === c.line ? 'code__line--mark' : ''}"><span class="code__ln">${n}</span><span>${esc(l)}</span></div>`;
  }).join('')}</div>`;
}

function noCode(f, earlier) {
  if (f.line == null) return t('pd.ev.no_line');
  return t(earlier.some(e => e && e.path === f.path) ? 'pd.ev.no_code.same_as' : 'pd.ev.no_code.not_read');
}

function where(f) { return f.path ? `<div class="code__path" style="margin:0"><bdi class="mono">${esc(f.path)}${f.line != null ? ':' + f.line : ''}</bdi></div>` : ''; }
function others(f) {
  const sites = (f.sites || []).filter(s => s.path);
  return sites.length ? `<p class="small muted">${t('pd.ev.others', { list: sites.slice(0, 6).map(s => code(s.path + (s.line != null ? ':' + s.line : ''))).join(' ') })}</p>` : '';
}

function factHTML(f, first, earlier) {
  return `<div class="fact">
    <div class="fact__top"><span>${f.engine ? `<span class="fact__engine">${esc(f.engine)}</span> ` : ''}${code(f.kind)}</span>
      <button class="btn btn--quiet btn--sm" data-act="sheet" data-sheet="fact:${esc(f.id)}">${t('pd.ev.open')}</button></div>
    ${where(f)}
    <p class="fact__sum">${rich(L(f.summary))}</p>
    ${f.code && first ? codeBlock(f.code) : f.code ? '' : `<p class="small muted">${noCode(f, earlier)}</p>`}
    ${others(f)}
  </div>`;
}

function decisionHTML(p) {
  const d = p.decision;
  if (d && d.state === 'fixes') {
    return `<div class="ai-block"><span class="ai-block__label">${icon('ai', 'icon--sm')}${t('ai.label')}</span>${md(L(d.text))}
      <p class="small muted mt-1">${t('ai.hypothesis')}</p></div>`;
  }
  if (d && d.state === 'asks') {
    const asked = model.decisions().find(x => x.id === d.decision);
    const saved = asked && asked.state === 'answered';
    const answer = saved && asked.saved ? asked.saved.label || asked.saved.text : '';
    return `<div class="ai-block"><span class="ai-block__label">${icon('ai', 'icon--sm')}${t('ai.label')}</span>
      <p class="mt-1">${esc(saved ? t('pd.decision.answered', { when: fmtWhen(asked.saved && asked.saved.at) }) : t('pd.decision.asks'))}</p>
      <p class="small ink-2 mt-1">${rich(L(d.question))}</p>
      ${saved ? `<p class="mt-2"><span class="tag tag--ok">${icon('check')}${esc(L(answer))}</span></p>`
        : asked ? `<div class="actions mt-2"><a class="btn btn--secondary btn--sm" href="${href('/waiting/' + enc(asked.id))}">${t('pd.decision.answer')}</a></div>` : ''}</div>`;
  }
  return `<p class="small ink-2">${t('pd.decision.none')}</p>`;
}

function planHTML(p, all) {
  const step = model.plan().steps.find(s => s.id === p.milestone);
  if (!step) return `<p class="small ink-2">${t('pd.plan.none')}</p>`;
  const ids = step.tasks.map(x => x.id);
  const k = ids.indexOf(p.id) + 1;
  const sameFile = all.filter(x => x !== p && x.paths.some(path => p.paths.includes(path)));
  const waitsFor = sameFile.find(x => all.indexOf(x) < all.indexOf(p) && x.state === 'open');
  return `<div class="planline"><b>${esc(k ? t('pd.plan.task', { step: step.id, k: num(k), n: num(ids.length) }) : t('pd.plan.step', { step: step.id }))}</b>
      ${step.gate ? `<span>${esc(t('pd.plan.gate', { gate: L(step.gate) }))}</span>` : ''}
      <span>${waitsFor ? t('pd.plan.waits.on', { id: `<a class="link" href="${href('/problems/' + enc(waitsFor.id))}">${code(waitsFor.id)}</a>` }) : t('pd.plan.waits')}</span></div>
    <div class="actions mt-3"><a class="btn btn--secondary btn--sm" href="${href('/problems/plan/' + enc(step.id))}">${t('pd.plan.open')}</a></div>`;
}

function noteHTML(p) {
  const note = S.notes[p.id];
  if (note) return `<div class="saved"><b>${icon('check', 'icon--sm')} ${esc(note)}</b><span>${t('pd.note.kept')}</span></div>`;
  if (offline()) return `<p class="small muted">${icon('lock', 'icon--sm')} ${t('pd.note.offline')}</p>`;
  return `<label class="sr-only" for="note-${esc(p.id)}">${t('pd.note')}</label>
    <textarea class="input" id="note-${esc(p.id)}" data-fk="note-${esc(p.id)}" placeholder="${esc(t('pd.note.ph'))}"></textarea>
    <div><button class="btn btn--secondary btn--sm" data-act="note-save" data-id="${esc(p.id)}">${t('pd.note.save')}</button></div>
    <p class="small muted">${t('pd.note.kept')}</p>`;
}

export function detailHTML(p, ctx) {
  const all = model.problems();
  const sameFile = all.filter(x => x !== p && x.paths.some(path => p.paths.includes(path)));
  const conf = confidence(p.confidence);
  const primary = (p.decision && p.decision.state === 'fixes') || (p.fixable && !p.needs_decision) ? 'fix' : 'explain';
  const verbs = ['fix', 'verify', 'explain', 'plan'].map(v => `<button class="btn ${v === primary ? 'btn--primary' : 'btn--secondary'}" data-act="sheet" data-sheet="${ctx.offline ? 'open-live' : `verb:${v}:${esc(p.id)}`}">${t('verb.' + v)}</button>`).join('');
  const read = (p.evidence || []).map(model.fact);
  const known = read.filter(Boolean);
  const evidence = known.length
    ? `<div class="panel rows">${known.map((f, i) => factHTML(f, i === 0, known.slice(0, i))).join('')}</div>${read.length > known.length ? `<p class="small muted mt-2">${esc(t('pd.ev.unread', { n: num(read.length - known.length) }))}</p>` : ''}`
    : `<p class="small muted">${t(p.evidence && p.evidence.length ? 'pd.ev.notloaded' : 'pd.ev.none')}</p>`;
  const places = p.paths.slice(0, 6).map(path => `<li class="place">${icon('file', 'icon--sm muted')}<bdi class="mono">${esc(path)}</bdi>
      <button class="btn btn--quiet btn--sm" data-act="sheet" data-sheet="impact:${esc(path)}">${t('pd.touches')}</button></li>`).join('')
    + (p.paths.length > 6 ? `<li class="small muted pad-2-3">${esc(tn('pl.file', p.paths.length - 6))} ${t('more')}</li>` : '');
  return `<article class="pdetail" aria-labelledby="pd-title">
    ${ac.back('/problems', t('pd.back'), keepQuery(parseHash().query))}
    <header class="pdetail__head">
      <div class="pdetail__tags">${sev(p.severity)}
        ${who(p) === 'you' ? `<span class="tag tag--you">${t('who.you')}</span>` : `<span class="tag tag--eaos">${t('who.eaos')}</span>`}
        <span class="tag tag--state">${t('state.' + p.state)}</span>${conf ? `<span class="tag tag--state">${t('pd.conf.' + conf)}</span>` : ''}${code(p.id)}</div>
      <h2 class="title" id="pd-title">${rich(L(p.title))}</h2>
      <div class="verbs">${verbs}</div>
      <label class="small ink-2 pick mt-1">${chk(`data-change="sel" value="${esc(p.id)}" data-fk="dsel-${esc(p.id)}"`, selection.picked.ids.has(p.id), t('pd.select'))}<span class="pick__label">${t('pd.select')}</span></label>
    </header>
    ${p.why ? `<section class="psec"><h2>${t('pd.why')}</h2><p>${rich(L(p.why))}</p></section>` : ''}
    <section class="psec" id="pd-decision"><h2>${t('pd.decision')}</h2>${decisionHTML(p)}</section>
    <section class="psec"><h2>${t('pd.where')}</h2><ul class="places">${places}</ul>
      ${facts([
          [t('pd.component'), code(component(p))],
          [t('pd.area'), t('area.' + (p.category || 'none'))],
          [t('pd.kind'), esc(kindWord(p.kind))],
        ], 'mt-3')}</section>
    <section class="psec"><h2>${t('pd.evidence')} <span class="muted small">${read.length ? esc(tn('pl.fact', read.length)) : ''}</span></h2>${evidence}</section>
    <section class="psec"><h2>${t('pd.plan')}</h2>${planHTML(p, all)}</section>
    <div class="panel">
      <details class="fold"><summary>${rowWords(t('pd.same'), esc(tn('pl.problem', sameFile.length)))}${icon('chev', 'chev')}</summary>
        <div class="fold__body">${sameFile.length ? `<ul class="rows">${sameFile.map(x => `<li><a class="row" style="padding-inline:0" href="${href('/problems/' + enc(x.id))}">${sev(x.severity, false)}<span class="row__main small">${code(x.id)} ${rich(L(x.title))}</span></a></li>`).join('')}</ul>` : `<p class="small muted">${t('pd.same.none')}</p>`}</div></details>
      <details class="fold" style="border-top:1px solid var(--line)" ${S.notes[p.id] ? 'open' : ''}><summary>${icon('note', 'muted')}${rowWords(t('pd.note'))}${icon('chev', 'chev')}</summary>
        <div class="fold__body stack-2">${noteHTML(p)}</div></details>
    </div>
  </article>`;
}

/* ---------- one evidence fact (PRB-09) ---------- */
sheet('fact', {
  needs: ['cards', 'evidence'],
  kind: 'drawer',
  render(id) {
    const f = model.fact(id);
    if (!f) return { title: esc(t('pd.notfound', { id })), body: `<p class="small ink-2">${t('pd.notfound.guide')}</p>` };
    return {
      title: `${f.engine ? esc(f.engine) + ' ' : ''}${code(f.kind)}`,
      sub: code(id),
      body: `<p>${rich(L(f.summary))}</p>
        ${facts([
            [t('pd.kind'), code(f.kind)],
            f.path ? [t('pd.where'), code(f.path + (f.line != null ? ':' + f.line : ''))] : '',
          ])}
        ${f.code ? codeBlock(f.code) : `<p class="small muted">${noCode(f, [])}</p>`}
        ${others(f)}
        ${titledBlock(t('pd.ev.rests'), `<div class="panel rows">${f.cards.map(c => { const p = model.problem(c); return p ? `<a class="row" href="${href('/problems/' + enc(c))}" data-act="go" data-href="${href('/problems/' + enc(c))}">${sev(p.severity, false)}<span class="row__main small">${code(c)} ${rich(L(p.title))}</span></a>` : ''; }).join('')}</div>`)}`,
    };
  },
});

/* ---------- a note on the problem for whoever goes on after (PRB-15): the `note` action, kept in the handover ---------- */
act('note-save', async el => {
  const id = el.dataset.id;
  const ta = document.getElementById('note-' + id);
  const text = ta && ta.value.trim();
  if (!text || !client || el.disabled) return;
  el.disabled = true;
  try {
    await client.start({ action: 'note', inputs: { text, card: id } });
    S.notes[id] = text;
    refresh();
    toast(t('pd.note.saved'));
  } catch (e) {
    el.disabled = false;
    toast(said(e), { refusal: true });
  }
});
