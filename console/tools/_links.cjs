const Lib = require('./lib.cjs');
(async () => {
  const b = await Lib.chromium.launch(); const ctx = await Lib.context(b, 390); const p = await ctx.newPage();
  await Lib.open(p, process.argv[2], 'ar', 'light');
  for (const s of process.argv.slice(3)) { await p.locator(s + ' >> visible=true').first().click({ timeout: 4000 }).catch(() => console.log('CLICK FAIL', s)); await p.waitForTimeout(400); }
  console.log((await p.evaluate(() => [...document.querySelectorAll('#main a[href*="/activity/run/"]')].map(a => a.getAttribute('href') + (a.checkVisibility() ? '' : ' (hidden)')).join('\n'))));
  console.log(await p.evaluate(() => JSON.stringify({ last: EAOS.ac.lastCheck() && EAOS.ac.lastCheck().id, await: (EAOS.store.awaiting()[0] || {}).id })));
  await b.close();
})();
