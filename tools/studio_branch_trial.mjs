// The browser half of the branch-control and scan-freshness trial (tools/studio_branch_trial.py). The shipped Studio,
// opened from the live server with its launch token, in a real Chromium. One phase per call (TRIAL_PHASE); git changes a
// phase needs are made here with git as argv, the API calls the page itself does are the page's own. Prints one JSON
// line: {checks: {name: {pass, evidence}}, views: [...]}.
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const fromFolder = (folder) => createRequire(path.join(folder, 'eaos-resolve.js'))
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(process.env.TRIAL_PLAYWRIGHT, '..', '..', 'browsers')
const { chromium } = fromFolder(process.env.TRIAL_PLAYWRIGHT)('playwright')
const { AxeBuilder } = fromFolder(process.env.TRIAL_AXE)('@axe-core/playwright')

const base = process.env.TRIAL_BASE
const token = process.env.TRIAL_TOKEN
const phase = process.env.TRIAL_PHASE
const out = process.env.TRIAL_OUT
const extra = JSON.parse(process.env.TRIAL_EXTRA || '{}')
const shots = path.join(out, 'shots')
fs.mkdirSync(shots, { recursive: true })
const checks = {}
const views = []
const errors = []
const check = (name, pass, evidence) => { checks[name] = { pass: Boolean(pass), evidence: String(evidence).slice(0, 1500) } }
const git = (...args) => execFileSync('git', ['-C', extra.project, ...args], { encoding: 'utf8', env: { ...process.env, GIT_AUTHOR_NAME: 'Owner', GIT_AUTHOR_EMAIL: 'owner@example.com', GIT_COMMITTER_NAME: 'Owner', GIT_COMMITTER_EMAIL: 'owner@example.com' } }).trim()
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa']

const browser = await chromium.launch()

async function open({ width = 1440, height = 900, lang = 'en', theme = 'light', zone, route = '/', storage, phone = width < 768 } = {}) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: phone ? 2 : 1, isMobile: phone, hasTouch: phone,
    colorScheme: theme, timezoneId: zone, locale: lang === 'ar' ? 'ar' : 'en-GB' })
  await ctx.addInitScript(([l, t, s]) => {
    try { localStorage.setItem('eaos.studio', JSON.stringify({ lang: l, theme: t, ...(s || {}) })) } catch { /* fresh */ }
  }, [lang, theme, storage])
  const page = await ctx.newPage()
  page.on('pageerror', (e) => errors.push(`${phase}: ${e}`))
  await page.goto(`${base}#token=${token}`, { waitUntil: 'load' })
  await page.waitForSelector('main#main', { timeout: 20000 })
  await page.waitForFunction(() => document.querySelector('[data-fresh]') !== null, null, { timeout: 30000 })
  if (route !== '/') await page.evaluate((r) => { location.hash = '#' + r }, route)
  await page.waitForTimeout(800)
  return { ctx, page }
}

const freshState = (page) => page.evaluate(() => document.querySelector('[data-fresh]')?.getAttribute('data-fresh'))
async function waitFresh(page, want, ms = 75000, poke) {
  const start = Date.now()
  while (Date.now() - start < ms) {
    const now = await freshState(page)
    if (want.includes(now)) return { state: now, ms: Date.now() - start }
    if (poke) await poke()
    await page.waitForTimeout(500)
  }
  return { state: await freshState(page), ms: null }
}

async function measure(page, width) {
  return page.evaluate((w) => {
    const visible = (el) => { const s = getComputedStyle(el); if (s.display === 'none' || s.visibility === 'hidden') return false; const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1 }
    const interactive = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], [role=checkbox], [role=tab], [tabindex]:not([tabindex="-1"])'
    const scope = [...document.querySelectorAll('main#main, [role=dialog], header')]
    const small = []
    for (const root of scope) for (const el of root.querySelectorAll(interactive)) {
      if (!visible(el) || el.disabled || el.closest('[inert], [aria-hidden="true"]')) continue
      const s = getComputedStyle(el)
      if (el.tagName === 'A' && s.display === 'inline' && [...(el.parentElement?.childNodes ?? [])].some((n) => n.nodeType === 3 && n.textContent.trim())) continue
      let r = el.getBoundingClientRect()
      const label = el.labels && el.labels[0]
      if (label && visible(label)) { const b = label.getBoundingClientRect(); if (b.width * b.height > r.width * r.height) r = b }
      if (r.width < 44 || r.height < 44) small.push(`${el.tagName.toLowerCase()}.${[...el.classList].slice(0, 1).join('')} ${Math.round(r.width)}x${Math.round(r.height)} "${(el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 30)}"`)
    }
    return { layout: document.documentElement.scrollWidth, inner: window.innerWidth, viewport: w, scrollY: window.scrollY, scrollX: window.scrollX, small }
  }, width)
}

async function axe(page) {
  const result = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze()
  return result.violations.filter((v) => ['serious', 'critical'].includes(v.impact)).map((v) => `${v.id} (${v.nodes.length}) ${v.nodes[0]?.target}`)
}

async function api(page, method, route, body) {
  return page.evaluate(async ([m, r, b, t]) => {
    const headers = { 'X-EAOS-Token': t, Accept: 'application/json' }
    if (m === 'POST') {
      const s = await (await fetch('/api/session', { headers })).json()
      Object.assign(headers, { 'Content-Type': 'application/json', 'X-EAOS-CSRF': s.csrf })
    }
    const res = await fetch(r, { method: m, headers, body: m === 'POST' ? JSON.stringify(b || {}) : undefined })
    return { status: res.status, body: await res.json().catch(() => ({})) }
  }, [method, route, body, token])
}

const openScanSheet = async (page) => { await page.click('[data-fresh]'); await page.waitForSelector('[role=dialog]', { timeout: 10000 }); await page.waitForTimeout(400) }
const closeSheet = async (page) => { await page.keyboard.press('Escape'); await page.waitForTimeout(400) }

try {
  if (phase === 'detached') {
    const { ctx, page } = await open({ route: '/branches' })
    await page.waitForSelector('[data-context]', { timeout: 20000 })
    const chip = await page.locator('[data-open=branches]').first().innerText()
    const ctxText = await page.locator('[data-context]').first().innerText()
    check('detached_chip', /Detached HEAD at [0-9a-f]{7}/.test(chip) && /Detached HEAD at [0-9a-f]{12}/.test(ctxText), `chip "${chip}"; context "${ctxText.replace(/\n/g, ' | ')}"`)
    await openScanSheet(page)
    const sheet = await page.locator('[role=dialog]').innerText()
    check('detached_scan_named', /Detached HEAD at [0-9a-f]{12}/.test(sheet) && /[0-9a-f]{40}/.test(sheet), sheet.replace(/\n/g, ' | ').slice(0, 600))
    await page.screenshot({ path: path.join(shots, 'detached-1440-en-light.png') })
    await ctx.close()
  }

  if (phase === 'freshness') {
    // realtime: one page, never reloaded, follows commits, dirt, focus, the interval and a finished run
    const { ctx, page } = await open({ route: '/' })
    await page.evaluate(() => { window.__trialMarker = 'still-the-same-page' })
    const first = await freshState(page)
    git('switch', '-q', 'develop')
    fs.writeFileSync(path.join(extra.project, 'later.js'), 'export const later = 1\n')
    git('add', 'later.js'); git('commit', '-q', '-m', 'a change after the scan')
    const onFocus = await waitFresh(page, ['behind'], 15000, async () => page.evaluate(() => window.dispatchEvent(new Event('focus'))))
    await openScanSheet(page)
    const sheet = await page.locator('[role=dialog]').innerText()
    const fallback = await page.locator('details').first()
    await fallback.locator('summary').click()
    const instruction = await page.locator('[data-instruction]').innerText()
    await page.screenshot({ path: path.join(shots, 'fresh-behind-1440-en-light.png') })
    await closeSheet(page)
    const same = await page.evaluate(() => window.__trialMarker)
    check('behind_without_reload', first === 'fresh' && onFocus.state === 'behind' && sheet.includes('later.js') && same === 'still-the-same-page',
      `before ${first}; after commit + focus: ${onFocus.state} in ${onFocus.ms} ms; sheet lists later.js: ${sheet.includes('later.js')}; page not reloaded: ${same}`)
    check('focus_refresh', onFocus.state === 'behind' && onFocus.ms !== null && onFocus.ms < 15000, `${onFocus.ms} ms after a focus event`)
    const tip = git('rev-parse', 'HEAD')
    check('copy_fallback', instruction.includes(extra.project) && instruction.includes('develop') && instruction.includes(tip) && instruction.includes(extra.scanned) && /audit/.test(instruction) && /Do not change/.test(instruction),
      instruction.replace(/\n/g, ' | '))
    // dirty: a tracked file changed, then the interval alone (no focus, no reload) must show it
    git('reset', '-q', '--hard', 'HEAD~1')
    const back = await waitFresh(page, ['fresh'], 15000, async () => page.evaluate(() => window.dispatchEvent(new Event('focus'))))
    fs.appendFileSync(path.join(extra.project, 'package.json'), '\n')
    const interval = await waitFresh(page, ['dirty'], 75000)
    check('dirty_tree', interval.state === 'dirty', `back to ${back.state}; then a tracked file changed: ${interval.state} after ${interval.ms} ms with no reload or focus`)
    check('interval_refresh', interval.state === 'dirty' && interval.ms !== null && interval.ms <= 70000, `${interval.ms} ms by the 60 s interval alone`)
    await openScanSheet(page)
    await page.screenshot({ path: path.join(shots, 'fresh-dirty-1440-en-light.png') })
    await closeSheet(page)
    git('checkout', '--', 'package.json')
    // a finished run refreshes too: a commit, then a quick run (a fetch of origin) ends before the interval
    fs.writeFileSync(path.join(extra.project, 'later2.js'), 'export const later2 = 1\n')
    git('add', 'later2.js'); git('commit', '-q', '-m', 'another change')
    const started = Date.now()
    const ran = await api(page, 'POST', '/api/branches/fetch', { remote: 'origin' })
    const afterRun = await waitFresh(page, ['behind'], 20000)
    check('run_completion_refresh', ran.status === 200 && afterRun.state === 'behind' && afterRun.ms !== null,
      `fetch run ${ran.body?.run?.id} ${ran.body?.run?.state}; chip behind ${Date.now() - started} ms later (no focus event)`)
    git('reset', '-q', '--hard', 'HEAD~1')
    await waitFresh(page, ['fresh'], 15000, async () => page.evaluate(() => window.dispatchEvent(new Event('focus'))))
    // rewritten: the scanned commit leaves the branch history
    git('commit', '-q', '--amend', '-m', 'first (rewritten)')
    const rewritten = await waitFresh(page, ['rewritten'], 15000, async () => page.evaluate(() => window.dispatchEvent(new Event('focus'))))
    await openScanSheet(page)
    const rewrittenText = await page.locator('[role=dialog]').innerText()
    await page.screenshot({ path: path.join(shots, 'fresh-rewritten-1440-en-light.png') })
    await closeSheet(page)
    check('rewritten', rewritten.state === 'rewritten' && /no longer in this branch/.test(rewrittenText), `${rewritten.state}: ${rewrittenText.split('\n')[1] ?? ''}`)
    git('reset', '-q', '--hard', extra.scanned)
    await waitFresh(page, ['fresh'], 15000, async () => page.evaluate(() => window.dispatchEvent(new Event('focus'))))
    // branch switch in the person's own folder
    git('switch', '-q', 'main')
    const other = await waitFresh(page, ['other_branch'], 15000, async () => page.evaluate(() => window.dispatchEvent(new Event('focus'))))
    await openScanSheet(page)
    const otherText = await page.locator('[role=dialog]').innerText()
    await page.screenshot({ path: path.join(shots, 'fresh-other-branch-1440-en-light.png') })
    await closeSheet(page)
    check('branch_switch', other.state === 'other_branch' && otherText.includes('develop') && otherText.includes('main'), `${other.state}: ${otherText.split('\n').slice(0, 3).join(' | ')}`)
    git('switch', '-q', 'develop')
    await waitFresh(page, ['fresh'], 15000, async () => page.evaluate(() => window.dispatchEvent(new Event('focus'))))
    await ctx.close()
  }

  if (phase === 'legacy') {
    const { ctx, page } = await open({ route: '/' })
    const state = await waitFresh(page, ['legacy'], 15000)
    await openScanSheet(page)
    const text = await page.locator('[role=dialog]').innerText()
    const rescan = await page.locator('[data-fresh-actions=live] button').count()
    await page.screenshot({ path: path.join(shots, 'fresh-legacy-1440-en-light.png') })
    check('legacy', state.state === 'legacy' && /Older report/.test(await page.locator('[data-fresh]').innerText()) && /Not recorded \(older report\)/.test(text) && rescan > 0,
      `chip ${state.state}; sheet: ${text.split('\n').slice(0, 4).join(' | ')}; Re-scan button: ${rescan}`)
    await ctx.close()
  }

  if (phase === 'rescan') {
    // Re-scan now, from the sheet, through the live command centre; saved, running, done; the report refreshes
    const { ctx, page } = await open({ route: '/' })
    await page.evaluate(() => { window.__trialMarker = 'same' })
    const builtBefore = (await api(page, 'GET', '/api/freshness')).body.freshness.report_built
    await openScanSheet(page)
    const seen = new Set()
    await page.locator('[data-fresh-actions=live] button').first().click()
    const start = Date.now()
    let runId = null
    while (Date.now() - start < 900000) {
      const st = await page.evaluate(() => document.querySelector('[data-run-state]')?.getAttribute('data-run-state'))
      if (st) seen.add(st)
      runId ??= await page.evaluate(() => document.querySelector('[data-run-state] a')?.getAttribute('href'))
      if (['done', 'failed', 'stopped'].includes(st)) break
      await page.waitForTimeout(500)
    }
    await page.screenshot({ path: path.join(shots, 'rescan-done-1440-en-light.png') })
    await closeSheet(page)
    const after = await waitFresh(page, ['fresh'], 30000, async () => page.evaluate(() => window.dispatchEvent(new Event('focus'))))
    const builtAfter = (await api(page, 'GET', '/api/freshness')).body.freshness.report_built
    check('rescan_roundtrip', seen.has('done') && (seen.has('running') || seen.has('queued')) && after.state === 'fresh' && builtAfter !== builtBefore && (await page.evaluate(() => window.__trialMarker)) === 'same',
      `states seen ${[...seen].join(',')}; run link ${runId}; ${Math.round((Date.now() - start) / 1000)} s; freshness ${after.state}; report built ${builtBefore} -> ${builtAfter}; no reload`)
    await ctx.close()
  }

  if (phase === 'rescan_branch') {
    // Analyse and re-scan another branch from the switcher, then come back without a scan
    const { ctx, page } = await open({ route: '/' })
    const before = git('symbolic-ref', '--short', 'HEAD')
    await page.click('[data-open=branches]')
    await page.waitForSelector(`[data-branch="${extra.branch}"] button`, { timeout: 20000 })
    await page.locator(`[data-branch="${extra.branch}"] button`).nth(1).click()
    const start = Date.now()
    let st = null
    const seen = new Set()
    while (Date.now() - start < 900000) {
      st = await page.evaluate(() => document.querySelector('[role=dialog] [data-run-state]')?.getAttribute('data-run-state'))
      if (st) seen.add(st)
      if (['done', 'failed', 'stopped'].includes(st)) break
      await page.waitForTimeout(500)
    }
    await page.screenshot({ path: path.join(shots, 'rescan-branch-1440-en-light.png') })
    await closeSheet(page)
    const chip = await page.locator('[data-open=branches]').first().innerText()
    const ctxNow = (await api(page, 'GET', '/api/context')).body.context
    const fresh = (await api(page, 'GET', '/api/freshness')).body.freshness
    check('rescan_branch', st === 'done' && chip.includes(extra.branch) && ctxNow.analysis.branch === extra.branch && ctxNow.checkout.branch === before && fresh.scanned_branch === extra.branch && fresh.state === 'fresh',
      `states ${[...seen].join(',')}; chip "${chip}"; analysis ${ctxNow.analysis.branch}; checkout ${ctxNow.checkout.branch} (was ${before}); scanned ${fresh.scanned_branch} ${fresh.state}`)
    // back to develop: analysis only, its own scan comes back
    await page.click('[data-open=branches]')
    await page.waitForSelector(`[data-branch="${extra.back}"] button`, { timeout: 20000 })
    await page.locator(`[data-branch="${extra.back}"] button`).first().click()
    await page.waitForTimeout(2500)
    await closeSheet(page)
    const backCtx = (await api(page, 'GET', '/api/context')).body.context
    const chipBack = await page.locator('[data-open=branches]').first().innerText()
    check('ui_selected_branch_report_consistency', backCtx.analysis.branch === extra.back && chipBack.includes(extra.back) && backCtx.report.branch === extra.back,
      `chip "${chipBack}"; analysis ${backCtx.analysis.branch}; report of ${backCtx.report.branch}; checkout ${backCtx.checkout.branch}`)
    await ctx.close()
  }

  if (phase === 'zones') {
    const want = (iso, zone) => {
      const d = new Date(iso)
      const clock = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: zone, hourCycle: 'h23', timeZoneName: 'short' }).format(d)
      return clock
    }
    for (const [zone, name, offset] of [['Asia/Dubai', 'device_time_zone_non_utc', /GMT\+4/], ['Asia/Kolkata', 'half_hour_offset_time_zone', /GMT\+5:30/]]) {
      const { ctx, page } = await open({ zone, route: '/' })
      await openScanSheet(page)
      const times = await page.$$eval('[role=dialog] time[datetime]', (all) => all.map((t) => ({ iso: t.getAttribute('datetime'), title: t.getAttribute('title'), text: t.textContent })))
      const good = times.length >= 2 && times.every((t) => t.title.includes(want(t.iso, zone)) && offset.test(t.title) && /ago|now|minute|hour/.test(t.text))
      await page.locator('[role=dialog] time[datetime]').first().click()
      const tapped = await page.locator('[role=dialog] time[datetime]').first().innerText()
      check(name, good && offset.test(tapped), `${zone}: ${times.map((t) => `${t.iso} -> "${t.text}" / "${t.title}"`).join('; ')}; tap shows "${tapped}"`)
      await page.screenshot({ path: path.join(shots, `zone-${zone.replace('/', '-')}-1440-en-light.png`) })
      await ctx.close()
    }
    // the Settings override, remembered across a reload
    const { ctx, page } = await open({ zone: 'Asia/Dubai', route: '/' })
    await page.click('[data-open=project]')
    await page.waitForSelector('select[data-zone]')
    await page.selectOption('select[data-zone]', 'America/St_Johns')
    await closeSheet(page)
    await page.reload({ waitUntil: 'load' })
    await page.waitForSelector('[data-fresh]', { timeout: 20000 })
    await openScanSheet(page)
    const titles = await page.$$eval('[role=dialog] time[datetime]', (all) => all.map((t) => t.getAttribute('title')))
    const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('eaos.studio') || '{}').zone)
    check('time_zone_override_persisted', saved === 'America/St_Johns' && titles.length > 0 && titles.every((t) => /GMT-2:30|NDT|GMT-3:30|NST/.test(t)), `saved ${saved}; titles ${titles.join(' / ')}`)
    await closeSheet(page)
    // every time on the pages that show times: relative with the exact zoned time, never "UTC"
    const seen = []
    let utc = 0
    for (const route of ['/', '/runs', '/branches', `/runs/${extra.run}`]) {
      await page.evaluate((r) => { location.hash = '#' + r }, route)
      await page.waitForTimeout(2500)
      const found = await page.$$eval('main time[datetime], [role=dialog] time[datetime], main [title]', (all) => all.map((t) => ({ text: t.textContent.trim().slice(0, 40), title: t.getAttribute('title') || '' })))
      utc += await page.evaluate(() => (document.querySelector('main')?.innerText.match(/\bUTC\b/g) || []).length)
      seen.push(`${route}: ${found.filter((f) => /GMT|N[DS]T/.test(f.title)).length} zoned`)
    }
    check('relative_and_exact_zoned_times_everywhere', utc === 0 && seen.every((s) => !s.endsWith(' 0 zoned')), `${seen.join('; ')}; "UTC" shown ${utc} times`)
    await page.screenshot({ path: path.join(shots, 'zone-override-run-1440-en-light.png') })
    await ctx.close()
  }

  if (phase === 'snapshot') {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 })
    const page = await ctx.newPage()
    await page.goto('file://' + extra.snapshot, { waitUntil: 'load' })
    await page.waitForSelector('[data-fresh]', { timeout: 20000 })
    await openScanSheet(page)
    const text = await page.locator('[role=dialog]').innerText()
    const mode = await page.evaluate(() => document.querySelector('[data-fresh-actions]')?.getAttribute('data-fresh-actions'))
    await page.screenshot({ path: path.join(shots, 'snapshot-390-en-light.png') })
    check('static_snapshot', mode === 'snapshot' && /read-only/i.test(text) && /Open live Studio/.test(text) && /eaos studio/.test(text), `${mode}: ${text.replace(/\n/g, ' | ').slice(0, 500)}`)
    await ctx.close()
  }

  if (phase === 'ui') {
    // run links, governance, keyboard, error recovery; on the real live page
    const { ctx, page } = await open({ route: `/runs/${extra.run}` })
    await page.waitForSelector('[data-run-branches]', { timeout: 20000 })
    const runLine = await page.locator('[data-run-branches]').innerText()
    const link = await page.locator('[data-run-branches] a').first().getAttribute('href')
    await page.screenshot({ path: path.join(shots, 'run-branch-1440-en-light.png') })
    check('ui_task_run_branch_links', runLine.includes(extra.workBranch) && link && link.includes('branches'), `"${runLine}" link ${link}`)
    // keyboard: Tab to the branch chip, Enter opens the switcher, Escape closes and returns focus
    await page.evaluate(() => { location.hash = '#/branches' })
    await page.waitForSelector('[data-context]', { timeout: 20000 })
    await page.locator('[data-open=branches]').first().focus()
    await page.keyboard.press('Enter')
    const opened = await page.waitForSelector('[role=dialog]', { timeout: 5000 }).then(() => true, () => false)
    await page.keyboard.press('Escape')
    await page.waitForTimeout(400)
    const back = await page.evaluate(() => document.activeElement?.getAttribute('data-open'))
    let tabs = 0, reached = false
    for (; tabs < 60 && !reached; tabs++) { await page.keyboard.press('Tab'); reached = await page.evaluate(() => document.activeElement?.textContent?.trim() === 'Details') }
    if (reached) await page.keyboard.press('Enter')
    const drawer = await page.waitForSelector('[role=dialog]', { timeout: 8000 }).then(() => true, () => false)
    const m = await measure(page, 1440)
    await page.screenshot({ path: path.join(shots, 'keyboard-drawer-1440-en-light.png') })
    check('keyboard', opened && back === 'branches' && reached && drawer, `chip Enter opens: ${opened}; focus back on chip: ${back}; Details reached by Tab in ${tabs}; drawer: ${drawer}; small targets in drawer ${m.small.length}`)
    await closeSheet(page)
    // error recovery: a stale merge preview says so and shows the new one; the page keeps working
    const rec = extra.stale
    if (rec) {
      await page.evaluate((b) => { location.hash = `#/branches?show=all&b=${encodeURIComponent('refs/heads/' + b)}` }, rec.branch)
      await page.waitForSelector('[role=dialog] button:has-text("Preview the merge")', { timeout: 20000 })
      await page.click('[role=dialog] button:has-text("Preview the merge")')
      await page.waitForSelector('[data-merge-preview]', { timeout: 20000 })
      execFileSync('git', ['-C', extra.project, 'update-ref', `refs/heads/${rec.branch}`, rec.moveTo], { encoding: 'utf8' })
      const box = page.locator('[data-merge-preview] input[type=checkbox]')
      if (await box.count()) await box.check()
      await page.click('[data-merge-preview] button:has-text("Confirm the merge")')
      const stale = await page.waitForSelector('[data-merge-preview] [role=alert]', { timeout: 15000 }).then(async (el) => el.innerText(), () => '')
      const head = await page.evaluate(() => document.querySelector('[data-merge-preview] dl, [data-merge-preview]')?.innerText ?? '')
      await page.screenshot({ path: path.join(shots, 'error-recovery-stale-1440-en-light.png') })
      check('ui_error_recovery', /moved after the preview/.test(stale) && head.includes(rec.moveTo.slice(0, 12)), `alert "${stale}"; new preview shows ${rec.moveTo.slice(0, 12)}: ${head.includes(rec.moveTo.slice(0, 12))}`)
      await closeSheet(page)
    }
    // governance: the plan step and the card act directly (the preview sheet with a live start), copy only inside it
    const direct = []
    for (const route of extra.directRoutes || []) {
      await page.evaluate((r) => { location.hash = '#' + r }, route)
      await page.waitForTimeout(2500)
      const button = page.locator('[data-direct]').first()
      const has = await button.count()
      let live = false
      if (has) { await button.click(); live = await page.waitForSelector('[role=dialog]', { timeout: 8000 }).then(async () => !/read-only|snapshot/i.test(await page.locator('[role=dialog]').innerText()), () => false); await closeSheet(page) }
      direct.push(`${route}: direct ${has ? 'yes' : 'no'}, opens live preview ${live}`)
    }
    const freshChip = await page.locator('[data-fresh]').first().getAttribute('data-fresh')
    check('governance', direct.every((d) => d.includes('direct yes') && d.includes('preview true')) && freshChip, `${direct.join('; ')}; freshness shown live: ${freshChip}`)
    await ctx.close()
  }

  if (phase === 'realtime_branches') {
    // the Branches page follows a branch created outside the Studio without a reload (focus refresh)
    const { ctx, page } = await open({ route: '/branches?show=all' })
    await page.waitForSelector('[data-context]', { timeout: 20000 })
    await page.evaluate(() => { window.__trialMarker = 'same' })
    git('branch', extra.newBranch, 'develop')
    const start = Date.now()
    let shown = false
    while (!shown && Date.now() - start < 20000) {
      await page.evaluate(() => window.dispatchEvent(new Event('focus')))
      await page.waitForTimeout(700)
      shown = await page.locator(`[data-branch="${extra.newBranch}"]`).count() > 0
    }
    check('ui_realtime_state', shown && (await page.evaluate(() => window.__trialMarker)) === 'same', `new branch ${extra.newBranch} shown after ${Date.now() - start} ms without a reload: ${shown}`)
    git('branch', '-D', extra.newBranch)
    await ctx.close()
  }

  if (phase === 'views') {
    for (const width of [390, 768, 1440]) for (const lang of ['ar', 'en']) for (const theme of ['light', 'dark']) {
      const height = width === 390 ? 844 : width === 768 ? 1024 : 900
      const { ctx, page } = await open({ width, height, lang, theme, route: '/branches' })
      await page.waitForSelector('[data-context]', { timeout: 20000 })
      await page.evaluate(() => window.scrollTo(0, 0))
      await page.waitForTimeout(600)
      const m = await measure(page, width)
      const violations = await axe(page)
      const shot = path.join(shots, `branches-${width}-${lang}-${theme}.png`)
      await page.screenshot({ path: shot, fullPage: width === 390 })
      // the drawer and the scan sheet are measured in the same view
      await page.locator('button:has-text("Details"), button:has-text("التفاصيل")').first().click()
      await page.waitForSelector('[role=dialog]', { timeout: 10000 })
      await page.waitForTimeout(1200)
      const md = await measure(page, width)
      const vd = await axe(page)
      await page.screenshot({ path: path.join(shots, `branches-drawer-${width}-${lang}-${theme}.png`) })
      await closeSheet(page)
      await openScanSheet(page)
      const ms = await measure(page, width)
      const vs = await axe(page)
      await page.screenshot({ path: path.join(shots, `scan-sheet-${width}-${lang}-${theme}.png`) })
      await closeSheet(page)
      const small = [...m.small, ...md.small, ...ms.small]
      const axeAll = [...violations, ...vd, ...vs]
      views.push({ viewport: width, lang, theme, screenshot: shot, width_equals_viewport: m.layout === width && md.layout === width && ms.layout === width,
        initial_scroll_zero: m.scrollY === 0 && m.scrollX === 0, axe_violations: axeAll.length, axe: axeAll, small_targets: small.length, small: small.slice(0, 12),
        pass: m.layout === width && m.scrollY === 0 && axeAll.length === 0 && small.length === 0 })
      await ctx.close()
    }
  }
} catch (problem) {
  errors.push(`${phase}: ${problem?.stack ?? problem}`)
} finally {
  await browser.close()
}
console.log(JSON.stringify({ phase, checks, views, errors }))
