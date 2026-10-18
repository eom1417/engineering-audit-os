// S-33 infrastructure (SYS-13), on infra.json: where the project runs and what it depends on outside its code, in seven
// areas (hosting, CI, environments, databases, queues, outside services, observability), each item with its kind,
// facts and evidence, an empty area with its reason; and the target per area (keep or introduce, the decision, the
// tool), with the areas the target is silent on.
import { t, num, esc, code, screen, data } from 'eaos';
import { tabs, seg, prov, loading, notMeasured, empty, where } from '../understand-kit/kit.js';

const NEEDS = ['infra', 'coverage'];
const detail = d => Object.entries(d || {}).filter(([, v]) => v != null && v !== false).map(([k, v]) => (v === true ? t('un.infrad.' + k) : t('un.infrad.n', { what: t('un.infrad.' + k), n: num(v) }))).join(t('list.sep'));

function infraPage(ctx) {
  if (ctx.state === 'empty') return empty(t('un.idx.empty'), t('un.idx.empty.guide'));
  const d = data.section('infra');
  if (!d) return notMeasured('infra', 'infra');
  const mode = ctx.query.mode === 'target' ? 'target' : 'today';
  const targetLane = id => d.target && d.target.lanes.find(l => l.id === id);
  const area = lane => {
    if (mode === 'target') {
      const tl = targetLane(lane.id);
      const items = tl ? tl.items : [];
      return `<section class="panel un-area"><div class="un-area__head"><h2 class="h2">${t('un.infra.' + lane.id)}</h2>${items.length ? '' : `<span class="tag tag--nm">${t('un.infra.silent')}</span>`}</div>
        ${items.length ? `<ul class="rows">${items.map(x => `<li class="row un-area__item"><span class="tag ${x.op === 'introduce' ? 'tag--you' : 'tag--ok'}">${t('un.infra.t.' + x.op)}</span>
          <span class="row__main"><span class="row__title">${esc(t('un.infra.target.' + x.area))}</span><span class="row__meta" style="display:block">${esc(x.decision)}${x.tool ? `${t('list.sep')}${esc(t('un.infra.tool', { tool: x.tool }))}` : ''}</span>
          <span class="small muted" style="display:block">${esc(x.evidence)}</span></span></li>`).join('')}</ul>` : `<p class="small ink-2">${t('un.infra.silent.why')}</p>`}</section>`;
    }
    const nodes = lane.nodes.concat(lane.folded || []);
    return `<section class="panel un-area"><div class="un-area__head"><h2 class="h2">${t('un.infra.' + lane.id)}</h2><span class="small muted">${t('un.infra.' + lane.id + '.what')}</span></div>
      ${nodes.length ? `<ul class="rows">${nodes.map(n => `<li class="row un-area__item"><span class="tag tag--state">${esc(t('un.infrak.' + n.kind))}</span>
        <span class="row__main"><span class="row__title">${code(n.name)}</span><span class="row__meta" style="display:block">${esc(detail(n.detail))}${(n.items || []).length ? `${t('list.sep')}${n.items.slice(0, 6).map(code).join(' ')}${n.items.length > 6 ? ' ' + esc(t('un.comp.andmore', { n: num(n.items.length - 6) })) : ''}` : ''}</span>
        ${(n.sites || []).length ? `<span class="small muted" style="display:block">${code(where(n.sites[0].path, n.sites[0].line))}${n.sites.length > 1 ? ' ' + esc(t('un.comp.andmore', { n: num(n.sites.length - 1) })) : ''}</span>` : ''}</span></li>`).join('')}</ul>`
        : `<div class="nm" style="margin-top:8px"><div class="nm__title"><span class="tag tag--nm">${t('un.infra.empty')}</span></div><p class="small ink-2">${t('un.infra.why.' + lane.reason)}</p></div>`}</section>`;
  };
  const silent = d.target ? d.target.lanes.filter(l => !l.items.length).map(l => t('un.infra.' + l.id)) : [];
  return `<div class="page page--wide">
    ${tabs('infra')}
    <h1 class="lede">${t('un.infra.lede')}</h1>
    <p class="guide">${t('un.infra.guide')}</p>
    ${mode === 'target' ? prov(d.provenance) : ''}
    <div class="ptools">${seg('mode', [['today', t('un.story.today')], ['target', t('un.story.target')]], mode, t('un.comp.mode'), { dflt: 'today', cls: 'un-seg2' })}</div>
    ${mode === 'target' && d.target && d.target.reference ? `<p class="small ink-2">${esc(t('un.infra.reference', { ref: d.target.reference }))}</p>` : ''}
    ${mode === 'target' && !d.target ? `<p class="small muted">${t('un.infra.notarget')}</p>` : `<div class="un-areas section" style="margin-top:20px">${d.lanes.map(area).join('')}</div>`}
    ${mode === 'target' && silent.length ? `<p class="small muted" style="margin-top:12px">${esc(t('un.infra.silentlist', { list: silent.join(t('list.sep')) }))}</p>` : ''}
  </div>`;
}
screen({ id: 'S-33', path: '/understand/infra', place: 'understand', needs: NEEDS, title: () => t('un.v.infra'), render: infraPage, loading: () => loading(t('un.infra.loading')) });
