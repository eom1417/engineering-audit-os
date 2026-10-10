// The browser half of the live scan map trial (tools/live_scan_map_trial.py). The shipped Studio, served by the real
// `eaos studio` of a project while a real check of it runs, opened in Chromium with its launch token. It waits for the
// check to start and takes three moments (early, middle, done), each at 390, 768 and 1440 px, Arabic and English, light
// and dark, plus reduced motion and the banner on another page mid-run. Every view is measured: layout width against
// the viewport, the initial scroll, axe (WCAG 2.2 AA), targets under 44 px, and on the map the glow and the moving
// light, the map's toolbar against every stage it could cover. Phase 4 of the plan adds the phone's bottom sheet, a
// produced file read in its sheet, the polling fallback with the stream held back, and the replay of the finished
// check at 30x, every glow and light of which is matched to its line of run-progress.jsonl (I9). Phase 5 adds two modes
// (TRIAL_MODE): `watch`, one long check watched from start to end (plan 7.1 and 7.7), `look`, the page at a given
// address (7.3, 7.4, 7.5), and `button`, a check started by the Studio's own button (7.3).
// Writes TRIAL_OUT/browser.json; prints one JSON line.
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
const VIEWS = [390, 768, 1440].flatMap((width) => ['ar', 'en'].flatMap((lang) => ['light', 'dark'].map((theme) => ({ width, lang, theme }))))
// the views the moment cannot miss come first, while the run is surely still in that moment
const FIRST = (v) => (v.width === 1440 && v.lang === 'en' && v.theme === 'light') || (v.width === 390 && v.lang === 'ar' && v.theme === 'light') ? 0 : 1
VIEWS.sort((a, b) => FIRST(a) - FIRST(b))
// browser.json, filled as the trial runs
const result = { moments: {}, rows: [], checks: {}, errors: [] }
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
      try { await view(moment, v, extra) } catch (problem) { result.errors.push(`${moment} ${v.width}-${v.lang}-${v.theme}: ${problem}`) }
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

async function open({ width, lang, theme, route = '/scan', reduced = false, holdStream = false }) {
  const phone = width < 768
  const height = phone ? 844 : width >= 1200 ? 900 : 1024
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: phone ? 2 : 1,
    isMobile: phone, hasTouch: phone, colorScheme: theme, reducedMotion: reduced ? 'reduce' : 'no-preference', locale: lang === 'ar' ? 'ar' : 'en-GB' })
  await ctx.addInitScript(([l, t]) => { try { localStorage.setItem('eaos.studio', JSON.stringify({ lang: l, theme: t })) } catch { /* fresh */ } }, [lang, theme])
  // the stream held back, as a proxy that buffers server-sent events would: the page must fall back to reading
  if (holdStream) await ctx.route('**/api/events', () => undefined)
  const page = await ctx.newPage()
  page.on('pageerror', (e) => result.errors.push(`${width}-${lang}-${theme}: ${e}`))
  await page.goto(`${base}/#/${route.replace(/^\//, '')}${route.includes('?') ? '&' : '?'}token=${token}`, { waitUntil: 'load' })
  await page.waitForSelector('main#main', { timeout: 30000 })
  if (route.startsWith('/scan')) await page.waitForSelector('[data-run-state]', { timeout: 30000 })
  await page.waitForTimeout(1500)
  return { ctx, page }
}

/** The visible controls under 44 px, as the Studio gate measures them (the phone: everything on screen; wider: the page
 * itself, not the shared chrome). A link inside a sentence is left out. */
async function smallTargets(page, width) {
  return page.evaluate((w) => {
    const interactive = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], [role=checkbox], [role=tab], [tabindex]:not([tabindex="-1"])'
    const scope = [...document.querySelectorAll(w <= 480 ? 'main#main, header, [role=dialog]' : 'main#main, [role=dialog]')]
    const hidden = (el) => { const s = getComputedStyle(el); const r = el.getBoundingClientRect(); return s.display === 'none' || s.visibility === 'hidden' || r.width <= 1 || r.height <= 1 }
    const inText = (el) => el.tagName === 'A' && getComputedStyle(el).display === 'inline' && [...(el.parentElement?.childNodes ?? [])].some((n) => n.nodeType === 3 && n.textContent.trim())
    const skipped = (el) => hidden(el) || el.disabled || el.closest('[inert], [aria-hidden="true"]') || inText(el)
    const label = (el, r) => `${el.tagName.toLowerCase()}.${[...el.classList].slice(0, 1).join('')} ${Math.round(r.width)}x${Math.round(r.height)} "${(el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 30)}"`
    return scope.flatMap((root) => [...root.querySelectorAll(interactive)]).filter((el) => !skipped(el))
      .map((el) => [el, el.getBoundingClientRect()]).filter(([, r]) => r.width < 44 || r.height < 44).map(([el, r]) => label(el, r))
  }, width)
}

async function measure(page, width) {
  const small = await smallTargets(page, width)
  return page.evaluate(([w, small]) => {
    const glow = [...document.querySelectorAll('[data-glow]')]
    const halo = glow[0] ? getComputedStyle(glow[0]) : null
    const attribute = (selector, name) => document.querySelector(selector)?.getAttribute(name) ?? null
    return {
      layout: document.documentElement.scrollWidth, viewport: w, scrollY: window.scrollY, scrollX: window.scrollX, small,
      runState: attribute('[data-run-state]', 'data-run-state'),
      running: document.querySelectorAll('[data-state=running]').length, glow: glow.length, flows: document.querySelectorAll('[data-light]').length,
      haloAnimation: halo?.animationName ?? null, haloDuration: halo?.animationDuration ?? null,
      motion: attribute('[data-motion]', 'data-motion'),
      banner: !!document.querySelector('[data-scan-banner] a'),
      endedOnPage: document.querySelectorAll('[data-state=ok],[data-state=skipped],[data-state=unavailable],[data-state=failed],[data-state=not_reached]').length,
    }
  }, [width, small])
}

/** What phase 4 adds to a view's measure: how many toolbar controls cover a stage (each stage taken where the canvas
 * shows it), the journey's steps, which path carries the changes, and the stages the list shows ended. */
async function mapFacts(page) {
  return page.evaluate(() => {
    const canvas = document.querySelector('[data-motion]')?.getBoundingClientRect()
    const meet = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom
    const shown = (r) => ({ left: Math.max(r.left, canvas.left), right: Math.min(r.right, canvas.right), top: Math.max(r.top, canvas.top), bottom: Math.min(r.bottom, canvas.bottom) })
    const stages = canvas ? [...document.querySelectorAll('g[data-stage]')].map((g) => g.getBoundingClientRect()).filter((r) => meet(r, canvas)).map(shown) : []
    const ended = ['ok', 'skipped', 'unavailable', 'failed', 'not_reached']
    return { overlaps: [...document.querySelectorAll('[role=toolbar] button')].filter((b) => stages.some((r) => meet(b.getBoundingClientRect(), r))).length,
      journey: document.querySelectorAll('[data-journey]').length, transport: document.querySelector('[data-transport]')?.getAttribute('data-transport'),
      endedInList: [...document.querySelectorAll('[data-list-state]')].filter((b) => ended.includes(b.getAttribute('data-list-state'))).length }
  })
}

/** A light that leaves a stage (one runs for 700 ms after each stage ends ok), read twice 100 ms apart: it must have
 * moved. A light caught at its very end is read again on the next one, for up to 3 minutes (the external tools' stage
 * can run that long without a stage ending). */
async function lightMoves(page) {
  const at = () => page.evaluate(() => { const c = document.querySelector('[data-light]'); if (!c) return null; const r = c.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y)] })
  const end = Date.now() + 180000
  let a = null
  let b = null
  while (!(a && b) && Date.now() < end) {
    await page.waitForSelector('[data-light]', { timeout: end - Date.now() }).catch(() => undefined)
    a = await at()
    await page.waitForTimeout(100)
    b = await at()
    if (!(a && b)) await page.waitForTimeout(800)            // that light has ended; wait for the next
  }
  return { a, b, moved: !!a && !!b && (a[0] !== b[0] || a[1] !== b[1]) }
}

async function axe(page) {
  const found = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze()
  return { total: found.violations.length, serious: found.violations.filter((v) => ['serious', 'critical'].includes(v.impact)).map((v) => `${v.id} (${v.nodes.length}) ${v.nodes[0]?.target}`),
    all: found.violations.map((v) => `${v.impact} ${v.id} (${v.nodes.length}) ${v.nodes[0]?.target}`) }
}

/** What a view does before it is measured: open a stage's bottom sheet on the phone, a produced file's sheet, or wait
 * for the polling fallback to carry the run. */
async function act(page, extra) {
  if (extra.sheet) {
    await page.locator('[data-list-stage]').first().click()
    await page.waitForSelector('[role=dialog] [data-hook=scan-stage-panel]', { timeout: 10000 })
    await page.waitForTimeout(800)             // the sheet's entrance has ended
  }
  if (extra.file) {
    await page.locator('[data-list-stage="facts"]').click()
    await page.locator('[data-file]').first().click()
    await page.waitForSelector('[data-file-text]', { timeout: 10000 })
    result.checks.file = { shown: (await page.locator('[data-file-text]').textContent()).length }
  }
  if (extra.holdStream) {
    await page.waitForSelector('[data-transport=polling]', { timeout: 20000 })
    await page.waitForTimeout(6000)
  }
}

const KINDS = ['reduced', 'sheet', 'file', 'holdStream']
/** What a view shows besides the map itself: reduced motion, the phone's sheet, a file, the stream held back. */
const kindOf = (extra) => ({ holdStream: 'polling' })[KINDS.find((k) => extra[k])] ?? KINDS.find((k) => extra[k]) ?? 'map'

/** The screen gates of a view; a sheet or a file was opened by a tap, which may scroll the page, so the initial scroll
 * is the map views' gate, and the toolbar is measured on the live map only. */
function passes(row, extra) {
  const scrolled = row.initial_scroll_zero || row.kind === 'sheet' || row.kind === 'file'
  return row.width_equals_viewport && scrolled && row.axe_violations === 0 && row.small_targets === 0 && (!!extra.route || row.overlaps === 0)
}

async function view(moment, v, extra = {}) {
  const { ctx, page } = await open({ ...v, ...extra })
  try {
    await act(page, extra)
    const m = { ...(await measure(page, v.width)), ...(await mapFacts(page)) }
    const api = await progress()                // the run as the page was measured, before any wait for a light
    const light = moment === 'middle' && !Object.keys(extra).length && FIRST(v) === 0 ? await lightMoves(page) : null
    const a = await axe(page)
    const kind = kindOf(extra)
    const name = `${moment}-${v.width}-${v.lang}-${v.theme}${kind === 'map' ? '' : `-${kind}`}${extra.route ? '-banner' : ''}.png`
    const file = path.join(shots, name)
    await page.screenshot({ path: file })
    let full = null
    if (v.width < 768 && !extra.route && !extra.sheet) { full = file.replace(/\.png$/, '-full.png'); await page.screenshot({ path: full, fullPage: true }) }
    const row = { moment, viewport: v.width, lang: v.lang, theme: v.theme, reduced: !!extra.reduced, route: extra.route ?? '/scan', kind, screenshot: file, full,
      overlaps: m.overlaps, journey: m.journey, transport: m.transport,
      width_equals_viewport: m.layout === m.viewport, initial_scroll_zero: m.scrollY === 0 && m.scrollX === 0,
      axe_violations: a.total, axe_serious: a.serious, axe_all: a.all, small_targets: m.small.length, small: m.small.slice(0, 6),
      run_state: m.runState, running_on_page: m.running, glow: m.glow, flows: m.flows, halo_animation: m.haloAnimation, halo_duration: m.haloDuration,
      motion: m.motion, banner: m.banner, ended_on_page: m.endedOnPage, ended_in_list: m.endedInList, ended_in_api: ended(api), api_state: api?.state ?? null, light, at: new Date().toISOString() }
    row.pass = passes(row, extra)
    result.rows.push(row)
    log(moment, v.width, v.lang, v.theme, kind, extra.route ?? '', `run=${m.runState} glow=${m.glow} overlaps=${m.overlaps} transport=${m.transport} pass=${row.pass}`, a.all.join('; '), m.small.slice(0, 2).join('; '))
    return row
  } finally {
    await ctx.close()
  }
}

/** In the page: every glow and light drawn now, [kind, stage, to, the time of the line that drew it]. */
function drawnNow() {
  return [...[...document.querySelectorAll('[data-glow]')].map((g) => ['glow', g.closest('[data-stage]').getAttribute('data-stage'), '', g.getAttribute('data-at')]),
    ...[...document.querySelectorAll('[data-light]')].map((l) => ['light', l.getAttribute('data-from'), l.getAttribute('data-to'), l.getAttribute('data-at')])]
}

/** Every glow and light the map draws while the replay plays, until the replay has ended and the map has shown it
 * all (3 s with nothing drawn). */
async function watchReplay(page, shot) {
  const seen = new Map()
  const start = Date.now()
  let quietSince = Date.now()
  while (Date.now() - start < 90000 && Date.now() - quietSince < 3000) {
    const now = { drawn: await page.evaluate(drawnNow),
      done: await page.evaluate(() => document.querySelector('[data-replay]')?.getAttribute('data-run-state') === 'done') }
    for (const item of now.drawn) seen.set(item.join('|'), item)
    if (now.drawn.length || !now.done) quietSince = Date.now()
    if (seen.size > 6 && !fs.existsSync(shot)) await page.screenshot({ path: shot })
    await sleep(50)
  }
  return { items: [...seen.values()], seconds: (Date.now() - start) / 1000 }
}

/** The drawn items no line explains: a glow without its stage's `stage.started` at that time, a light without its
 * stage's `stage.ended` ok or towards a stage that does not need it. */
function unmatched(items, rows) {
  const needs = new Map((rows[0]?.stages ?? []).map((st) => [st.name, st.requires]))
  const line = (event, stage, at, status) => rows.some((r) => r.event === event && r.stage === stage && r.at === at && (!status || r.status === status))
  return items.filter(([kind, stage, to, at]) => (kind === 'glow' ? !line('stage.started', stage, at)
    : !(line('stage.ended', stage, at, 'ok') && (needs.get(to) ?? []).includes(stage))))
}

/** I9: the finished check replayed at 30x in the page; every glow and every light seen is matched to its line of the
 * real progress file. */
async function replayMatched() {
  const { ctx, page } = await open({ width: 1440, lang: 'ar', theme: 'dark' })
  try {
    await page.locator('[data-replay-speed="30"]').click()
    await page.waitForSelector('[data-replay]', { timeout: 10000 })
    const shot = path.join(shots, 'replay-1440-ar-dark.png')
    const { items, seconds } = await watchReplay(page, shot)
    const answer = await fetch(`${base}/api/report-file?path=run-progress.jsonl`, { headers: { 'X-EAOS-Token': token } })
    const rows = (await answer.text()).split('\n').filter(Boolean).map((line) => JSON.parse(line))
    result.checks.replay = { speed: 30, seconds, glows: items.filter((i) => i[0] === 'glow').length, lights: items.filter((i) => i[0] === 'light').length,
      started_lines: rows.filter((r) => r.event === 'stage.started').length, unmatched: unmatched(items, rows).map((i) => i.join(' ')),
      screenshot: fs.existsSync(shot) ? shot : null }
    log('replay', JSON.stringify(result.checks.replay))
  } finally {
    await ctx.close()
  }
}

async function threeMoments() {
  log('waiting for the check to start')
  const first = await until((p) => p && p.state === 'running', waitStartMs)
  if (!first) throw new Error('the check did not start in time')
  result.moments.early = { at: new Date().toISOString(), ended: ended(first), total: asked(first) }
  await all('early', VIEWS)

  // the middle: once a stage or more has ended and one runs; a page opened now must show at once what the run did
  const mid = await until((p) => p && (p.state !== 'running' || (ended(p) >= 1 && p.stages.some((s) => s.state === 'running'))), 30 * 60 * 1000)
  result.moments.middle = { at: new Date().toISOString(), ended: ended(mid), total: asked(mid), state: mid?.state ?? null }
  await all('middle', [...VIEWS.filter((v) => FIRST(v) === 0), ...VIEWS.filter((v) => FIRST(v) === 1)])
  await Promise.all([
    view('middle', { width: 1440, lang: 'ar', theme: 'light' }, { reduced: true }),
    view('middle', { width: 390, lang: 'ar', theme: 'dark' }, { reduced: true }),
    view('middle', { width: 390, lang: 'ar', theme: 'light' }, { route: '/' }),
    view('middle', { width: 1440, lang: 'en', theme: 'dark' }, { route: '/problems' }),
  ])
  await Promise.all([
    view('middle', { width: 390, lang: 'ar', theme: 'light' }, { sheet: true }),
    view('middle', { width: 390, lang: 'en', theme: 'dark' }, { sheet: true }),
    view('middle', { width: 1440, lang: 'en', theme: 'light' }, { holdStream: true }),
  ])

  const done = await until((p) => p && p.state !== 'running', 60 * 60 * 1000, 1000)
  result.moments.done = { at: new Date().toISOString(), state: done?.state ?? null, status: done?.status ?? null, ended: ended(done), total: asked(done) }
  await sleep(4000)            // the report's own reload after the run
  await all('done', VIEWS)
  await view('done', { width: 1440, lang: 'en', theme: 'light' }, { file: true })
  await view('done', { width: 390, lang: 'ar', theme: 'dark' }, { sheet: true })
  await replayMatched()
}

/** In the page: what the map and the panel show of the run now: each running stage's card line, the stage the panel
 * follows, its counted steps, its "n of N" steps and the programs it runs. */
function shownNow() {
  const panel = document.querySelector('[data-hook=scan-stage-panel]')
  const steps = [...(panel?.parentElement?.querySelectorAll('section') ?? [])].find((s) => s.querySelector('[data-step-status]'))
  return {
    cards: [...document.querySelectorAll('g[data-stage][data-state=running]')].map((g) => [g.getAttribute('data-stage'), g.querySelectorAll('text')[1]?.textContent ?? '']),
    panel: panel?.getAttribute('data-stage') ?? null,
    counted: [...(steps?.querySelectorAll('[data-step-status] bdi:first-child') ?? [])].map((b) => b.textContent).filter((t) => /\d+\/\d+$/.test(t)),
    stepsOf: steps?.querySelector('h3 span')?.textContent ?? '',
    programs: [...document.querySelectorAll('[data-programs] li > bdi:first-child')].map((b) => b.textContent),
  }
}

/** Keeps, per stage, the distinct texts the page showed of it (at most 40 of each kind). */
function note(seen, now) {
  const add = (stage, key, value) => {
    const kept = ((seen[stage] ??= {})[key] ??= [])
    if (value && !kept.includes(value) && kept.length < 40) kept.push(value)
  }
  for (const [stage, line] of now.cards) add(stage, 'card', line)
  if (!now.panel) return
  for (const text of now.counted) add(now.panel, 'counted', text)
  add(now.panel, 'steps_of', now.stepsOf)
  for (const name of now.programs) add(now.panel, 'programs', name)
}

/** Chrome's own measure of a page: main-thread task seconds and the JS heap (after a full collection when asked). */
async function usage(chrome, collect = false) {
  if (collect) await chrome.send('HeapProfiler.collectGarbage')
  const metrics = Object.fromEntries((await chrome.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]))
  return { at: Date.now(), task_seconds: metrics.TaskDuration, heap_bytes: metrics.JSHeapUsedSize }
}

async function photo(desk, phone, n) {
  const name = (width) => path.join(shots, `watch-${String(n).padStart(3, '0')}-${width}.png`)
  await desk.screenshot({ path: name(1440) })
  await phone.screenshot({ path: name(390) })
  return { at: new Date().toISOString(), desk: name(1440), phone: name(390) }
}

/** Plan 7.1 and 7.7: one long real check watched from its start to its end. A desktop and a phone page are
 * photographed every 30 s; the desktop page is read every 250 ms (every glow and light drawn, the running stages'
 * cards, the panel); a third page is left alone and measured by Chrome: its main thread's task time against the wall
 * clock, and its heap after a full collection at the start and the end. Every glow and light is then matched to its
 * line of the run's progress file (I9). */
async function watchRun() {
  const first = await until((p) => p && p.state === 'running', waitStartMs)
  if (!first) throw new Error('the check did not start in time')
  const desk = await open({ width: 1440, lang: 'ar', theme: 'light' })
  const phone = await open({ width: 390, lang: 'ar', theme: 'dark' })
  const quiet = await open({ width: 1440, lang: 'en', theme: 'light' })
  const chrome = await quiet.ctx.newCDPSession(quiet.page)
  await chrome.send('Performance.enable')
  const usages = [await usage(chrome, true)]
  const drawn = new Map()
  const seen = {}
  const photos = []
  let state = 'running'
  for (let nextPhoto = 0, nextUsage = Date.now() + 60000, nextState = 0; state === 'running';) {
    if (Date.now() >= nextPhoto) { photos.push(await photo(desk.page, phone.page, photos.length)); nextPhoto = Date.now() + 30000 }
    if (Date.now() >= nextUsage) { usages.push(await usage(chrome)); nextUsage += 60000 }
    if (Date.now() >= nextState) { state = (await progress())?.state ?? state; nextState = Date.now() + 2000 }
    for (const item of await desk.page.evaluate(drawnNow)) drawn.set(item.join('|'), item)
    note(seen, await desk.page.evaluate(shownNow))
    await sleep(250)
  }
  await sleep(5000)                                // the map's queue shows the last changes
  photos.push(await photo(desk.page, phone.page, photos.length))
  usages.push(await usage(chrome, true))
  const answer = await fetch(`${base}/api/report-file?path=run-progress.jsonl`, { headers: { 'X-EAOS-Token': token } })
  const lines = (await answer.text()).split('\n').filter(Boolean).map((line) => JSON.parse(line))
  const items = [...drawn.values()]
  result.checks.watch = { state, photos, seen, usages, lines: lines.length, glows: items.filter((i) => i[0] === 'glow').length,
    lights: items.filter((i) => i[0] === 'light').length, lights_from: [...new Set(items.filter((i) => i[0] === 'light').map((i) => i[1]))],
    unmatched: unmatched(items, lines).map((i) => i.join(' ')) }
  for (const view of [desk, phone, quiet]) await view.ctx.close()
}

/** Plan 7.3: the page at a given address (TRIAL_BASE, TRIAL_TOKEN, TRIAL_ROUTE) is the live map: its run, its flow,
 * its journey; one screenshot. */
async function look() {
  const { ctx, page } = await open({ width: 1440, lang: 'ar', theme: 'light', route: process.env.TRIAL_ROUTE || '/scan' })
  if (process.env.TRIAL_STAGE) await page.locator(`[data-list-stage="${process.env.TRIAL_STAGE}"]`).click()
  const shot = path.join(shots, `look-${Date.now()}.png`)
  await page.screenshot({ path: shot })
  result.checks.look = { url: page.url().replace(/token=[^&]+/, 'token=<redacted>'), screenshot: shot, ...(await mapFacts(page)),
    ...(await page.evaluate(() => { const run = document.querySelector('[data-run-state]'); return { run_state: run?.getAttribute('data-run-state'), flow: run?.getAttribute('data-flow'), stages: document.querySelectorAll('g[data-stage]').length,
      panel: document.querySelector('[data-hook=scan-stage-panel]')?.parentElement?.textContent ?? '', shots: [...document.querySelectorAll('img[data-shot]')].filter((img) => img.complete && img.naturalWidth > 0).length } })) }
  await ctx.close()
}

/** Plan 7.3: the Studio's own Check button (the freshness chip's sheet, "Re-scan now") opens the live map on the
 * check it started. */
async function button() {
  const { ctx, page } = await open({ width: 1440, lang: 'ar', theme: 'light', route: '/' })
  const before = (await progress())?.run ?? null
  await page.locator('span[data-live] button, span[data-live] [role=button]').first().click()
  await page.locator('[data-fresh-actions=live] button').first().click()
  await page.waitForFunction(() => location.hash.startsWith('#/scan'), null, { timeout: 30000 })
  const started = await until((p) => p && p.run && p.run !== before, 120000)
  await page.waitForSelector('[data-run-state]', { timeout: 30000 })
  const shot = path.join(shots, 'button-scan.png')
  await page.screenshot({ path: shot })
  result.checks.button = { hash: await page.evaluate(() => location.hash.replace(/token=[^&]+/, 'token=<redacted>')), run_before: before, run_started: started?.run ?? null,
    run_state: await page.locator('[data-run-state]').getAttribute('data-run-state'), flow: await page.locator('[data-run-state]').getAttribute('data-flow'), screenshot: shot }
  await ctx.close()
}

try {
  await ({ watch: watchRun, look, button }[process.env.TRIAL_MODE] ?? threeMoments)()
} catch (problem) {
  result.errors.push(String(problem && problem.stack || problem))
} finally {
  await browser.close()
}
fs.writeFileSync(path.join(out, 'browser.json'), JSON.stringify(result, null, 1))
console.log(JSON.stringify({ rows: result.rows.length, failed: result.rows.filter((r) => !r.pass).length, errors: result.errors.length }))
process.exit(0)
