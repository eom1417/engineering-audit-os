// S-34 the pipelines (SYS-14) and one stage (SYS-15, ?sheet=pstage:<stage>), on pipeline.json: whether the project
// is a pipeline, every pipeline with its stages in EAOS's reading order (layer, then order), the stages' kinds and
// marks; the ideal by the rules (operations on stages) and the gap (one row per broken rule); what was looked for.
import { t, tn, L, num, has, esc, icon, code, href, rich, screen, sheet, data } from 'eaos';
import { tabs, seg, prov, nm, fold, facts, opTag, opOf, OPS, pct, glyph, enc, loading, notMeasured, empty, where } from '../understand-kit/kit.js';

const NEEDS = ['pipeline', 'coverage'];
const MARK = { slow: 'clock', risky: 'warn', external: 'external' };
const P = () => data.section('pipeline');
const stagesOf = (d, pid) => d.stages.filter(s => s.pipeline === pid).sort((a, b) => a.layer - b.layer || a.order - b.order);
const idealOf = (d, id) => d.views.ideal.stages.find(s => s.id === id);

function stageChip(d, s, i, view) {
  const ideal = view === 'ideal' ? idealOf(d, s.id) : null;
  const marks = (s.marks || []).filter(m => MARK[m]);
  const label = `${t('un.pipes.stage', { n: num(i + 1) })} ${s.label}${s.kind !== 'stage' ? ', ' + t('un.skind.' + s.kind) : ''}${marks.length ? ', ' + marks.map(m => t('un.smark.' + m)).join(t('list.sep')) : ''}${ideal ? ', ' + t('un.op.' + opOf(ideal.op)) : ''}`;
  return `<li><button class="un-stage un-stage--${esc(s.kind)}" data-act="sheet" data-sheet="pstage:${esc(s.id)}" aria-label="${esc(label)}">
    <span class="un-stage__n num" aria-hidden="true">${i + 1}</span>${s.kind === 'ai' ? icon('ai', 'icon--sm ai-ic') : ''}<span class="un-stage__name">${esc(s.label)}</span>
    ${ideal && opOf(ideal.op) !== 'retain' ? glyph(ideal.op, 14) : ''}${marks.map(m => icon(MARK[m], 'icon--sm muted')).join('')}</button></li>`;
}
const lookedFor = (d, open) => fold(t('un.pipes.looked'), esc(t('un.pipes.looked.sum', { n: num(d.looked_for.length) })), `<ul class="un-looked">${d.looked_for.map(l => `<li class="${l.found ? '' : 'muted'}"><span>${esc(has('un.lf.' + l.kind) ? t('un.lf.' + l.kind) : l.label)}</span><b class="num">${num(l.found)}</b></li>`).join('')}</ul>`, { open });

function pipesPage(ctx) {
  if (ctx.state === 'empty') return empty(t('un.idx.empty'), t('un.idx.empty.guide'));
  const d = P();
  if (!d) return notMeasured('pipelines', 'pipeline');
  const view = ctx.query.view === 'ideal' || ctx.query.view === 'gap' ? ctx.query.view : 'current';
  if (!d.detected || !d.pipelines.length) {
    return `<div class="page page--wide">${tabs('pipelines')}<h1 class="lede">${t('un.pipes.nm.lede')}</h1>${nm(t('un.pipes.nm'), t('un.pipes.nm.why'))}<div class="panel section">${lookedFor(d, true)}</div></div>`;
  }
  const total = d.stages.length;
  const biggest = d.pipelines.slice().sort((a, b) => b.stages.length - a.stages.length)[0];
  let body;
  if (view === 'gap') {
    const gaps = d.views.gap;
    body = gaps.length ? `<div class="panel rows">${gaps.map(g => {
      const p = d.pipelines.find(x => x.id === g.pipeline);
      const st = d.stages.find(s => s.id === g.subject);
      return `<div class="row" style="align-items:flex-start">${opTag(g.operation)}<span class="row__main"><span class="row__title">${code(st ? st.label : p ? p.title : g.subject)} <span class="small muted">${p ? esc(p.title) : ''}</span></span>
      <span class="row__meta" style="display:block">${rich(L(g.detail))}${t('list.sep')}${esc(t('un.pipes.rule', { rule: g.rule }))}</span>${g.card || g.step ? `<span class="small" style="display:block;margin-top:4px">${g.card ? `<a class="link" href="${href('/problems/' + enc(g.card))}">${code(g.card)}</a> ` : ''}${g.step ? `<a class="link" href="${href('/problems/plan/' + enc(g.step))}">${code(g.step)}</a>` : ''}</span>` : ''}</span></div>`;
    }).join('')}</div>` : `<p class="small muted">${t('un.pipes.nogap')}</p>`;
  } else {
    body = d.pipelines.map(p => `<section class="un-pipe" aria-labelledby="pp-${esc(enc(p.id))}">
      <div class="un-pipe__head"><h2 class="h2" id="pp-${esc(enc(p.id))}">${esc(p.title)}</h2>
        <span class="tag tag--state">${t('un.pipes.role.' + p.role)}</span><span class="small muted">${esc(tn('pl.stage', p.stages.length))}${t('list.sep')}${esc(t('un.pipes.conf', { c: pct(p.confidence) }))}${t('list.sep')}${code(where(p.entry.path, p.entry.line))}</span></div>
      <ol class="un-stages">${stagesOf(d, p.id).map((s, i) => stageChip(d, s, i, view)).join('')}</ol></section>`).join('');
  }
  const idealOps = OPS.filter(o => d.views.ideal.stages.some(s => opOf(s.op) === o));
  return `<div class="page page--wide">
    ${tabs('pipelines')}
    <h1 class="lede">${esc(t('un.pipes.lede', { n: tn('un.pl.pipe', d.pipelines.length), stages: num(total), big: biggest.title, k: num(biggest.stages.length) }))}</h1>
    <p class="guide">${t('un.pipes.guide')}</p>
    ${view !== 'current' ? prov(d.provenance) : ''}
    <div class="ptools">${seg('view', [['current', t('un.pipes.current')], ['ideal', t('un.pipes.ideal')], ['gap', t('un.pipes.gap'), d.views.gap.length]], view, t('un.path.view'), { dflt: 'current' })}</div>
    ${view !== 'gap' ? `<div class="un-key" style="margin-top:16px"><span class="un-key__item">${icon('ai', 'icon--sm ai-ic')}${t('un.skind.ai')}</span>${Object.keys(MARK).filter(m => d.stages.some(s => (s.marks || []).includes(m))).map(m => `<span class="un-key__item">${icon(MARK[m], 'icon--sm muted')}${t('un.smark.' + m)}</span>`).join('')}${view === 'ideal' ? idealOps.map(o => `<span class="un-key__item">${opTag(o)}</span>`).join('') : ''}</div>` : ''}
    <div class="un-body">${body}</div>
    <div class="panel section">${lookedFor(d, false)}${fold(t('un.pipes.rules'), esc(tn('un.pl.rule', d.rules.length)), `<ul class="rows">${d.rules.map(r => `<li class="row" style="padding-inline:0;align-items:flex-start">${code(r.id)}<span class="row__main"><span class="row__title small">${esc(r.title)}</span><span class="row__meta" style="display:block">${esc(r.why)}</span></span><b class="num">${num(r.broken)}</b></li>`).join('')}</ul>`)}</div>
  </div>`;
}
screen({ id: 'S-34', path: '/understand/pipelines', place: 'understand', needs: NEEDS, title: () => t('un.v.pipelines'), render: pipesPage, loading: () => loading(t('un.pipes.loading')) });

const go = h => `href="${h}" data-act="go" data-href="${h}"`;
sheet('pstage', {
  kind: 'drawer',
  needs: ['pipeline', 'nodes'],
  render(id) {
    const d = P();
    const s = d && d.stages.find(x => x.id === id);
    if (!s) return { title: esc(t('pd.notfound', { id })), body: '' };
    const p = d.pipelines.find(x => x.id === s.pipeline);
    const list = stagesOf(d, s.pipeline), i = list.indexOf(s);
    const ins = d.edges.filter(e => e.to === s.id), outs = d.edges.filter(e => e.from === s.id);
    const ideal = idealOf(d, s.id);
    const gaps = d.views.gap.filter(g => g.subject === s.id);
    const node = s.kind === 'ai' && ((data.section('nodes') || {}).nodes || []).find(n => n.id === s.label);
    const stageLink = sid => { const x = d.stages.find(y => y.id === sid); return x ? `<button class="link" data-act="sheet" data-sheet="pstage:${esc(sid)}">${code(x.label)}</button>` : code(sid); };
    const ports = list2 => list2.map(x => code(x.name)).join(' ');
    return {
      title: code(s.label),
      sub: esc(`${p ? p.title : ''}${t('list.sep')}${t('un.pipes.stageof', { n: num(i + 1), m: num(list.length) })}`),
      body: `<div class="un-itemtags"><span class="tag tag--state">${t('un.skind.' + s.kind)}</span>${(s.marks || []).filter(m => MARK[m]).map(m => `<span class="tag tag--state">${t('un.smark.' + m)}</span>`).join('')}${ideal ? opTag(ideal.op) : ''}${s.optional ? `<span class="tag tag--state">${t('un.stage.optional')}</span>` : ''}</div>
        <p>${t('un.skind.' + s.kind + '.does')}</p>
        ${s.entry && s.entry.text ? `<div class="code" style="padding:12px 16px">${esc(s.entry.text)}</div>` : ''}
        ${facts([
          [t('un.stage.takes'), ins.length ? ins.map(e => stageLink(e.from)).join(' ') : t('un.stage.entry')],
          [t('un.stage.gives'), outs.length ? outs.map(e => stageLink(e.to)).join(' ') : t('un.stage.end')],
          (s.inputs || []).length ? [t('un.stage.inputs'), ports(s.inputs)] : null,
          (s.outputs || []).length ? [t('un.stage.outputs'), ports(s.outputs)] : null,
          (s.tools || []).length ? [t('un.stage.tools'), s.tools.map(code).join(' ')] : null,
          [t('un.stage.known'), t('un.stage.cov.' + s.coverage)],
          [t('un.stage.at'), code(where(s.entry.path, s.entry.line))],
          (s.cards || []).length ? [t('un.gap.cards'), s.cards.map(c => `<a class="link" ${go(href('/problems/' + enc(c)))}>${code(c)}</a>`).join(' ')] : null,
          (s.steps || []).length ? [t('un.gap.steps'), s.steps.map(c => `<a class="link" ${go(href('/problems/plan/' + enc(c)))}>${code(c)}</a>`).join(' ')] : null,
        ])}
        ${ideal && ideal.why ? `<div><div class="block-title">${t('un.stage.ideal')}</div><p class="small">${rich(L(ideal.why))}${ideal.rule ? ` <span class="muted">(${esc(t('un.pipes.rule', { rule: ideal.rule }))})</span>` : ''}</p></div>` : ''}
        ${gaps.length ? `<div><div class="block-title">${t('un.pipes.gap')}</div><ul class="rows">${gaps.map(g => `<li class="row small" style="padding-inline:0">${opTag(g.operation, true)}<span class="row__main">${rich(L(g.detail))}</span></li>`).join('')}</ul></div>` : ''}
        ${node ? `<div class="ai-block"><span class="ai-block__label">${icon('ai', 'icon--sm')}${esc(L(node.title))}</span><p class="small" style="margin-top:4px">${esc(node.method === 'model' ? t('un.node.by', { who: node.assistant || '', model: node.model || '' }) : t('un.node.rulesonly'))}</p>
          <a class="link small" ${go(href('/understand/ai-decisions', { sheet: 'node:' + node.id }))}>${t('un.stage.lastdecision')}</a></div>` : ''}
        <div class="un-insp__more"><a class="link" ${go(href('/understand/paths', { q: s.entry.path }))}>${icon('code', 'icon--sm')}${t('un.stage.paths')}</a></div>`,
    };
  },
});
