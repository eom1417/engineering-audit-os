/* Proves a change of the console's code left every screen as it was: snapshots what each screen and each sheet it
   offers draws (the page's markup, scripts aside), then draws them again and names every one that differs.
   --save=FILE crawls the served console from every place (its links and its sheets, a few of each kind of address)
   and writes what each drew; --against=FILE draws the same addresses again and compares. --assets=DIR serves the
   console's code (boot.js and assets/) from a build folder instead of the server's, the server and its data the same.
   Two drawings are compared without the strip of the run working now and with every number masked (steady()): a
   live server moves both on its own; the markup and the words must be the same.
   --look compares what is seen instead of the markup: each element is its tag, its own words and its computed look
   (colours, borders, fonts, spacing, radii, shadow, layering, place and size; ::before and ::after too), so moving a
   style from an attribute into a class, or a part into the one function that draws it, leaves two drawings equal. Its
   attributes (class and style aside) are saved to read a difference by, not compared. A save and its comparison are
   both made with --look or both without; --diff=FILE writes the two drawings of each address that differs.
   Usage: node console/tools/same.cjs --save=before.json [--assets=DIR] [--look]
          node console/tools/same.cjs --against=before.json --assets=../eaos/data/studio [--look] [--diff=FILE] */
const fs = require('fs');
const path = require('path');
const L = require('./lib.cjs');

const arg = name => (process.argv.find(a => a.startsWith(`--${name}=`)) || '').slice(name.length + 3);
const ASSETS = arg('assets');
const LOOK = process.argv.includes('--look');
const COMBOS = L.COMBOS.filter(c => ['1440-ar-light', '390-en-dark'].includes(c.key));
const SEEDS = ['/status', '/waiting', '/waiting/decided', '/waiting/questions', '/waiting/sign-in', '/problems', '/problems/plan',
  '/problems/plan/waves', '/activity', '/activity/runs', '/report', '/report?part=screens', '/report?part=files', '/project/app', '/project/assistants',
  '/project/tools', '/project/settings', '/project/branches', '/open', '/ask'];
const PER_KIND = 3, MOST = 400;

/** What a screen draws, without what moves on its own between two drawings: the strips of the run working now (side and phone), and
 *  every number (times, durations, counts of a live server). Markup and words are compared as they are; with --look,
 *  each element's attributes are left out (seen() masked its numbers already). */
const steady = html => LOOK ? html.replace(/^( *<[\w-]+) [^\n]*?> /gm, '$1> ') : html.replace(/<a class="(side-live|live-strip)[^]*?<\/a>/g, '').replace(/\d+/g, '#');

/** The kind of an address: its first two parts, how many parts follow, and which query names it has. */
function kind(route) {
  const [p, q = ''] = route.split('?');
  const parts = p.split('/').filter(Boolean);
  const names = q.split('&').filter(Boolean).map(x => x.split('=')[0]).sort().join(',');
  return `${parts.slice(0, 2).join('/')}+${Math.max(0, parts.length - 2)}?${names}`;
}

/** What the page draws, scripts and the passing notices aside. */
const drawn = () => {
  const body = document.body.cloneNode(true);
  body.querySelectorAll('script, style, .toast, [aria-live="polite"]:empty').forEach(e => e.remove());
  return body.innerHTML;
};

/** What the page shows, element by element (--look): one line per element, indented by depth, of its tag, attributes
 *  (class and style aside, numbers masked), own words (numbers masked) and its computed look, only what draws: a value
 *  inherited unchanged from the parent or left at its initial value is not written. The strips of the run working now
 *  are left out as in steady(), and what is inside an element not displayed; a width that follows words holding a number is masked (it moves with a live count). */
const seen = () => {
  const INHERITED = ['color', 'font-family', 'font-size', 'font-weight', 'font-style', 'line-height', 'letter-spacing', 'text-align',
    'text-transform', 'white-space', 'visibility', 'direction', 'cursor', 'list-style-type', 'fill', 'stroke'];
  const OWN = { 'background-color': 'rgba(0, 0, 0, 0)', 'background-image': 'none', 'box-shadow': 'none', 'z-index': 'auto', position: 'static',
    opacity: '1', 'row-gap': 'normal', 'column-gap': 'normal', 'flex-direction': 'row', 'flex-wrap': 'nowrap', 'align-items': 'normal',
    'justify-content': 'normal', 'grid-template-columns': 'none', 'grid-template-rows': 'none', overflow: 'visible', 'text-decoration-line': 'none',
    'outline-style': 'none', top: 'auto', right: 'auto', bottom: 'auto', left: 'auto', 'max-width': 'none', 'min-width': 'auto|0px',
    'min-height': 'auto|0px', transform: 'none', 'text-overflow': 'clip' };
  for (const side of ['top', 'right', 'bottom', 'left']) { OWN[`margin-${side}`] = '0px'; OWN[`padding-${side}`] = '0px'; }
  for (const corner of ['top-left', 'top-right', 'bottom-right', 'bottom-left']) OWN[`border-${corner}-radius`] = '0px';
  const SKIP = 'script, style, .toast, .side-live, .live-strip';
  const mask = t => t.replace(/\d+/g, '#');
  const look = (cs, parent, own) => {
    const out = [`display:${cs.display}`];
    for (const p of INHERITED) if (!parent || cs.getPropertyValue(p) !== parent.getPropertyValue(p)) out.push(`${p}:${cs.getPropertyValue(p)}`);
    for (const p of Object.keys(OWN)) if (!OWN[p].split('|').includes(cs.getPropertyValue(p))) out.push(`${p}:${cs.getPropertyValue(p)}`);
    for (const side of ['top', 'right', 'bottom', 'left']) {
      const w = cs.getPropertyValue(`border-${side}-width`);
      if (w !== '0px' && cs.getPropertyValue(`border-${side}-style`) !== 'none') out.push(`border-${side}:${w} ${cs.getPropertyValue(`border-${side}-style`)} ${cs.getPropertyValue(`border-${side}-color`)}`);
    }
    if (cs.getPropertyValue('outline-style') !== 'none') out.push(`outline:${cs.outlineWidth} ${cs.outlineColor} ${cs.outlineOffset}`);
    if (own) out.push(own);
    return out.join(';');
  };
  const lines = [];
  const walk = (el, depth, parent) => {
    if (el.matches(SKIP) || (el.matches('[aria-live="polite"]') && !el.childNodes.length)) return;
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    const attrs = [...el.attributes].filter(a => a.name !== 'class' && a.name !== 'style').map(a => `${a.name}=${mask(a.value)}`).sort().join(' ');
    const words = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).filter(Boolean).join(' ');
    const size = `size:${/\d/.test(el.textContent) ? '~' : Math.round(r.width)}x${Math.round(r.height)}`;
    lines.push(`${' '.repeat(depth)}<${el.tagName.toLowerCase()} ${attrs}> ${mask(words)} {${look(cs, parent, size)}}`);
    for (const pseudo of ['::before', '::after']) {
      const ps = getComputedStyle(el, pseudo);
      if (ps.content !== 'none' && ps.content !== 'normal') lines.push(`${' '.repeat(depth + 1)}${pseudo} {${look(ps, cs, `content:${mask(ps.content)}`)}}`);
    }
    if (cs.display !== 'none') for (const child of el.children) walk(child, depth + 1, cs);
  };
  walk(document.body, 0, null);
  return lines.join('\n');
};

/** What `route` draws; opened again once when the screen moved on while it was read (a run ended, an address redirected). */
async function draw(page, route, c) {
  for (let tries = 2; ; tries--) {
    await L.open(page, route, c.lang, c.theme);
    try { return await page.evaluate(LOOK ? seen : drawn); } catch (e) { if (!tries || !/context was destroyed/.test(e.message)) throw e; }
  }
}

async function serveFrom(ctx) {
  if (!ASSETS) return;
  const dir = path.resolve(ASSETS);
  await ctx.route(/\/(boot\.js|assets\/[\w-]+\.(js|css))(\?.*)?$/, r => {
    const name = new URL(r.request().url()).pathname;
    const file = path.join(dir, name.endsWith('/boot.js') ? 'boot.js' : `assets/${path.basename(name)}`);
    r.fulfill({ status: 200, contentType: file.endsWith('.css') ? 'text/css' : 'text/javascript', body: fs.readFileSync(file) });
  });
}

/** Every address worth drawing: the seeds, then the links and sheets each one offers, PER_KIND of each kind. */
async function crawl(page) {
  const queue = [...new Set([...SEEDS, ...await L.routes(page)])];
  const seen = new Set(queue), kinds = {}, out = [];
  while (queue.length && out.length < MOST) {
    const route = queue.shift();
    const k = kind(route);
    if ((kinds[k] = (kinds[k] || 0) + 1) > PER_KIND && !SEEDS.includes(route)) continue;
    out.push(route);
    if (out.length % 50 === 0) console.error(`${out.length} found`);
    await L.open(page, route, 'en', 'light');
    const found = await page.evaluate(() => ({
      links: [...document.querySelectorAll('a[href^="#/"]')].map(a => a.getAttribute('href').slice(1)),
      sheets: [...new Set([...document.querySelectorAll('[data-act="sheet"]')].map(e => e.dataset.sheet))],
    }));
    const base = route.split('?')[0];
    const next = found.links.map(h => h.replace(/[?&](lang|theme)=[^&]*/g, '').replace(/^([^?]*)&/, '$1?'))
      .concat(route.includes('sheet=') ? [] : found.sheets.map(n => `${base}?sheet=${encodeURIComponent(n)}`));
    for (const r of next) if (!seen.has(r)) { seen.add(r); queue.push(r); }
  }
  return out;
}

(async () => {
  const save = arg('save'), against = arg('against');
  if (!save && !against) throw new Error('give --save=FILE or --against=FILE');
  const before = against ? JSON.parse(fs.readFileSync(against, 'utf8')) : null;
  const browser = await L.chromium.launch();
  const shots = {}, errors = [];
  let routes = before && before.routes;
  for (const c of COMBOS) {
    const ctx = await L.context(browser, c.w, c.theme);
    await serveFrom(ctx);
    const page = await ctx.newPage();
    let current = '';
    page.on('pageerror', e => errors.push(`${c.key} ${current} PAGEERROR ${e.message}`));
    page.on('console', m => { if (m.type() === 'error') errors.push(`${c.key} ${current} console: ${m.text()}`); });
    if (!routes) routes = await crawl(page);
    for (const r of routes) {
      current = r;
      shots[`${c.key} ${r}`] = await draw(page, r, c);
      if (Object.keys(shots).length % 50 === 0) console.error(`${Object.keys(shots).length} drawn`);
    }
    await ctx.close();
  }
  await browser.close();
  if (save) fs.writeFileSync(save, JSON.stringify({ routes, shots }));
  const differ = before ? Object.keys(before.shots).filter(k => steady(before.shots[k]) !== steady(shots[k] || '')) : [];
  console.log(`${routes.length} addresses x ${COMBOS.length}: ${Object.keys(shots).length} drawn; ${differ.length} differ; ${errors.length} errors`);
  differ.forEach(k => console.log(`differs: ${k}`));
  [...new Set(errors)].forEach(e => console.log(e));
  if (before && arg('diff')) fs.writeFileSync(arg('diff'), JSON.stringify(Object.fromEntries(differ.map(k => [k, [before.shots[k], shots[k]]]))));
  process.exitCode = differ.length || errors.length ? 1 : 0;
})();
