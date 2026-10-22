// EAOS's own Playwright, by its path: the probe sits in the app's copy, whose own (another version) Node would find first
const { chromium } = require(process.env.EAOS_PLAYWRIGHT);
(async () => {
  const browser = await chromium.launch({ args: ['--proxy-server=http://127.0.0.1:9', '--proxy-bypass-list=127.0.0.1;localhost;[::1]'] });
  const page = await browser.newPage(process.env.EAOS_STORAGE_STATE ? { storageState: process.env.EAOS_STORAGE_STATE } : {});
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e.message).slice(0, 300)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 300)); });
  const visit = async (path) => {   // a hash route (/#/x) is drawn in the page already loaded: no request, so goto answers null
    let status = 0;
    try {
      const href = new URL(path, process.env.BASE_URL).href, r = await page.goto(href, { waitUntil: 'load', timeout: 60000 });
      status = r ? r.status() : new URL(href).hash ? 200 : 0;
      // an app that keeps a live connection open (server-sent events, a socket) is never idle: a few seconds, then read it
      try { await page.waitForLoadState('networkidle', { timeout: 5000 }); } catch {}
    }
    catch (e) { errors.push(String(e.message).slice(0, 300)); }
    return { path, status, url: page.url(), password: await page.locator('input[type=password]').count().catch(() => 0),
             text: (await page.locator('body').innerText().catch(() => '')).slice(0, 4000) };
  };
  const first = await visit('/');
  const others = [];
  for (const path of JSON.parse(process.env.EAOS_ROUTES || '[]')) others.push(await visit(path));
  console.log(JSON.stringify({ ...first, others, errors: errors.slice(0, 10) }));
  await browser.close();
})();
