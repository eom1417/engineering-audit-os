// The browser half of tools/docs_reader_trial.py: opens each document of the config in the shipped Studio (from a
// file), waits until no diagram is drawing, and prints what the reader drew as one line of JSON.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const config = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const { chromium } = createRequire(join(config.modules, 'eaos-resolve.js'))('playwright');

const browser = await chromium.launch();
const documents = [];
for (const doc of config.docs) {
  const row = { path: doc.path, blocks: doc.blocks };
  for (const width of [1440, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.goto(`file://${config.folder}/index.html?lang=ar&theme=light#/library/docs/${encodeURIComponent(doc.path)}`);
    await page.waitForSelector('article', { timeout: 30000 });
    await page.waitForFunction(() => document.querySelectorAll('figure[data-kind]').length > 0
      && !document.querySelector('figure[data-state="loading"]'), null, { timeout: 120000 }).catch(() => undefined);
    const seen = await page.evaluate(() => {
      const figures = [...document.querySelectorAll('article figure[data-kind]')];
      const drawn = figures.filter((f) => {
        const svg = f.querySelector('[data-ready] svg');
        const box = svg && svg.getBoundingClientRect();
        return f.dataset.state === 'drawn' && box && box.width > 0 && box.height > 0;
      });
      return { diagrams: figures.length, drawn: drawn.length, failed: figures.filter((f) => f.dataset.state === 'failed').length,
        tables: document.querySelectorAll('article table').length, overflow: document.documentElement.scrollWidth - window.innerWidth };
    });
    if (width === 1440) Object.assign(row, { diagrams: seen.diagrams, drawn: seen.drawn, failed: seen.failed, tables: seen.tables, errors });
    else row.overflow_390 = seen.overflow;
    await page.close();
  }
  documents.push(row);
}
await browser.close();
console.log(JSON.stringify({ documents }));
