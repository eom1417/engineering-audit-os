// S-05 Questions from runs (builder A): DEC-02..06, FIX-08, FIX-14. A run stops and asks when only the owner can
// decide (GET /api/questions: which branch, consent to run the app, the assistant not answering, the changes that
// fail together, or the assistant's own question); the answer resumes the same run (POST /api/questions/<id>/answer),
// an option or the owner's own words: their answer, never counted as consent, and a clarification only where EAOS
// carries out the option itself (`binding`).
import { t, num, esc, rich, icon, code, href, fmtWhen, L, screen, act, refresh, toast, offline, S, live, store, client, ActionError, ac } from 'eaos';

const answered = {};   // question id -> what was sent in this visit
const WHY = { branch: 'branch', 'run consent': 'consent', assistant: 'assistant', together: 'together' };
const kindOf = q => WHY[q.why] || 'other';
/** What the person's own words do: their answer, or, where only an option answers (`binding`), a clarification. */
const ownNote = q => (kindOf(q) === 'consent' ? 'ac.q.own.consent' : q.binding ? 'wt.own.clarify' : 'wt.own.note');

function card(q) {
  const run = ac.runOf(q.run);
  const meta = `<span class="tag tag--owner">${icon('seal')}${t('owner.only')}</span>${run ? `<span class="muted small">${esc(t('ac.q.from', { label: ac.runLabel(run) }))}</span>` : ''}<a class="link small" href="${href('/activity/run/' + encodeURIComponent(q.run))}">${code(q.run)}</a>`;
  const sent = answered[q.id];
  if (sent) {
    return `<article class="panel wcard wcard--done" id="w-${esc(q.id)}" aria-labelledby="wq-${esc(q.id)}"><div class="wcard__meta">${meta}</div><h3 class="wcard__q" id="wq-${esc(q.id)}">${rich(L(q.text))}</h3>
      <div class="saved" role="status"><b>${icon('check', 'icon--sm')} ${esc(sent.label ? t('ac.q.saved', { answer: sent.label }) : t('ac.q.saved.own'))}</b><span>${t(sent.label ? (sent.option === 'no' ? 'ac.q.saved.no' : 'ac.q.saved.note') : ownNote(q))}</span></div></article>`;
  }
  const lock = offline();
  const chosen = S.chosen[q.id];
  const opts = (q.options || []).slice().sort((a, b) => (a.id === q.recommendation ? -1 : b.id === q.recommendation ? 1 : 0));
  const radios = opts.map(o => `<label class="opt"><input type="radio" name="opt-${esc(q.id)}" value="${esc(o.id)}" data-change="choose" data-id="${esc(q.id)}" data-fk="opt-${esc(q.id)}-${esc(o.id)}" ${chosen === o.id ? 'checked' : ''} ${lock ? 'disabled' : ''}><span class="opt__dot" aria-hidden="true"></span>
    <span class="opt__text">${kindOf(q) === 'branch' ? `<bdi class="mono">${esc(o.id)}</bdi><span class="opt__note">${rich(L(o.label))}</span>` : rich(L(o.label))}${o.id === q.recommendation ? `<span class="tag tag--you">${t('wt.recommended')}</span>` : ''}</span></label>`).join('');
  const ownOpen = S.ownOpen[q.id];
  const own = ownOpen ? `<div class="own" style="display:grid;gap:8px"><label class="sr-only" for="own-${esc(q.id)}">${t('wt.own')}</label>
      <textarea class="input" id="own-${esc(q.id)}" data-fk="own-${esc(q.id)}" data-input="ac-q-own" data-id="${esc(q.id)}" maxlength="4000" placeholder="${esc(t('wt.own.ph'))}">${esc(S.own[q.id] || '')}</textarea>
      <div class="small muted" style="display:flex;justify-content:space-between;gap:12px"><span>${t(ownNote(q))}</span><span class="num" id="own-count-${esc(q.id)}">${esc(t('wt.own.count', { n: num((S.own[q.id] || '').length) }))}</span></div></div>` : '';
  const sending = S.sending[q.id];
  const off = lock || sending || !(chosen || (ownOpen && (S.own[q.id] || '').trim()));
  return `<article class="panel wcard" id="w-${esc(q.id)}" aria-labelledby="wq-${esc(q.id)}">
    <div class="wcard__meta">${meta}</div>
    <div><h3 class="wcard__q" id="wq-${esc(q.id)}">${rich(L(q.text))}</h3></div>
    <fieldset class="opts" style="border:0;padding:0;margin:0"><legend class="sr-only">${rich(L(q.text))}</legend>${radios}</fieldset>
    ${own}
    ${lock ? `<p class="small muted">${icon('lock', 'icon--sm')} ${t('wt.offline')}</p>` : ''}
    <div class="wcard__actions">
      <button class="btn btn--primary" data-act="ac-q-send" data-id="${esc(q.id)}" data-fk="send-${esc(q.id)}" ${off ? 'disabled' : ''} aria-describedby="${off ? 'pick-' + esc(q.id) : ''}">${sending ? t('wt.sending') : t('wt.send')}</button>
      ${ownOpen || lock ? '' : `<button class="btn btn--plain" data-act="own-open" data-id="${esc(q.id)}">${t('wt.own')}</button>`}
      <span class="sr-only" id="pick-${esc(q.id)}">${t('wt.pick')}</span></div>
    <details class="fold" style="margin:0 -16px -16px;border-top:1px solid var(--line);border-radius:0 0 12px 12px"><summary>${icon('info', 'muted')}<span class="row__main small">${t('wt.why')}</span>${icon('chev', 'chev icon--sm')}</summary>
      <div class="fold__body small ink-2">${t('ac.q.why.' + kindOf(q))}${q.asked ? ' ' + esc(t('wt.asked', { when: fmtWhen(q.asked) })) + '.' : ''}</div></details>
  </article>`;
}

function questionsPage(ctx) {
  const back = `<a class="back" href="${href('/waiting')}">${icon('back', 'icon--dir')}${t('wt.item.back')}</a>`;
  if (ctx.offline) return `<div class="page">${back}<h1 class="lede">${t('ac.q.offline')}</h1><p class="guide">${t('ac.q.offline.guide')}</p><div class="actions"><button class="btn btn--primary" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button></div></div>`;
  const list = live.questions.concat(Object.keys(answered).filter(id => !live.questions.some(q => q.id === id)).map(id => answered[id].question));
  return `<div class="page">
    ${back}
    <h1 class="lede">${t('ac.q.lede')}</h1>
    <p class="guide">${t('ac.q.guide')}</p>
    <section class="wgroup" style="margin-top:32px" aria-labelledby="g-q"><div class="wgroup__head"><h2 id="g-q">${t('wt.g.questions')}</h2>${live.questions.length ? `<span class="count" aria-hidden="true">${num(live.questions.length)}</span>` : ''}</div>
      ${list.length ? `<div style="display:grid;gap:12px">${list.map(card).join('')}</div>`
        : `<div class="panel empty"><p class="empty__title">${t(live.loaded ? 'wt.q.none' : 'st.loading')}</p><p class="small ink-2">${t('ac.q.none.guide')}</p><a class="btn btn--secondary" href="${href('/activity')}">${t('nav.activity')}</a></div>`}</section>
  </div>`;
}
screen({ id: 'S-05', path: '/waiting/questions', place: 'waiting', title: () => t('wt.g.questions'), render: questionsPage });

act('ac-q-own', el => {
  S.own[el.dataset.id] = el.value;
  const c = document.getElementById('own-count-' + el.dataset.id);
  if (c) c.textContent = t('wt.own.count', { n: num(el.value.length) });
  const btn = document.querySelector(`[data-act="ac-q-send"][data-id="${CSS.escape(el.dataset.id)}"]`);
  if (btn) btn.disabled = !(S.chosen[el.dataset.id] || el.value.trim());
});
act('ac-q-send', async el => {
  const id = el.dataset.id;
  const q = live.questions.find(x => x.id === id);
  const option = S.chosen[id] || null, text = option ? null : (S.own[id] || '').trim() || null;
  if (!q || (!option && !text) || !client || S.sending[id]) return;
  S.sending[id] = true; refresh();
  try {
    const run = await client.answer(id, option, text);
    const opt = (q.options || []).find(o => o.id === option);
    answered[id] = { question: q, option, label: opt ? L(opt.label) : null };
    delete S.chosen[id]; delete S.own[id]; delete S.ownOpen[id];
    store.patchRun(run.id, run);
    toast(t('toast.saved'));
    store.refresh();
  } catch (e) {
    toast(e instanceof ActionError ? e.message : String(e), { refusal: true });
  } finally { delete S.sending[id]; refresh(); }
});
