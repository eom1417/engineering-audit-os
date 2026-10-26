/* Proves a change of the console's code left every screen as it was: snapshots what each screen and each sheet it
   offers draws (the page's markup, scripts aside), then draws them again and names every one that differs.
   --save=FILE crawls the served console from every place (its links and its sheets, a few of each kind of address)
   and writes what each drew; --against=FILE draws the same addresses again and compares. --assets=DIR serves the
   console's code (boot.js and assets/) from a build folder instead of the server's, the server and its data the same.
   Two drawings are compared without the strip of the run working now and with every number masked (steady()): a
   live server moves both on its own; the markup and the words must be the same.
   Usage: node console/tools/same.cjs --save=before.json [--assets=DIR]
          node console/tools/same.cjs --against=before.json --assets=../eaos/data/studio */
const fs = require('fs');
const path = require('path');
const L = require('./lib.cjs');

const arg = name => (process.argv.find(a => a.startsWith(`--${name}=`)) || '').slice(name.length + 3);
const ASSETS = arg('assets');
const COMBOS = L.COMBOS.filter(c => ['1440-ar-light', '390-en-dark'].includes(c.key));
const SEEDS = ['/status', '/waiting', '/waiting/decided', '/waiting/questions', '/waiting/sign-in', '/problems', '/problems/plan',
  '/problems/plan/waves', '/activity', '/activity/runs', '/report', '/report?part=screens', '/report?part=files', '/project/app', '/project/assistants',
  '/project/tools', '/project/settings', '/project/branches', '/open', '/ask'];
const PER_KIND = 3, MOST = 400;

/** What a screen draws, without what moves on its own between two drawings: the strips of the run working now (side and phone), and
 *  every number (times, durations, counts of a live server). Markup and words are compared as they are. */
const steady = html => html.replace(/<a class="(side-live|live-strip)[^]*?<\/a>/g, '').replace(/\d+/g, '#');

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

/** What `route` draws; opened again once when the screen moved on while it was read (a run ended, an address redirected). */
async function draw(page, route, c) {
  for (let tries = 2; ; tries--) {
    await L.open(page, route, c.lang, c.theme);
    try { return await page.evaluate(drawn); } catch (e) { if (!tries || !/context was destroyed/.test(e.message)) throw e; }
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
