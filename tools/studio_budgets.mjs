// The Studio's filter budget in a real browser: the shipped Problems page on 5,000 cards, each step a person takes
// (typing a search, ticking a facet, grouping, clearing) timed from the input event to the first frame painted after
// the list changed. Run by tools/studio_budgets.py:  node studio_budgets.mjs <config.json>; prints one JSON object.
//
// config: {url, modules: {playwright}, profiles: [{name, width, height, mobile, cpu}], rounds}
// `cpu` is Chromium's CPU slowdown (DevTools' throttling): 4 stands for a mid phone.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const config = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const require = createRequire(join(config.modules.playwright, 'eaos-resolve.js'));
const playwright = (() => { try { return require('playwright'); } catch { return require('@playwright/test'); } })();

// Each step changes what the list shows; a step is [what it does, how] and runs inside the page.
const STEPS = [
  ['search Arabic words', { type: 'يُصعِّب اختبارها' }],
  ['search a component', { type: 'fuel' }],
  ['clear the search', { type: '' }],
  ['tick a severity', { toggle: 'severity' }],
  ['group by plan step', { group: 'step' }],
  ['tick a state', { toggle: 'state' }],
  ['clear the filters', { clear: true }],
  ['group by area', { group: 'area' }],
  ['no grouping', { group: null }],
];

/** Runs inside the page: performs one step and resolves with the ms from the event to the frame after the change. */
async function step(how) {
  const changed = () => new Promise((resolve) => {
    const list = document.querySelector('main');
    const seen = new MutationObserver(() => { seen.disconnect(); requestAnimationFrame(() => requestAnimationFrame(resolve)); });
    seen.observe(list, { childList: true, subtree: true, characterData: true, attributes: true });
  });
  const press = (el) => el.click();   // a virtual press, as React Aria handles a click with no pointer
  let act;
  if ('type' in how) {
    const input = document.querySelector('main input[type=search], main input');
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    act = () => { setter.call(input, how.type); input.dispatchEvent(new Event('input', { bubbles: true })); };
  } else if ('toggle' in how) {
    const value = document.querySelector(`[role=dialog] [role=group][aria-labelledby="facet-${how.toggle}"] button[aria-pressed="false"]`);
    act = () => press(value);
  } else if ('group' in how) {
    const buttons = [...document.querySelectorAll('[role=dialog] [role=group][aria-labelledby="facet-group"] button')];
    const target = buttons[how.group === null ? 0 : { area: 1, component: 2, step: 3 }[how.group]];
    act = () => press(target);
  } else {
    act = () => press([...document.querySelectorAll('[role=dialog] button')].at(-1));
  }
  const done = changed();
  const started = performance.now();
  act();
  await done;
  return performance.now() - started;
}

const median = (values) => { const s = [...values].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };

const browser = await playwright.chromium.launch();
const out = { profiles: [] };
try {
  for (const profile of config.profiles) {
    const context = await browser.newContext({ viewport: { width: profile.width, height: profile.height }, isMobile: profile.mobile, hasTouch: profile.mobile, deviceScaleFactor: 1 });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (error) => errors.push(String(error)));
    await page.goto(config.url);
    await page.waitForSelector('main [role=region] li');
    const cards = await page.evaluate(() => (window.EAOS_STUDIO?.cards?.cards ?? []).length);
    if (profile.cpu > 1) {
      const cdp = await context.newCDPSession(page);
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: profile.cpu });
    }
    const times = Object.fromEntries(STEPS.map(([name]) => [name, []]));
    for (let round = 0; round < config.rounds; round += 1) {
      for (const [name, how] of STEPS) {
        if (!('type' in how) && !(await page.$('[role=dialog]'))) {
          await page.click('[data-open="filters"]');
          await page.waitForSelector('[role=dialog]');
          await page.waitForTimeout(400);
        }
        if ('type' in how && (await page.$('[role=dialog]'))) {
          await page.keyboard.press('Escape');
          await page.waitForSelector('[role=dialog]', { state: 'detached' });
        }
        times[name].push(await page.evaluate(step, how));
        await page.waitForTimeout(120);
      }
    }
    const steps = Object.entries(times).map(([name, values]) => ({ name, median_ms: Math.round(median(values) * 10) / 10, max_ms: Math.round(Math.max(...values) * 10) / 10, runs: values.length }));
    out.profiles.push({ ...profile, cards, steps, worst_median_ms: Math.max(...steps.map((s) => s.median_ms)), errors });
    await context.close();
  }
} finally {
  await browser.close();
}
out.version = playwright.chromium.name();
console.log(JSON.stringify(out));
