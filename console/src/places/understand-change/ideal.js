// S-22 the ideal target per view (PLN-11, PLN-13) and "Plan it again…" (PLN-12): for each of the eight views
// (ideal.json), the rules' target against what the person's assistant planned on top, their differences, the elements
// dropped for lack of evidence, the critique, the departures, the questions and the planning runs. Re-planning is the
// replan_ideal action, previewed free first.
import { t, tn, L, num, esc, icon, code, href, rich, fmtWhen, screen, data, model } from 'eaos';
import { tabs, prov, fold, opTag, pct, start, enc, loading, notMeasured, empty } from '../understand-kit/kit.js';
import { actionSheet } from '../understand-kit/preview.js';

const NEEDS = ['ideal', 'decisions', 'coverage'];
/** The address names a view as the design does; the report as its section does. */
const VIEWS = [['structure', 'system'], ['change', 'change'], ['journeys', 'journeys'], ['paths', 'paths'], ['data', 'data_paths'], ['infra', 'infra'],
  ['pipeline', 'pipeline'], ['order', 'plan_order']];
const DIFFS = ['added', 'changed', 'dropped_from_rules', 'same'];

function elementRow(e) {
  return `<li class="row" style="padding-inline:0;align-items:flex-start">${opTag(e.operation, true)}<span class="row__main"><span class="row__title small">${rich(L(e.title))}${e.subject ? ` ${code(e.subject)}` : ''}</span>
    ${e.detail ? `<span class="row__meta" style="display:block">${rich(L(e.detail))}</span>` : ''}
    ${(e.cites || []).length ? `<span class="small muted" style="display:block">${esc(t('un.ideal.cites', { list: e.cites.slice(0, 4).join(t('list.sep')) }))}${e.cites.length > 4 ? ' ' + esc(t('un.comp.andmore', { n: num(e.cites.length - 4) })) : ''}</span>` : ''}</span></li>`;
}

const provOf = (ideal, k) => (ideal.views[k] || {}).provenance || {};

/** The eight views as chips, each marked when its ideal is not the assistant's plan. */
function picker(ideal, addr) {
  return `<nav class="un-chips" aria-label="${esc(t('un.ideal.views'))}">${VIEWS.map(([a, k]) => {
    const state = provOf(ideal, k).state;
    return `<a href="${href('/understand/ideal', a === 'structure' ? {} : { view: a })}" ${a === addr ? 'aria-current="true"' : ''}>${t('un.iv.' + a)}${state && state !== 'planned' ? `<span class="un-chips__dot un-chips__dot--${state === 'not_planned' ? 'rules' : state}" aria-hidden="true"></span>` : ''}</a>`;
  }).join('')}</nav>`;
}

/** How far the view's plan stands on evidence, or why the rules' target is shown alone. */
function stateLine(ideal, p, planned) {
  const ev = ideal.evidence || {};
  return planned ? `<p class="small ink-2">${esc(t('un.ideal.state', { conf: pct(planned.confidence), ev: pct(ev.share && ev.share.value), raw: pct(ev.raw_share && ev.raw_share.value) }))}${p.state === 'stale' ? ` <span class="tag tag--caution">${icon('warn')}${t('un.ideal.stale')}</span>` : ''}</p>`
    : `<p class="small ink-2">${icon('info', 'icon--sm')} ${t('un.ideal.rulesonly')} ${esc(L(p.message || ideal.message || ''))}</p>`;
}

/** The rules' target beside the assistant's plan (or why there is none). */
function pair(ideal, v, p, rules) {
  return `<div class="un-pair">
      <div class="un-rules"><span class="un-rules__label">${icon('check', 'icon--sm')}${t('un.ideal.rules')}</span><p>${rich(L((v.rules && v.rules.summary) || ''))}</p>
        <p class="small muted">${esc(tn('un.pl.element', rules.length))}</p></div>
      ${v.planned ? `<div class="ai-block"><span class="ai-block__label">${icon('ai', 'icon--sm')}${t('ai.label')}</span><p style="margin-top:4px">${rich(L(v.planned.summary))}</p><p class="small muted" style="margin-top:4px">${t('ai.hypothesis')}</p></div>`
        : `<div class="nm"><div class="nm__title"><span class="tag tag--nm">${t('un.ideal.notplanned')}</span></div><p class="small ink-2">${esc(L(p.message || ideal.message || t('un.ideal.notplanned.why')))}</p></div>`}
    </div>`;
}

function differences(v) {
  if (!v.planned) return '';
  const diffs = DIFFS.map(k => [k, (v.differences || []).filter(d => d.kind === k).length]);
  return `<div class="un-diffs" role="list">${diffs.map(([k, n]) => `<div class="un-diff" role="listitem"><b class="num">${num(n)}</b><span>${t('un.ideal.d.' + k)}</span></div>`).join('')}</div>`;
}

/** Where the plan departs from the rules, and why. */
function departures(p) {
  const dep = (p.departures || []).map(d => `<li class="row un-dep"><span class="row__main"><span class="un-gaprow__top">${d.element ? code(d.element) : ''}</span>
      <span class="row__meta" style="display:block">${t('un.ideal.dep', { rule: opTag(d.rule_says, true), plan: opTag(d.plan_chose, true) })}</span>
      <span class="small ink-2" style="display:block;margin-top:4px">${rich(L(d.because))}</span></span></li>`).join('');
  return dep ? `<div class="section-head" style="margin-top:24px"><h3 class="h2">${t('un.ideal.deps')}</h3></div><ul class="panel rows">${dep}</ul>` : '';
}

/** The view's open questions, each a link to where it waits for the person. */
function questions(qs) {
  return qs.length ? `<div class="section-head" style="margin-top:24px"><h3 class="h2">${t('un.ideal.qs')}</h3></div><div class="panel rows">${qs.map(x => {
    const d = model.decisions().find(y => y.id === x.id || y.id.endsWith(x.id));
    return `<a class="row row--you" href="${href(d ? '/waiting/' + enc(d.id) : '/waiting')}"><span class="dot dot--you" aria-hidden="true"></span><span class="row__main"><span class="row__title">${rich(L(x.question))}</span><span class="row__meta" style="display:block">${t('un.ideal.qs.where')}</span></span>${icon('chev', 'icon--dir muted')}</a>`;
  }).join('')}</div>` : '';
}

function critiqueFold(critique) {
  return critique ? fold(t('un.ideal.critique'), t('un.ideal.critique.sum'), ['missed', 'risks', 'order'].map(k => `<div class="block-title">${t('un.ideal.' + k)}</div>${(critique[k] || []).length ? `<ul class="rows">${critique[k].map(x => `<li class="row small" style="padding-inline:0">${rich(L(x.text || x.title || x.why || JSON.stringify(x)))}</li>`).join('')}</ul>` : `<p class="small muted">${t('un.none')}</p>`}`).join('')) : '';
}

function runsFold(runs) {
  return fold(t('un.ideal.runs'), esc(tn('un.pl.run', runs.length)), runs.length ? `<ul class="rows">${runs.slice().reverse().map(r => `<li class="row" style="padding-inline:0">${r.state === 'failed' ? icon('fail', 'danger-ic') : icon('check', 'ok-ic')}<span class="row__main"><span class="row__title small">${esc(fmtWhen(r.at))}${r.assistant ? `${t('list.sep')}${esc(r.assistant)}` : ''} ${r.model ? code(r.model) : ''}</span>
      <span class="row__meta" style="display:block">${esc(t('un.ideal.run', { s: num(Math.round(r.seconds || 0)), p: tn('un.pl.pass', (r.passes || []).length) }))}${t('list.sep')}${t('un.prov.st.' + r.state)}${r.message ? `${t('list.sep')}${esc(L(r.message))}` : ''}</span></span></li>`).join('')}</ul>` : `<p class="small muted">${t('un.ideal.noruns')}</p>`);
}

/** The folded lists: the rules' elements, the planned ones, those dropped for lack of evidence, the critique, the runs. */
function folds(ideal, key, planned, rules) {
  const dropped = ((ideal.evidence || {}).dropped || []).filter(d => d.view === key);
  return `<div class="panel" style="margin-top:24px">
      ${fold(t('un.ideal.elements'), esc(tn('un.pl.element', rules.length)), rules.length ? `<ul class="rows">${rules.slice(0, 100).map(elementRow).join('')}</ul>${rules.length > 100 ? `<p class="small muted">${esc(t('un.comp.andmore', { n: num(rules.length - 100) }))}</p>` : ''}` : `<p class="small muted">${t('un.none')}</p>`)}
      ${planned ? fold(t('un.ideal.planned'), esc(tn('un.pl.element', planned.elements.length)), `<ul class="rows">${planned.elements.slice(0, 100).map(elementRow).join('')}</ul>`) : ''}
      ${dropped.length ? fold(t('un.ideal.droppedf'), esc(tn('un.pl.element', dropped.length)), `<ul class="rows">${dropped.map(d => `<li class="row" style="padding-inline:0"><span class="row__main"><span class="row__title small">${rich(L(d.title || d.id))}</span><span class="row__meta" style="display:block">${rich(L(d.why))}</span></span></li>`).join('')}</ul>`) : ''}
      ${critiqueFold(ideal.critique)}
      ${runsFold(ideal.runs || [])}
    </div>`;
}

function idealPage(ctx) {
  if (ctx.state === 'empty') return empty(t('un.idx.empty'), t('un.idx.empty.guide'));
  const ideal = data.section('ideal');
  if (!ideal) return notMeasured('ideal', 'ideal');
  const [addr, key] = VIEWS.find(x => x[0] === ctx.query.view) || VIEWS[0];
  const v = ideal.views[key] || {};
  const p = v.provenance || ideal.provenance || {};
  const rules = (v.rules && v.rules.elements) || [];
  const asked = ideal.questions || [];
  const departed = VIEWS.reduce((n, [, k]) => n + (provOf(ideal, k).departures || []).length, 0);
  return `<div class="page page--wide">
    ${tabs('ideal')}
    <h1 class="lede">${esc(t('un.ideal.lede', { n: num(VIEWS.length), dep: tn('un.pl.departure', departed), q: tn('un.pl.question', asked.length) }))}</h1>
    <p class="guide">${t('un.ideal.guide')}</p>
    <div class="actions">${start('replan', esc(t('un.ideal.replan')))}<p class="actions__note">${t('un.ideal.replan.note')}</p></div>
    ${prov(ideal.provenance)}
    <div style="margin-top:24px">${picker(ideal, addr)}</div>
    <section class="section un-view" aria-labelledby="iv-h">
      <h2 class="h2" id="iv-h">${t('un.iv.' + addr)}</h2>
      ${stateLine(ideal, p, v.planned)}
      ${pair(ideal, v, p, rules)}
      ${differences(v)}
      ${departures(p)}
      ${questions(asked.filter(x => x.view === key))}
      ${folds(ideal, key, v.planned, rules)}
    </section>
  </div>`;
}
screen({ id: 'S-22', path: '/understand/ideal', place: 'understand', needs: NEEDS, title: () => t('un.v.ideal'), render: idealPage, loading: () => loading(t('un.ideal.loading')) });

actionSheet('replan', { action: 'replan_ideal', title: () => t('un.replan.title'), inputs: () => ({}), command: () => 'eaos replan-ideal' });
