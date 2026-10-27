// EAOS crawl: every page of a running app, found by following its links and pressing its moving buttons, through the
// pinned Playwright.
//
// Run by eaos/live/screens/crawl.py as a separate process:  node crawl.mjs <config.json>
// The config names the Playwright module folder, the app's base URL and the most pages to open. Each page is opened
// once, breadth first from the base, and the links it shows are read after it settles; nothing is measured here (the
// heavy Lighthouse audit runs on a few distinct pages only, in crawl.py). A hash-routed app (#/problems) is followed
// by its routes; any other fragment is an anchor of the same page. Requests to any other origin are aborted. Signed in,
// a link matching config.leaves (sign out, delete, change) is never opened; config.read_only (a published site) lets
// nothing but GET through.
// The result is one JSON object on stdout: {routes: [{path, depth, status}]}. With config.coverage (a file), the
// JavaScript each page ran is written there, every script's functions with whether any page ran them (M13.2,
// eaos/live/testing/ran.py browser).
import { readFileSync, writeFileSync } from 'node:fs';
import { playwrightFrom } from './pinned.mjs';

const config = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const playwright = playwrightFrom(config.modules.playwright);
const base = new URL(config.base);
const leaves = config.leaves ? new RegExp(config.leaves, 'i') : null;

// The page's address as the crawl names it: its path and, for a hash route, the route; null for another origin.
function pathOf(href) {
  let url;
  try { url = new URL(href, base); } catch { return null; }
  if (url.origin !== base.origin || !['http:', 'https:'].includes(url.protocol)) return null;
  // a hash route is the screen wherever the page sits: CoreUI's links, read on /components, named /components#/x
  if (url.hash.startsWith('#/')) return base.pathname + url.hash;
  return (url.pathname || '/') + url.search;
}

// An app that moves by buttons (a tab bar, a menu of buttons) and opens on a welcome: its pages are found by pressing
// them, never a button that would change or remove something (an SPA: one page found of many, nothing locked).
const STARTS = /^\s*(ابدأ|ابدا|ابدأ الآن|يلا|start|get started|begin|continue|متابعة|تابع|skip|تخطَّ?ي?|next|التالي)(\s|!|$)/i;
const MOVERS = 'nav button, [role=navigation] button, header button, footer button, [role=tablist] button, [role=tab], [role=link], [role=menuitem]';
const UNSAFE = /delete|remove|clear|reset|save|submit|send|pay|buy|sign|log ?out|حذف|امسح|مسح|احفظ|حفظ|أرسل|ارسل|إرسال|ادفع|دفع|شراء|خروج|تسجيل/i;

// {url: {name: ran}}: the functions of every script the pages loaded from the app, ran when any page ran them.
const ran = {};
function collect(entries) {
  for (const entry of entries) {
    if (!entry.url.startsWith(base.origin) || entry.url.includes('/node_modules/')) continue;
    const functions = (ran[entry.url] ||= {});
    for (const f of entry.functions) {
      if (f.functionName) functions[f.functionName] = functions[f.functionName] || (f.ranges[0]?.count || 0) > 0;
    }
  }
}

const hrefs = (page) => page.evaluate(() => [...document.querySelectorAll('a[href]')].map((a) => a.href));

// The welcome dismissed (once: the context keeps what it stored), then each moving button pressed in turn: the
// addresses it led to and the links it showed.
async function pressed(page, path) {
  const found = [];
  const start = page.getByRole('button', { name: STARTS }).first();
  if (await start.isVisible().catch(() => false)) { await start.click({ timeout: 2000 }).catch(() => {}); await page.waitForTimeout(500); }
  const movers = page.locator(MOVERS);
  for (let i = 0; i < Math.min(await movers.count(), 15); i++) {
    const button = movers.nth(i);
    if (UNSAFE.test((await button.innerText().catch(() => '')) + (await button.getAttribute('aria-label').catch(() => '') || ''))) continue;
    try {
      await button.click({ timeout: 2000 });
      await page.waitForTimeout(300);
      found.push(page.url(), ...await hrefs(page));
      if (pathOf(page.url()) !== path) await page.goto(new URL(path, base).href, { waitUntil: 'load' });
    } catch {}
  }
  return [...found, ...await hrefs(page)];
}

const browser = await playwright.chromium.launch({ headless: true, args: config.chromium_args || [] });
const routes = [];
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block',
    storageState: config.storage_state || undefined });
  await context.route('**/*', (route) => {
    const target = new URL(route.request().url());
    if (config.read_only && route.request().method() !== 'GET') return route.abort('blockedbyclient');
    if (['data:', 'blob:'].includes(target.protocol) || target.origin === base.origin) return route.continue();
    return route.abort('blockedbyclient');
  });
  const seen = new Set([pathOf(base.href)]);
  const queue = [{ path: pathOf(base.href), depth: 0 }];
  // The screens the code names, opened like links of the entry page
  const seeded = new Set();
  for (const seed of config.seeds || []) {
    const found = pathOf(seed);
    if (found && !seen.has(found) && !(leaves && leaves.test(found))) { seen.add(found); seeded.add(found); queue.push({ path: found, depth: 1 }); }
  }
  while (queue.length && routes.length < config.max_routes) {
    const { path, depth } = queue.shift();
    const page = await context.newPage();
    if (config.coverage) await page.coverage.startJSCoverage({ resetOnNavigation: false }).catch(() => {});
    let status = 'observed', links = [];
    try {
      const answer = await page.goto(new URL(path, base).href, { waitUntil: 'load', timeout: config.timeout_ms || 30000 });
      // a route that answers with data (JSON, a file) is no screen: a server's GET routes are tried as pages
      if (answer && !/html/i.test(answer.headers()['content-type'] || 'text/html')) throw new Error('not a page');
      // an address the code names that the app does not have (a route read without its prefix) is no screen
      if (answer && answer.status() >= 400 && seeded.has(path)) throw new Error('not a page');
      // A development server can take long to draw the first screen: wait until the page shows something
      try { await page.waitForFunction(() => document.body && document.body.innerText.trim().length > 0, null, { timeout: 60000 }); } catch {}
      try { await page.waitForLoadState('networkidle', { timeout: 5000 }); } catch {}
      links = [page.url(), ...(config.read_only ? await hrefs(page) : await pressed(page, path))];   // with where it led (a redirect)
    } catch (error) {
      status = 'error';
    }
    if (config.coverage) collect(await page.coverage.stopJSCoverage().catch(() => []));
    await page.close();
    routes.push({ path, depth, status });
    for (const href of links) {
      const found = pathOf(href);
      if (found && !seen.has(found) && !(leaves && leaves.test(found))) { seen.add(found); queue.push({ path: found, depth: depth + 1 }); }
    }
  }
} finally {
  await browser.close();
  if (config.coverage) writeFileSync(config.coverage, JSON.stringify(Object.entries(ran).map(([url, functions]) => ({
    url, functions: Object.entries(functions).map(([functionName, hit]) => ({ functionName, ranges: [{ count: hit ? 1 : 0 }] })) }))));
}
process.stdout.write(JSON.stringify({ routes }) + '\n');
