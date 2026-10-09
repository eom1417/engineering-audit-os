// Shipped-browser timing trial, called by tools/studio_gates.py --budgets.
// Cold first search includes indexing; no prewarming can hide startup work.
import { createRequire } from 'node:module'
import fs from 'node:fs'
const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const require = createRequire(`${config.modules}/eaos-resolve.js`)
const { chromium } = require('playwright')
const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] })
const samples = []
try {
  for (let repeat = 0; repeat < 3; repeat++) {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, deviceScaleFactor: 1, reducedMotion: 'reduce' })
    const page = await context.newPage()
    const failures = []
    page.on('pageerror', error => failures.push(error.message))
    const origin = new URL(config.base).origin
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort())
    const cdp = await context.newCDPSession(page)
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 })
    let start = performance.now()
    await page.goto(`${config.base}index.html?lang=ar&theme=light#/`)
    await page.locator('main#main h1').waitFor()
    await page.keyboard.press('Control+k')
    await page.getByRole('dialog').waitFor()
    const home_interactive_ms = performance.now() - start
    await page.keyboard.press('Escape')
    await page.goto(`${config.base}index.html?lang=ar&theme=light#/problems`)
    const input = page.locator('main input').first()
    await input.waitFor()
    start = performance.now()
    await input.fill(config.card)
    // Wait for a committed filtered result and disappearance of an unrelated card.
    await page.locator('main a').filter({ hasText: config.card }).first().waitFor()
    await page.locator('main a').filter({ hasText: config.other }).first().waitFor({ state: 'hidden' })
    const filter_5000_ms = performance.now() - start
    if (![home_interactive_ms, filter_5000_ms].every(value => Number.isFinite(value) && value > 0)) {
      throw new Error('Timing must be finite and positive')
    }
    if (failures.length) throw new Error(failures.join('; '))
    samples.push({ home_interactive_ms, filter_5000_ms })
    await context.close()
  }
  console.log(JSON.stringify({
    schema_version: 1, studio_source_sha256: config.source, card_count: config.count,
    profile: { viewport: 390, cpu_slowdown: 4, network: 'loopback; unthrottled', repeats: 3 },
    home_definition: 'cold navigation to rendered Home and keyboard palette dialog',
    filter_definition: 'cold Problems query through rendered unique result; includes index construction and browser IPC',
    samples,
    home_interactive_ms: Math.max(...samples.map(row => row.home_interactive_ms)),
    filter_5000_ms: Math.max(...samples.map(row => row.filter_5000_ms)),
  }))
} finally { await browser.close() }
