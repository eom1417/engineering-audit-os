/* axe-core (WCAG 2.0/2.1/2.2 A and AA) over screens and sheets of the served console: 390 and 1440, Arabic and
   English, light and dark. Usage: node console/tools/axe.cjs [--routes=/a,/b] */
const fs = require('fs');
const L = require('./lib.cjs');

const AXE = fs.readFileSync(L.AXE, 'utf8');
const given = (process.argv.find(a => a.startsWith('--routes=')) || '').slice(9).split(',').filter(Boolean);

(async () => {
  const b = await L.chromium.launch();
  const out = {};
  let pages = 0, routes = given;
  for (const c of L.COMBOS) {
    const ctx = await L.context(b, c.w, c.theme);
    const p = await ctx.newPage();
    if (!routes.length) routes = await L.routes(p);
    for (const r of routes) {
      await L.open(p, r, c.lang, c.theme);
      if (r.includes('sheet=search')) { await p.fill('#search-input', 'toolchain'); await p.waitForTimeout(200); }
      await p.addScriptTag({ content: AXE });
      const res = await p.evaluate(async () => {
        const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] } });
        return r.violations.map(v => ({ id: v.id, n: v.nodes.length, ex: v.nodes.slice(0, 2).map(n => n.target.join(' ')) }));
      });
      pages++;
      for (const v of res) (out[v.id] = out[v.id] || []).push(`${c.key} ${r} n=${v.n} ${v.ex.join(' | ')}`);
    }
    await ctx.close();
  }
  await b.close();
  console.log(`axe: ${pages} screen-combos; rules failing: ${Object.keys(out).length}`);
  for (const [k, v] of Object.entries(out)) { console.log(`\n### ${k}: ${v.length}`); console.log(v.slice(0, 5).join('\n')); }
  process.exitCode = Object.keys(out).length ? 1 : 0;
})();
