/* Headless pass over screens and sheets of the served console: 390 and 1440, Arabic and English, light and dark.
   Reports console errors and warnings (a missing word warns), page errors, horizontal overflow of the page or of any
   element not inside its own scrolling box, a missing h1, raw dictionary keys and "undefined" / "NaN" text.
   Routes: the lead's on the real report (lib.cjs routes), or those given after --routes= (comma separated).
   Usage: node console/tools/sweep.cjs [--only=390-ar-light,1440-en-dark] [--routes=/a,/b] [filter] */
const L = require('./lib.cjs');

const args = process.argv.slice(2);
const only = (args.find(a => a.startsWith('--only=')) || '').slice(7).split(',').filter(Boolean);
const given = (args.find(a => a.startsWith('--routes=')) || '').slice(9).split(',').filter(Boolean);
const filter = args.find(a => !a.startsWith('--'));

function audit(vw) {
  const out = [];
  const doc = document.documentElement;
  if (doc.scrollWidth > vw + 1) out.push(`page scrollWidth ${doc.scrollWidth}`);
  const scrollers = el => { for (let a = el.parentElement; a; a = a.parentElement) { const ox = getComputedStyle(a).overflowX; if (ox !== 'visible') { const b = a.getBoundingClientRect(); if (b.left >= -1 && b.right <= vw + 1) return true; } } return false; };
  const seen = new Set();
  document.querySelectorAll('body *').forEach(el => {
    const b = el.getBoundingClientRect();
    if (!b.width || !b.height) return;
    if ((b.right > vw + 1 || b.left < -1) && getComputedStyle(el).position !== 'fixed' && !scrollers(el)) {
      if (el.closest('.sheet') && !el.closest('.sheet').classList.contains('is-open')) return;
      let top = el; while (top.parentElement && (() => { const p = top.parentElement.getBoundingClientRect(); return p.right > vw + 1 || p.left < -1; })() && !scrollers(top.parentElement)) top = top.parentElement;
      const id = top.tagName + '.' + String(top.className).slice(0, 50);
      if (!seen.has(id)) { seen.add(id); out.push(`overflow ${id} L${Math.round(b.left)} R${Math.round(b.right)}`); }
    }
  });
  if (!document.querySelector('#main h1')) out.push('no h1');
  const text = document.body.innerText;
  const raw = text.match(/(?<![\w/.-])(?:ac|un|pb|st|wt|pd|pv|cf|nav|proj|todo|as|live|stale)\.[a-z][\w.-]+/g);
  if (raw) out.push('raw keys: ' + [...new Set(raw)].slice(0, 5).join(' '));
  if (/\bundefined\b|\bNaN\b|\[object /.test(text)) out.push('undefined/NaN text: ' + (text.match(/.{0,30}(undefined|NaN|\[object).{0,20}/) || [''])[0].replace(/\n/g, ' '));
  if (location.hash.includes('sheet=') && !document.querySelector('.sheet.is-open')) out.push('sheet did not open');
  return out.slice(0, 6);
}

(async () => {
  const browser = await L.chromium.launch();
  const issues = [];
  let pages = 0, routes = given;
  for (const c of L.COMBOS) {
    if (only.length && !only.includes(c.key)) continue;
    const ctx = await L.context(browser, c.w, c.theme);
    const page = await ctx.newPage();
    if (!routes.length) routes = await L.routes(page);
    let current = '';
    page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') issues.push(`${c.key} ${current} console: ${m.text()}`); });
    page.on('pageerror', e => issues.push(`${c.key} ${current} PAGEERROR ${e.message}`));
    for (const r of routes) {
      if (filter && !r.includes(filter)) continue;
      current = r;
      await L.open(page, r, c.lang, c.theme);
      pages++;
      (await page.evaluate(audit, c.w)).forEach(x => issues.push(`${c.key} ${r} ${x}`));
    }
    await ctx.close();
  }
  await browser.close();
  const uniq = [...new Set(issues)];
  console.log(`pages visited: ${pages}; issues: ${uniq.length}`);
  console.log(uniq.join('\n'));
  process.exitCode = uniq.length ? 1 : 0;
})();
