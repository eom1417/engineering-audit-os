// The library's Mermaid flowcharts drawn as light SVG (any other diagram shows its source), for the documents the core
// draws from their Markdown (core/markdown.js render, ctx.diagram).
import { t, esc, icon } from 'eaos';

const enc = encodeURIComponent;

/* ---------- Mermaid flowcharts as light SVG ---------- */
/** The nodes, the groups (subgraphs) and the links of a flowchart; null when it is another kind of diagram. */
export function parseFlowchart(src) {
  const lines = src.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('%%'));
  const head = /^(flowchart|graph)\s*(LR|RL|TD|TB|BT)?/.exec(lines[0] || '');
  if (!head) return null;
  const nodes = new Map(), groups = [], links = [];
  let group = null;
  const node = (id, label) => { if (!nodes.has(id)) nodes.set(id, { id, label: id, group: group ? group.id : null }); const n = nodes.get(id); if (label) n.label = label; return n; };
  const ref = s => { const m = /^([\w.:-]+)\s*(?:\[\(?"?([^\]"]*)"?\)?\]|\("?([^)"]*)"?\)|\{"?([^}"]*)"?\})?$/.exec(s.trim()); return m ? node(m[1], m[2] || m[3] || m[4]) : null; };
  for (const l of lines.slice(1)) {
    const sg = /^subgraph\s+([\w.-]+)(?:\s*\["?([^\]"]*)"?\])?/.exec(l);
    if (sg) { group = { id: sg[1], label: sg[2] || sg[1] }; groups.push(group); continue; }
    if (l === 'end') { group = null; continue; }
    if (/^(linkStyle|style|classDef|class|click|direction)\b/.test(l)) continue;
    const edge = /^(.+?)\s*(-->|---|-\.->|==>)\s*(?:\|([^|]*)\|\s*)?(.+)$/.exec(l);
    if (edge) { const a = ref(edge[1]), b = ref(edge[4]); if (a && b) links.push({ from: a.id, to: b.id, label: edge[3] || '', dotted: edge[2] === '-.->' }); continue; }
    ref(l);
  }
  return { down: /^(TD|TB|BT)$/.test(head[2] || ''), nodes: [...nodes.values()], groups, links };
}
/** The flowchart drawn: groups as columns (or nodes by the longest path when it has none), links as curves. */
export function flowchartSVG(g, big) {
  const W = 190, H = 40, GX = 80, GY = 16;
  const cols = [];
  if (g.groups.length) {
    g.groups.forEach(gr => cols.push({ label: gr.label, ids: g.nodes.filter(n => n.group === gr.id).map(n => n.id) }));
    const loose = g.nodes.filter(n => !n.group).map(n => n.id);
    if (loose.length) cols.push({ label: '', ids: loose });
  } else {
    const depth = new Map();
    const of = (id, seen) => { if (depth.has(id)) return depth.get(id); if (seen.has(id)) return 0; seen.add(id); const d = Math.max(-1, ...g.links.filter(l => l.to === id && l.from !== id).map(l => of(l.from, seen))) + 1; depth.set(id, d); return d; };
    g.nodes.forEach(n => { const d = of(n.id, new Set()); (cols[d] = cols[d] || { label: '', ids: [] }).ids.push(n.id); });
  }
  const filled = cols.filter(c => c && c.ids.length);
  const rows = Math.max(1, ...filled.map(c => c.ids.length));
  const top = filled.some(c => c.label) ? 30 : 10;
  const at = {};
  filled.forEach((c, ci) => c.ids.forEach((id, ri) => { at[id] = { x: 10 + ci * (W + GX), y: top + ri * (H + GY) }; }));
  const w = 20 + filled.length * (W + GX) - GX, h = top + rows * (H + GY) + 10;
  const fit = s => (s.length > 24 ? s.slice(0, 23) + '…' : s);
  const labels = g.links.length <= 20; // past that the numbers crowd the drawing: each link keeps its own in its title
  const links = g.links.filter(l => at[l.from] && at[l.to]).map(l => {
    const a = at[l.from], b = at[l.to];
    const same = a.x === b.x;
    const x1 = same ? a.x + W : a.x + (b.x > a.x ? W : 0), y1 = a.y + H / 2, x2 = same ? b.x + W : b.x + (b.x > a.x ? 0 : W), y2 = b.y + H / 2;
    const mx = same ? x1 + 40 : (x1 + x2) / 2;
    return `<path class="un-dg__edge" d="M${x1} ${y1}C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}" marker-end="url(#dg-arrow${big ? 'b' : ''})" ${l.dotted ? 'stroke-dasharray="4 4"' : ''}>${l.label ? `<title>${esc(l.label)}</title>` : ''}</path>${l.label && labels ? `<text class="un-dg__label" x="${mx}" y="${(y1 + y2) / 2 - 4}">${esc(l.label)}</text>` : ''}`;
  }).join('');
  const heads = filled.map((c, ci) => (c.label ? `<text class="un-dg__group" x="${10 + ci * (W + GX)}" y="18">${esc(c.label)}</text>` : '')).join('');
  const nodes = g.nodes.filter(n => at[n.id]).map(n => `<g class="un-dg__node"><rect x="${at[n.id].x}" y="${at[n.id].y}" width="${W}" height="${H}" rx="8"/><text x="${at[n.id].x + W / 2}" y="${at[n.id].y + 25}">${esc(fit(n.label))}</text><title>${esc(n.label)}</title></g>`).join('');
  return `<svg class="un-dg ${big ? 'un-map' : ''}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(t('un.doc.diagram.label'))}" ${big ? 'tabindex="0"' : ''}><defs>
    <marker id="dg-arrow${big ? 'b' : ''}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" class="un-dg__arrow"/></marker></defs>${heads}${links}${nodes}</svg>`;
}
export function mermaidBlock(src, ctx, n) {
  const g = parseFlowchart(src);
  const drawn = g ? `<figure class="un-diagram panel">${flowchartSVG(g, false)}` : `<figure class="un-diagram panel"><p class="small muted">${t('un.doc.cannotdraw')}</p>`;
  return `${drawn}<figcaption class="un-diagram__bar">
    ${g ? `<button class="btn btn--plain btn--sm" data-act="sheet" data-sheet="diagram:${n}:${esc(enc(ctx.path))}">${icon('external', 'icon--sm')}${t('un.doc.full')}</button>` : ''}
    <details class="un-diagram__src" ${g ? '' : 'open'}><summary class="link">${icon('code', 'icon--sm')}${t('un.doc.source')}</summary><div class="code" style="padding:12px 16px;white-space:pre" tabindex="0">${esc(src)}</div>
      <button class="btn btn--secondary btn--sm" data-act="copy" data-text="${esc(src)}">${icon('copy', 'icon--sm')}${t('un.doc.copysrc')}</button></details></figcaption></figure>`;
}
/** The n-th Mermaid source of a text. */
export const mermaidOf = (md, n) => [...md.matchAll(/```mermaid\n([\s\S]*?)```/g)].map(m => m[1])[n] || null;
