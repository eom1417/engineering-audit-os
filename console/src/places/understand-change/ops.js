// S-21 the operations in the order the plan runs them (PLN-09), on operations.json; one operation is a sheet
// (?sheet=op:<order>) with its reason, what it comes after, its step, its gap, its sources, its branch and its open
// problems, which "Fix this operation's problems…" picks for the one Fix preview.
import { t, tn, L, num, esc, icon, code, href, rich, screen, sheet, data, model } from 'eaos';
import { tabs, seg, prov, count, opTag, opOf, OPS, facts, prow, fixBtn, enc, loading, notMeasured, emptyView, openOf } from '../understand-kit/kit.js';

const NEEDS = ['operations', 'gaps', 'cards', 'coverage'];
const opsOf = () => (data.section('operations') || {}).operations || [];
const byId = () => new Map(opsOf().map(o => [o.id, o]));

function stateTag(s) {
  const known = ['todo', 'active', 'done', 'blocked', 'regressed'].includes(s) ? s : 'todo';
  return `<span class="tag ${known === 'done' ? 'tag--ok' : known === 'active' ? 'tag--live' : known === 'blocked' ? 'tag--caution' : 'tag--state'}">${known === 'done' ? icon('check') : ''}${t('un.opstate.' + known)}</span>`;
}
const orderOf = (ids, all) => ids.map(id => all.get(id)).filter(Boolean).map(o => '#' + num(o.order));
function opRow(o, all) {
  const after = orderOf(o.after || [], all);
  return `<button class="row un-oprow" data-act="sheet" data-sheet="op:${o.order}">
    <span class="un-num num" aria-hidden="true">${num(o.order)}</span>
    <span class="row__main"><span class="un-gaprow__top">${opTag(o.op)}${code(o.subject)}<span class="small muted">${t('un.kind.' + o.subject_kind)}</span></span>
      <span class="row__meta" style="display:block">${after.length ? esc(t('un.ops.after', { list: after.join(t('list.sep')) })) : t('un.ops.free')}${t('list.sep')}${o.step ? esc(t('un.ops.step', { step: o.step })) : t('un.ops.nostep')}</span></span>
    <span class="row__end">${stateTag(o.state)}</span></button>`;
}

function opsPage(ctx) {
  if (ctx.state === 'empty') return emptyView('operations');
  if (!data.section('operations')) return notMeasured('operations', 'operations');
  const view = ctx.query.view === 'kind' ? 'kind' : 'order';
  const ops = opsOf().slice().sort((a, b) => a.order - b.order), all = byId();
  const canStart = ops.filter(o => o.state !== 'done' && (o.after || []).every(a => { const p = all.get(a); return p && p.state === 'done'; })).length;
  const list = !ops.length ? `<div class="panel empty"><p class="empty__title">${t('un.ops.none')}</p></div>`
    : view === 'kind' ? `<div class="panel">${OPS.filter(k => ops.some(o => opOf(o.op) === k)).map(k => `<div class="group-head"><span>${opTag(k)}</span><span class="num">${num(ops.filter(o => opOf(o.op) === k).length)}</span></div>
      <div class="rows">${ops.filter(o => opOf(o.op) === k).map(o => opRow(o, all)).join('')}</div>`).join('')}</div>`
      : `<div class="panel rows">${ops.map(o => opRow(o, all)).join('')}</div>`;
  return `<div class="page page--wide">
    ${tabs('operations')}
    <h1 class="lede">${esc(t('un.ops.lede', { n: tn('un.pl.op', ops.length) }))}</h1>
    <p class="guide">${esc(t('un.ops.guide', { k: num(canStart) }))}</p>
    ${prov((data.section('operations') || {}).provenance)}
    <div class="ptools">${seg('view', [['order', t('un.ops.inorder')], ['kind', t('un.ops.bykind')]], view, t('un.v.operations'), { dflt: 'order', cls: 'un-seg2' })}</div>
    <div class="listhead">${count(ops.length, ops.length)}</div>
    ${list}
  </div>`;
}
screen({ id: 'S-21', path: '/understand/operations', place: 'understand', needs: NEEDS, title: () => t('un.v.operations'), render: opsPage, loading: () => loading(t('un.ops.loading')) });

const go = h => `href="${h}" data-act="go" data-href="${h}"`;
sheet('op', {
  kind: 'drawer',
  needs: NEEDS,
  render(arg) {
    const o = opsOf().find(x => String(x.order) === String(arg));
    if (!o) return { title: esc(t('pd.notfound', { id: '#' + arg })), body: '' };
    const all = byId();
    const g = ((data.section('gaps') || {}).gaps || []).find(x => x.id === o.gap);
    const cards = (o.cards || []).map(id => model.problem(id)).filter(p => p && p.state === 'open');
    const link = (path, query, text) => `<a class="link" ${go(href(path, query))}>${text}</a>`;
    const before = opsOf().filter(x => (x.after || []).includes(o.id));
    return {
      title: `#${num(o.order)} ${esc(t('un.op.' + opOf(o.op)))} ${code(o.subject)}`,
      sub: esc(t('un.kind.' + o.subject_kind)),
      body: `<div>${stateTag(o.state)}</div>
        ${o.reason ? `<p>${rich(L(o.reason))}</p>` : ''}
        ${facts([
          [t('un.gap.becomes'), o.target ? code(o.target) : t('un.gap.removed')],
          [t('un.ops.comesafter'), (o.after || []).length ? o.after.map(id => all.get(id)).filter(Boolean).map(x => link('/understand/operations', { sheet: 'op:' + x.order }, '#' + num(x.order))).join(' ') : t('un.ops.free')],
          [t('un.ops.comesbefore'), before.length ? before.map(x => link('/understand/operations', { sheet: 'op:' + x.order }, '#' + num(x.order))).join(' ') : t('un.none')],
          [t('un.gap.steps'), o.step ? link('/problems/plan/' + enc(o.step), null, code(o.step)) : t('un.gap.nostep')],
          [t('un.ops.gap'), g ? link('/understand/gaps/' + enc(g.id), null, code(g.component)) : '—'],
          (o.sources || []).length ? [t('un.ops.sources'), o.sources.map(code).join(' ')] : null,
          o.files != null ? [t('un.gap.files'), esc(tn('pl.file', o.files))] : null,
          [t('un.ops.branch'), o.branch ? code(o.branch) : `<span class="muted">${t('un.ops.nobranch')}</span>`],
        ])}
        ${cards.length ? `<div><div class="block-title">${t('un.gap.cards')} (${num(cards.length)})</div><div class="panel rows">${cards.slice(0, 6).map(p => prow(p)).join('')}</div>${cards.length > 6 ? `<p class="small muted">${esc(t('un.comp.andmore', { n: num(cards.length - 6) }))}</p>` : ''}</div>` : ''}`,
      foot: openOf(o.cards || []).length && o.state !== 'done' ? fixBtn(o.cards, `#${o.order} ${o.subject}`, t('un.ops.fix'), 'btn--primary btn--block', 'operation')
        : `<p class="sheet__fine">${t(o.state === 'done' ? 'un.ops.done' : 'un.ops.nocards')}</p>`,
    };
  },
});
