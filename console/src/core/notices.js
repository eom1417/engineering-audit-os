// Notices: a toast (a refusal stays until pressed), the screen reader's calm announcements (ACT-06: at most one every
// 3 s, the newest wins) and copying a request for the person's assistant.
import { esc, icon } from './format.js';
import { t } from './i18n.js';

export function toast(text, opts) {
  const host = document.getElementById('toasts');
  const el = document.createElement('div');
  const refusal = opts && opts.refusal;
  el.className = 'toast' + (refusal ? ' toast--refusal' : '');
  el.innerHTML = `${icon(refusal ? 'warn' : 'check')}<span>${esc(text)}</span>${opts && opts.link ? `<a href="${opts.link.href}">${esc(opts.link.text)}</a>` : ''}`;
  host.append(el);
  announce(text);
  if (refusal) el.addEventListener('click', () => el.remove());
  else setTimeout(() => el.remove(), 5000);
}

let lastAnnounce = 0, timer = 0;
export function announce(text) {
  const el = document.getElementById('announce');
  const wait = Math.max(0, 3000 - (Date.now() - lastAnnounce));
  clearTimeout(timer);
  timer = setTimeout(() => { el.textContent = text; lastAnnounce = Date.now(); }, wait);
}

export function copyText(text, said) {
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).catch(() => {});
  toast(said || t('toast.copy'));
}
