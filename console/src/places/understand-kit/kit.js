// What builder B's places share (the plan, Understand and its four groups): the view tabs, the operation glyphs and
// tags, rows, folds, segmented controls whose choices are addresses, each view's own search, lists 50 at a time, the
// loading and not-measured states, the provenance line of every target view (PLN-13), pan and zoom for any map
// (SYS-18), the readout of marks, the two-column flow (bridge, seen and unseen), and picking problems for the one Fix
// preview in Problems. A kit: stateless helpers bundled into each place that imports them (scripts/build.mjs).
import {
  t, tn, L, num, esc, icon, code, sev, rich, href, parseHash, setQuery, navigate, act, announce, fmtWhen, exactTime, offline, openSheet,
  model, selection, data, normalize,
} from 'eaos';

export const q = () => parseHash().query;
export const enc = encodeURIComponent;
export const pct = v => (v == null ? '—' : Math.round(v * 100) + '%');
export const rtl = () => document.documentElement.dir === 'rtl';
export const matches = normalize.matches;

/** Understand's four groups and their views (IA section 3), as the quiet tabs of each view. */
export const GROUPS = [
  { id: 'change', views: ['story', 'gaps', 'operations', 'ideal', 'ai-decisions'] },
  { id: 'built', views: ['components', 'paths', 'functions', 'data', 'unseen', 'infra', 'pipelines', 'architecture'] },
  { id: 'screens', views: ['screens', 'screens/all', 'journeys'] },
  { id: 'records', views: ['library', 'report-files', 'history'] },
];
export const groupOf = v => GROUPS.find(g => g.views.includes(v));
export const vkey = v => v.replace('/', '-');
export function tabs(view) {
  const g = groupOf(view);
  return `<nav class="un-tabs" aria-label="${esc(t('nav.u.' + g.id))}">${g.views.map(v => `<a href="${href('/understand/' + v)}" ${v === view ? 'aria-current="page"' : ''}>${t('un.v.' + vkey(v))}</a>`).join('')}</nav>`;
}
export const back = (path, label, query) => `<a class="back" href="${href(path, query)}">${icon('back', 'icon--dir')}${esc(label)}</a>`;

/* ---------- operations: categorical colour, the glyph always drawn, the word always written (DESIGN-SYSTEM 2.7) ---------- */
const GLYPH = {
  introduce: 'M8 3.5v9M3.5 8h9',
  rebuild: 'M12.2 8.6A4.3 4.3 0 1 1 10.9 4.6M11.4 2.6v2.6H8.8',
  merge: 'M4 3.5c0 4.2 4 3.6 4 9M12 3.5c0 4.2-4 3.6-4 9',
  modify: 'M3 9.2c1.6-2.6 3.3-2.6 5 0s3.4 2.6 5 0',
  delete: 'M3.5 8h9',
  retain: 'M4 6.3h8M4 9.7h8',
};
export const OPS = ['introduce', 'rebuild', 'merge', 'modify', 'delete', 'retain'];
/** The report names an operation in two vocabularies (gaps and operations: refactor, new; the maps and the story:
 *  modify, introduce, missing); the screens draw one. */
const SAME_OP = { refactor: 'modify', new: 'introduce', missing: 'introduce', keep: 'retain' };
export const opOf = op => SAME_OP[op] || (GLYPH[op] ? op : 'modify');
export const glyph = (op, size) => `<svg class="opg opg--${opOf(op)}" viewBox="0 0 16 16" ${size ? `width="${size}" height="${size}"` : ''} aria-hidden="true"><path d="${GLYPH[opOf(op)]}"/></svg>`;
export const opTag = (op, quiet) => `<span class="optag optag--${opOf(op)}${quiet ? ' optag--quiet' : ''}"><span class="optag__sw">${glyph(op)}</span>${t('un.op.' + opOf(op))}</span>`;

/** The severity mix of a component or a check: one 100 % bar, critical at the start, words for screen readers. */
const MIX = ['critical', 'high', 'medium', 'low'];
export function sevMix(f, wide) {
  const parts = MIX.map(k => [k, (f && f[k]) || 0]);
  const total = parts.reduce((s, p) => s + p[1], 0);
  if (!total) return `<span class="un-mix un-mix--none">${t('un.nofindings')}</span>`;
  return `<span class="un-mix ${wide ? 'un-mix--wide' : ''}" role="img" aria-label="${esc(parts.filter(p => p[1]).map(p => `${t('sev.' + p[0])} ${p[1]}`).join(', '))}">
    <span class="sevbar">${parts.filter(p => p[1]).map(p => `<span class="s-${p[0]}" style="flex:${p[1]}"></span>`).join('')}</span><b class="num">${num(total)}</b></span>`;
}
export const findings = f => MIX.reduce((s, k) => s + ((f && f[k]) || 0), 0);
export const band = n => (n === 0 ? 0 : n <= 3 ? 1 : n <= 9 ? 2 : n <= 19 ? 3 : 4);

/* ---------- rows, folds, facts ---------- */
export const facts = pairs => `<dl class="facts">${pairs.filter(Boolean).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>`;
export const fold = (title, sum, body, opts) => `<details class="fold" ${opts && opts.open ? 'open' : ''} ${opts && opts.id ? `id="${opts.id}"` : ''}>
    <summary>${opts && opts.icon ? icon(opts.icon, 'muted') : ''}<span class="row__main"><span class="row__title">${title}</span>${sum ? `<span class="row__meta" style="display:block">${sum}</span>` : ''}</span>${icon('chev', 'chev')}</summary>
    <div class="fold__body">${body}</div></details>`;
export const row = (link, ic, title, meta, end, cls) => `<a class="row ${cls || ''}" href="${link}">${ic ? icon(ic, 'muted') : ''}<span class="row__main"><span class="row__title">${title}</span>${meta ? `<span class="row__meta" style="display:block">${meta}</span>` : ''}</span>${end ? `<span class="row__end">${end}</span>` : ''}${icon('chev', 'icon--sm icon--dir muted')}</a>`;

/** A segmented control whose choices are addresses (LNK-01): [value, label, count]. */
export function seg(param, items, cur, label, opts) {
  const r = parseHash();
  return `<nav class="seg ${opts && opts.cls ? opts.cls : ''}" aria-label="${esc(label)}">${items.map(([v, lab, n]) => {
    const query = Object.assign({}, r.query, { [param]: v === (opts && opts.dflt) ? null : v, n: null, sheet: null });
    return `<a href="${href(r.path, query)}" ${String(cur) === String(v) ? 'aria-current="true"' : ''}><span>${lab}</span>${n != null ? ` <b>${num(n)}</b>` : ''}</a>`;
  }).join('')}</nav>`;
}

/** Each view's own search (SRC-03), the same matching as everywhere (SRC-02); the address keeps it. */
export const search = (value, ph) => `<label class="field un-search">${icon('search')}<span class="sr-only">${esc(ph)}</span>
    <input type="search" data-input="unq" data-fk="unq" value="${esc(value || '')}" placeholder="${esc(ph)}" autocomplete="off"></label>`;
let qTimer = 0;
act('unq', el => {
  clearTimeout(qTimer);
  const v = el.value;
  qTimer = setTimeout(() => {
    setQuery({ q: v || null, n: null });
    const inp = document.querySelector('[data-fk="unq"]');
    if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
  }, 180);
});

/** A large list 50 rows at a time (?n= keeps how many are shown): the rows, the "Show 50 more" link, how many shown. */
export function page(items, render, step) {
  step = step || 50;
  const n = Math.max(step, parseInt(q().n, 10) || step);
  const shown = items.slice(0, n);
  const r = parseHash();
  const more = items.length > n ? `<a class="btn btn--secondary un-more" href="${href(r.path, Object.assign({}, r.query, { n: n + step }))}">${t('un.more', { n: num(Math.min(step, items.length - n)) })}</a>` : '';
  return { html: shown.map(render).join(''), more, shown: shown.length };
}
export const count = (shown, total) => `<span class="listhead__count" aria-live="polite">${esc(t('un.showing', { shown: num(shown), total: num(total) }))}</span>`;

/* ---------- state templates (DESIGN-SYSTEM section 10) ---------- */
export const skeleton = rows => `<ul class="panel rows" style="margin-top:24px">${Array.from({ length: rows || 5 }, () => `<li class="row"><span style="flex:1;display:grid;gap:8px"><span class="skel-line" style="width:45%"></span><span class="skel-line" style="width:80%"></span></span></li>`).join('')}</ul>`;
export const loading = (title, rows) => `<div class="page page--wide" aria-busy="true"><h1 class="lede">${title}</h1>${skeleton(rows)}</div>`;
export const nm = (title, why, actHTML) => `<div class="nm"><div class="nm__title"><span class="tag tag--nm">${t('nm')}</span>${title}</div><p class="small ink-2">${why}</p>${actHTML ? `<div>${actHTML}</div>` : ''}</div>`;
/** The empty state of a view (no check has written the report yet): what will be here, and the one action. */
export const empty = (lede, guide, head) => `<div class="page">${head || ''}<h1 class="lede">${lede}</h1><p class="guide">${guide}</p>
    <div class="actions"><a class="btn btn--primary" href="${href('/activity', { sheet: offline() ? 'open-live' : 'check' })}">${t('st.empty.act')}</a></div></div>`;
export const checkBtn = () => `<a class="btn btn--secondary btn--sm" href="${href('/activity', { sheet: offline() ? 'open-live' : 'check' })}">${t('st.empty.act')}</a>`;

/** Why the report has no `name` section, from its coverage row (coverage.json): {state, detail, step}; null when it
 *  is there. A section the coverage says is measured but whose file could not be read says so too. */
export function absent(name) {
  if (data.section(name) !== undefined) return null;
  const rows = (data.section('coverage') || {}).sections || [];
  const row = rows.find(r => r.section === name);
  return row ? { state: row.state, detail: row.detail, step: row.step } : { state: data.isMissing(name) ? 'failed' : 'not_measured', detail: '', step: null };
}
/** The honest state of a view whose section is not in the report: not measured, its reason and the step that makes it. */
export function notMeasured(view, name) {
  const why = absent(name);
  const reason = why && why.detail ? `${rich(L(why.detail))}${why.step ? ` <span class="small muted">(${esc(t('un.nm.step', { step: why.step }))})</span>` : ''}` : esc(t('un.nm.none'));
  return `<div class="page page--wide">${tabs(view)}<h1 class="lede">${t('un.v.' + vkey(view))}</h1>${nm(t(why && why.state === 'failed' ? 'un.nm.unread' : 'un.nm.title'), reason, checkBtn())}</div>`;
}
/** A part of a section the report says it did not measure (a `missing` row: {id, state, step, detail {ar, en}}). */
export const missingRow = m => nm(esc(L(m.detail)), esc(t('un.nm.step', { step: m.step || '—' })));

/* ---------- how each target was made (PLN-13): one line, the detail one press away, the same on every target view ---------- */
export function prov(p) {
  if (!p) return '';
  const planned = p.method === 'planned';
  const line = p.state === 'stale' || p.state === 'failed' || p.state === 'not_planned' ? L(p.message)
    : planned ? t('un.prov.line', { who: p.assistant || '', when: p.at ? fmtWhen(p.at) : '', conf: pct(p.confidence) }) : t('un.prov.rules');
  const departures = (p.departures || []).length, questions = (p.open_questions || []).length;
  return `<details class="un-prov">
    <summary>${icon('ai', 'icon--sm')}<span>${esc(line || t('un.prov.rules'))}</span><span class="link">${t('un.prov.how')}</span></summary>
    <div class="un-prov__body">
      ${facts([
        [t('un.prov.made'), t(planned ? 'un.prov.made.planned' : 'un.prov.made.rules')],
        [t('un.prov.state'), t('un.prov.st.' + (p.state || (planned ? 'planned' : 'not_planned')))],
        planned ? [t('un.prov.by'), `${esc(p.assistant || '')} ${p.model ? code(p.model) : ''}`] : null,
        planned && p.at ? [t('un.prov.when'), esc(exactTime(p.at))] : null,
        planned ? [t('un.prov.conf'), pct(p.confidence)] : null,
        planned ? [t('un.prov.dep'), `<a class="link" href="${href('/understand/ideal')}">${esc(tn('un.pl.departure', departures))}</a>`] : null,
        planned ? [t('un.prov.q'), questions ? `<a class="link" href="${href('/waiting')}">${esc(tn('un.pl.question', questions))}</a>` : esc(tn('un.pl.question', 0))] : null,
      ])}
      <div class="un-key">${keyItem('rules')}${planned ? keyItem('ai') : ''}${keyItem('nm')}</div>
      ${planned ? `<p class="small muted">${t('ai.hypothesis')}</p>` : ''}
    </div></details>`;
}
export const keyItem = k => `<span class="un-key__item"><span class="un-key__sw un-key__sw--${k}" aria-hidden="true"></span>${t('un.key.' + k)}</span>`;

/* ---------- problems: one row, and picking them for the one Fix preview in Problems (one home per job) ---------- */
export const problem = id => model.problem(id);
export const prow = (p, extra) => `<a class="row" href="${href('/problems/' + enc(p.id))}">${sev(p.severity, false)}<span class="row__main"><span class="row__title small">${code(p.id)} ${rich(L(p.title))}</span>${extra ? `<span class="row__meta" style="display:block">${extra}</span>` : ''}</span>${p.state !== 'open' ? `<span class="tag tag--state">${t('state.' + p.state)}</span>` : ''}</a>`;
export const openOf = ids => ids.filter(id => { const p = model.problem(id); return p && p.state === 'open'; });
/** A button that picks these problems (open ones only) as a group and opens the Fix preview over them. */
export function fixBtn(ids, name, label, cls, by) {
  const open = openOf(ids);
  if (offline()) return `<button class="btn ${cls || 'btn--primary'}" data-act="sheet" data-sheet="open-live">${esc(label)}</button>`;
  if (!open.length) return `<button class="btn ${cls || 'btn--primary'}" disabled>${esc(label)}</button>`;
  return `<button class="btn ${cls || 'btn--primary'}" data-act="un-fix" data-ids="${esc(open.join(','))}" data-name="${esc(name)}" data-by="${esc(by || 'gap')}">${esc(label)}</button>`;
}
act('un-fix', el => {
  if (offline()) { openSheet('open-live'); return; }
  const ids = openOf((el.dataset.ids || '').split(',').filter(Boolean));
  selection.pick(ids, el.dataset.name ? { by: el.dataset.by || 'gap', value: el.dataset.name, label: el.dataset.name } : null);
  navigate('/problems', { sheet: 'verb:fix' });
});
act('un-select', el => {
  const ids = openOf((el.dataset.ids || '').split(',').filter(Boolean));
  selection.pick(ids, el.dataset.name ? { by: 'component', value: el.dataset.name, label: el.dataset.name } : null);
  navigate('/problems', el.dataset.comp ? { comp: el.dataset.comp } : {});
  announce(tn('pl.selected', selection.picked.ids.size));
});
/** A button that opens a sheet; in the read-only copy it explains how to open the live console (OFF-01..03). */
export const start = (sheetName, label, cls, extra) => `<button class="btn ${cls || 'btn--primary'}" data-act="sheet" data-sheet="${esc(offline() ? 'open-live' : sheetName)}" ${extra || ''}>${label}</button>`;

export function notFound(id, backPath, label) {
  return `<div class="page">${back(backPath, label)}<div class="empty panel" style="margin-top:12px"><h1 class="empty__title">${esc(t('pd.notfound', { id }))}</h1>
    <p class="small ink-2">${t('un.notfound.guide')}</p><a class="btn btn--secondary" href="${href(backPath)}">${esc(label)}</a></div></div>`;
}
/** `code` spans of a report sentence (already escaped) drawn as code. */
export const ticks = h => h.replace(/`([^`]+)`/g, '<bdi class="mono">$1</bdi>');
export const where = (path, line) => (path ? (line ? `${path}:${line}` : path) : '');

/* ---------- pan and zoom for any map (SYS-18): buttons, drag, wheel, keyboard; 0.7x to 8x ---------- */
export function zoomable(root) {
  root.querySelectorAll('[data-zoom-root]').forEach(wrap => {
    const svg = wrap.querySelector('svg.un-map');
    if (!svg || svg.dataset.zoomReady) return;
    svg.dataset.zoomReady = '1';
    const base = svg.viewBox.baseVal;
    const v0 = { x: base.x, y: base.y, w: base.width, h: base.height };
    let z = 1, cx = v0.x + v0.w / 2, cy = v0.y + v0.h / 2;
    const apply = () => {
      const w = v0.w / z, h = v0.h / z;
      svg.setAttribute('viewBox', `${(cx - w / 2).toFixed(1)} ${(cy - h / 2).toFixed(1)} ${w.toFixed(1)} ${h.toFixed(1)}`);
      const out = wrap.querySelector('[data-zoom-level]');
      if (out) out.textContent = z.toFixed(1) + 'x';
    };
    const fit = () => { z = 1; cx = v0.x + v0.w / 2; cy = v0.y + v0.h / 2; apply(); };
    const set = nz => { z = Math.min(8, Math.max(0.7, nz)); apply(); };
    wrap.addEventListener('click', e => {
      const b = e.target.closest('[data-zoom]');
      if (!b) return;
      const k = b.dataset.zoom;
      if (k === 'in') set(z * 1.4); else if (k === 'out') set(z / 1.4); else fit();
    });
    svg.addEventListener('wheel', e => { if (!e.ctrlKey && !e.metaKey) return; e.preventDefault(); set(z * (e.deltaY < 0 ? 1.15 : 1 / 1.15)); }, { passive: false });
    let drag = null;
    svg.addEventListener('pointerdown', e => { if (e.target.closest('a')) return; drag = { x: e.clientX, y: e.clientY, cx, cy }; svg.setPointerCapture(e.pointerId); });
    svg.addEventListener('pointermove', e => {
      if (!drag) return;
      const r = svg.getBoundingClientRect();
      cx = drag.cx - (e.clientX - drag.x) * (v0.w / z) / r.width;
      cy = drag.cy - (e.clientY - drag.y) * (v0.h / z) / r.height;
      apply();
    });
    svg.addEventListener('pointerup', () => { drag = null; });
    svg.addEventListener('keydown', e => {
      const s = 30 / z;
      if (e.key === '+' || e.key === '=') set(z * 1.4);
      else if (e.key === '-') set(z / 1.4);
      else if (e.key === '0') fit();
      else if (e.key.startsWith('Arrow') && e.target === svg) { cx += e.key === 'ArrowRight' ? s : e.key === 'ArrowLeft' ? -s : 0; cy += e.key === 'ArrowDown' ? s : e.key === 'ArrowUp' ? -s : 0; apply(); }
      else return;
      e.preventDefault();
    });
  });
}
export const zoomBar = () => `<div class="un-zoom" role="group" aria-label="${esc(t('un.map.zoom'))}">
    <button class="btn btn--icon btn--sm" data-zoom="out" aria-label="${esc(t('un.map.out'))}">${icon('minus')}</button>
    <span class="un-zoom__lvl num" data-zoom-level aria-live="polite">1.0x</span>
    <button class="btn btn--icon btn--sm" data-zoom="in" aria-label="${esc(t('un.map.in'))}">${icon('plus')}</button>
    <button class="btn btn--plain btn--sm" data-zoom="fit">${t('un.map.fit')}</button></div>`;

/** A readout for the marks of a chart or a map: hover and keyboard focus show the same line (dataviz interaction). */
export function readout(root) {
  root.querySelectorAll('[data-readout-root]').forEach(wrap => {
    const out = wrap.querySelector('[data-readout]');
    if (!out || wrap.dataset.readoutReady) return;
    wrap.dataset.readoutReady = '1';
    const show = e => { const m = e.target.closest('[data-tip]'); if (m) out.textContent = m.dataset.tip; };
    wrap.addEventListener('pointerover', show);
    wrap.addEventListener('focusin', show);
  });
}
export const after = el => { zoomable(el); readout(el); };

/** Two columns joined by weighted links (the bridge, seen and unseen), drawn on wide screens only; the list beside it
 *  is its twin. left/right: [{id, label, n, glyph, cls, tip, mono}]; links: [from, to, weight, kind, tip]. */
export function flow(left, right, links, opts) {
  if (rtl()) { // reading order: today on the start side
    [left, right] = [right, left];
    links = links.map(l => [l[1], l[0], l[2], l[3], l[4]]);
    opts = Object.assign({}, opts, { leftTitle: opts.rightTitle, rightTitle: opts.leftTitle });
  }
  const rowH = 30, gap = 10, w = 860, nodeW = 230;
  const lh = left.length * (rowH + gap), rh = right.length * (rowH + gap);
  const h = Math.max(lh, rh) + 20;
  const ly = i => 10 + i * (rowH + gap) + (h - 20 - lh) / 2;
  const ry = i => 10 + i * (rowH + gap) + (h - 20 - rh) / 2;
  const max = Math.max(1, ...links.map(l => l[2]));
  const fit = s => (s.length > 26 ? s.slice(0, 25) + '…' : s);
  const paths = links.map(l => {
    const a = left.findIndex(x => x.id === l[0]), b = right.findIndex(x => x.id === l[1]);
    if (a < 0 || b < 0) return '';
    const y1 = ly(a) + rowH / 2, y2 = ry(b) + rowH / 2, x1 = nodeW, x2 = w - nodeW;
    const sw = 1.5 + 9 * (l[2] / max);
    return `<path class="flow__link ${l[3] ? 'flow__link--' + l[3] : ''}" d="M${x1} ${y1}C${(x1 + x2) / 2} ${y1} ${(x1 + x2) / 2} ${y2} ${x2} ${y2}" stroke-width="${sw.toFixed(1)}" data-tip="${esc(l[4] || '')}"><title>${esc(l[4] || '')}</title></path>`;
  }).join('');
  const node = (n, x, y, end) => `<g class="flow__node ${n.cls || ''}" transform="translate(${x} ${y})" data-tip="${esc(n.tip || n.label)}">
      <rect width="${nodeW}" height="${rowH}" rx="6"/>${n.glyph ? `<g transform="translate(${end ? nodeW - 24 : 8} 7)">${n.glyph}</g>` : ''}
      <text x="${end ? nodeW - 12 - (n.glyph ? 20 : 0) : 12 + (n.glyph ? 20 : 0)}" y="${rowH / 2 + 4}" text-anchor="${end ? 'end' : 'start'}" class="${n.mono ? 'flow__mono' : ''}">${esc(fit(n.label))}</text>
      ${n.n != null ? `<text x="${end ? 12 : nodeW - 10}" y="${rowH / 2 + 4}" text-anchor="${end ? 'start' : 'end'}" class="flow__n">${esc(num(n.n))}</text>` : ''}<title>${esc(n.tip || n.label)}</title></g>`;
  return `<div class="flow only-desk" data-readout-root>
    <div class="flow__heads"><span>${esc(opts.leftTitle)}</span><span>${esc(opts.rightTitle)}</span></div>
    <svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(opts.label)}">${paths}${left.map((n, i) => node(n, 0, ly(i), false)).join('')}${right.map((n, i) => node(n, w - nodeW, ry(i), true)).join('')}</svg>
    <p class="small muted un-readout" data-readout aria-live="polite">${esc(opts.hint || t('un.map.hint'))}</p></div>`;
}

const CHANGE = ['rebuild', 'merge', 'modify', 'delete', 'retain'];

/** The change as one bar of operations with a legend; each operation opens its gaps when `link`. */
export function opBar(ops, link) {
  const shown = CHANGE.filter(o => ops[o]);
  if (!shown.length) return `<p class="small muted">${t('un.story.nochange')}</p>`;
  return `<div class="un-opbar" role="img" aria-label="${esc(shown.map(o => `${t('un.op.' + o)} ${ops[o]}`).join(', '))}">${shown.map(o => `<span class="un-opbar__s un-opbar__s--${o}" style="flex:${ops[o]}"></span>`).join('')}</div>
    <div class="legend">${shown.map(o => {
      const inner = `${glyph(o)}<span>${t('un.op.' + o)}</span> <b>${num(ops[o])}</b>`;
      return link ? `<a class="optag-l optag-l--${o}" href="${href('/understand/gaps', { op: o })}">${inner}</a>` : `<span class="optag-l optag-l--${o}">${inner}</span>`;
    }).join('')}</div>`;
}

/** A decision the gap waits for: the report's decision when it is one (an answer in Waiting), else its record's id. */
export function decisionLink(id) {
  if (!id) return `<span class="muted">${t('un.gap.nodecision')}</span>`;
  const d = model.decisions().find(x => x.id === id);
  if (!d) return code(id);
  return `<a class="link" href="${href('/waiting/' + enc(d.id))}">${rich(L(d.question))}</a> <span class="tag ${d.state === 'waiting' ? 'tag--you' : 'tag--ok'}">${t(d.state === 'waiting' ? 'un.dec.waiting' : 'un.dec.answered')}</span>`;
}

/** The build's one next step (model.buildNext): the blueprint's questions first, else the milestone to build. */
export function buildStep() {
  const n = model.buildNext();
  if (!n) return '';
  if (n.link) return `<a class="btn btn--primary" href="${href(n.link)}">${esc(n.label)}</a>`;
  return `<button class="btn btn--primary" data-act="sheet" data-sheet="${offline() ? 'open-live' : n.sheet}">${icon('layers', 'icon--sm')}${esc(n.label)}</button>`;
}
