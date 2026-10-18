/* What every check of the served console shares: Playwright (the one copy, beta's tools), the address of a live
   console and its launch token, and opening one route the way a person does, waiting until it has drawn.
   Environment:
     EAOS_STUDIO_URL         the console's address (default http://127.0.0.1:8099/, the scratch preview)
     EAOS_STUDIO_TOKEN       its launch token, or EAOS_STUDIO_TOKEN_FILE a file holding it (default: the preview's
                             launch record, /workspace/eaos-work/studio-design/build-home/home/studio/<project>.token)
     PLAYWRIGHT_BROWSERS_PATH where the browsers are (default /workspace/eaos-beta-trial/tools/browsers)
   A file:// address checks the read-only copy (no token). */
const fs = require('fs');
const path = require('path');

process.env.PLAYWRIGHT_BROWSERS_PATH = process.env.PLAYWRIGHT_BROWSERS_PATH || '/workspace/eaos-beta-trial/tools/browsers';
const TOOLS = '/workspace/eaos-beta-trial/tools';
const { chromium } = require(path.join(TOOLS, 'node/node_modules/playwright'));
const AXE = path.join(TOOLS, 'npm/axe-core/node_modules/axe-core/axe.min.js');

const URL_ = (process.env.EAOS_STUDIO_URL || 'http://127.0.0.1:8099/').replace(/#.*$/, '');
function token() {
  if (process.env.EAOS_STUDIO_TOKEN) return process.env.EAOS_STUDIO_TOKEN;
  let file = process.env.EAOS_STUDIO_TOKEN_FILE;
  if (!file) {
    const dir = '/workspace/eaos-work/studio-design/build-home/home/studio';
    const found = fs.existsSync(dir) ? fs.readdirSync(dir).filter(n => n.endsWith('.token')) : [];
    file = found.length ? path.join(dir, found[0]) : null;
  }
  return file && fs.existsSync(file) ? fs.readFileSync(file, 'utf8').trim() : null;
}
const TOKEN = /^https?:/.test(URL_) ? token() : null;

const COMBOS = [];
for (const w of [390, 1440]) for (const lang of ['ar', 'en']) for (const theme of ['light', 'dark']) COMBOS.push({ w, lang, theme, key: `${w}-${lang}-${theme}` });

/** A browser context of one viewport, holding the launch token for the tab (as boot.js keeps it). */
async function context(browser, w, theme) {
  const ctx = await browser.newContext({ viewport: { width: w, height: w === 390 ? 844 : 900 }, colorScheme: theme || 'light', reducedMotion: 'reduce' });
  if (TOKEN) await ctx.addInitScript(t => { try { sessionStorage.setItem('eaos.token', t); } catch (e) { /* about:blank */ } }, TOKEN);
  // a server behind the Remote sign-in gives its token in live-token.js to the sign-in's proxy only; here the token is
  // already in the tab, so that script is answered empty instead of the 404 a local peer gets
  await ctx.route('**/live-token.js*', r => r.fulfill({ status: 200, contentType: 'text/javascript', body: '' }));
  return ctx;
}

/** The address of `route` (#/x?y) in a language and theme. */
const address = (route, lang, theme) => `${URL_}#${route}${route.includes('?') ? '&' : '?'}lang=${lang}${theme ? `&theme=${theme}` : ''}`;

/** Opens `route` and waits until its screen has drawn (its bundle and sections read, no loading state left), and
 *  its sheet has opened when the address names one. */
async function open(page, route, lang, theme) {
  await page.goto('about:blank');
  await page.goto(address(route, lang, theme));
  const loading = /[?&]state=loading/.test(route); // a loading state asked for stays busy
  const t0 = Date.now();
  await page.waitForFunction(loading => {
    const main = document.getElementById('main');
    const E = window.EAOS;
    return main && main.dataset.screen && (loading || (!main.querySelector('[aria-busy="true"]') && !document.querySelector('.sheet [aria-busy="true"]')))
      && E && (E.data.mode !== 'live' || E.live.loaded);
  }, loading, { timeout: 15000 }).catch(() => console.error(`slow: ${route} did not settle in 15 s`));
  if (process.env.EAOS_TIMING) console.error(`${Date.now() - t0} ms ${route}`);
  if (route.includes('sheet=')) await page.waitForSelector('.sheet.is-open', { timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(route.includes('sheet=') ? 260 : 80);
}

/** The lead's routes on the real report (the ids come from the served data: see routes()). */
async function routes(page) {
  await open(page, '/status', 'ar');
  const ids = await page.evaluate(async () => {
    const E = window.EAOS;
    await E.data.need(['cards', 'decisions', 'evidence']);
    const problems = E.model.problems();
    const withFacts = problems.find(p => (p.evidence || []).some(id => E.model.fact(id) && E.model.fact(id).code)) || problems[0];
    const decision = E.model.decisions().find(d => d.state === 'waiting') || E.model.decisions()[0];
    const run = E.store.awaiting()[0];
    return { problem: withFacts && withFacts.id, fact: withFacts && (withFacts.evidence || [])[0], decision: decision && decision.id, run: run && run.id,
      other: problems[1] && problems[1].id };
  });
  const enc = encodeURIComponent;
  const out = ['/status', '/status?state=empty', '/status?state=loading', '/status?state=offline', '/status?sheet=freshness', '/status?sheet=health',
    '/status?sheet=search', '/status?sheet=project', '/status?state=offline&sheet=open-live', '/status?sheet=verb:fix:fixable',
    '/waiting', '/waiting?state=empty', '/waiting?state=offline', '/waiting/decided',
    '/problems', '/problems?state=loading', '/problems?state=empty', '/problems?sheet=filters', '/problems?sheet=groups', '/problems?group=step',
    '/problems?q=toolchain', '/problems?who=you', '/problems/TASK-999', '/problems?sheet=verb:explain:assistant',
    '/status?ask=1', '/problems?ask=1'];
  if (ids.decision) out.push(`/waiting/${enc(ids.decision)}`);
  if (ids.run) out.push(`/waiting/${enc(ids.run)}`, `/waiting?sheet=accept:${enc(ids.run)}`, `/waiting?sheet=reject:${enc(ids.run)}`);
  if (ids.problem) out.push(`/problems/${enc(ids.problem)}`, `/problems/${enc(ids.problem)}?ask=1`, `/problems?sheet=verb:verify:${enc(ids.problem)}`);
  if (ids.fact) out.push(`/problems/${enc(ids.problem)}?sheet=fact:${enc(ids.fact)}`);
  if (ids.other) out.push(`/problems/${enc(ids.other)}`);
  return out;
}

module.exports = { chromium, AXE, URL: URL_, TOKEN, COMBOS, context, address, open, routes };
