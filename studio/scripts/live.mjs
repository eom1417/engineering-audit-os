// The browser half of the live trial (tools/studio_live_trial.py, indicator F9): the shipped Studio, opened from the
// live server with its launch token, must show each event (a new scan, a batch, a merge, a decision) on screen within
// EAOS_LIVE_WITHIN ms of the data being written. The Python half started the server and rewrites the data; this
// script asks it for each event (EAOS_LIVE_MUTATE mutate …) and times the page. Writes EAOS_LIVE_OUT/live.json and a
// screenshot of each view after its last event.
// Playwright comes from the EAOS toolchain ($EAOS_ENGINE_TOOLS, default ~/.eaos/tools), as in gates.mjs.
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const tools = process.env.EAOS_ENGINE_TOOLS || path.join(os.homedir(), '.eaos/tools')
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(tools, 'browsers')
const { chromium } = require(path.join(tools, 'node/node_modules/playwright'))

const base = process.env.EAOS_LIVE_BASE
const token = process.env.EAOS_LIVE_TOKEN
const data = process.env.EAOS_LIVE_DATA
const python = process.env.EAOS_LIVE_PYTHON
const mutator = process.env.EAOS_LIVE_MUTATE
const out = process.env.EAOS_LIVE_OUT
const within = Number(process.env.EAOS_LIVE_WITHIN || 5000)
const KINDS = ['scan', 'batch', 'merge', 'decision']
const VARIANTS = [
  { name: 'phone-ar-light', width: 390, height: 844, lang: 'ar', theme: 'light', phone: true },
  { name: 'desktop-en-dark', width: 1440, height: 900, lang: 'en', theme: 'dark', phone: false },
]

const mutate = (kind, n, plan) => JSON.parse(execFileSync(python, [mutator, 'mutate', data, kind, String(n), ...(plan ? ['--plan'] : [])], { encoding: 'utf8' }))
const shows = ({ scope, text }) => (document.querySelector(scope) || document.body).innerText.includes(text)

fs.mkdirSync(out, { recursive: true })
const browser = await chromium.launch()
const events = []
const errors = []
let tokenLeft = true
let n = 0
try {
  for (const v of VARIANTS) {
    const ctx = await browser.newContext({ viewport: { width: v.width, height: v.height }, deviceScaleFactor: v.phone ? 2 : 1, isMobile: v.phone, hasTouch: v.phone, colorScheme: v.theme })
    const page = await ctx.newPage()
    page.on('pageerror', (e) => errors.push(`${v.name}: ${e}`))
    page.on('console', (m) => { if (m.type() === 'error') errors.push(`${v.name}: ${m.text().slice(0, 300)}`) })
    await page.goto(`${base}?lang=${v.lang}&theme=${v.theme}#token=${token}`, { waitUntil: 'load' })
    await page.waitForSelector('main#main', { timeout: 15000 })
    await page.waitForFunction(() => document.documentElement.dataset.studioLive === 'connected', null, { timeout: 15000 })
    tokenLeft = tokenLeft && !(await page.evaluate(() => location.href)).includes('token')
    for (const kind of KINDS) {
      n += 1
      const plan = mutate(kind, n, true)
      const text = plan.text[v.lang]
      await page.evaluate((hash) => { location.hash = hash }, plan.route)
      try {
        await page.waitForFunction(({ scope }) => document.querySelector(scope) !== null, { scope: plan.scope }, { timeout: 10000 })
      } catch (e) {
        await page.screenshot({ path: path.join(out, `failed-${v.name}-${kind}.png`) })
        throw new Error(`${v.name} ${kind}: ${plan.route} did not show ${plan.scope} (at ${await page.evaluate(() => location.href.replace(/token=[^&]*/, 'token=…'))})`)
      }
      await page.waitForTimeout(300)
      const already = await page.evaluate(shows, { scope: plan.scope, text })
      const written = Date.now()
      mutate(kind, n, false)
      let ms = null
      try {
        await page.waitForFunction(shows, { scope: plan.scope, text }, { timeout: within + 2000, polling: 50 })
        ms = Date.now() - written
      } catch { ms = null }
      events.push({ variant: v.name, kind, route: plan.route, text, shown: ms !== null && !already, ms, already_shown_before: already })
    }
    await page.screenshot({ path: path.join(out, `${v.name}.png`), fullPage: false })
    await ctx.close()
  }
} catch (e) {
  errors.push(String(e))
} finally {
  await browser.close()
}
fs.writeFileSync(path.join(out, 'live.json'), JSON.stringify({ events, errors, variants: VARIANTS.map((v) => v.name), token_left_address: tokenLeft }, null, 1) + '\n')
console.log(`${events.filter((e) => e.shown && e.ms <= within).length}/${events.length} events shown within ${within} ms`)
process.exit(errors.length ? 1 : 0)
