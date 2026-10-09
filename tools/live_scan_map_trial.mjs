// The browser half of the live scan map trial (tools/live_scan_map_trial.py). The shipped Studio, served by the real
// `eaos studio` of a project while a real check of it runs, opened in Chromium with its launch token. It waits for the
// check to start and takes three moments (early, middle, done), each at 390, 768 and 1440 px, Arabic and English, light
// and dark, plus reduced motion and the banner on another page mid-run. Every view is measured: layout width against
// the viewport, the initial scroll, axe (WCAG 2.2 AA), targets under 44 px, and on the map the glow and the moving
// light. Writes TRIAL_OUT/browser.json; prints one JSON line.
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

const fromFolder = (folder) => createRequire(path.join(folder, 'eaos-resolve.js'))
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(process.env.TRIAL_PLAYWRIGHT, '..', '..', 'browsers')
const { chromium } = fromFolder(process.env.TRIAL_PLAYWRIGHT)('playwright')
const { AxeBuilder } = fromFolder(process.env.TRIAL_AXE)('@axe-core/playwright')

const base = process.env.TRIAL_BASE.replace(/\/$/, '')
const token = process.env.TRIAL_TOKEN
const out = process.env.TRIAL_OUT
const waitStartMs = Number(process.env.TRIAL_WAIT_START_MS || 20 * 60 * 1000)
const shots = path.join(out, 'shots')
fs.mkdirSync(shots, { recursive: true })
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa']
const VIEWS = []
for (const width of [390, 768, 1440]) for (const lang of ['ar', 'en']) for (const theme of ['light', 'dark']) VIEWS.push({ width, lang, theme })
// the views the moment cannot miss come first, while the run is surely still in that moment
const FIRST = (v) => (v.width === 1440 && v.lang === 'en' && v.theme === 'light') || (v.width === 390 && v.lang === 'ar' && v.theme === 'light') ? 0 : 1
VIEWS.sort((a, b) => FIRST(a) - FIRST(b))
const rows = []
const moments = {}
const errors = []
const log = (...args) => console.error(new Date().toISOString(), ...args)

async function progress() {
  try {
    const answer = await fetch(`${base}/api/scan-progress`, { headers: { 'X-EAOS-Token': token } })
    return answer.ok ? await answer.json() : null
  } catch { return null }
}
const ended = (p) => (p?.stages ?? []).filter((s) => s.requested && !['waiting', 'running'].includes(s.state)).length
const asked = (p) => (p?.stages ?? []).filter((s) => s.requested).length
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const POOL = Number(process.env.TRIAL_POOL || 4)

/** Every view of a moment, `POOL` at a time, so a short check is still in that moment when its views are taken. */
async function all(moment, views, extra) {
  const queue = [...views]
  await Promise.all(Array.from({ length: POOL }, async () => {
    while (queue.length) {
      const v = queue.shift()
      try { await view(moment, v, extra) } catch (problem) { errors.push(`${moment} ${v.width}-${v.lang}-${v.theme}: ${problem}`) }
    }
  }))
}

async function until(test, ms, every = 500) {
  const start = Date.now()
  while (Date.now() - start < ms) {
    const p = await progress()
    if (test(p)) return p
    await sleep(every)
  }
  return null
}

const browser = await chromium.launch()

async function open({ width, lang, theme, route = '/scan', reduced = false }) {
  const phone = width < 768
  const ctx = await browser.newContext({ viewport: { width, height: phone ? 844 : width < 1200 ? 1024 : 900 }, deviceScaleFactor: phone ? 2 : 1,
    isMobile: phone, hasTouch: phone, colorScheme: theme, reducedMotion: reduced ? 'reduce' : 'no-preference', locale: lang === 'ar' ? 'ar' : 'en-GB' })
  await ctx.addInitScript(([l, t]) => { try { localStorage.setItem('eaos.studio', JSON.stringify({ lang: l, theme: t })) } catch { /* fresh */ } }, [lang, theme])
  const page = await ctx.newPage()
  page.on('pageerror', (e) => errors.push(`${width}-${lang}-${theme}: ${e}`))
  await page.goto(`${base}/#/${route.replace(/^\//, '')}?token=${token}`, { waitUntil: 'load' })
  await page.waitForSelector('main#main', { timeout: 30000 })
  if (route === '/scan') await page.waitForSelector('[data-run-state]', { timeout: 30000 })
  await page.waitForTimeout(1500)
  return { ctx, page }
}

async function measure(page, width) {
  return page.evaluate((w) => {
    const visible = (el) => { const s = getComputedStyle(el); if (s.display === 'none' || s.visibility === 'hidden') return false; const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1 }
    const interactive = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], [role=checkbox], [role=tab], [tabindex]:not([tabindex="-1"])'
    // the phone: everything on screen, as the Studio gate measures it; wider: the page itself (not the shared chrome)
    const scope = w <= 480 ? [...document.querySelectorAll('main#main, header, [role=dialog]')] : [...document.querySelectorAll('main#main, [role=dialog]')]
    const small = []
    for (const el of scope.flatMap((root) => [...root.querySelectorAll(interactive)])) {
      if (!visible(el) || el.disabled || el.closest('[inert], [aria-hidden="true"]')) continue
      const s = getComputedStyle(el)
      if (el.tagName === 'A' && s.display === 'inline' && [...(el.parentElement?.childNodes ?? [])].some((n) => n.nodeType === 3 && n.textContent.trim())) continue
      const r = el.getBoundingClientRect()
      if (r.width < 44 || r.height < 44) small.push(`${el.tagName.toLowerCase()}.${[...el.classList].slice(0, 1).join('')} ${Math.round(r.width)}x${Math.round(r.height)} "${(el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 30)}"`)
    }
    const glow = [...document.querySelectorAll('[data-glow]')]
    const flows = [...document.querySelectorAll('[data-flow]')]
    const halo = glow[0] ? getComputedStyle(glow[0]) : null
    return {
      layout: document.documentElement.scrollWidth, viewport: w, scrollY: window.scrollY, scrollX: window.scrollX, small,
      runState: document.querySelector('[data-run-state]')?.getAttribute('data-run-state') ?? null,
      running: document.querySelectorAll('[data-state=running]').length, glow: glow.length, flows: flows.length,
      haloAnimation: halo ? halo.animationName : null, haloDuration: halo ? halo.animationDuration : null,
      motion: document.querySelector('[data-motion]')?.getAttribute('data-motion') ?? null,
      banner: !!document.querySelector('[data-scan-banner] a'),
      endedOnPage: document.querySelectorAll('[data-state=ok],[data-state=skipped],[data-state=unavailable],[data-state=failed],[data-state=not_reached]').length,
    }
  }, width)
}

/** Where the first moving light is now, twice, 300 ms apart: it must have moved. */
async function lightMoves(page) {
  const at = () => page.evaluate(() => { const c = document.querySelector('[data-flow]'); if (!c) return null; const r = c.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y)] })
  const a = await at()
  await page.waitForTimeout(300)
  const b = await at()
  return { a, b, moved: !!a && !!b && (a[0] !== b[0] || a[1] !== b[1]) }
}

async function axe(page) {
  const result = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze()
  return { total: result.violations.length, serious: result.violations.filter((v) => ['serious', 'critical'].includes(v.impact)).map((v) => `${v.id} (${v.nodes.length}) ${v.nodes[0]?.target}`),
    all: result.violations.map((v) => `${v.impact} ${v.id} (${v.nodes.length}) ${v.nodes[0]?.target}`) }
}

async function view(moment, v, extra = {}) {
  const { ctx, page } = await open({ ...v, ...extra })
  try {
    const m = await measure(page, v.width)
    const light = moment === 'middle' && !extra.reduced ? await lightMoves(page) : null
    const a = await axe(page)
    const name = `${moment}-${v.width}-${v.lang}-${v.theme}${extra.reduced ? '-reduced' : ''}${extra.route && extra.route !== '/scan' ? '-banner' : ''}.png`
    const file = path.join(shots, name)
    await page.screenshot({ path: file })
    let full = null
    if (v.width < 768 && !extra.route) { full = file.replace(/\.png$/, '-full.png'); await page.screenshot({ path: full, fullPage: true }) }
    const api = await progress()
    const row = { moment, viewport: v.width, lang: v.lang, theme: v.theme, reduced: !!extra.reduced, route: extra.route ?? '/scan', screenshot: file, full,
      width_equals_viewport: m.layout === m.viewport, initial_scroll_zero: m.scrollY === 0 && m.scrollX === 0,
      axe_violations: a.total, axe_serious: a.serious, axe_all: a.all, small_targets: m.small.length, small: m.small.slice(0, 6),
      run_state: m.runState, running_on_page: m.running, glow: m.glow, flows: m.flows, halo_animation: m.haloAnimation, halo_duration: m.haloDuration,
      motion: m.motion, banner: m.banner, ended_on_page: m.endedOnPage, ended_in_api: ended(api), api_state: api?.state ?? null, light, at: new Date().toISOString() }
    row.pass = row.width_equals_viewport && row.initial_scroll_zero && row.axe_violations === 0 && row.small_targets === 0
    rows.push(row)
    log(moment, v.width, v.lang, v.theme, extra.reduced ? 'reduced' : '', extra.route ?? '', `run=${m.runState} glow=${m.glow} flows=${m.flows} pass=${row.pass}`, a.all.join('; '), m.small.slice(0, 2).join('; '))
    return row
  } finally {
    await ctx.close()
  }
}

try {
  log('waiting for the check to start')
  const first = await until((p) => p && p.state === 'running', waitStartMs)
  if (!first) throw new Error('the check did not start in time')
  moments.early = { at: new Date().toISOString(), ended: ended(first), total: asked(first) }
  await all('early', VIEWS)

  // the middle: once a stage or more has ended and one runs; a page opened now must show at once what the run did
  const mid = await until((p) => p && (p.state !== 'running' || (ended(p) >= 1 && p.stages.some((s) => s.state === 'running'))), 30 * 60 * 1000)
  moments.middle = { at: new Date().toISOString(), ended: ended(mid), total: asked(mid), state: mid?.state ?? null }
  await all('middle', [...VIEWS.filter((v) => FIRST(v) === 0), ...VIEWS.filter((v) => FIRST(v) === 1)])
  await Promise.all([
    view('middle', { width: 1440, lang: 'ar', theme: 'light' }, { reduced: true }),
    view('middle', { width: 390, lang: 'ar', theme: 'dark' }, { reduced: true }),
    view('middle', { width: 390, lang: 'ar', theme: 'light' }, { route: '/' }),
    view('middle', { width: 1440, lang: 'en', theme: 'dark' }, { route: '/problems' }),
  ])

  const done = await until((p) => p && p.state !== 'running', 60 * 60 * 1000, 1000)
  moments.done = { at: new Date().toISOString(), state: done?.state ?? null, status: done?.status ?? null, ended: ended(done), total: asked(done) }
  await sleep(4000)            // the report's own reload after the run
  await all('done', VIEWS)
} catch (problem) {
  errors.push(String(problem && problem.stack || problem))
} finally {
  await browser.close()
}
const result = { moments, rows, errors }
fs.writeFileSync(path.join(out, 'browser.json'), JSON.stringify(result, null, 1))
console.log(JSON.stringify({ rows: rows.length, failed: rows.filter((r) => !r.pass).length, errors: errors.length }))
process.exit(0)
