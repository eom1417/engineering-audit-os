/* Touch targets at 390 px: every visible control outside running text must be at least 44 x 44 (its own box or its
   hit area); and the floating assistant button never covers a primary action, a bar or the live strip (390 and 1440,
   at the top and the bottom of every screen). Usage: node console/tools/targets.cjs [ar|en] [--routes=/a,/b] */
const L = require('./lib.cjs');

const lang = process.argv.find(a => a === 'ar' || a === 'en') || 'ar';
const given = (process.argv.find(a => a.startsWith('--routes=')) || '').slice(9).split(',').filter(Boolean);

async function fabOverlaps(p) {
  return p.evaluate(() => {
    const f = document.getElementById('fab'); if (!f || !f.checkVisibility()) return [];
    const a = f.getBoundingClientRect();
    const hit = b => !(b.right <= a.left || b.left >= a.right || b.bottom <= a.top || b.top >= a.bottom);
    return [...document.querySelectorAll('.btn--primary, .tabbar, .live-strip, .selbar, .side-live, .toast')]
      .filter(e => e.checkVisibility && e.checkVisibility() && !e.closest('.sheet') && hit(e.getBoundingClientRect()))
      .map(e => (e.innerText || e.className).replace(/\s+/g, ' ').trim().slice(0, 30));
  });
}

function small() {
  const scope = document.querySelector('.sheet.is-open') || document;
  const els = [...scope.querySelectorAll('a[href], button, summary, input, select, textarea, [role=button], label.check, label.opt')];
  return els.filter(e => e.checkVisibility && e.checkVisibility() && !e.closest('details:not([open]) > :not(summary)')).map(e => {
    if (e.matches('input[type=checkbox], input[type=radio]') && e.closest('label.check, label.opt, .switch, .ack')) return null; // the label is the target
    if (e.closest('.sheet:not(.is-open)')) return null;
    const r = e.getBoundingClientRect(); if (!r.width || !r.height) return null;
    const after = getComputedStyle(e, '::after'); let hw = r.width, hh = r.height;
    if (after && after.content !== 'none' && after.position === 'absolute') {
      const it = parseFloat(after.top) || 0, ib = parseFloat(after.bottom) || 0, il = parseFloat(after.left) || 0, ir = parseFloat(after.right) || 0;
      hh = Math.max(hh, r.height - it - ib); hw = Math.max(hw, r.width - il - ir);
    }
    const cs = getComputedStyle(e);
    const inline = (e.tagName === 'A' || e.matches('button.link')) && cs.display === 'inline' && !!e.closest('p, .lede, .guide, li > span, dd, td, .small, .row__meta');
    if (inline || e.matches('.skip') || (hw >= 43.5 && hh >= 43.5)) return null;
    if (e.closest('svg')) { const sh = e.querySelector('circle, rect'); if (sh && getComputedStyle(sh).strokeWidth === '22px') return null; return hw >= 24 && hh >= 24 ? null : { t: 'svg node', w: Math.round(hw), h: Math.round(hh), c: '' }; }
    return { t: (e.getAttribute('aria-label') || e.innerText || e.value || '').replace(/\s+/g, ' ').trim().slice(0, 36), w: Math.round(hw), h: Math.round(hh), c: String(e.className).slice(0, 40) };
  }).filter(Boolean);
}

(async () => {
  const b = await L.chromium.launch();
  const ctx = await L.context(b, 390, 'light');
  const p = await ctx.newPage();
  const routes = given.length ? given : await L.routes(p);
  const all = {}; let total = 0; const overlaps = [];
  for (const r of routes) {
    await p.setViewportSize({ width: 390, height: 844 });
    await L.open(p, r, lang);
    const found = await p.evaluate(small);
    if (found.length) { all[r] = found; total += found.length; }
    if (r.includes('sheet=')) continue;
    for (const w of [390, 1440]) {
      await p.setViewportSize({ width: w, height: w === 390 ? 844 : 900 }); await p.waitForTimeout(80);
      for (const pos of ['top', 'bottom']) {
        await p.evaluate(x => window.scrollTo(0, x === 'top' ? 0 : document.documentElement.scrollHeight), pos); await p.waitForTimeout(60);
        const o = await fabOverlaps(p);
        if (o.length) overlaps.push(`${w} ${r} (${pos}): ${o.join(' | ')}`);
      }
    }
  }
  await b.close();
  const byClass = {};
  for (const [r, list] of Object.entries(all)) for (const x of list) (byClass[x.c || '(none)'] = byClass[x.c || '(none)'] || []).push(`${r} "${x.t}" ${x.w}x${x.h}`);
  console.log(`floating assistant button overlapping a primary action, a bar or the live strip: ${overlaps.length}`);
  overlaps.slice(0, 20).forEach(x => console.log('  ' + x));
  console.log(`controls under 44 px: ${total} on ${Object.keys(all).length} screens`);
  for (const [k, v] of Object.entries(byClass).sort((a, c) => c[1].length - a[1].length)) console.log(`\n## ${k} (${v.length})\n  ` + v.slice(0, 4).join('\n  '));
  process.exitCode = total || overlaps.length ? 1 : 0;
})();
