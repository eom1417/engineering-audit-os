// Lighthouse in the same signed-in browser state as the crawl and screenshots, never on the sign-in page instead.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createServer } from 'node:net';
import { fromFolder, playwrightFrom } from './pinned.mjs';

const config = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const { chromium } = playwrightFrom(config.modules.playwright);
const resolve = fromFolder(config.modules.lighthouse);
const { default: lighthouse } = await import(pathToFileURL(resolve.resolve('lighthouse')).href);
const state = JSON.parse(readFileSync(config.storage_state, 'utf8'));
const listener = createServer();
await new Promise((ok, fail) => { listener.once('error', fail); listener.listen(0, '127.0.0.1', ok); });
const port = listener.address().port;
await new Promise((ok) => listener.close(ok));
const context = await chromium.launchPersistentContext(join(config.folder, 'profile'), {
  headless: true, args: [`--remote-debugging-port=${port}`], serviceWorkers: 'block',
});
try {
  const origin = new URL(config.url).origin;
  await context.route('**/*', (route) => {
    const url = new URL(route.request().url());
    return url.origin === origin || ['data:', 'blob:', 'about:'].includes(url.protocol)
      ? route.continue() : route.abort('blockedbyclient');
  });
  await context.addCookies(state.cookies || []);
  await context.addInitScript((origins) => {
    for (const item of origins) {
      if (item.origin === location.origin) {
        for (const { name, value } of item.localStorage || []) localStorage.setItem(name, value);
      }
    }
  }, state.origins || []);
  const result = await lighthouse(config.url, { port, logLevel: 'silent', disableStorageReset: true,
    onlyCategories: config.categories, formFactor: 'mobile' });
  mkdirSync(dirname(config.out), { recursive: true });
  writeFileSync(config.out, JSON.stringify(result.lhr));
  process.stdout.write(JSON.stringify(result.lhr));
} finally {
  await context.close();
}
