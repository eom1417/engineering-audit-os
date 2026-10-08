// EAOS screen audit: one rendered page per viewport and variant, through the pinned Playwright and axe.
//
// Run by eaos/screens/audit.py as a separate process:  node audit.mjs <config.json>
// The config names the module folders (EAOS installs each tool in its own prefix; ES modules ignore NODE_PATH),
// the URL, the viewports, the variants and where screenshots go. The result is one JSON object on stdout.
// Requests to any origin other than the tested URL's are aborted and counted, so a gate run reaches
// nothing but the page under test.
//
// A URL is a string or a page: {url, name, actions, viewports, variants, wait_for}. `actions` run after the page
// settles and before it is measured, to check a state a person reaches (an open dialog, a typed search):
// {press: 'Control+k'}, {type: 'text'}, {click: 'css selector'} (its first visible match), {wait: ms}.
// `viewports` and `variants` name the subset the page is audited in; `wait_for` is a selector to wait for
// (config.wait_for for every page).
import { createRequire } from 'node:module';
import { readFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

const config = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const fromFolder = (folder) => createRequire(join(folder, 'eaos-resolve.js'));
const playwright = (() => {
  const require = fromFolder(config.modules.playwright);
  try { return require('playwright'); } catch { return require('@playwright/test'); }
})();
const { AxeBuilder } = fromFolder(config.modules.axe)('@axe-core/playwright');

const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa'];

function withQuery(url, query) {
  if (!query || !Object.keys(query).length) return url;
  const parsed = new URL(url);
  for (const [key, value] of Object.entries(query)) parsed.searchParams.set(key, value);
  return parsed.toString();
}

function allowed(request, base) {
  const target = new URL(request.url());
  if (['data:', 'blob:', 'about:'].includes(target.protocol)) return true;
  if (base.protocol === 'file:') return target.protocol === 'file:';
  return target.origin === base.origin;
}

// Runs inside the page: layout facts the gate judges. Kept self-contained (it is serialised into the page).
function measure({ phoneWidth, targetMin, viewportWidth }) {
  // Judge against the configured width: under mobile emulation a page wider than the screen silently widens
  // the layout viewport (innerWidth), which would hide its own overflow. The layout width is reported apart.
  const width = Math.min(window.innerWidth, viewportWidth);
  const selector = (el) => {
    const parts = [];
    for (let node = el; node && node.nodeType === 1 && parts.length < 4; node = node.parentElement) {
      if (node.id) { parts.unshift(`${node.tagName.toLowerCase()}#${node.id}`); break; }
      let part = node.tagName.toLowerCase();
      const classes = [...node.classList].slice(0, 2);
      if (classes.length) part += '.' + classes.join('.');
      const parent = node.parentElement;
      if (parent) {
        const same = [...parent.children].filter((c) => c.tagName === node.tagName);
        if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      if (node === document.body) break;
    }
    return parts.join(' > ');
  };
  const visible = (el) => {
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 1 && rect.height > 1;
  };
  // An element whose box is clipped by an ancestor (overflow other than visible) cannot widen the page;
  // the ancestor is measured instead. Elements inside a container marked data-scroll-x scroll on purpose.
  const clippedOrExempt = (el) => {
    if (el.closest('[data-scroll-x]')) return true;
    const style = getComputedStyle(el);
    if (style.position === 'fixed' && style.clip !== 'auto') return true;
    if (style.clipPath && style.clipPath !== 'none') return true;
    for (let node = el.parentElement; node && node !== document.body && node !== document.documentElement; node = node.parentElement) {
      const parent = getComputedStyle(node);
      if (parent.overflowX !== 'visible' || parent.overflow === 'hidden') return true;
    }
    return false;
  };
  const offenders = [];
  for (const el of document.body ? document.body.querySelectorAll('*') : []) {
    if (!visible(el) || clippedOrExempt(el)) continue;
    const rect = el.getBoundingClientRect();
    const left = rect.left + window.scrollX, right = rect.right + window.scrollX;
    if (right > width + 1 || left < -1) {
      if (offenders.some((o) => o.el.contains(el))) continue;
      offenders.push({ el, selector: selector(el), left: Math.round(left), right: Math.round(right), width: Math.round(rect.width) });
    }
  }
  const small = [];
  if (width <= phoneWidth) {
    const interactive = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], [role=checkbox], [role=tab], [role=menuitem], [tabindex]:not([tabindex="-1"])';
    for (const el of document.querySelectorAll(interactive)) {
      if (!visible(el) || el.disabled) continue;
      if (el.closest('[inert], [aria-hidden="true"]')) continue; // behind an open modal: not reachable
      const style = getComputedStyle(el);
      // WCAG 2.5.8 exception: a link inside a sentence of running text.
      if (el.tagName === 'A' && style.display === 'inline' && el.parentElement &&
          [...el.parentElement.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
      let rect = el.getBoundingClientRect();
      // A checkbox or radio is hit through its label: the label's box is the target.
      const label = el.labels && el.labels[0];
      if (label && visible(label)) {
        const box = label.getBoundingClientRect();
        if (box.width * box.height > rect.width * rect.height) rect = box;
      }
      if (rect.width < targetMin || rect.height < targetMin) {
        small.push({ selector: selector(el), width: Math.round(rect.width), height: Math.round(rect.height) });
      }
    }
  }
  // Text cut off on purpose must say so (data-truncate) and keep a path to the full text (a title, an accessible
  // name or description, or a link to where it is shown whole); any other clipped text is a layout fault.
  const truncated = [];
  for (const el of document.body ? document.body.querySelectorAll('*') : []) {
    if (!visible(el) || el.closest('[data-scroll-x]')) continue;
    const style = getComputedStyle(el);
    const clipsX = ['hidden', 'clip'].includes(style.overflowX) && el.scrollWidth > el.clientWidth + 1;
    const clamp = style.webkitLineClamp && style.webkitLineClamp !== 'none' && el.scrollHeight > el.clientHeight + 1;
    if (!clipsX && !clamp) continue;
    if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
    const marked = el.closest('[data-truncate]');
    const fullText = ['title', 'aria-label', 'aria-describedby'].some((name) => el.hasAttribute(name) || (marked && marked.hasAttribute(name)))
      || Boolean(el.closest('a[href]'));
    if (marked && fullText) continue;
    truncated.push({ selector: selector(el), problem: marked ? 'no_full_text' : 'not_marked',
      text: el.textContent.trim().replace(/\s+/g, ' ').slice(0, 80) });
  }
  // Arabic letters are joined: spacing them apart breaks the words.
  const tracking = [];
  for (const el of document.body ? document.body.querySelectorAll('*') : []) {
    if (!visible(el) || !(parseFloat(getComputedStyle(el).letterSpacing) > 0)) continue;
    if ([...el.childNodes].some((n) => n.nodeType === 3 && /[\u0600-\u06FF]/.test(n.textContent))) tracking.push(selector(el));
  }
  const scroller = document.scrollingElement || document.documentElement;
  const darkRules = (() => {
    const meta = document.querySelector('meta[name="color-scheme"]');
    if (meta && /dark/.test(meta.content)) return true;
    for (const sheet of document.styleSheets) {
      let rules;
      try { rules = sheet.cssRules; } catch { continue; }
      for (const rule of rules) if (rule.media && /prefers-color-scheme:\s*dark/.test(rule.media.mediaText)) return true;
    }
    return false;
  })();
  return {
    inner_width: width,
    layout_width: window.innerWidth,
    scroll_width: document.documentElement.scrollWidth,
    overflow_elements: offenders.slice(0, 20).map(({ el, ...rest }) => rest),
    overflow_element_count: offenders.length,
    scroll: { x: Math.round(window.scrollX), y: Math.round(window.scrollY), left: Math.round(scroller.scrollLeft) },
    dir: document.documentElement.dir || getComputedStyle(document.documentElement).direction,
    lang: document.documentElement.lang || '',
    page_height: document.documentElement.scrollHeight,
    truncated: truncated.slice(0, 20),
    truncated_count: truncated.length,
    small_targets: small.slice(0, 30),
    small_target_count: small.length,
    arabic_tracking: tracking.slice(0, 10),
    arabic_tracking_count: tracking.length,
    root_attributes: Object.fromEntries([...document.documentElement.attributes].map((a) => [a.name, a.value])),
    supports_dark: darkRules,
  };
}

async function act(page, actions) {
  for (const step of actions || []) {
    if (step.press) await page.keyboard.press(step.press);
    else if (step.type) await page.keyboard.type(step.type);
    else if (step.click) await page.locator(step.click).locator('visible=true').first().click();
    if (step.wait) await page.waitForTimeout(step.wait);
  }
}

async function auditOne(browser, entry, viewport, variant, index) {
  const page_url = entry.url;
  const base = new URL(page_url);
  const url = withQuery(page_url, variant.query);
  const mobile = viewport.mobile ?? viewport.width <= config.phone_width;
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1,
    // A phone is emulated as one (meta viewport honoured, touch), as the owner's phone renders the page.
    isMobile: mobile, hasTouch: mobile,
    colorScheme: variant.color_scheme || 'light', serviceWorkers: 'block',
  });
  const blocked = [];
  await context.route('**/*', (route) => {
    if (allowed(route.request(), base)) return route.continue();
    blocked.push(route.request().url());
    return route.abort('blockedbyclient');
  });
  if (variant.storage && Object.keys(variant.storage).length) {
    await context.addInitScript((pairs) => {
      try { for (const [key, value] of Object.entries(pairs)) window.localStorage.setItem(key, value); } catch {}
    }, variant.storage);
  }
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error.message || error).slice(0, 300)));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text().slice(0, 300)); });
  const row = { url, page: entry.name || null, viewport: viewport.name, width: viewport.width, height: viewport.height,
    variant: variant.name, mobile, expect: variant.expect || null };
  try {
    await page.goto(url, { waitUntil: 'load', timeout: config.timeout_ms || 30000 });
    try { await page.waitForLoadState('networkidle', { timeout: 3000 }); } catch {}
    const ready = entry.wait_for || config.wait_for;
    if (ready) await page.waitForSelector(ready, { timeout: 10000 });
    await page.evaluate(() => document.fonts && document.fonts.ready);
    await page.waitForTimeout(config.settle_ms ?? 300);
    if (entry.actions) { await act(page, entry.actions); await page.waitForTimeout(config.settle_ms ?? 300); }
    // The page's own errors, counted before axe runs (on file:// axe reads stylesheets the page's policy may refuse)
    row.page_errors = errors.slice(0, 10);
    Object.assign(row, await page.evaluate(measure, { phoneWidth: config.phone_width, targetMin: config.target_min,
      viewportWidth: viewport.width }));
    const axe = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
    row.axe = {
      version: axe.testEngine && axe.testEngine.version,
      violations: axe.violations.map((v) => ({
        id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,
        targets: v.nodes.slice(0, 10).map((n) => n.target.flat().join(' ')),
      })),
      passes: axe.passes.length, incomplete: axe.incomplete.length,
    };
    if (config.screenshots_dir) {
      mkdirSync(config.screenshots_dir, { recursive: true });
      const page_name = entry.name || (base.pathname.split('/').pop() || 'index').replace(/\.html?$/, '');
      const file = join(config.screenshots_dir, `${String(index).padStart(2, '0')}-${page_name}-${variant.name || 'default'}-${viewport.name}.png`
        .replace(/[^A-Za-z0-9._-]+/g, '_'));
      // Measured at the real viewport; the picture grows the viewport to the page, so bars fixed to the bottom of
      // the screen are drawn at the bottom of the page, where a person scrolling down meets them.
      if (!entry.actions && row.page_height > viewport.height) {
        await page.setViewportSize({ width: viewport.width, height: Math.min(row.page_height, 12000) });
        await page.waitForTimeout(150);
      }
      await page.screenshot({ path: file, fullPage: !entry.actions });
      row.screenshot = file;
    }
    row.status = 'observed';
  } catch (error) {
    row.status = 'error';
    row.reason = String(error && error.message || error).slice(0, 500);
  }
  if (row.status !== 'observed') row.page_errors = errors.slice(0, 10);
  row.blocked_requests = blocked.slice(0, 20);
  await context.close();
  return row;
}

const browser = await playwright.chromium.launch({ headless: true, args: config.chromium_args || [] });
const browserVersion = browser.version();
const rows = [];
let index = 0;
try {
  for (const item of config.urls) {
    const entry = typeof item === 'string' ? { url: item } : item;
    const page_url = entry.url;
    const viewports = config.viewports.filter((v) => !entry.viewports || entry.viewports.includes(v.name));
    let darkSupported = null;
    for (const variant of config.variants.filter((v) => !entry.variants || entry.variants.includes(v.name))) {
      // A dark variant set only through prefers-color-scheme is audited when the page answers it.
      if (variant.if_page_supports_dark && darkSupported === false) {
        for (const viewport of viewports) {
          rows.push({ url: page_url, page: entry.name || null, viewport: viewport.name, width: viewport.width, height: viewport.height, variant: variant.name,
            status: 'skipped', reason: 'the page has no dark theme (no prefers-color-scheme: dark rule, no color-scheme meta)' });
        }
        continue;
      }
      for (const viewport of viewports) {
        const row = await auditOne(browser, entry, viewport, variant, index++);
        if (row.status === 'observed' && darkSupported !== true) darkSupported = row.supports_dark;
        rows.push(row);
      }
    }
  }
} finally {
  await browser.close();
}
process.stdout.write(JSON.stringify({ rows, chromium: browserVersion }) + '\n');
