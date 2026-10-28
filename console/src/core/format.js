// Markup and time helpers every screen draws with. Times are shown in the person's time zone (prefs.tz), relative to
// now; paths, symbols and settings inside report texts are isolated left to right (SET-04).
import { prefs } from './prefs.js';
import { t, num } from './i18n.js';

export function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
export function icon(name, cls) { return `<svg class="icon ${cls || ''}" aria-hidden="true"><use href="#i-${name}"/></svg>`; }
export function code(s) { return `<bdi class="mono">${esc(s)}</bdi>`; }
/** A unified diff's lines, numbered, its added and removed lines marked (inside a `code diff` block). */
export function diffLines(lines) {
  return lines.map((l, i) => `<div class="code__line ${l.startsWith('+') && !l.startsWith('+++') ? 'code__line--add' : l.startsWith('-') && !l.startsWith('---') ? 'code__line--del' : ''}"><span class="code__ln">${i + 1}</span><span>${esc(l)}</span></div>`).join('');
}
/** A report text: isolated in its own script's direction (an Arabic sentence stays right to left on an English
 *  page, an engine's English line left to right on an Arabic one), with its paths and symbols isolated left to right. */
export function rich(s) {
  const dir = /[\u0600-\u06FF]/.test(String(s || '')) ? 'rtl' : 'ltr';
  return `<bdi dir="${dir}">${richInner(s)}</bdi>`;
}
function richInner(s) {
  return esc(s).replace(/[A-Za-z0-9_$@\-]+(?:[\/.=:][A-Za-z0-9_$@\-*]+)+/g, m => `<bdi class="tpath">${m.replace(/([\/.])/g, '$1<wbr>')}</bdi>`);
}
export function sev(level, withWord) {
  return `<span class="sev sev--${level}"><span class="sev__bars" aria-hidden="true"><i></i><i></i><i></i><i></i></span>${withWord === false ? `<span class="sr-only">${t('sev.' + level)}</span>` : `<span>${t('sev.' + level)}</span>`}</span>`;
}
export function chk(attrs, checked, label) {
  return `<label class="check"><input type="checkbox" ${attrs || ''} ${checked ? 'checked' : ''} aria-label="${esc(label || '')}"><span class="check__box">${icon('tick')}</span></label>`;
}
/** An action preview's estimate in words: minutes, hours past three, or that none could be made. */
export function estimate(p) {
  const lo = p.estimate && p.estimate.minutes_low, hi = p.estimate && p.estimate.minutes_high;
  if (lo == null || hi == null) return t('pv.estimate.none');
  return hi > 180 ? t('pv.estimate.h', { lo: num(Math.round(lo / 60)), hi: num(Math.ceil(hi / 60)) }) : t('pv.estimate.v', { lo: num(lo), hi: num(hi) });
}
/** A score's band; never good or excellent over ground this version does not check (partial: 'partial' instead). */
export function band(score, partial) {
  if (score == null) return null;
  const b = score < 40 ? 'critical' : score < 60 ? 'weak' : score < 75 ? 'fair' : score < 90 ? 'good' : 'excellent';
  return partial && (b === 'good' || b === 'excellent') ? 'partial' : b;
}

const locale = () => (prefs.lang === 'ar' ? 'ar-u-nu-latn-ca-gregory' : 'en-GB');
function dayKey(d) { return new Intl.DateTimeFormat('en-CA', { timeZone: prefs.tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(d); }
export function fmtTime(iso) {
  return new Intl.DateTimeFormat('en-GB', { timeZone: prefs.tz, hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(iso));
}
export function fmtWhen(iso) {
  if (!iso) return '';
  const d = new Date(iso), now = new Date();
  const time = fmtTime(iso);
  if (dayKey(d) === dayKey(now)) return t('when.today', { time });
  if (dayKey(d) === dayKey(new Date(now.getTime() - 864e5))) return t('when.yesterday', { time });
  const date = new Intl.DateTimeFormat(locale(), { timeZone: prefs.tz, day: 'numeric', month: 'long' }).format(d);
  return t('when.day', { date, time });
}
export function exactTime(iso) {
  return new Intl.DateTimeFormat(locale(), { timeZone: prefs.tz, dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso)) + ' (' + prefs.tz + ')';
}
/** An instant `minutes` from now, as the time of day (a sign-in's deadline). */
export function inMinutes(minutes) { return fmtTime(new Date(Date.now() + minutes * 60000).toISOString()); }
/** When a confirm token expires (epoch seconds, as the server gives it, or an ISO time), as the time of day. */
export function expiresAt(expires) {
  const ms = typeof expires === 'number' ? expires * 1000 : Date.parse(expires);
  return Number.isNaN(ms) ? inMinutes(10) : fmtTime(new Date(ms).toISOString());
}
