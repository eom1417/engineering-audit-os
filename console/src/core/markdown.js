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

/** {html, headings: [{id, depth, text}]} of a Markdown text. ctx: {path, docs: Set, cards: Set, diagram(src, n)}. */
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
      if (fence[1] === 'mermaid' && ctx.diagram) out.push(ctx.diagram(src, diagram++));
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
