// S-15 one run's result (RUN-07, RUN-09, FIX-07): the error or the facts of what it made, a fix batch's progress
// problem by problem, and the request waiting for the person's assistant elsewhere.
import { t, tn, L, num, esc, rich, icon, code, href, fmtWhen, has, model, derive, ac, rowWords, facts, titledSection } from 'eaos';

const enc = encodeURIComponent;
const pathName = p => (has('ac.path.' + p) ? t('ac.path.' + p) : p);
function errorHTML(e) {
  return `<section class="panel ac-result ac-result--fail" aria-label="${esc(t('ac.run.error'))}">
      ${facts([[t('ac.run.what'), `${rich(L(e.text))}${e.reason ? ` <span class="small muted">${rich(e.reason)}</span>` : ''}`], e.what_now ? `<dt>${t('ac.run.todo')}</dt><dd>${rich(L(e.what_now))}</dd>` : '', [t('ac.run.recoverable'), t(e.recoverable ? 'ac.run.recoverable.yes' : 'ac.run.recoverable.no')]])}
      ${e.detail ? `<details class="ac-ev-fold"><summary>${t('ac.run.tech')}${icon('chev-down', 'icon--sm muted')}</summary><div class="code pad-2-3 pre">${esc(e.detail)}</div></details>` : ''}</section>`;
}
/** The checks' verdict: changes kept and left out. */
function testsHTML(tests) {
  /* older records carry only the engine's English sentence: its two numbers are read back so the page speaks the person's language */
  const said = tests.kept == null && /^(\d+) change\(s\) passed every check; (\d+) left out/.exec(tests.summary || '');
  if (said) Object.assign(tests, { kept: +said[1], left: +said[2] });
  return ac.mark(tests.passed ? 'ok' : tests.passed === false ? 'failed' : 'skipped', esc(tests.kept != null ? t('ac.run.tests.n', { kept: tn('ac.run.change', tests.kept), left: num(tests.left || 0) }) : t(tests.passed ? 'wt.fix.tests.ok' : 'wt.fix.tests.no')));
}
const indicatorsHTML = list => list.map(x => esc(t('ac.run.indicator', { id: x.id, before: x.before == null ? '—' : num(x.before), after: x.after == null ? '—' : num(x.after) }))).join('<br>');
const decisionHTML = r => (r.outcome ? esc(t(r.outcome === 'accepted' ? 'wt.done.accepted' : 'wt.done.rejected', { when: fmtWhen(r.decided), target: ac.mergedInto(r) }))
  : `<span class="ac-c-accent">${t('ac.out.waits')}</span>`);
/** A check's own rows: the problems it found and the paths it checked. */
const checkRows = r => [[t('ac.run.check.found'), `<a class="link" href="${href('/problems')}">${esc(tn('pl.problem', model.totals().problems))}</a>`],
  [t('ac.run.check.paths'), esc(((r.inputs && r.inputs.paths) || ['complete']).map(pathName).join(t('list.sep')))]];
/** What the run changed: its branch, the diff's size, the checks' verdict, the problems left out. */
function changeRows(r, res) {
  const rows = [], d = res.diff_stat;
  if (res.branch) rows.push([t('ac.run.branch'), `<a class="link" href="${href('/project/branches/' + enc(res.branch))}">${code(res.branch)}</a>`]);
  if (d) rows.push([t('ac.run.diffstat'), `${esc(tn('pl.file_changed', d.files))} <bdi dir="ltr" class="num">+${num(d.insertions)} −${num(d.deletions)}</bdi>`]);
  if (res.tests) rows.push([t('ac.run.tests'), testsHTML(res.tests)]);
  if ((r.left_out || []).length) rows.push([t('ac.run.leftout'), r.left_out.slice(0, 8).map(x => code(x.id)).join(' ')]);
  return rows;
}
/** What the change closes and moves, and the owner's decision on its branch. */
function closeRows(r, res) {
  const rows = [];
  if ((res.cards_closed || []).length) rows.push([t('ac.run.closes'), res.cards_closed.slice(0, 12).map(c => `<a class="link" href="${href('/problems/' + enc(c))}">${code(c)}</a>`).join(' ')]);
  if ((res.indicators || []).length) rows.push([t('ac.run.indicators'), indicatorsHTML(res.indicators)]);
  if (res.branch) rows.push([t('ac.run.decision'), decisionHTML(r)]);
  return rows;
}
/** The result's facts as [label, value] rows. */
function resultRows(r, res) {
  const rows = changeRows(r, res).concat(closeRows(r, res));
  return r.action === 'audit' && ac.flowOfRun(r) ? rows.concat(checkRows(r)) : rows;
}
/** The result's own words: an answer, or any action's but a check's. */
const wordsOf = (r, res) => (typeof res.answer === 'string' || r.action !== 'audit' ? ac.answerHTML(res.answer) : '');
export function resultHTML(r, rs, view) {
  if (view.error && ['failed', 'stopped'].includes(rs)) return errorHTML(view.error);
  const res = view.result || r.result;
  if (!res) return '';
  const rows = resultRows(r, res);
  const words = wordsOf(r, res);
  if (!rows.length && !words) return '';
  return `<section class="panel ac-result ${r.outcome === 'undone' ? '' : 'ac-result--ok'}" aria-label="${esc(t('ac.run.result'))}">
    ${rows.length ? facts(rows) : ''}${words}</section>`;
}

/** FIX-07: the batches' progress and every problem of the batch, kept or taken back, from the edit events. */
export function fixProgress(r, rs, view) {
  const cards = r.cards || [];
  if (!cards.length) return '';
  const byCard = view.cards, tried = derive.fixCount(view, r);
  const row = id => {
    const p = model.problem(id);
    const k = byCard[id];
    const st = k === true ? 'ok' : k === false ? 'unchanged' : rs === 'running' ? 'waiting' : ac.ended(r) ? 'notreached' : 'waiting';
    const word = k === true ? t('ac.fix.p.kept') : k === false ? t('ac.ev.back') : ac.stateWord(st);
    return `<li class="row">${ac.glyph(st)}${rowWords(`<a class="link" href="${href('/problems/' + enc(id))}">${code(id)}</a> ${p ? rich(L(p.title)) : ''}`, esc(word), { title: 'small' })}</li>`;
  };
  const shown = cards.slice(0, 12);
  return titledSection('fp-h', t('ac.fix.progress'), `
    ${ac.progressBar(tried / cards.length, t('ac.fix.progress'))}
    <ul class="panel rows mt-3">${shown.map(row).join('')}${cards.length > shown.length ? `<li class="row small muted" style="min-height:44px">+ ${esc(tn('pl.problem', cards.length - shown.length))}</li>` : ''}</ul>`, `<span class="small muted num">${esc(t('ac.now.fix.sub', { done: num(tried), total: num(cards.length) }))}</span>`);
}

/** RUN-09: the request that waits for the person's assistant elsewhere, to copy. */
export function handoffHTML(r) {
  const req = r.handoff;
  if (!req) return '';
  return titledSection('ho-h', t('ac.ho.title'), `
    <div class="panel panel__pad ac-stack"><p class="small ink-2">${t('ac.ho.why')}</p>
      ${['ar', 'en'].filter(l => req[l]).map(l => `<div class="ac-req"><span class="block-title">${t('lang.' + l)}</span><div class="code ac-req__text pre" dir="${l === 'ar' ? 'rtl' : 'ltr'}">${esc(req[l])}</div>
        <button class="btn btn--secondary btn--sm" data-act="copy" data-text="${esc(req[l])}">${icon('copy')}${t('copy')}</button></div>`).join('')}</div>`);
}
