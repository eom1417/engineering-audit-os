// EAOS writes: what a running app sends when its pages save (M14.2), through the pinned Playwright.
//
// Run by eaos/live/keeping/writes.py as a separate process:  node writes.mjs <config.json>
// Each page of config.pages is opened (signed in with config.storage_state when given) and left to settle; every
// request it sends that is not a GET, to the app's own origin, is recorded: its method, address, the bytes of its body,
// whether it was compressed, how long the answer took, and the ids of the records its body carries; every JSON answer
// to a GET, the ids of the records it carries. Nothing is pressed: what a page sends on its own (an autosave, a sync).
// Requests to any other origin are aborted. The result is one JSON object on stdout: {pages: [{path, writes, reads}]}.
import { configured } from './pinned.mjs';

const { config, playwright } = configured();
const base = new URL(config.base);
const ID_KEYS = ['id', 'uuid', '_id', 'key'];

// The ids of the records a JSON value carries: every array of objects in it, each object by its id (else its whole text).
function ids(value, found = new Set(), depth = 0) {
  if (depth > 6 || value === null || typeof value !== 'object') return found;
  if (Array.isArray(value)) {
    for (const item of value) {
      if (item && typeof item === 'object' && !Array.isArray(item)) {
        const key = ID_KEYS.find((k) => k in item);
        found.add(key ? `${key}:${item[key]}` : JSON.stringify(item).slice(0, 200));
      }
      ids(item, found, depth + 1);
    }
  } else for (const inner of Object.values(value)) ids(inner, found, depth + 1);
  return found;
}

const parsed = (text) => { try { return JSON.parse(text); } catch { return null; } };

const browser = await playwright.chromium.launch({ headless: true, args: config.chromium_args || [] });
const pages = [];
try {
  const context = await browser.newContext({ storageState: config.storage_state || undefined, serviceWorkers: 'block' });
  await context.route('**/*', (route) => (new URL(route.request().url()).origin === base.origin ? route.continue() : route.abort('blockedbyclient')));
  for (const path of config.pages) {
    const page = await context.newPage();
    const writes = [], reads = [], started = new Map();
    page.on('request', (request) => {
      started.set(request, Date.now());
      if (request.method() === 'GET' || new URL(request.url()).origin !== base.origin) return;
      const body = request.postDataBuffer();
      writes.push({ method: request.method(), path: new URL(request.url()).pathname, bytes: body ? body.length : 0,
        encoding: request.headers()['content-encoding'] || null, ids: [...ids(parsed(body ? body.toString('utf8') : ''))].slice(0, 5000),
        request });
    });
    page.on('response', async (response) => {
      const request = response.request();
      const write = writes.find((w) => w.request === request);
      if (write) { write.status = response.status(); write.ms = Date.now() - (started.get(request) || Date.now()); return; }
      if (request.method() !== 'GET' || !/json/i.test(response.headers()['content-type'] || '')) return;
      try { reads.push({ path: new URL(request.url()).pathname, ids: [...ids(await response.json())].slice(0, 5000) }); } catch {}
    });
    try {
      await page.goto(new URL(path, base).href, { waitUntil: 'load', timeout: config.timeout_ms || 30000 });
      try { await page.waitForLoadState('networkidle', { timeout: 8000 }); } catch {}
      await page.waitForTimeout(config.settle_ms || 2000);
    } catch {}
    await page.close();
    pages.push({ path, writes: writes.map(({ request, ...w }) => w), reads });
  }
} finally {
  await browser.close();
}
process.stdout.write(JSON.stringify({ pages }) + '\n');
