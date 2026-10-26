// The plan of a project built from its plan (plans.json `build`, eaos/report/studio/blueprint_plan.py): its milestones in order,
// each with its build cards, their acceptance and state, and the one next step: answer the blueprint's questions, or
// build the next milestone (the `build_start` action: an assistant builds its cards through their gates).
import { t, tn, L, num, esc, icon, code, rich } from 'eaos';
import { buildStep } from '../kit/kit.js';

const TAG = { done: 'tag--ok', active: 'tag--live', blocked: 'tag--caution', todo: 'tag--state' };
const tag = st => `<span class="tag ${TAG[st] || TAG.todo}">${st === 'done' ? icon('check') : ''}${t(st === 'blocked' ? 'bp.st.skipped' : 'un.pst.' + (TAG[st] ? st : 'todo'))}</span>`;
const list = (items, cls) => items.length ? `<ul class="${cls}">${items.map(x => `<li>${x}</li>`).join('')}</ul>` : '';

function card(c) {
  const facts = [
    c.acceptance ? `<div class="block-title">${t('bp.accepted')}</div>${list(c.acceptance.split('\n').map(a => rich(a)), 'small')}` : '',
    c.paths.length ? `<p class="small muted">${t('bp.files')} ${c.paths.map(code).join(' ')}</p>` : '',
    c.tests.length ? `<p class="small muted">${t('bp.tests')} ${c.tests.map(code).join(' ')}</p>` : '',
    c.depends_on.length ? `<p class="small muted">${t('bp.after')} ${c.depends_on.map(code).join(' ')}</p>` : '',
  ].join('');
  return `<details class="fold"><summary>${code(c.id)}<span class="row__main"><span class="row__title">${rich(L(c.title))}</span></span>${tag(c.state)}${icon('chev', 'chev icon--sm')}</summary>
    <div class="fold__body">${facts}</div></details>`;
}

function milestone(s, next) {
  const done = s.tasks.filter(c => c.state === 'done').length;
  return `<details class="panel fold section" ${s.id === next ? 'open' : ''}><summary><span class="un-num num" aria-hidden="true">${esc(s.id)}</span>
      <span class="row__main"><span class="row__title">${rich(L(s.title))}</span>
      <span class="row__meta" style="display:block">${esc(t('bp.cards', { done: num(done), n: tn('bp.card', s.tasks.length) }))}${s.branch ? ` ${code(s.branch)}` : ''}</span></span>
      ${tag(s.state)}${s.id === next ? `<span class="tag tag--you">${t('un.plan.nexttag')}</span>` : ''}${icon('chev', 'chev')}</summary>
    <div class="fold__body rows">${(s.unproven || []).length ? `<div class="banner banner--caution"><strong>${t('bp.unproven')}</strong><ul>${s.unproven.map(u => `<li>${rich(u)}</li>`).join('')}</ul></div>` : ''}${s.tasks.map(card).join('')}</div></details>`;
}

export function buildPage(plan) {
  const cards = plan.steps.reduce((n, s) => n + s.tasks.length, 0);
  const done = plan.steps.reduce((n, s) => n + s.tasks.filter(c => c.state === 'done').length, 0);
  const share = cards ? done / cards : 0;
  const next = plan.open || plan.next;
  return `<div class="page page--wide">
    <h1 class="lede">${esc(t('bp.lede', { m: tn('bp.milestone', plan.steps.length), n: tn('bp.card', cards), done: num(done) }))}</h1>
    ${plan.goal ? `<p class="guide">${rich(L(plan.goal))}</p>` : ''}
    ${plan.requirements ? `<p class="small ink-2">${icon('check', 'icon--sm')} ${esc(t('bp.covered', { n: num(plan.requirements) }))}</p>` : ''}
    <div class="actions">${buildStep()}<p class="actions__note">${t('bp.note')}</p></div>
    <div class="un-progress section" role="img" aria-label="${esc(Math.round(share * 100) + '%')}"><span style="transform:scaleX(${share.toFixed(3)})"></span></div>
    <section class="section" aria-labelledby="bp-h"><div class="section-head"><h2 id="bp-h">${t('bp.milestones')}</h2><span class="small muted">${t('bp.order')}</span></div>
      ${plan.steps.map(s => milestone(s, next)).join('')}</section>
  </div>`;
}
