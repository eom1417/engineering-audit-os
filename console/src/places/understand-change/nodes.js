// S-23 how EAOS decided (SYS-16), on nodes.json: EAOS's own AI nodes as a small graph (what waits for what) with
// its list twin; one node is a sheet (?sheet=node:<id>) with its routes, its last run, its decisions with their
// evidence and its run log. "Run the AI nodes…" is the run_nodes action, previewed free first, with the nodes to ask.
import { t, tn, L, num, esc, icon, code, href, rich, fmtWhen, screen, sheet, act, local, chk, data } from 'eaos';
import { tabs, facts, start, loading, notMeasured, empty, keyItem, readout, pct } from '../understand-kit/kit.js';
import { actionSheet, again } from '../understand-kit/preview.js';

const NEEDS = ['nodes', 'coverage'];
const nodesOf = () => (data.section('nodes') || {}).nodes || [];
const nodeOf = id => nodesOf().find(n => n.id === id);
const name = id => { const n = nodeOf(id); if (n) return L(n.title); const s = ((data.section('nodes') || {}).sinks || []).find(x => x.id === id); return s ? L(s.title) : id; };
const ai = n => n.method === 'model';

function nodeMeta(n) {
  if (n.state === 'not_run') return esc(t('un.node.notrun'));
  const by = ai(n) ? t('un.node.by', { who: n.assistant || '', model: n.model || '' }) : t('un.node.byrules', { why: n.why ? L(n.why) : t('un.node.why.none') });
  return [esc(by), n.seconds != null ? esc(t('un.node.secs', { s: num(Math.round(n.seconds)) })) : '', n.cost_usd ? esc(t('un.node.cost', { c: n.cost_usd.toFixed(2) })) : t('un.node.free.m'),
    n.cached ? t('un.node.cached') : ''].filter(Boolean).join(t('list.sep'));
}
/** The nodes in columns: a node one column after the latest node it waits for. */
function columns(all) {
  const depth = {};
  const of = (n, seen) => {
    if (depth[n.id] != null) return depth[n.id];
    if (seen.has(n.id)) return 0;
    seen.add(n.id);
    return (depth[n.id] = Math.max(-1, ...(n.requires || []).map(r => (nodeOf(r) ? of(nodeOf(r), seen) : -1))) + 1);
  };
  const cols = [];
  all.forEach(n => (cols[of(n, new Set())] = cols[of(n, new Set())] || []).push(n.id));
  return cols.filter(Boolean);
}
function nodesSVG(all) {
  const cols = columns(all);
  const W = 860, nw = 220, nh = 52, gapX = cols.length > 1 ? (W - 40 - nw) / (cols.length - 1) : 0;
  const rows = Math.max(...cols.map(c => c.length));
  const H = 40 + rows * 76;
  const pos = {};
  cols.forEach((c, ci) => c.forEach((id, i) => { pos[id] = { x: 20 + ci * gapX, y: 20 + (i + (rows - c.length) / 2) * 76 }; }));
  const links = all.flatMap(n => (n.requires || []).filter(w => pos[w]).map(w => {
    const a = pos[w], b = pos[n.id];
    const x1 = a.x + nw, y1 = a.y + nh / 2, x2 = b.x, y2 = b.y + nh / 2;
    return `<path class="un-g__link" d="M${x1} ${y1}C${(x1 + x2) / 2} ${y1} ${(x1 + x2) / 2} ${y2} ${x2} ${y2}"/>`;
  })).join('');
  const nodes = all.map(n => {
    const p = pos[n.id], label = L(n.title);
    const tip = `${label}: ${nodeMeta(n).replace(/<[^>]+>/g, '')}`;
    return `<a href="${href('/understand/ai-decisions', { sheet: 'node:' + n.id })}" class="un-g__node ${ai(n) ? 'un-g__node--ai' : 'un-g__node--rules'}" data-tip="${esc(tip)}">
      <rect x="${p.x}" y="${p.y}" width="${nw}" height="${nh}" rx="10"/>
      <text x="${p.x + 14}" y="${p.y + 22}" class="un-g__t">${esc(label)}</text>
      <text x="${p.x + 14}" y="${p.y + 40}" class="un-g__s">${esc(n.state === 'not_run' ? t('un.node.notrun') : ai(n) ? n.assistant || '' : t('un.node.rulesonly'))}</text><title>${esc(label)}</title></a>`;
  }).join('');
  return `<div class="panel un-graph only-desk" data-readout-root><svg viewBox="0 0 ${W} ${H}" role="group" aria-label="${esc(t('un.nodes.svg'))}">${links}${nodes}</svg>
    <div class="un-key">${keyItem('ai')}${keyItem('rules')}</div><p class="small muted un-readout" data-readout aria-live="polite">${t('un.map.hint')}</p></div>`;
}

function nodesPage(ctx) {
  if (ctx.state === 'empty') return empty(t('un.idx.empty'), t('un.idx.empty.guide'));
  if (!data.section('nodes')) return notMeasured('ai-decisions', 'nodes');
  const all = nodesOf();
  const byAi = all.filter(ai).length;
  const cost = all.reduce((s, n) => s + (n.cost_usd || 0), 0);
  const rows = all.map(n => `<button class="row" data-act="sheet" data-sheet="node:${esc(n.id)}">${icon('ai', ai(n) ? 'ai-ic' : 'muted')}
    <span class="row__main"><span class="row__title">${esc(L(n.title))}</span>
      <span class="row__meta" style="display:block">${nodeMeta(n)}</span>
      ${(n.requires || []).length ? `<span class="row__meta" style="display:block">${esc(t('un.node.waits', { list: n.requires.map(name).join(t('list.sep')) }))}</span>` : ''}</span>
    ${icon('chev', 'icon--sm icon--dir muted')}</button>`).join('');
  return `<div class="page page--wide">
    ${tabs('ai-decisions')}
    <h1 class="lede">${esc(t('un.nodes.lede', { n: tn('un.pl.node', all.length), ai: num(byAi), rules: num(all.length - byAi) }))}</h1>
    <p class="guide">${t('un.nodes.guide')}</p>
    <div class="actions">${start('runnodes', esc(t('un.nodes.act')))}<p class="actions__note">${esc(t('un.nodes.cost', { c: cost.toFixed(2) }))}</p></div>
    <div class="section">${nodesSVG(all)}</div>
    <div class="section"><div class="panel rows">${rows}</div></div>
  </div>`;
}
screen({ id: 'S-23', path: '/understand/ai-decisions', place: 'understand', needs: NEEDS, title: () => t('un.v.ai-decisions'), render: nodesPage, after: readout,
  loading: () => loading(t('un.nodes.loading')) });

sheet('node', {
  kind: 'drawer',
  needs: NEEDS,
  render(id) {
    const n = nodeOf(id);
    if (!n) return { title: esc(t('pd.notfound', { id })), body: '' };
    const decisions = n.decisions || [];
    return {
      title: esc(L(n.title)),
      sub: esc(tn('un.pl.pass', (n.passes || []).length)),
      body: `${n.summary ? `<p>${rich(L(n.summary))}</p>` : ''}
        ${(n.requires || []).length ? `<p class="small ink-2">${esc(t('un.node.waits', { list: n.requires.map(name).join(t('list.sep')) }))}</p>` : ''}
        <div><div class="block-title">${t('un.node.routes')}</div><div class="panel rows">${(n.routes || []).map(r => `<div class="row" style="min-height:52px"><span class="row__main"><span class="row__title small">${esc(r.decision)} ${icon('chev', 'icon--sm icon--dir muted')} ${esc(name(r.to))}</span>${r.when ? `<span class="row__meta" style="display:block">${esc(L(r.when))}</span>` : ''}</span><b class="num">${num(r.subjects)}</b></div>`).join('')}</div></div>
        <div><div class="block-title">${t('un.node.last')}</div>${facts([
          [t('un.node.decidedby'), n.state === 'not_run' ? esc(t('un.node.notrun')) : ai(n) ? `${esc(n.assistant || '')} ${n.model ? code(n.model) : ''}` : esc(t('un.node.byrules', { why: n.why ? L(n.why) : t('un.node.why.none') }))],
          n.at ? [t('un.prov.when'), esc(fmtWhen(n.at))] : null,
          n.seconds != null ? [t('un.node.took'), esc(t('un.node.secs', { s: num(Math.round(n.seconds)) }))] : null,
          [t('un.node.costk'), n.cost_usd ? esc(t('un.node.cost', { c: n.cost_usd.toFixed(2) })) : t('un.node.free')],
          [t('un.node.cachedk'), t(n.cached ? 'un.yes' : 'un.no')],
          [t('un.node.droppedk'), esc(tn('un.pl.decision0', (n.dropped || []).length))],
        ])}</div>
        ${decisions.length ? `<div><div class="block-title">${t('un.node.decisions')} (${num(decisions.length)})</div><div style="display:grid;gap:8px">${decisions.slice(0, 20).map(d => `<div class="ai-block"><span class="ai-block__label">${icon('ai', 'icon--sm')}${code(d.subject)}</span>
          <p class="small" style="margin-top:4px">${esc(d.decision)}${d.confidence != null ? `${t('list.sep')}${esc(t('un.node.conf', { c: pct(d.confidence) }))}` : ''}</p>${d.why ? `<p class="small ink-2">${rich(L(d.why))}</p>` : ''}</div>`).join('')}</div>
          ${decisions.length > 20 ? `<p class="small muted">${esc(t('un.comp.andmore', { n: num(decisions.length - 20) }))}</p>` : ''}<p class="small muted">${t('ai.hypothesis')}</p></div>` : ''}
        ${(n.log || []).length ? `<div><div class="block-title">${t('un.node.log')}</div><ul class="rows">${n.log.slice().reverse().slice(0, 10).map(l => `<li class="row small" style="padding-inline:0"><span class="row__main">${esc(fmtWhen(l.at))}${t('list.sep')}${esc(l.assistant || t('un.node.rulesonly'))}${l.seconds != null ? `${t('list.sep')}${esc(t('un.node.secs', { s: num(Math.round(l.seconds)) }))}` : ''}${l.cost_usd ? `${t('list.sep')}${esc(t('un.node.cost', { c: l.cost_usd.toFixed(2) }))}` : ''}${l.cached ? `${t('list.sep')}${t('un.node.cached')}` : ''}</span></li>`).join('')}</ul></div>` : ''}`,
    };
  },
});

/* Run the AI nodes: all but the ideal planner by default (replan_ideal plans it), or the ones chosen; "ask again". */
const RUNNABLE = ['card_triage', 'pipeline_gap_planner', 'plan_orderer', 'fix_reviewer', 'ideal_planner'];
const picked = own => (own.nodes = own.nodes || RUNNABLE.filter(id => id !== 'ideal_planner' && nodeOf(id)));
actionSheet('runnodes', {
  action: 'run_nodes', needs: NEEDS,
  title: own => tn('un.nodes.title', picked(own).length),
  inputs: own => ({ nodes: picked(own), fresh: own.fresh ? true : undefined }),
  ready: own => picked(own).length > 0,
  command: own => `eaos nodes ${picked(own).join(' ')}${own.fresh ? ' --fresh' : ''}`,
  extra: own => `<fieldset style="border:0;padding:0;margin:0"><legend class="block-title">${t('un.nodes.pick')}</legend><div class="rows">
      ${RUNNABLE.filter(nodeOf).map(id => `<label class="row" style="min-height:48px;padding-inline:4px;gap:12px">${chk(`data-change="un-node" value="${esc(id)}" data-fk="nd-${esc(id)}"`, picked(own).includes(id), name(id))}
        <span class="row__main">${esc(name(id))}${id === 'ideal_planner' ? `<span class="small muted" style="display:block">${t('un.nodes.idealnote')}</span>` : ''}</span></label>`).join('')}</div></fieldset>
    <div class="toggle-row panel panel__pad"><span><span style="display:block">${t('un.nodes.fresh')}</span><span class="small muted">${t('un.nodes.fresh.note')}</span></span>
      <span class="switch"><input type="checkbox" data-change="un-fresh" data-fk="un-fresh" ${own.fresh ? 'checked' : ''} aria-label="${esc(t('un.nodes.fresh'))}"><span class="switch__track"></span><span class="switch__thumb"></span></span></div>`,
});
act('un-node', el => { const own = local(); const set = new Set(picked(own)); if (el.checked) set.add(el.value); else set.delete(el.value); again({ nodes: RUNNABLE.filter(id => set.has(id)) }); });
act('un-fresh', el => again({ fresh: el.checked }));
