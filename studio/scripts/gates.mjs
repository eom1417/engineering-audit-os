// The Studio's screen gates (DESIGN.md §7), run on the built Studio with a real report's data beside it: every route
// and the gallery at 390×844, 768×1024 and 1440×900, in Arabic and English, light and dark. Each shot must have no
// horizontal overflow (and a layout width equal to the viewport's: an overflowing phone page silently widens it),
// open at scroll 0, have no serious or critical axe violation, 44px touch targets on the phone, no letter-spacing on
// Arabic text, no request outside the Studio's own folder, no script error, and the phone Home within two screens.
// The checks come from the design direction's shoot.mjs; tools/studio_gates.py replaces them once it is on develop.
//
//   npm run build && node scripts/gates.mjs [--data <report>/studio] [--out <dir>] [--only <route-name>] [--quick]
//
// --data: a report's studio/ folder (default $EAOS_MEASURE/FleetManageWeb/studio); --out: where gates.json and the
// screenshots go (default $EAOS_MEASURE/studio-gates); --quick: phone and desktop, light only.
// Playwright and axe-core come from the EAOS toolchain ($EAOS_ENGINE_TOOLS, default ~/.eaos/tools).
import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath, pathToFileURL } from 'node:url'

const require = createRequire(import.meta.url)
const studio = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const shipped = path.resolve(studio, '../eaos/data/studio')
const args = process.argv.slice(2)
const option = (name, fallback) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : fallback }
const tools = process.env.EAOS_ENGINE_TOOLS || path.join(os.homedir(), '.eaos/tools')
const measure = process.env.EAOS_MEASURE || path.join(os.homedir(), '.eaos/dev/measure')
const dataDir = option('--data', path.join(measure, 'FleetManageWeb/studio'))
const outDir = option('--out', path.join(measure, 'studio-gates'))
const only = option('--only', null)
const quick = args.includes('--quick')

const { chromium } = require(path.join(tools, 'node/node_modules/playwright'))
const axeSource = fs.readFileSync(path.join(tools, 'npm/axe-core/node_modules/axe-core/axe.min.js'), 'utf8')
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(tools, 'browsers')

// The site: the shipped Studio with the report's data scripts beside it, as eaos/studio/export.py lays it out.
const site = fs.mkdtempSync(path.join(os.tmpdir(), 'studio-gates-'))
fs.cpSync(shipped, site, { recursive: true })
for (const name of fs.readdirSync(dataDir).filter((n) => n.endsWith('.js'))) fs.copyFileSync(path.join(dataDir, name), path.join(site, name))
const manifest = JSON.parse(fs.readFileSync(path.join(dataDir, 'manifest.json'), 'utf8'))
const cards = JSON.parse(fs.readFileSync(path.join(dataDir, 'cards.json'), 'utf8')).cards
const firstCard = cards.find((c) => c.evidence.length) ?? cards[0]

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2', '.json': 'application/json', '.txt': 'text/plain' }
const server = http.createServer((req, res) => {
  const name = decodeURIComponent((req.url || '/').split('?')[0]).replace(/^\/+/, '') || 'index.html'
  const file = path.join(site, name)
  if (!file.startsWith(site) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); return res.end() }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' })
  fs.createReadStream(file).pipe(res)
})
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
const origin = `http://127.0.0.1:${server.address().port}`

// Routes: the gallery and every section of the shell, plus the shell's overlays (palette, sheet) and stacked views.
const ROUTES = [
  { name: 'gallery', hash: '#/_gallery' },
  { name: 'gallery-matrix', hash: '#/_gallery?view=matrix', viewports: ['desktop'], variants: [['ar', 'light']] },
  { name: 'home', hash: '#/', budget: 2 },
  { name: 'system', hash: '#/system' },
  { name: 'system-focus', hash: `#/system?focus=${encodeURIComponent('src/pages')}` },
  { name: 'problems', hash: '#/problems' },
  { name: 'problem', hash: `#/problems?card=${encodeURIComponent(firstCard.id)}` },
  { name: 'change', hash: '#/change' },
  { name: 'decisions', hash: '#/decisions' },
  { name: 'palette', hash: '#/', open: async (page) => { await page.keyboard.press('Control+k'); await page.keyboard.type('مشاكل') } },
  { name: 'sheet', hash: '#/', open: async (page, vp) => { await page.locator('[data-open="project"]').locator('visible=true').first().click() } },
]
const VIEWPORTS = { phone: { width: 390, height: 844 }, tablet: { width: 768, height: 1024 }, desktop: { width: 1440, height: 900 } }
const VARIANTS = [['ar', 'light'], ['ar', 'dark'], ['en', 'light'], ['en', 'dark']]

fs.rmSync(path.join(outDir, 'shots'), { recursive: true, force: true })
fs.mkdirSync(path.join(outDir, 'shots'), { recursive: true })
const browser = await chromium.launch()
const results = []

async function shoot(route, vp, lang, theme, base) {
  const size = VIEWPORTS[vp]
  const phone = vp === 'phone'
  const name = `${route.name}-${vp}-${lang}-${theme}`
  const ctx = await browser.newContext({ viewport: size, deviceScaleFactor: phone ? 2 : 1, hasTouch: vp !== 'desktop', isMobile: phone, colorScheme: theme })
  const page = await ctx.newPage()
  const external = []
  const own = base.startsWith('file:') ? 'file:' : origin
  await page.route('**/*', (r) => {
    const url = r.request().url()
    if (url.startsWith(own) || url.startsWith('data:')) return r.continue()
    external.push(url); return r.abort()
  })
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
  await page.goto(`${base}?lang=${lang}&theme=${theme}${route.hash}`, { waitUntil: 'load' })
  await page.evaluate(() => document.fonts.ready)
  await page.waitForSelector('main#main', { timeout: 10000 })
  await page.waitForTimeout(250)
  if (route.open) { await route.open(page, vp); await page.waitForTimeout(400) }

  const geo = await page.evaluate(({ isPhone, vpWidth }) => {
    const vw = Math.min(window.innerWidth, vpWidth)
    const visible = (el) => {
      const r = el.getBoundingClientRect()
      if (r.width === 0 && r.height === 0) return null
      const cs = getComputedStyle(el)
      if (cs.visibility === 'hidden' || cs.display === 'none') return null
      return r
    }
    const label = (el) => `${el.tagName.toLowerCase()}.${String(el.className.baseVal ?? el.className).split(' ')[0]}`
    const outside = []
    for (const el of document.body.querySelectorAll('*')) {
      if (el.closest('[data-scroll-x]') && !el.matches('[data-scroll-x]')) continue
      if (el.closest('svg') && el.tagName.toLowerCase() !== 'svg') continue
      if (el.closest('.sr')) continue
      const r = visible(el); if (!r) continue
      if (r.left < -1 || r.right > vw + 1) outside.push(`${label(el)} [${Math.round(r.left)},${Math.round(r.right)}]`)
    }
    const arabicTracking = []
    for (const el of document.body.querySelectorAll('*')) {
      if (![...el.childNodes].some((n) => n.nodeType === 3 && /[؀-ۿ]/.test(n.textContent))) continue
      if (parseFloat(getComputedStyle(el).letterSpacing) > 0) arabicTracking.push(label(el))
    }
    const small = []
    if (isPhone) {
      const sel = 'a[href], button, input, select, textarea, summary, [role="button"], [role="option"], [tabindex]:not([tabindex="-1"])'
      for (const el of document.querySelectorAll(sel)) {
        const r = visible(el); if (!r) continue
        if (getComputedStyle(el).opacity === '0' && el.matches('a[href^="#main"]')) continue // the skip link, 44px when shown
        if (el.closest('[inert]') || el.closest('[aria-hidden="true"]')) continue // behind an open modal
        if (r.width <= 1 && r.height <= 1) continue // visually hidden for screen readers only (React Aria's dismiss button)
        if (r.width < 43.5 || r.height < 43.5) small.push(`${label(el)} ${Math.round(r.width)}x${Math.round(r.height)} "${(el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 30)}"`)
      }
    }
    return { scrollWidth: document.documentElement.scrollWidth, innerWidth: vw, layoutWidth: window.innerWidth, scrollX: window.scrollX, scrollY: window.scrollY,
      height: document.documentElement.scrollHeight, outside: outside.slice(0, 20), outsideCount: outside.length, arabicTracking: arabicTracking.slice(0, 10),
      small: small.slice(0, 30), smallCount: small.length, dir: document.documentElement.dir, theme: document.documentElement.dataset.theme }
  }, { isPhone: phone, vpWidth: size.width })

  // Errors are counted before axe runs: on file:// axe fetches the stylesheets itself, which the page's CSP refuses
  const pageErrors = errors.slice()
  await page.evaluate(axeSource) // evaluated by the harness, so the page's own CSP still forbids inline scripts
  const axe = await page.evaluate(async () => {
    const r = await window.axe.run(document, { resultTypes: ['violations'] })
    return r.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
      .map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, sample: v.nodes.slice(0, 3).map((n) => n.target.join(' ') + ' :: ' + (n.failureSummary || '').split('\n').slice(1, 2).join('')) }))
  })

  const file = path.join(outDir, 'shots', `${name}.png`)
  // The checks ran at the real viewport; the picture grows the viewport to the page so fixed bars sit where they end.
  if (!route.open) await page.setViewportSize({ width: size.width, height: Math.min(Math.max(size.height, geo.height), 12000) })
  await page.waitForTimeout(120)
  await page.screenshot({ path: file, fullPage: !route.open })

  const checks = {
    noHorizontalOverflow: geo.scrollWidth <= geo.innerWidth && geo.layoutWidth === size.width && geo.outsideCount === 0,
    initialScrollZero: route.open ? null : geo.scrollX === 0 && geo.scrollY === 0,
    axeNoSeriousOrCritical: axe.length === 0,
    touchTargets44: phone ? geo.smallCount === 0 : null,
    phoneHeight: route.budget && phone ? geo.height <= route.budget * size.height : null,
    noArabicLetterSpacing: geo.arabicTracking.length === 0,
    noExternalRequests: external.length === 0,
    noScriptErrors: pageErrors.length === 0,
    languageAndTheme: geo.dir === (lang === 'ar' ? 'rtl' : 'ltr') && geo.theme === theme,
  }
  const pass = Object.values(checks).every((v) => v !== false)
  results.push({ shot: path.relative(outDir, file), route: route.name, viewport: vp, lang, theme, pass, checks,
    detail: { scrollWidth: geo.scrollWidth, layoutWidth: geo.layoutWidth, pageHeight: geo.height, outside: geo.outside, arabicTracking: geo.arabicTracking, smallTargets: geo.small, axe, external, errors: pageErrors } })
  console.log(`${pass ? 'PASS' : 'FAIL'} ${name}  h=${geo.height}${pass ? '' : '  ' + JSON.stringify(Object.fromEntries(Object.entries(checks).filter(([, v]) => v === false)))}`)
  if (!pass) console.log('     ' + JSON.stringify({ outside: geo.outside.slice(0, 4), small: geo.small.slice(0, 6), axe: axe.map((a) => `${a.id}: ${a.sample[0]}`), errors: pageErrors.slice(0, 3), external: external.slice(0, 3) }))
  await ctx.close()
}

const base = `${origin}/index.html`
for (const route of ROUTES) {
  if (only && !route.name.startsWith(only)) continue
  for (const vp of route.viewports ?? (quick ? ['phone', 'desktop'] : Object.keys(VIEWPORTS))) {
    for (const [lang, theme] of route.variants ?? (quick ? [['ar', 'light'], ['en', 'light']] : VARIANTS)) await shoot(route, vp, lang, theme, base)
  }
}
// Offline from a file: the same Studio opened with file:// (how a person opens a report folder) still renders.
if (!only) await shoot({ name: 'file-home', hash: '#/' }, 'phone', 'ar', 'light', pathToFileURL(path.join(site, 'index.html')).href)
await browser.close()
server.close()

const source = JSON.parse(fs.readFileSync(path.join(shipped, 'SOURCE.json'), 'utf8')).source_sha256
const summary = {
  generated: new Date().toISOString(), studio_source_sha256: source, data: { project: manifest.project.name, contract: manifest.contract },
  viewports: VIEWPORTS, shots: results.length, passed: results.filter((r) => r.pass).length, complete: !only && !quick, results,
}
if (!only) fs.writeFileSync(path.join(outDir, 'gates.json'), JSON.stringify(summary, null, 1) + '\n')
fs.rmSync(site, { recursive: true, force: true })
console.log(`${summary.passed}/${summary.shots} shots pass every gate${only ? '' : ` -> ${path.join(outDir, 'gates.json')}`}`)
process.exit(summary.passed === summary.shots ? 0 : 1)
