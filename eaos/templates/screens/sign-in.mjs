// EAOS sign-in: the person signs in to their app by hand, by any way it has (a password, a code, a link, two factors,
// an outside sign-in page), in the pinned Chromium, driven from the sign-in page (eaos/api/sign_in.py) or, headed, by
// the person themselves.
//
// Run as a separate process:  node sign-in.mjs <config.json>     config: {modules: {playwright}, base, state, headed}
// One JSON command a line on stdin, one JSON answer a line on stdout:
//   {do: 'look' | 'click' (x, y) | 'type' (text) | 'key' (key) | 'scroll' (dy) | 'back'}   -> {url, title, picture}
//   {do: 'done'}    the browser's storage state saved to config.state (its owner only), the browser closed -> {saved}
//   {do: 'close'}   the browser closed, nothing saved -> {closed}
// The picture is a JPEG of the page as it is now (none when headed). Nothing typed is written anywhere.
import { createRequire } from 'node:module';
import { chmodSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createInterface } from 'node:readline';

const config = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const playwright = (() => {
  const require = createRequire(join(config.modules.playwright, 'eaos-resolve.js'));
  try { return require('playwright'); } catch { return require('@playwright/test'); }
})();
const say = (answer) => process.stdout.write(JSON.stringify(answer) + '\n');

const browser = await playwright.chromium.launch({ headless: !config.headed });
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
let page = await context.newPage();
// An outside sign-in (a company's, Google's) may open its own window: the person drives the newest one.
context.on('page', (opened) => { page = opened; opened.on('close', () => { page = context.pages().at(-1) ?? page; }); });
try { await page.goto(config.base, { waitUntil: 'load', timeout: 60000 }); } catch {}

const look = async () => ({ url: page.url(), title: await page.title().catch(() => ''),
  picture: config.headed ? null : (await page.screenshot({ type: 'jpeg', quality: 70 }).catch(() => Buffer.alloc(0))).toString('base64') });

const act = {
  click: (c) => page.mouse.click(Number(c.x), Number(c.y)),
  type: (c) => page.keyboard.type(String(c.text ?? '')),
  key: (c) => page.keyboard.press(String(c.key)),
  scroll: (c) => page.mouse.wheel(0, Number(c.dy) || 0),
  back: () => page.goBack({ timeout: 10000 }),
  look: () => null,
};

for await (const line of createInterface({ input: process.stdin })) {
  const command = JSON.parse(line);
  if (command.do === 'done') {
    await context.storageState({ path: config.state });
    chmodSync(config.state, 0o600);
    await browser.close();
    say({ saved: true });
    process.exit(0);
  }
  if (command.do === 'close') break;
  try {
    await act[command.do]?.(command);
    await page.waitForLoadState('load', { timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(250);
  } catch {}
  say(await look());
}
await browser.close();          // closed, or the page that drove it went away: nothing is saved
say({ closed: true });
