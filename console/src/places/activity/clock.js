// The check's clock (CHK-08): the time since the check began, counting each second while it runs and frozen while it is
// paused (EAOS.ac.runTicker: its pauses left out), what it took once it ended, and beside it the stage under way with
// its own time. Activity's "now" panel and the run page
// draw it the same way.
import { t, num, esc, ac } from 'eaos';
import { stageTitle, stageTime } from './stages.js';

/** The clock of check run `r` on its flow's times (the run's own while its flow has not begun). */
export function clockHTML(r, flow, list) {
  const own = flow && flow.started_at ? flow : null;
  const ended = ac.ended(r) || (own && own.state !== 'running' && own.state !== 'stalled');
  const from = own ? own.started_at : r.started;
  const took = ended ? (own && own.seconds != null ? own.seconds - ac.pausedIn(r, Date.parse(from), Date.parse(from) + own.seconds * 1000)
    : r.started && r.ended ? (Date.parse(r.ended) - Date.parse(r.started)) / 1000 - ac.pausedIn(r, Date.parse(r.started), Date.parse(r.ended)) : null) : null;
  const total = ended ? ac.ticker(null, took, 'ac-tick--big') : ac.runTicker(r, from, 'ac-tick--big');
  if (!total) return '';
  const now = ended ? [] : list.filter(s => ['running', 'you', 'paused'].includes(s.state));
  const word = ended ? 'ac.clock.took' : r.state === 'paused' ? 'ac.clock.paused' : 'ac.clock.elapsed';
  return `<div class="ac-clock" role="timer" aria-label="${esc(t(word))}">
    <div class="ac-clock__total"><span class="small ink-2">${t(word)}</span>${total}</div>
    ${now.map(s => `<button class="ac-clock__stage" data-act="sheet" data-sheet="stage:${esc(s.id)}"><span class="small ink-2">${esc(stageTitle(s.id))}</span>${stageTime(s, 'ac-tick--mid')}</button>`).join('')}
  </div>${own && own.mode ? `<p class="small ink-2 ac-clock__mode"><b>${t('ac.clock.mode')}:</b> ${esc(t('ac.clock.' + own.mode, { n: num(own.assistants || 1) }))}${now.length > 1 ? ` · ${esc(t('ac.clock.together', { n: num(now.length) }))}` : ''}</p>` : ''}`;
}
