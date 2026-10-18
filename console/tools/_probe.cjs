const Lib = require('./lib.cjs');
(async () => {
  const b = await Lib.chromium.launch(); const ctx = await Lib.context(b, 390); const p = await ctx.newPage();
  const errs = []; p.on('console', m => m.type() === 'error' && errs.push(m.text())); p.on('pageerror', e => errs.push(String(e)));
  const t = Date.now(); await Lib.open(p, process.argv[2], 'ar', 'light'); console.log('open ms', Date.now() - t);
  console.log(await p.evaluate(() => (document.querySelector('#main') || document.body).innerText.slice(0, 600)));
  console.log((await p.evaluate(() => [...document.querySelectorAll('#main [data-sheet], #main a[href*="replay"]')].map(a => a.getAttribute('href') || 'sheet:' + a.dataset.sheet).slice(0, 30).join(' | '))));
  console.log('ERR', errs.slice(0, 5)); await p.screenshot({ path: '/tmp/probe.png' }); await b.close();
})();
