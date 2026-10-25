// What a decision of the report (list.js) and a run's question (questions.js) share: the person's own words typed,
// and an answer sent.
import { t, num, refresh, toast, S, store, ActionError } from 'eaos';

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
    toast(e instanceof ActionError ? e.message : String(e), { refusal: true });
  } finally { delete S.sending[id]; refresh(); }
}
