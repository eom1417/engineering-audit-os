// S-04 Sign in to your app (builder A): SGN-03..07. While a check waits for the owner's sign-in (GET /api/sign-in),
// a real browser on this computer (eaos/interfaces/studio_server/sign_in.py) is shown as a picture they drive: a press on the picture
// clicks there, typing and keys go to the field they clicked, scrolling and back; what the app sent (its last output
// lines, the mails its mail catcher caught) beside it. "I have signed in" saves the session for the owner alone and
// the check goes on; "Go on without" lets it go on signed out. Nothing typed is kept or logged.
import { t, esc, icon, code, href, fmtTime, rich, screen, sheet, act, refresh, toast, announce, closeSheetThen, afterRender, live, store, client, ActionError, ac } from 'eaos';

const LOOK = 1500;     // ms between two pictures while the browser is open
const STATUS = 4000;   // ms between two readings of what the check asks
const page = { status: null, view: null, busy: false, problem: null, done: null, timers: [] };
const said = e => (e instanceof ActionError ? e.message : String(e));

function stop() { page.timers.forEach(clearInterval); page.timers = []; }
afterRender(ctx => { if (ctx.path !== '/waiting/sign-in') stop(); });

async function readStatus() {
  if (!client) return;
  try { page.status = await client.signIn.status(); store.live.signIn = page.status; if (page.status.asked) page.done = null; } catch (e) { page.status = page.status || { asked: null }; }
  refresh();
}
async function send(command) {
  if (!client || page.busy) return;
  page.busy = true; page.problem = null;
  try { page.view = await client.signIn.input(command); } catch (e) { page.problem = said(e); }
  page.busy = false;
  refresh();
}

function picture() {
  const v = page.view;
  return `<div class="ac-browser" dir="ltr">
    <div class="ac-browser__bar">
      <button class="btn btn--icon btn--sm" data-act="ac-si-key" data-key="back" aria-label="${esc(t('ac.si.back'))}">${icon('back')}</button>
      <span class="ac-browser__addr"><bdi class="mono">${esc(v.url || '')}</bdi></span>
    </div>
    <button class="ac-browser__view" data-act="ac-si-click" aria-label="${esc(t('ac.si.view'))}" aria-describedby="si-fresh" style="padding:0">
      <img src="data:image/jpeg;base64,${esc(v.picture)}" alt="" style="display:block;width:100%;height:auto" draggable="false"></button>
    <div class="ac-browser__foot" dir="auto"><span class="small muted" id="si-fresh">${esc(t('ac.si.fresh', { title: v.title || '' }))}</span></div>
  </div>`;
}
function sentPanel(codes) {
  const out = (codes && codes.output) || [], mails = (codes && codes.mail) || [];
  if (!out.length && !mails.length) return `<p class="small muted">${t('ac.si.sent.none')}</p><p class="small muted">${t('ac.si.sms')}</p>`;
  return `<div class="ac-stack">
    ${out.length ? `<div><div class="block-title">${t('ac.si.output')}</div><div class="code pad-2-3 pre" dir="ltr">${esc(out.slice(-12).join('\n'))}</div></div>` : ''}
    ${mails.length ? `<div><div class="block-title">${t('ac.si.mails')}</div><ul class="panel rows">${mails.map(m => `<li class="row" style="align-items:flex-start"><span class="row__main" dir="auto"><span class="row__title small">${esc(m.subject || '')}</span>
      <span class="row__meta" style="display:block">${esc(t('ac.si.mail.to', { to: m.to || '' }))}${m.at ? ', ' + esc(fmtTime(m.at)) : ''}</span><span class="small ink-2" style="display:block;white-space:pre-wrap">${rich(m.text || '')}</span></span>
      <button class="btn btn--icon" data-act="copy" data-text="${esc(m.text || '')}" aria-label="${esc(t('ac.si.copy_text'))}">${icon('copy')}</button></li>`).join('')}</ul></div>` : ''}
    <p class="small muted">${t('ac.si.sms')}</p></div>`;
}

// the owner's answer was taken: signed in, or going on without
function donePage(back, check) {
  const follow = check ? `<a class="btn btn--primary" href="${href('/activity/run/' + encodeURIComponent(check.id))}">${t('ac.si.follow')}</a>` : '';
  const done = page.done === 'done';
  return `<div class="page">${back}<h1 class="lede">${t(done ? 'ac.si.done' : 'ac.si.skipped')}</h1><p class="guide">${t(done ? 'ac.si.done.guide' : 'ac.si.skipped.guide')}</p>
      <div class="actions">${follow}<a class="btn btn--quiet" href="${href('/project/app')}">${t(done ? 'ac.si.manage' : 'proj.app')}</a></div>
      ${done ? `<div class="ac-note section">${ac.glyph('ok')}<span class="small">${t('ac.si.private')}</span></div>` : ''}</div>`;
}
// no check waits for a sign-in now
function noAskPage(back, st) {
  return `<div class="page">${back}<h1 class="lede">${t('ac.si.none')}</h1><p class="guide">${t('ac.si.none.guide')}</p>
      ${st.kept ? `<div class="ac-note section">${ac.glyph('ok')}<span class="small">${t('ac.si.kept')}</span></div>` : ''}
      <div class="actions"><a class="btn btn--secondary" href="${href('/project/app')}">${t('proj.app')}</a>${st.kept ? `<button class="btn btn--quiet" data-act="sheet" data-sheet="forget">${t('ac.app.forget')}</button>` : ''}</div></div>`;
}
// why the check asks for a sign-in
function whyAsked(asked) {
  if (asked.published) return t('ac.si.why.published', { base: code(asked.base || '') });
  if (asked.why === 'expired' || asked.why === 'not_signed_in') return t('ac.si.why.' + asked.why);
  return t('ac.si.why.needed', { base: code(asked.base || '') }) + tried(asked.tried);
}
// what EAOS tried before asking: a test account of its own on the app's sign-up and sign-in pages
function tried(steps) {
  if (!steps || !steps.length) return '';
  return ' ' + t('ac.si.tried', { steps: steps.map((s) => t('ac.si.did.' + s.did, { at: code(s.at || '') })).join('، ') });
}
const KEY_BUTTONS = [['enter', 'ac.si.k.enter'], ['tab', 'ac.si.k.tab'], ['erase', 'ac.si.k.erase'], ['up', 'ac.si.k.up'], ['down', 'ac.si.k.down']];
// the browser picture (or the button that opens it), the typing field and the keys
function picSection(st, tab) {
  const view = page.view;
  return `<section class="ac-si-pic ${tab === 'sent' ? 'ac-hide-phone' : ''}" aria-label="${esc(t('ac.si.tab.pic'))}">
        ${view && view.picture ? picture() : `<div class="panel empty"><p class="small ink-2">${t(st.open ? 'st.loading' : 'ac.si.closed')}</p>
          <button class="btn btn--primary" data-act="ac-si-open" data-fk="si-open" ${page.busy ? 'disabled' : ''}>${t('ac.si.open')}</button></div>`}
        <div class="ac-si-type"><label class="field">${icon('note')}<span class="sr-only">${t('ac.si.type')}</span><input id="si-type" data-fk="si-type" type="text" autocomplete="off" placeholder="${esc(t('ac.si.type'))}" ${view ? '' : 'disabled'} aria-describedby="si-type-note"></label>
          <button class="btn btn--secondary" data-act="ac-si-send" ${view ? '' : 'disabled'}>${t('ac.si.type.send')}</button></div>
        <p class="small muted" id="si-type-note">${t(view ? 'ac.si.type.note' : 'ac.si.type.first')}</p>
        <div class="ac-si-keys" role="group" aria-label="${esc(t('ac.si.keys'))}">
          ${KEY_BUTTONS.map(([k, w]) => `<button class="btn btn--secondary btn--sm" data-act="ac-si-key" data-key="${k}" ${view ? '' : 'disabled'}>${t(w)}</button>`).join('')}</div>
      </section>`;
}
// a check waits for the owner's sign-in
function askedPage(q, st, back) {
  const asked = st.asked;
  const tab = q.tab === 'sent' ? 'sent' : 'pic';
  const until = asked.until ? fmtTime(asked.until) : '';
  const why = whyAsked(asked);
  const view = page.view;
  return `<div class="page ac-page--signin">
    ${back}
    <div class="context"><span class="tag tag--owner">${icon('seal')}${t('owner.only')}</span>${until ? `<span class="tag tag--caution">${icon('clock')}${esc(t('ac.si.until', { time: until }))}</span>` : ''}</div>
    <h1 class="lede">${t('ac.si.lede')}</h1>
    <p class="guide">${t('ac.si.guide')}</p>
    <p class="small ink-2 mt-2">${why}${until ? ' ' + esc(t('ac.si.then', { time: until })) : ''}</p>
    ${page.problem ? `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(page.problem)}</p>` : ''}
    <nav class="seg only-phone ac-si-tabs" aria-label="${esc(t('ac.si.tabs'))}"><a href="${href('/waiting/sign-in', Object.assign({}, q, { tab: null }))}" aria-current="${tab === 'pic'}">${t('ac.si.tab.pic')}</a><a href="${href('/waiting/sign-in', Object.assign({}, q, { tab: 'sent' }))}" aria-current="${tab === 'sent'}">${t('ac.si.tab.sent')}</a></nav>
    <div class="ac-si-grid">
      ${picSection(st, tab)}
      <section class="panel panel__pad ac-si-sent ${tab === 'pic' ? 'ac-hide-phone' : ''}" aria-labelledby="sent-h"><h2 class="h2 mb-3" id="sent-h">${t('ac.si.tab.sent')}</h2>${sentPanel(st.codes)}</section>
    </div>
    <div class="actions ac-si-acts">
      <button class="btn btn--primary" data-act="ac-si-done" data-fk="si-done" ${view && !page.busy ? '' : 'disabled'}>${t('ac.si.signed')}</button>
      <button class="btn btn--secondary" data-act="sheet" data-sheet="signin-skip">${t('ac.si.skip')}</button>
      <p class="actions__note">${t('ac.si.never_alone')}</p>
    </div>
  </div>`;
}

function signinPage(ctx) {
  const back = `<a class="back" href="${href('/waiting')}">${icon('back', 'icon--dir')}${t('wt.item.back')}</a>`;
  if (ctx.offline) return `<div class="page">${back}<h1 class="lede">${t('ac.si.offline')}</h1><p class="guide">${t('ac.si.offline.guide')}</p><div class="actions"><button class="btn btn--primary" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button></div></div>`;
  const st = page.status || live.signIn;
  const check = ac.lastCheck();
  if (page.done) return donePage(back, check);
  if (!st) return `<div class="page" aria-busy="true">${back}<h1 class="lede">${t('st.loading')}</h1></div>`;
  if (!st.asked) return noAskPage(back, st);
  return askedPage(ctx.query, st, back);
}

screen({
  id: 'S-04', path: '/waiting/sign-in', place: 'waiting', title: () => t('ac.si.title'), render: signinPage,
  after() {
    if (!client || page.timers.length) return;
    if (!page.status) readStatus();
    page.timers.push(setInterval(readStatus, STATUS));
    page.timers.push(setInterval(() => { if (page.view && !page.busy && document.visibilityState === 'visible') send({ do: 'look' }); }, LOOK));
  },
});

act('ac-si-open', async () => {
  if (!client || page.busy) return;
  page.busy = true; page.problem = null; refresh();
  try { page.view = await client.signIn.open(); } catch (e) { page.problem = said(e); }
  page.busy = false;
  readStatus();
});
act('ac-si-click', (el, e) => {
  const img = el.querySelector('img');
  if (!img) return;
  const box = img.getBoundingClientRect();
  // a keyboard press clicks the picture's centre
  const x = e && e.clientX ? e.clientX - box.left : box.width / 2, y = e && e.clientY ? e.clientY - box.top : box.height / 2;
  send({ do: 'click', x: Math.round(x * img.naturalWidth / box.width), y: Math.round(y * img.naturalHeight / box.height) });
  announce(t('ac.si.clicked'));
  const input = document.getElementById('si-type'); if (input) input.focus({ preventScroll: true });
});
act('ac-si-send', () => {
  const input = document.getElementById('si-type');
  if (!input || !input.value) return;
  const text = input.value;
  input.value = '';     // nothing typed stays on the page either
  send({ do: 'type', text });
});
// Enter in the field sends what was typed, as the "Type" button does
document.addEventListener('keydown', e => {
  if (e.target && e.target.id === 'si-type' && e.key === 'Enter' && !e.isComposing) {
    e.preventDefault();
    const button = document.querySelector('[data-act="ac-si-send"]'); if (button) button.click();
  }
});
const KEYS = { enter: { do: 'key', key: 'Enter' }, tab: { do: 'key', key: 'Tab' }, erase: { do: 'key', key: 'Backspace' }, up: { do: 'scroll', dy: -400 }, down: { do: 'scroll', dy: 400 }, back: { do: 'back' } };
act('ac-si-key', el => { if (el.disabled) return; send(KEYS[el.dataset.key]); announce(t('ac.si.key.sent', { key: el.textContent.trim() || el.dataset.key })); });
act('ac-si-done', async el => {
  if (el.disabled || !client) return;
  page.busy = true; refresh();
  try { page.status = await client.signIn.done(); page.done = 'done'; page.view = null; toast(t('ac.si.done.toast')); store.refresh(); } catch (e) { page.problem = said(e); }
  page.busy = false; refresh();
});
sheet('signin-skip', {
  kind: 'dialog',
  render() {
    return { title: esc(t('ac.si.skip.title')), body: `<p>${t('ac.si.skip.body')}</p>`,
      foot: `<div class="sheet__foot-row"><button class="btn btn--secondary" data-act="sheet-close" data-autofocus>${t('cancel')}</button><button class="btn btn--primary" data-act="ac-si-skip">${t('ac.si.skip.do')}</button></div>` };
  },
});
act('ac-si-skip', async () => {
  if (!client) return;
  try { page.status = await client.signIn.skip(); page.done = 'skipped'; page.view = null; } catch (e) { page.problem = said(e); }
  closeSheetThen(() => { refresh(); toast(t(page.done ? 'ac.si.skipped.toast' : 'ac.si.notskipped')); store.refresh(); });
});
