// EAOS's browser agent: one browser kept open and driven a step at a time (eaos/live/agent.py), the one browser layer an
// explorer with a goal and a replay without AI both use (M5.2; M10's simulated users reuse it).
//
// Run as a separate process:  node agent.mjs <config.json>   (config: modules.playwright, base, out, storage_state?)
// Reads one JSON command per line on stdin, answers one JSON line on stdout:
//   {op: 'open', path} | {op: 'click', target} | {op: 'fill', target, value} | {op: 'press', key} | {op: 'back'} | {op: 'look'}
// Every answer is the page after the step: {ok, error?, path, title, text, controls: [{role, name, nth}], picture}.
// A target is {role, name, nth}: the n-th control of that role and name, found again the same way on a replay.
// Requests to any other origin are aborted; a control whose name deletes, pays, sends or signs out is never pressed.
import { createInterface } from 'node:readline';
import { configured } from './pinned.mjs';

const { config, playwright } = configured();
const base = new URL(config.base);
const UNSAFE = /delete|remove|clear|reset|pay|buy|purchase|send|log ?out|sign ?out|unsubscribe|حذف|امسح|مسح|ادفع|دفع|شراء|أرسل|ارسل|إرسال|خروج/i;
const CONTROLS = 'a[href], button, [role=button], [role=link], [role=tab], [role=menuitem], [role=checkbox], [role=switch], input:not([type=hidden]), select, textarea, summary';

// The page's address as the crawl names it (crawl.mjs pathOf): its path and query, or its hash route.
function pathOf(href) {
  const url = new URL(href, base);
  if (url.origin !== base.origin) return href;
  return url.hash.startsWith('#/') ? base.pathname + url.hash : (url.pathname || '/') + url.search;
}

const browser = await playwright.chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block',
  storageState: config.storage_state || undefined });
await context.route('**/*', (route) => {
  const target = new URL(route.request().url());
  return ['data:', 'blob:'].includes(target.protocol) || target.origin === base.origin ? route.continue() : route.abort('blockedbyclient');
});
const page = await context.newPage();
let step = 0;

async function settle() {
  try { await page.waitForLoadState('load', { timeout: 15000 }); } catch {}
  try { await page.waitForLoadState('networkidle', { timeout: 4000 }); } catch {}
  await page.waitForTimeout(300);
}

// The visible controls a person could use, each named by its role, its name and its place among those alike.
async function controls() {
  const found = await page.locator(CONTROLS).evaluateAll((elements) => elements.filter((e) => {
    const box = e.getBoundingClientRect();
    return box.width > 0 && box.height > 0 && getComputedStyle(e).visibility !== 'hidden';
  }).map((e) => {
    const tag = e.tagName.toLowerCase(), type = (e.getAttribute('type') || '').toLowerCase();
    const role = e.getAttribute('role') || (tag === 'a' ? 'link' : tag === 'select' ? 'combobox' : tag === 'summary' ? 'button'
      : ['textarea'].includes(tag) || (tag === 'input' && !['submit', 'button', 'checkbox', 'radio'].includes(type)) ? 'textbox'
      : tag === 'input' && ['checkbox', 'radio'].includes(type) ? type : 'button');
    const name = (e.getAttribute('aria-label') || (role === 'textbox' ? '' : e.innerText) || e.getAttribute('placeholder')
      || e.getAttribute('title') || e.value || e.getAttribute('name') || '').trim().replace(/\s+/g, ' ').slice(0, 80);
    return { role, name };
  }));
  const seen = {};
  return found.filter((c) => c.name).map((c) => ({ ...c, nth: (seen[c.role + c.name] = (seen[c.role + c.name] ?? -1) + 1) })).slice(0, 120);
}

function locate(target) {
  const byRole = page.getByRole(target.role, { name: target.name, exact: true });
  return byRole.nth(target.nth || 0);
}

async function look(extra = {}) {
  await settle();
  step += 1;
  const picture = `${config.out}/step-${String(step).padStart(2, '0')}.jpg`;
  await page.screenshot({ path: picture, type: 'jpeg', quality: 60 }).catch(() => {});
  return { ok: true, ...extra, path: pathOf(page.url()), title: await page.title().catch(() => ''),
    text: (await page.locator('body').innerText().catch(() => '')).slice(0, 3000), controls: await controls().catch(() => []), picture };
}

async function act(command) {
  if (command.op === 'open') await page.goto(new URL(command.path || '/', base).href, { waitUntil: 'load', timeout: 60000 });
  else if (command.op === 'back') await page.goBack({ waitUntil: 'load' });
  else if (command.op === 'press') await page.keyboard.press(command.key || 'Enter');
  else if (command.op === 'look') {}
  else {
    const target = command.target || {};
    if (command.op === 'click' && UNSAFE.test(target.name || '')) return { ok: false, error: `refused: "${target.name}" could change or remove something` };
    let control = locate(target);
    if (!(await control.count())) control = page.getByText(target.name || '', { exact: true }).nth(target.nth || 0);
    if (!(await control.count())) return { ok: false, error: `no ${target.role} named "${target.name}" on this page` };
    if (command.op === 'fill') await control.fill(String(command.value ?? ''), { timeout: 5000 });
    else await control.click({ timeout: 5000 });
  }
  return { ok: true };
}

const lines = createInterface({ input: process.stdin });
for await (const line of lines) {
  if (!line.trim()) continue;
  let answer;
  try {
    const command = JSON.parse(line);
    if (command.op === 'close') break;
    const done = await act(command);
    answer = await look(done.ok ? {} : done);
  } catch (error) {
    answer = await look({ ok: false, error: String(error.message || error).split('\n')[0].slice(0, 300) }).catch(() => ({ ok: false, error: String(error) }));
  }
  process.stdout.write(JSON.stringify(answer) + '\n');
}
await browser.close();
process.exit(0);
