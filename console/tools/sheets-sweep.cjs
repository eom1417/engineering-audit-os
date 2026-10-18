/* Opens every sheet the given screens offer (every data-sheet value on them) and checks it: no console error, the
   sheet opens, nothing overflows the viewport, words are complete.
   Usage: node console/tools/sheets-sweep.cjs [--only=390-ar-light,1440-en-dark] [--routes=/a,/b] */
const L = require('./lib.cjs');

const args = process.argv.slice(2);
const only = ((args.find(a => a.startsWith('--only=')) || '').slice(7) || '390-ar-light,1440-en-dark').split(',');
const given = (args.find(a => a.startsWith('--routes=')) || '').slice(9).split(',').filter(Boolean);

(async () => {
  const browser = await L.chromium.launch();
  const issues = [];
  let opened = 0;
  for (const key of only) {
    const [w, lang, theme] = key.split('-');
    const ctx = await L.context(browser, +w, theme);
    const page = await ctx.newPage();
    const routes = (given.length ? given : await L.routes(page)).filter(r => !r.includes('sheet='));
    let cur = '';
    page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') issues.push(`${key} ${cur} console: ${m.text()}`); });
    page.on('pageerror', e => issues.push(`${key} ${cur} PAGEERROR ${e.message}`));
    const done = new Set();
    for (const r of routes) {
      await L.open(page, r, lang, theme);
      const names = await page.evaluate(() => [...new Set([...document.querySelectorAll('[data-act="sheet"]')].map(e => e.dataset.sheet))]);
      for (const n of names) {
        const id = r.split('?')[0] + '|' + n;
        if (done.has(id)) continue;
        done.add(id);
        cur = `${r} sheet=${n}`;
        await L.open(page, `${r}${r.includes('?') ? '&' : '?'}sheet=${encodeURIComponent(n)}`, lang, theme);
        opened++;
        const res = await page.evaluate(vw => {
          const out = []; const sh = document.querySelector('.sheet.is-open');
          if (!sh) return ['sheet did not open'];
          const scrollers = el => { for (let a = el.parentElement; a && a !== sh; a = a.parentElement) { if (getComputedStyle(a).overflowX !== 'visible') return true; } return false; };
          const sb = sh.getBoundingClientRect();
          sh.querySelectorAll('*').forEach(el => { const b = el.getBoundingClientRect(); if (b.width && (b.right > Math.min(vw, sb.right) + 1 || b.left < Math.max(0, sb.left) - 1) && !scrollers(el)) out.push('overflow ' + el.tagName + '.' + String(el.className).slice(0, 40)); });
          const text = sh.innerText;
          const raw = text.match(/(?<![\w/.-])(?:ac|un|pb|st|wt|pd|pv|cf|nav|proj|as|live)\.[a-z][\w.-]+/g); if (raw) out.push('raw keys ' + raw.slice(0, 3).join(' '));
          if (/\bundefined\b|\bNaN\b|\[object /.test(text)) out.push('undefined/NaN text');
          const title = sh.querySelector('.sheet__title') ? sh.querySelector('.sheet__title').textContent : '';
          if (/not in this check|ليست في هذا الفحص/.test(title)) out.push('sheet says not found');
          return [...new Set(out)].slice(0, 4);
        }, +w);
        res.forEach(x => issues.push(`${key} ${cur} ${x}`));
      }
    }
    await ctx.close();
  }
  await browser.close();
  const uniq = [...new Set(issues)];
  console.log(`sheets opened: ${opened}; issues: ${uniq.length}`);
  console.log(uniq.join('\n'));
  process.exitCode = uniq.length ? 1 : 0;
})();
