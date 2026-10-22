// Markdown drawn without any library (LIB-03, LIB-04, LIB-05), for a report document and for what an assistant writes
// (a run's words, Ask's answers): headings with anchors for the contents, paragraphs, lists and task lists, tables with
// their number columns aligned, quotes and GitHub's alerts, code with copy; a diagram is the caller's (ctx.diagram,
// the library's Mermaid flowcharts), else its source. Nothing is ever injected as HTML: every text is escaped, then
// only the marks below are added. Problem ids open the problem, links to other documents open them here, outside
// links open outside, a file the library lacks is a dead link.
import { t } from './i18n.js';
import { esc, icon } from './format.js';
import { href } from './address.js';
import { problems } from '../data/model.js';

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
    return (ctx.docs || new Set()).has(path) ? `<a class="link" href="${href('/understand/library/' + enc(path))}">${label}</a>` : `<span class="un-deadlink" title="${esc(t('un.doc.dead'))}">${label}</span>`;
  });
  s = s.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, '$1<em>$2</em>');
  s = s.replace(/\b(TASK-\d{1,6})\b/g, (m, id) => ((ctx.cards || new Set()).has(id) ? `<a class="link" href="${href('/problems/' + id)}"><bdi class="mono">${id}</bdi></a>` : m));
  s = s.replace(/\\([_*`#|\[\]])/g, '$1');
  return s.replace(/\u0000code([^\u0001]*)\u0001/g, '<bdi class="mono">$1</bdi>');
}
export const slug = text => String(text).toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '');
const dir = text => (/[؀-ۿ]/.test(text) ? 'rtl' : 'ltr');

/* The block readers: each answers [html, the next line] for the block starting at line i, or null when it is not its
   kind. doc: {out, para, heads, diagram}, the document drawn so far. */
function fence(lines, i, ctx, doc) {
  const m = /^\s*```\s*(\S*)/.exec(lines[i]);
  if (!m) return null;
  const body = [];
  for (i += 1; i < lines.length && !/^\s*```/.test(lines[i]); i += 1) body.push(lines[i]);
  const src = body.join('\n');
  if (m[1] === 'mermaid' && ctx.diagram) return [ctx.diagram(src, doc.diagram++), i + 1];
  return [`<div class="un-codeblock"><div class="un-codeblock__bar"><span class="small muted">${esc(m[1] || '')}</span><button class="btn btn--plain btn--sm" data-act="copy" data-text="${esc(src)}">${icon('copy', 'icon--sm')}${t('copy')}</button></div>
        <div class="code" tabindex="0">${body.map((l, j) => `<div class="code__line"><span class="code__ln">${j + 1}</span><span>${esc(l)}</span></div>`).join('')}</div></div>`, i + 1];
}
function heading(lines, i, ctx, doc) {
  const h = /^(#{1,6})\s+(.*?)\s*#*\s*$/.exec(lines[i]);
  if (!h) return null;
  const depth = h[1].length, text = h[2].replace(/[*`]/g, '');
  if (depth === 1 && !doc.out.length && !doc.para.length) return ['', i + 1]; // the document's title is the page's
  const id = 'h-' + slug(text), tag = `h${Math.min(depth + 1, 4)}`;
  doc.heads.push({ id, depth, text });
  return [`<${tag} id="${id}" dir="${dir(text)}">${inline(h[2], ctx)}</${tag}>`, i + 1];
}
function table(lines, i, ctx) {
  if (!/^\s*\|.*\|\s*$/.test(lines[i]) || !/^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1] || '')) return null;
  const cells = l => l.trim().replace(/^\||\|$/g, '').split(/(?<!\\)\|/).map(c => c.trim());
  const head = cells(lines[i]), rows = [];
  for (i += 2; i < lines.length && /^\s*\|/.test(lines[i]); i += 1) rows.push(cells(lines[i]));
  const numeric = head.map((_, j) => rows.length && rows.every(r => /^[-+]?[\d,.]+%?$|^—?$/.test(r[j] || '')));
  const cls = j => (numeric[j] ? 'num' : '');
  return [`<div class="un-table-wrap panel" tabindex="0"><table class="un-table"><thead><tr>${head.map((c, j) => `<th scope="col" class="${cls(j)}">${inline(c, ctx)}</th>`).join('')}</tr></thead>
        <tbody>${rows.map(r => `<tr>${head.map((_, j) => `<td class="${cls(j)}">${inline(r[j] || '', ctx)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`, i];
}
function quote(lines, i, ctx) {
  if (!/^\s*>/.test(lines[i])) return null;
  const body = [];
  for (; i < lines.length && /^\s*>/.test(lines[i]); i += 1) body.push(lines[i].replace(/^\s*>\s?/, ''));
  const alert = ALERT.exec(body[0] || '');
  if (!alert) return [`<blockquote dir="${dir(body.join(' '))}">${inline(body.join(' '), ctx)}</blockquote>`, i];
  body[0] = body[0].replace(ALERT, '');
  const kind = alert[1].toLowerCase(), warn = kind === 'warning' || kind === 'caution';
  return [`<div class="un-alert un-alert--${warn ? 'warning' : 'note'}" role="note">${icon(warn ? 'warn' : 'info')}<div><b>${t('un.doc.' + kind)}</b><p>${inline(body.join(' '), ctx)}</p></div></div>`, i];
}
const ITEM = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
function list(lines, i, ctx) {
  const first = ITEM.exec(lines[i]);
  if (!first) return null;
  const items = [];
  for (; i < lines.length; i += 1) {
    const m = ITEM.exec(lines[i]);
    if (m) items.push({ depth: m[1].length >= 2 ? 1 : 0, text: m[3] });
    else if (/^\s{2,}\S/.test(lines[i]) && items.length) items[items.length - 1].text += ' ' + lines[i].trim();
    else break;
  }
  return [listHTML(items, /\d/.test(first[2]), ctx), i];
}
const rule = (lines, i) => (/^\s*(---|\*\*\*|___)\s*$/.test(lines[i]) ? ['<hr>', i + 1] : null);
const BLOCKS = [fence, heading, table, quote, list, rule];

/** {html, headings: [{id, depth, text}]} of a Markdown text. ctx: {path, docs: Set, cards: Set, diagram(src, n)}. */
export function render(md, ctx) {
  const lines = md.replace(/\r\n?/g, '\n').split('\n');
  const doc = { out: [], para: [], heads: [], diagram: 0 };
  const flush = () => { if (doc.para.length) { const s = doc.para.join(' '); doc.out.push(`<p dir="${dir(s)}">${inline(s, ctx)}</p>`); doc.para.length = 0; } };
  let i = 0;
  while (i < lines.length) {
    // a blank line ends a paragraph; a line no block reader takes is one
    const block = lines[i].trim() ? BLOCKS.reduce((found, read) => found || read(lines, i, ctx, doc), null) : ['', i + 1];
    if (!block) { doc.para.push(lines[i].trim()); i += 1; continue; }
    flush();
    if (block[0]) doc.out.push(block[0]);
    i = block[1];
  }
  flush();
  return { html: doc.out.join(''), headings: doc.heads };
}
function listHTML(items, ordered, ctx) {
  const tag = ordered ? 'ol' : 'ul';
  const li = it => {
    const task = /^\[([ xX])\]\s+(.*)$/.exec(it.text);
    if (task) { const done = task[1] !== ' '; return `<li class="un-doc__task">${icon(done ? 'check' : 'circle', done ? 'ok-ic' : 'muted')}<bdi dir="${dir(task[2])}">${inline(task[2], ctx)}</bdi><span class="sr-only">${t(done ? 'un.doc.done' : 'un.doc.todo')}</span></li>`; }
    return `<li><bdi dir="${dir(it.text)}">${inline(it.text, ctx)}</bdi></li>`; // the marker keeps the page's side
  };
  let html = `<${tag} class="un-doc__ul">`, nested = false;
  items.forEach(it => {
    if (it.depth && !nested) { html += '<ul>'; nested = true; } else if (!it.depth && nested) { html += '</ul>'; nested = false; }
    html += li(it);
  });
  return html + (nested ? '</ul>' : '') + `</${tag}>`;
}

/** What an assistant wrote, drawn as Markdown: its tables, lists, headings and bold; its problem ids open them. */
export function md(text) {
  return `<div class="md">${render(String(text || ''), { path: '', cards: new Set(problems().map(p => p.id)) }).html}</div>`;
}
