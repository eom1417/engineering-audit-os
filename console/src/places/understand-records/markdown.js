// A report document drawn from its Markdown (LIB-03, LIB-04, LIB-05) without any library: headings with anchors for the
// contents, paragraphs, lists and task lists, tables with their number columns aligned, quotes and GitHub's alerts,
// code with copy, and Mermaid flowcharts drawn as light SVG (any other diagram shows its source). Nothing from a report
// is ever injected as HTML: every text is escaped, then only the marks below are added. Problem ids open the problem,
// links to other documents open them here, outside links open outside, a file the library lacks is a dead link.
import { t, esc, icon, href } from 'eaos';

const enc = encodeURIComponent;
const ALERT = /^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*/i;

/** A link inside a document, resolved against the document's folder: './a.md', '../b/c.md', 'd.md#part'. */
export function resolveLink(from, target) {
  const [file, hash = ''] = target.split('#');
  if (!file) return { path: from, hash };
  const parts = file.startsWith('/') ? [] : from.split('/').slice(0, -1);
  for (const part of file.replace(/^\/+/, '').split('/')) { if (part === '..') parts.pop(); else if (part && part !== '.') parts.push(part); }
  return { path: parts.join('/'), hash };
}

function inline(text, ctx) {
  let s = esc(text);
  s = s.replace(/`([^`]+)`/g, (m, c) => `\u0000code${c}\u0001`);
  s = s.replace(/!\[([^\]]*)\]\(([^)\s]+)[^)]*\)/g, (m, alt, src) => {
    const p = resolveLink(ctx.path, src).path;
    return `<a class="link" href="${href('/understand/library', { tab: 'images', q: p.split('/').pop() })}">${icon('map', 'icon--sm')}${alt || p.split('/').pop()}</a>`;
  });
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)[^)]*\)/g, (m, label, target) => {
    const raw = target.replace(/&amp;/g, '&');
    if (/^https?:/i.test(raw)) return `<a class="link" href="${esc(raw)}" target="_blank" rel="noopener noreferrer">${label}${icon('external', 'icon--sm')}</a>`;
    if (raw.startsWith('#')) return `<a class="link" href="#" data-act="un-toc" data-target="h-${esc(slug(raw.slice(1)))}">${label}</a>`;
    const { path } = resolveLink(ctx.path, raw);
    return ctx.docs.has(path) ? `<a class="link" href="${href('/understand/library/' + enc(path))}">${label}</a>` : `<span class="un-deadlink" title="${esc(t('un.doc.dead'))}">${label}</span>`;
  });
  s = s.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, '$1<em>$2</em>');
  s = s.replace(/\b(TASK-\d{1,6})\b/g, (m, id) => (ctx.cards.has(id) ? `<a class="link" href="${href('/problems/' + id)}"><bdi class="mono">${id}</bdi></a>` : m));
  s = s.replace(/\\([_*`#|\[\]])/g, '$1');
  return s.replace(/\u0000code([^\u0001]*)\u0001/g, '<bdi class="mono">$1</bdi>');
}
export const slug = text => String(text).toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '');
const dir = text => (/[؀-ۿ]/.test(text) ? 'rtl' : 'ltr');

/** {html, headings: [{id, depth, text}]} of a Markdown text. ctx: {path, docs: Set, cards: Set}. */
export function render(md, ctx) {
  const lines = md.replace(/\r\n?/g, '\n').split('\n');
  const out = [], heads = [];
  let i = 0, diagram = 0;
  const para = [];
  const flush = () => { if (para.length) { const s = para.join(' '); out.push(`<p dir="${dir(s)}">${inline(s, ctx)}</p>`); para.length = 0; } };
  while (i < lines.length) {
    const line = lines[i];
    const fence = /^\s*```\s*(\S*)/.exec(line);
    if (fence) {
      flush();
      const body = [];
      for (i += 1; i < lines.length && !/^\s*```/.test(lines[i]); i += 1) body.push(lines[i]);
      i += 1;
      const src = body.join('\n');
      if (fence[1] === 'mermaid') out.push(mermaidBlock(src, ctx, diagram++));
      else out.push(`<div class="un-codeblock"><div class="un-codeblock__bar"><span class="small muted">${esc(fence[1] || '')}</span><button class="btn btn--plain btn--sm" data-act="copy" data-text="${esc(src)}">${icon('copy', 'icon--sm')}${t('copy')}</button></div>
        <div class="code" tabindex="0">${body.map((l, j) => `<div class="code__line"><span class="code__ln">${j + 1}</span><span>${esc(l)}</span></div>`).join('')}</div></div>`);
      continue;
    }
    const h = /^(#{1,6})\s+(.*?)\s*#*\s*$/.exec(line);
    if (h) {
      flush();
      const depth = h[1].length, text = h[2].replace(/[*`]/g, '');
      const id = 'h-' + slug(text);
      if (!(depth === 1 && out.length === 0)) { heads.push({ id, depth, text }); out.push(`<h${Math.min(depth + 1, 4)} id="${id}" dir="${dir(text)}">${inline(h[2], ctx)}</h${Math.min(depth + 1, 4)}>`); }
      i += 1; continue;
    }
    if (/^\s*\|.*\|\s*$/.test(line) && /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1] || '')) {
      flush();
      const cells = l => l.trim().replace(/^\||\|$/g, '').split(/(?<!\\)\|/).map(c => c.trim());
      const head = cells(line), rows = [];
      for (i += 2; i < lines.length && /^\s*\|/.test(lines[i]); i += 1) rows.push(cells(lines[i]));
      const numeric = head.map((_, j) => rows.length && rows.every(r => /^[-+]?[\d,.]+%?$|^—?$/.test(r[j] || '')));
      out.push(`<div class="un-table-wrap panel" tabindex="0"><table class="un-table"><thead><tr>${head.map((c, j) => `<th scope="col" class="${numeric[j] ? 'num' : ''}">${inline(c, ctx)}</th>`).join('')}</tr></thead>
        <tbody>${rows.map(r => `<tr>${head.map((_, j) => `<td class="${numeric[j] ? 'num' : ''}">${inline(r[j] || '', ctx)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
      continue;
    }
    if (/^\s*>/.test(line)) {
      flush();
      const body = [];
      for (; i < lines.length && /^\s*>/.test(lines[i]); i += 1) body.push(lines[i].replace(/^\s*>\s?/, ''));
      const alert = ALERT.exec(body[0] || '');
      if (alert) {
        body[0] = body[0].replace(ALERT, '');
        const kind = alert[1].toLowerCase();
        out.push(`<div class="un-alert un-alert--${kind === 'warning' || kind === 'caution' ? 'warning' : 'note'}" role="note">${icon(kind === 'warning' || kind === 'caution' ? 'warn' : 'info')}<div><b>${t('un.doc.' + kind)}</b><p>${inline(body.join(' '), ctx)}</p></div></div>`);
      } else out.push(`<blockquote dir="${dir(body.join(' '))}">${inline(body.join(' '), ctx)}</blockquote>`);
      continue;
    }
    const item = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/.exec(line);
    if (item) {
      flush();
      const ordered = /\d/.test(item[2]);
      const items = [];
      for (; i < lines.length; i += 1) {
        const m = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/.exec(lines[i]);
        if (m) items.push({ depth: m[1].length >= 2 ? 1 : 0, text: m[3] });
        else if (/^\s{2,}\S/.test(lines[i]) && items.length) items[items.length - 1].text += ' ' + lines[i].trim();
        else break;
      }
      out.push(listHTML(items, ordered, ctx));
      continue;
    }
    if (!line.trim()) { flush(); i += 1; continue; }
    if (/^\s*(---|\*\*\*|___)\s*$/.test(line)) { flush(); out.push('<hr>'); i += 1; continue; }
    para.push(line.trim());
    i += 1;
  }
  flush();
  return { html: out.join(''), headings: heads };
}
function listHTML(items, ordered, ctx) {
  const tag = ordered ? 'ol' : 'ul';
  const li = it => {
    const task = /^\[([ xX])\]\s+(.*)$/.exec(it.text);
    if (task) { const done = task[1] !== ' '; return `<li class="un-doc__task">${icon(done ? 'check' : 'circle', done ? 'ok-ic' : 'muted')}<span dir="${dir(task[2])}">${inline(task[2], ctx)}</span><span class="sr-only">${t(done ? 'un.doc.done' : 'un.doc.todo')}</span></li>`; }
    return `<li dir="${dir(it.text)}">${inline(it.text, ctx)}</li>`;
  };
  let html = `<${tag} class="un-doc__ul">`, nested = false;
  items.forEach(it => {
    if (it.depth && !nested) { html += '<ul>'; nested = true; } else if (!it.depth && nested) { html += '</ul>'; nested = false; }
    html += li(it);
  });
  return html + (nested ? '</ul>' : '') + `</${tag}>`;
}

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
function mermaidBlock(src, ctx, n) {
  const g = parseFlowchart(src);
  const drawn = g ? `<figure class="un-diagram panel">${flowchartSVG(g, false)}` : `<figure class="un-diagram panel"><p class="small muted">${t('un.doc.cannotdraw')}</p>`;
  return `${drawn}<figcaption class="un-diagram__bar">
    ${g ? `<button class="btn btn--plain btn--sm" data-act="sheet" data-sheet="diagram:${n}:${esc(enc(ctx.path))}">${icon('external', 'icon--sm')}${t('un.doc.full')}</button>` : ''}
    <details class="un-diagram__src" ${g ? '' : 'open'}><summary class="link">${icon('code', 'icon--sm')}${t('un.doc.source')}</summary><div class="code" style="padding:12px 16px;white-space:pre" tabindex="0">${esc(src)}</div>
      <button class="btn btn--secondary btn--sm" data-act="copy" data-text="${esc(src)}">${icon('copy', 'icon--sm')}${t('un.doc.copysrc')}</button></details></figcaption></figure>`;
}
/** The n-th Mermaid source of a text. */
export const mermaidOf = (md, n) => [...md.matchAll(/```mermaid\n([\s\S]*?)```/g)].map(m => m[1])[n] || null;
