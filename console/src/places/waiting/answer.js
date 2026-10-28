// What a decision of the report (list.js) and a run's question (questions.js) share: the person's own words typed,
// and an answer sent.
import { said, t, num, esc, refresh, toast, S, store, radio, smallFold } from 'eaos';

/** The owner's own words for a decision or a question (`input` its typing act): the box, the note under it (what the
 *  words do) and how many characters are written. */
export const ownBox = (id, input, note) => `<div class="own stack-2"><label class="sr-only" for="own-${esc(id)}">${t('wt.own')}</label>
      <textarea class="input" id="own-${esc(id)}" data-fk="own-${esc(id)}" data-input="${input}" data-id="${esc(id)}" maxlength="4000" placeholder="${esc(t('wt.own.ph'))}">${esc(S.own[id] || '')}</textarea>
      <div class="small muted own__foot"><span>${note}</span><span class="num" id="own-count-${esc(id)}">${esc(t('wt.own.count', { n: num((S.own[id] || '').length) }))}</span></div></div>`;
/** Why a card asks, folded at its foot. */
export const whyFold = body => smallFold('info', t('wt.why'), body, { cls: 'bleed bleed--end line-top wcard__why', body: 'small ink-2' });
/** One answer of a decision or a question `id`: never drawn off, only disabled where answers cannot be sent. */
export const choice = (id, o, chosen, lock, text) => radio({ name: `opt-${id}`, value: o.id, 'data-change': 'choose', 'data-id': id, 'data-fk': `opt-${id}-${o.id}`,
  checked: chosen === o.id, disabled: lock }, text, null, false);

/** Send stays off while offline, while sending, or with nothing chosen or typed. */
export const sendBlocked = (id, lock, chosen, ownOpen) => lock || S.sending[id] || !(chosen || (ownOpen && (S.own[id] || '').trim()));

/** The `own` words typed for one item: kept, counted, and its `sendAct` button live once there is something to send. */
export function ownTyped(el, sendAct) {
  S.own[el.dataset.id] = el.value;
  const c = document.getElementById('own-count-' + el.dataset.id);
  if (c) c.textContent = t('wt.own.count', { n: num(el.value.length) });
  const btn = document.querySelector(`[data-act="${sendAct}"][data-id="${CSS.escape(el.dataset.id)}"]`);
  if (btn) btn.disabled = !(S.chosen[el.dataset.id] || el.value.trim());
}

/** One answer sent by `work`: the item busy while it goes, the person's draft dropped once saved, a refusal said. */
export async function sendAnswer(id, work) {
  S.sending[id] = true; refresh();
  try {
    await work();
    delete S.chosen[id]; delete S.own[id]; delete S.ownOpen[id];
    toast(t('toast.saved'));
    store.refresh();
  } catch (e) {
    toast(said(e), { refusal: true });
  } finally { delete S.sending[id]; refresh(); }
}
