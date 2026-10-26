// The pictures of the app's screens the check took (screens.json): each reviewed page at its widest width with its
// findings numbered on it (eaos/report/studio/screens.py gallery); a check that reviewed none shows each screen's own
// picture with its open issues. Twelve at a time: every picture is read with the launch token.
import { t, tn, L, num, esc, code, sev, data } from 'eaos';
import { nm, page, count } from '../kit/kit.js';
import { figure } from '../kit/pictures.js';

export const SCREENS_NEEDS = ['screens'];
const PER_PAGE = 12;
const widest = shots => shots.slice().sort((a, b) => (b.width || 0) - (a.width || 0))[0];

/** A reviewed page: its widest picture and the findings placed on that picture. */
function fromPage(p, titles) {
  const shot = widest(p.pictures || []);
  const findings = (shot.findings || []).map(f => ({ title: L(f.title), severity: f.severity, region: f.region }));
  return { title: titles[(p.same_as || [])[0]] || '', route: p.path, shot, findings };
}
/** A screen the check pictured but did not review: its widest picture before any fix, and its open issues. */
function fromScreen(s) {
  const shot = widest((s.shots || []).filter(x => x.phase !== 'after'));
  const findings = (s.issues || []).filter(x => x.state !== 'fixed').map(x => ({ title: L(x.summary), severity: x.severity, region: null }));
  return { title: s.title || '', route: s.route, shot, findings };
}
function pictured(S) {
  const titles = Object.fromEntries((S.screens || []).map(s => [s.id, s.title]));
  const pages = (S.pages || []).filter(p => (p.pictures || []).length).map(p => fromPage(p, titles));
  return pages.length ? pages : (S.screens || []).filter(s => (s.shots || []).some(x => x.phase !== 'after')).map(fromScreen);
}

function card(item) {
  const pins = item.findings.map((f, i) => ({ n: i + 1, region: f.region }));
  const list = item.findings.length ? `<ol class="rows rp-findings">${item.findings.map((f, i) => `<li class="row small"><span class="un-num num">${num(i + 1)}</span><span class="row__main">${esc(f.title)}</span>${sev(f.severity)}</li>`).join('')}</ol>`
    : `<p class="small muted">${t('rp.scr.clean')}</p>`;
  return `<article class="panel panel__pad rp-shot"><h2 class="h2">${item.title ? esc(item.title) + ' ' : ''}${code(item.route || '')}</h2>
    ${figure(item.shot, pins, t('un.pic.cap', { w: num(item.shot.width || 0) }))}
    <p class="small ink-2">${esc(tn('un.pl.finding', item.findings.length))}</p>${list}</article>`;
}

export function screensPart() {
  const S = data.section('screens');
  if (!S) return nm(t('rp.scr.none'), t('rp.scr.none.why'));
  const items = pictured(S);
  if (!items.length) return nm(t('rp.scr.none'), t('rp.scr.none.why'));
  const pg = page(items, card, PER_PAGE);
  return `<div class="listhead">${count(pg.shown, items.length)}</div><div class="rp-shots">${pg.html}</div>${pg.more}`;
}
