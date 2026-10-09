// The browser half of the real command-centre trial (tools/studio_trial.py, indicator F15, NS46.T11 and NS46.T17).
// One phase per call (EAOS_TRIAL_PHASE): scan, decisions, persist, fix or controls. It opens the live Studio the
// Python half started (EAOS_TRIAL_WORK/server-main.json: its port and launch token) in Chromium and does what the
// owner does, by clicking and typing only: nothing is posted to the API from here. What only the server can tell
// (consent recorded, an answer saved exactly, the guards of accept and undo) it asks the Python half
// (`studio_trial.py check …`), at the moment it needs to know. Writes EAOS_TRIAL_OUT/phases/<phase>.json with its
// screenshots (EAOS_TRIAL_OUT/shots) and, for the scan and the fix, a video of the whole phase.
// Playwright comes from the EAOS toolchain ($EAOS_ENGINE_TOOLS, default ~/.eaos/tools), as in studio/scripts/live.mjs.
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const tools = process.env.EAOS_ENGINE_TOOLS || path.join(os.homedir(), '.eaos/tools')
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(tools, 'browsers')
const { chromium } = require(path.join(tools, 'node/node_modules/playwright'))

const phase = process.env.EAOS_TRIAL_PHASE
const work = process.env.EAOS_TRIAL_WORK
const out = process.env.EAOS_TRIAL_OUT
const given = JSON.parse(fs.readFileSync(process.env.EAOS_TRIAL_INPUT, 'utf8'))
const context = JSON.parse(fs.readFileSync(path.join(work, 'context.json'), 'utf8'))
const server = () => JSON.parse(fs.readFileSync(path.join(work, 'server-main.json'), 'utf8'))
const shots = path.join(out, 'shots')
const videos = path.join(out, 'videos')
fs.mkdirSync(shots, { recursive: true })
fs.mkdirSync(path.join(out, 'phases'), { recursive: true })

const result = { phase, ok: false, errors: [], screenshots: [], states_seen: {}, started_at: new Date().toISOString() }
const lang = given.lang || context.lang || 'ar'
const STATES = JSON.parse(fs.readFileSync(path.resolve(path.dirname(new URL(import.meta.url).pathname), '../../docs/studio-actions.json'), 'utf8')).lifecycle.states
const log = (...words) => console.log(new Date().toISOString(), phase, ...words)

/** What only the server side can see, from tools/studio_trial.py check. */
function check(what, ...args) {
  const text = execFileSync(process.env.EAOS_TRIAL_PYTHON, [process.env.EAOS_TRIAL_TOOL, 'check', work, what, ...args.map(String)], { encoding: 'utf8', timeout: 120000 })
  return JSON.parse(text.trim().split('\n').pop())
}

const browser = await chromium.launch()

/** A tab on the live Studio, opened the way `eaos studio` opens it (its address with #token=), in a language and theme. */
async function open({ width = 390, height = 844, theme = 'light', record = false, language = lang } = {}) {
  const phone = width < 600
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: phone ? 2 : 1, isMobile: phone, hasTouch: phone,
    colorScheme: theme, ...(record ? { recordVideo: { dir: videos, size: { width, height } } } : {}) })
  await ctx.addInitScript(([l, t]) => {
    if (!sessionStorage.getItem('eaos.trial.prefs')) {
      localStorage.setItem('eaos.studio', JSON.stringify({ ...JSON.parse(localStorage.getItem('eaos.studio') || '{}'), lang: l, theme: t }))
      sessionStorage.setItem('eaos.trial.prefs', '1')
    }
  }, [language, theme])
  const page = await ctx.newPage()
  page.on('pageerror', (e) => result.errors.push(`page error: ${String(e).slice(0, 300)}`))
  const info = server()
  await page.goto(`${info.base}?lang=${language}&theme=${theme}#token=${info.token}`, { waitUntil: 'load' })
  await page.waitForSelector('main#main', { timeout: 30000 })
  return { ctx, page }
}

async function go(page, hash) {
  await page.evaluate((h) => { location.hash = h }, hash)
  await page.waitForTimeout(600)
}

let shot = 0
async function snap(page, name) {
  shot += 1
  const file = path.join(shots, `${phase}-${String(shot).padStart(2, '0')}-${name}.png`)
  try { await page.screenshot({ path: file }); result.screenshots.push(file) } catch (e) { result.errors.push(`screenshot ${name}: ${e}`) }
  return file
}

/** The run page's state, and the words its chip shows for it (recorded for "every state understood"). */
async function runState(page) {
  const seen = await page.evaluate(() => {
    const head = document.querySelector('[data-run-state]')
    if (!head) return null
    const chip = [...head.children].find((el, i) => i > 0 && el.textContent.trim()) || head
    return { state: head.getAttribute('data-run-state'), text: chip.textContent.trim() }
  })
  if (seen?.state) result.states_seen[seen.state] ??= seen.text
  return seen?.state ?? null
}

async function runId(page) {
  const hash = await page.evaluate(() => location.hash)
  const found = /#\/runs\/([^?/]+)/.exec(hash)
  return found ? decodeURIComponent(found[1]) : null
}

/** Waits on the run page until the run is in one of `states` (or the time is up); returns its state. */
async function until(page, run, states, ms, onEach) {
  const end = Date.now() + ms
  let state = null
  while (Date.now() < end) {
    if ((await runId(page)) !== run) await go(page, `#/runs/${encodeURIComponent(run)}`)
    state = await runState(page)
    if (states.includes(state)) return state
    if (onEach) { const stop = await onEach(state); if (stop) return state }
    await page.waitForTimeout(2000)
  }
  return state
}

/** Press a button, counting it as one of the owner's actions. */
let actions = 0
async function press(locator, what) {
  await locator.waitFor({ state: 'visible', timeout: 60000 })
  const end = Date.now() + 120000
  while (await locator.isDisabled() && Date.now() < end) await locator.page().waitForTimeout(500)
  await locator.click()
  actions += 1
  log('pressed', what)
}

/** The preview sheet: wait for its preview, choose the assistant when asked, confirm. Returns the new run's id. */
async function confirmPreview(page, assistant) {
  const start = page.locator('[data-confirm="start"]')
  await start.waitFor({ state: 'visible', timeout: 120000 })
  const end = Date.now() + 120000
  while (await start.isDisabled() && Date.now() < end) {
    const problem = await page.locator('[role="dialog"] [role="alert"], [role="dialog"] [data-kind="error"]').first().textContent().catch(() => null)
    if (problem) throw new Error(`the preview failed: ${problem}`)
    await page.waitForTimeout(500)
  }
  if (assistant) {
    const choice = page.locator('[role="dialog"] [role="radio"], [role="dialog"] [aria-pressed]').filter({ hasText: assistant })
    if (await choice.count()) {
      if ((await choice.first().getAttribute('aria-checked')) !== 'true' && (await choice.first().getAttribute('aria-pressed')) !== 'true') await press(choice.first(), `assistant ${assistant}`)
      await page.waitForTimeout(1500)
      while (await start.isDisabled() && Date.now() < end + 60000) await page.waitForTimeout(500)
    }
    result.assistant_shown = await page.locator('[role="dialog"]').innerText().then((t) => t.includes(assistant)).catch(() => false)
  }
  await snap(page, 'preview')
  await press(start, 'confirm')
  await page.waitForFunction(() => /#\/runs\/[^/]+/.test(location.hash), null, { timeout: 60000 })
  return runId(page)
}

const isBlue = (rgb) => {
  const [r, g, b] = (rgb.match(/\d+(\.\d+)?/g) || []).map(Number)
  return b !== undefined && b > r + 40 && b >= g
}

/** One report decision card on the Decisions page. */
const card = (page, id) => page.locator(`[data-hook="decision:${id}"]`)
async function savedOf(page, id, ms = 30000) {
  const status = card(page, id).locator('[data-hook="decision-status"][data-saved]')
  try { await status.waitFor({ state: 'attached', timeout: ms }) } catch { return null }
  return { saved: await status.getAttribute('data-saved'), text: (await status.innerText()).trim() }
}

// ---------------------------------------------------------------- the phases

async function scan() {
  const began = Date.now()
  const { ctx, page } = await open({ record: true })
  await snap(page, 'empty')
  const button = page.locator('[data-start-action="audit"]').first()
  await button.waitFor({ state: 'visible', timeout: 60000 })
  result.first_action_s = Math.round((Date.now() - began) / 100) / 10
  await press(button, 'check the project')
  const preview = page.locator('[data-confirm="preview"]')
  if (await preview.count()) await press(preview, 'preview')
  const run = await confirmPreview(page, null)
  result.audit_run = run
  log('audit run', run)
  // The check may first ask which branch to work on: answered in the inbox, with the branch the copy has checked out
  const end = Date.now() + Number(given.limit_ms || 3 * 3600 * 1000) - 300000
  let state = null
  result.scan_questions = []
  while (Date.now() < end) {
    state = await until(page, run, ['done', 'failed', 'stopped', 'waiting_for_person'], Math.max(1000, end - Date.now()))
    if (state !== 'waiting_for_person') break
    await go(page, '#/decisions')
    const box = page.locator(`[data-hook^="question:${run}-q"]`).first()
    await box.waitFor({ state: 'visible', timeout: 60000 })
    const options = await box.locator('[data-option]').evaluateAll((els) => els.map((el) => ({ id: el.getAttribute('data-option'), recommended: el.hasAttribute('data-recommended') })))
    const choice = options.find((o) => o.id === given.branch) || options.find((o) => o.recommended) || options[0]
    result.scan_questions.push({ question: (await box.getAttribute('data-hook')).slice('question:'.length), text: (await box.innerText()).slice(0, 400), options, answered: choice?.id })
    await snap(page, 'scan-question')
    if (!choice) throw new Error('the check asked a question with no option')
    await press(box.locator(`[data-option="${choice.id}"]`), `answer ${choice.id}`)
    await page.waitForTimeout(2000)
    await go(page, `#/runs/${encodeURIComponent(run)}`)
  }
  await snap(page, `audit-${state}`)
  result.audit_state = state
  if (state !== 'done') throw new Error(`the check ended ${state}`)
  // The Studio fills in by itself: no reload, the report appears on Home and the cards on Problems
  await go(page, '#/problems')
  try {
    await page.waitForSelector('input[type="checkbox"][aria-label]', { timeout: 120000 })
    result.filled_without_reload = true
  } catch {
    result.filled_without_reload = false
    result.errors.push('the Studio did not show the new report without a reload')
    await page.reload()
    await page.waitForSelector('input[type="checkbox"][aria-label]', { timeout: 60000 })
  }
  await snap(page, 'problems')
  await go(page, '#/')
  await snap(page, 'home')
  result.audit_done = true
  result.actions = actions
  await ctx.close()
  result.video = await page.video()?.path()
}

async function decisions() {
  const picked = given.picked || {}
  const { ctx, page } = await open({ width: 1440, height: 900 })
  await go(page, '#/decisions')
  await page.waitForSelector('[data-hook^="decision:"]', { timeout: 60000 })
  await page.waitForFunction(() => document.querySelectorAll('[data-hook^="decision:"] [data-option]:not([disabled])').length > 0, null, { timeout: 60000 })
  await snap(page, 'inbox')

  // The recommendation (blue, labelled) is not a selection; choosing another option keeps both visible and apart
  if (picked.recommended) {
    const row = picked.recommended
    const box = card(page, row.id)
    await box.scrollIntoViewIfNeeded()
    const rec = box.locator(`[data-option="${row.recommended}"]`)
    const out = { decision: row.id, recommended: row.recommended }
    out.recommended_blue = isBlue(await rec.evaluate((el) => getComputedStyle(el).backgroundColor))
    out.recommended_tag = (await rec.getAttribute('data-recommended')) !== null && /Recommended|موصى|المقترح|ننصح/.test(await rec.innerText())
    out.recommended_text = await rec.innerText()
    out.nothing_selected_before = (await box.locator('[aria-pressed="true"]').count()) === 0
    const other = row.options.find((o) => o !== row.recommended)
    await snap(page, 'recommended-before')
    await press(box.locator(`[data-option="${other}"]`), 'a non-recommended option')
    const saved = await savedOf(page, row.id)
    out.saved = Boolean(saved)
    out.chosen = saved?.saved ?? null
    out.recommendation_still_shown = (await box.innerText()).length > 0 && (await box.locator('[class*="Rec"], [class*="rec"]').count()) > 0
    await snap(page, 'recommended-after')
    result.recommended = out
  }

  // A typed answer, unrelated to the options: saved exactly, queued, still there after a reload
  if (picked.custom) {
    const row = picked.custom
    const box = card(page, row.id)
    await box.scrollIntoViewIfNeeded()
    await press(box.locator('[data-write-answer]'), 'write a different answer')
    await box.locator('textarea').fill(context.answers.decision)
    await press(box.locator('[data-send-answer]'), 'send the typed answer')
    const saved = await savedOf(page, row.id)
    await snap(page, 'custom-saved')
    const out = { decision: row.id, saved: saved?.saved === 'text', shown: saved?.text?.includes(context.answers.decision.split('\n')[0]) }
    await page.reload()
    await page.waitForSelector('main#main')
    await go(page, '#/decisions')
    const again = await savedOf(page, row.id, 60000)
    out.after_reload = again?.saved === 'text' && again.text.includes(context.answers.decision.split('\n')[0])
    await snap(page, 'custom-after-reload')
    result.custom = out
  }

  // The keyboard alone: Tab to "write a different answer", Enter, type, Tab to send, Enter
  if (picked.keyboard) {
    const row = picked.keyboard
    const out = { decision: row.id, keyboard_only: true }
    await page.mouse.click(5, 5)
    await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0) })
    let found = false
    for (let i = 0; i < 600 && !found; i++) {
      await page.keyboard.press('Tab')
      found = await page.evaluate((id) => {
        const el = document.activeElement
        return Boolean(el && el.hasAttribute('data-write-answer') && el.closest(`[data-hook="decision:${id}"]`))
      }, row.id)
    }
    out.reached_by_tab = found
    if (found) {
      out.focus_visible = await page.evaluate(() => {
        const style = getComputedStyle(document.activeElement)
        return (style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0) || style.boxShadow !== 'none'
      })
      await snap(page, 'keyboard-focus')
      await page.keyboard.press('Enter')
      actions += 1
      await page.waitForTimeout(400)
      await page.keyboard.type(context.answers.keyboard)
      for (let i = 0; i < 6; i++) {
        await page.keyboard.press('Tab')
        if (await page.evaluate(() => document.activeElement?.hasAttribute('data-send-answer'))) break
      }
      await page.keyboard.press('Enter')
      actions += 1
      const saved = await savedOf(page, row.id)
      out.saved = saved?.saved === 'text' && saved.text.includes(context.answers.keyboard)
      await snap(page, 'keyboard-saved')
    }
    result.keyboard = out
  }

  // A send that fails (the connection drops): the error shows, the draft stays, nothing is marked answered; then it goes
  if (picked.draft) {
    const row = picked.draft
    const box = card(page, row.id)
    const out = { decision: row.id, how: 'the browser connection to the answer endpoint was dropped once (Playwright route abort)' }
    await box.scrollIntoViewIfNeeded()
    await press(box.locator('[data-write-answer]'), 'write a different answer')
    await box.locator('textarea').fill(context.answers.draft)
    let dropped = 0
    await page.route(`**/api/decisions/${encodeURIComponent(row.id)}/answer`, (route) => { dropped += 1; return route.abort('connectionreset') })
    await press(box.locator('[data-send-answer]'), 'send (fails)')
    await page.waitForTimeout(1500)
    out.dropped = dropped
    out.failed_visibly = await box.locator('[role="alert"]').isVisible().catch(() => false)
    out.not_marked_answered = (await box.locator('[data-hook="decision-status"][data-saved]').count()) === 0
    out.draft_kept = (await box.locator('textarea').inputValue()) === context.answers.draft
    await snap(page, 'draft-failed')
    await page.unroute(`**/api/decisions/${encodeURIComponent(row.id)}/answer`)
    await press(box.locator('[data-send-answer]'), 'send again')
    const saved = await savedOf(page, row.id)
    out.saved_after_retry = saved?.saved === 'text'
    result.draft = out
  }

  // The same questions, the same answers, in the other language
  const ids = async () => (await page.locator('[data-hook^="decision:"]').evaluateAll((els) => els.map((el) => el.getAttribute('data-hook')))).sort()
  const answeredIds = async () => (await page.locator('[data-hook^="decision:"]:has([data-saved])').evaluateAll((els) => els.map((el) => el.getAttribute('data-hook')))).sort()
  const first = { ids: await ids(), answered: await answeredIds() }
  await ctx.close()
  const other = lang === 'ar' ? 'en' : 'ar'
  const second = await open({ width: 390, height: 844, language: other, theme: 'dark' })
  await go(second.page, '#/decisions')
  await second.page.waitForSelector('[data-hook^="decision:"]', { timeout: 60000 })
  await second.page.waitForTimeout(2500)
  const then = { ids: (await second.page.locator('[data-hook^="decision:"]').evaluateAll((els) => els.map((el) => el.getAttribute('data-hook')))).sort(),
    answered: (await second.page.locator('[data-hook^="decision:"]:has([data-saved])').evaluateAll((els) => els.map((el) => el.getAttribute('data-hook')))).sort() }
  await snap(second.page, `inbox-${other}`)
  result.languages = { first: lang, second: other, same_cards: JSON.stringify(first.ids) === JSON.stringify(then.ids),
    answered_in_both: first.answered.length > 0 && JSON.stringify(first.answered) === JSON.stringify(then.answered), answered: first.answered }
  await second.ctx.close()
  result.actions = actions
}

async function persist() {
  // After the server restarted (a new launch token): the owner's answers are still there, in both widths
  const { ctx, page } = await open({ width: 390, height: 844 })
  await go(page, '#/decisions')
  await page.waitForSelector('[data-hook^="decision:"]', { timeout: 60000 })
  result.shown = {}
  for (const id of given.answered || []) result.shown[id] = Boolean(await savedOf(page, id, 30000))
  await snap(page, 'after-restart')
  await ctx.close()
}

/** Every question of `run` that waits, answered in the inbox (Decisions): the first one with a typed answer. */
async function answerInInbox(page, run, state) {
  await go(page, '#/decisions')
  const box = page.locator(`[data-hook^="question:${run}-q"]`).first()
  try { await box.waitFor({ state: 'visible', timeout: 60000 }) } catch { return false }
  const id = (await box.getAttribute('data-hook')).slice('question:'.length)
  if (state.answered.includes(id)) return false
  const text = await box.innerText()
  const options = await box.locator('[data-option]').evaluateAll((els) => els.map((el) => ({ id: el.getAttribute('data-option'), recommended: el.hasAttribute('data-recommended'), label: el.textContent.trim() })))
  state.questions.push({ id, text: text.slice(0, 600), options })
  state.text_ok = state.text_ok !== false && text.trim().length > 0 && options.length > 0 && options.every((o) => o.label)
  await snap(page, `question-${state.questions.length}`)
  const binary = options.length === 2 && options.some((o) => o.id === 'yes')
  if (!state.typed) {
    // The first question gets a typed answer that says "yes" in words: it must not become consent
    state.typed = true
    const consent = check('consent')
    await press(box.locator('[data-write-answer]'), 'write a different answer')
    await box.locator('textarea').fill(context.answers.run)
    result.typed_in_studio = (result.typed_in_studio || 0) + 1
    await press(box.locator('[data-send-answer]'), 'send the typed answer')
    await page.waitForTimeout(2000)
    const seen = check('custom-run', run, id)
    result.custom_run = { question: id, binary, typed_in_inbox: true, consent_before: consent.consent, ...seen }
    state.answered.push(id)
    result.answered_in_inbox = (result.answered_in_inbox || 0) + 1
    result.actions_answers = (result.actions_answers || 0) + 2
    await snap(page, 'question-typed')
    state.after_typed = { text }
    return true
  }
  // Then the options: yes to running the project's code only when the owner authorized it
  let choice = options.find((o) => o.recommended) || options[0]
  if (binary) choice = options.find((o) => o.id === (context.run_code ? 'yes' : 'no')) || choice
  if (binary && state.after_typed && !result.consent) {
    result.consent = { restored: true, same_question_text: state.after_typed.text.split('\n').slice(0, 3).join('\n') === text.split('\n').slice(0, 3).join('\n'),
      before_yes: check('consent').consent, answered: choice.id }
  }
  await press(box.locator(`[data-option="${choice.id}"]`), `answer ${choice.id}`)
  state.answered.push(id)
  result.answered_in_inbox = (result.answered_in_inbox || 0) + 1
  result.actions_answers = (result.actions_answers || 0) + 1
  await page.waitForTimeout(1500)
  if (binary && !result.run_answer_idempotent) result.run_answer_idempotent = check('run-answer-idempotent', run, id, choice.id)
  if (binary && choice.id === 'yes' && result.consent) result.consent.after_yes = check('consent').consent
  return true
}

async function fix() {
  const group = given.group
  const { ctx, page } = await open({ record: true })
  await go(page, '#/problems')
  await page.waitForSelector('input[type="checkbox"][aria-label]', { timeout: 60000 })
  const before = actions
  let picked = false
  if (group.by) {
    await press(page.locator('[data-hook="select-group"]').first(), 'select a group')
    const kind = page.locator(`[data-hook="group-kind:${group.by}"]`)
    if (await kind.count()) {
      await press(kind, `group kind ${group.by}`)
      const row = page.locator(`[data-hook="group:${group.by}:${group.value}"]`)
      if (await row.count()) { await snap(page, 'group-sheet'); await press(row, `group ${group.value}`); picked = true }
    }
    if (!picked) { await page.keyboard.press('Escape'); result.errors.push(`the group ${group.by}:${group.value} was not offered; picking its cards one by one`) }
  }
  if (!picked) {
    for (const id of group.cards) {
      await go(page, `#/problems?q=${encodeURIComponent(id)}`)
      const box = page.locator(`input[type="checkbox"][aria-label*="${id}"]`).first()
      await box.waitFor({ state: 'visible', timeout: 30000 })
      if (!(await box.isChecked())) await press(box, `card ${id}`)
    }
  }
  await snap(page, 'selected')
  await press(page.locator('[data-verb="fix"]').first(), 'fix')
  const run = await confirmPreview(page, given.assistant_name)
  result.selected = group.cards
  result.run = run
  result.actions_fix = actions - before
  log('fix run', run)
  const state = { answered: [], questions: [], typed: false }
  const end = Date.now() + Number(given.limit_ms || 4 * 3600 * 1000) - 300000
  let last = null
  while (Date.now() < end) {
    last = await until(page, run, ['done', 'failed', 'stopped', 'waiting_for_person'], Math.max(1000, end - Date.now()))
    if (last !== 'waiting_for_person') break
    await snap(page, 'waiting')
    if (!(await answerInInbox(page, run, state))) await page.waitForTimeout(3000)
    await go(page, `#/runs/${encodeURIComponent(run)}`)
  }
  result.fix_state = last
  result.questions = state.questions
  result.questions_text_ok = Boolean(state.text_ok)
  await snap(page, `fix-${last}`)
  if (last !== 'done') throw new Error(`the fix ended ${last}`)
  const accept = page.locator('[data-decide="accept"]')
  try { await accept.waitFor({ state: 'visible', timeout: 30000 }) } catch { throw new Error('the fix handed no branch to accept') }
  result.result_on_screen = (await page.locator('main').innerText()).length > 0
  result.guards = check('guards', run)
  const pressed = actions
  await press(accept, 'accept the branch')
  await press(page.locator('[data-confirm="decide"]'), 'confirm accept')
  await page.waitForFunction(() => !document.querySelector('[data-decide="accept"]'), null, { timeout: 300000 })
  await page.waitForTimeout(1500)
  result.actions_accept = actions - pressed
  await snap(page, 'accepted')
  result.undo_after_accept = check('undo-after-accept', run)
  await go(page, '#/')
  await snap(page, 'home-after')
  await ctx.close()
  result.video = await page.video()?.path()
}

async function controls() {
  const { ctx, page } = await open({ width: 1440, height: 900 })
  const start = async (verb, cards) => {
    for (const id of cards) {
      await go(page, `#/problems?q=${encodeURIComponent(id)}`)
      const box = page.locator(`input[type="checkbox"][aria-label*="${id}"]`).first()
      await box.waitFor({ state: 'visible', timeout: 30000 })
      if (!(await box.isChecked())) await press(box, `card ${id}`)
    }
    await press(page.locator(`[data-verb="${verb}"]`).first(), verb)
    return confirmPreview(page, given.assistant_name)
  }
  const cards = given.cards
  const explain = await start('explain', cards)
  const plan = await start('plan', cards)
  const verify = await start('verify', cards)
  result.explain = explain; result.plan = plan; result.verify = verify
  const queue = {}
  // Reorder: verify before plan, from the runs page
  await go(page, '#/runs')
  await page.waitForTimeout(1500)
  await snap(page, 'queue')
  const before = check('queue').queue
  const moveUp = page.locator(`[data-hook="queue-up:${verify}"]`)
  if (before.indexOf(verify) > 0 && await moveUp.count()) { await press(moveUp, 'move verify up'); await page.waitForTimeout(1500) }
  const after = check('queue').queue
  queue.before = before; queue.after = after
  queue.reordered = before.indexOf(verify) > after.indexOf(verify) && after.indexOf(verify) >= 0
  // Pause and resume the explain run while it runs
  await go(page, `#/runs/${encodeURIComponent(explain)}`)
  await until(page, explain, ['running', 'done', 'failed'], 600000)
  for (let i = 0; i < 30 && !(await page.locator('[data-control="pause"]').count()); i++) await page.waitForTimeout(1000)
  if (await page.locator('[data-control="pause"]').count()) {
    await press(page.locator('[data-control="pause"]'), 'pause')
    queue.paused = (await until(page, explain, ['paused'], 30000)) === 'paused'
    await snap(page, 'paused')
    await press(page.locator('[data-control="resume"]'), 'resume')
    queue.resumed = (await until(page, explain, ['running', 'done', 'waiting_for_person'], 30000)) !== 'paused'
  }
  const answerAll = async (run) => { const s = { answered: [], questions: [], typed: true }; return async (st) => { if (st === 'waiting_for_person') { await answerInInbox(page, run, s); await go(page, `#/runs/${encodeURIComponent(run)}`) } return false } }
  result.explain_state = await until(page, explain, ['done', 'failed', 'stopped'], 3600000, await answerAll(explain))
  result.explain_done = result.explain_state === 'done'
  await snap(page, 'explain-done')
  // Stop the verify run (first in the queue now) once it runs
  await go(page, `#/runs/${encodeURIComponent(verify)}`)
  await until(page, verify, ['running', 'done', 'failed'], 900000)
  if (await page.locator('[data-control="stop"]').count()) {
    await press(page.locator('[data-control="stop"]'), 'stop')
    queue.stopped = (await until(page, verify, ['stopped'], 60000)) === 'stopped'
    await snap(page, 'stopped')
  }
  // The plan run dies (its assistant is killed), shows it failed, and is tried again as the same run
  await go(page, `#/runs/${encodeURIComponent(plan)}`)
  await until(page, plan, ['running', 'done', 'failed'], 900000)
  const retry = { run: plan }
  const runsBefore = check('queue')
  retry.killed = check('kill-run', plan)
  retry.failed = (await until(page, plan, ['failed', 'done'], 120000)) === 'failed'
  await snap(page, 'failed')
  if (retry.failed) {
    await press(page.locator('[data-control="retry"]'), 'retry')
    const again = await until(page, plan, ['queued', 'running', 'done'], 60000)
    retry.retried_same_run = ['queued', 'running', 'done'].includes(again) && (await runId(page)) === plan
    const runsAfter = check('queue')
    retry.runs_before = runsBefore.runs; retry.runs_after = runsAfter.runs
    retry.no_duplicate = runsBefore.runs === runsAfter.runs
    result.plan_state = await until(page, plan, ['done', 'failed', 'stopped'], 3600000, await answerAll(plan))
    result.plan_reached = result.plan_state === 'done'
    await snap(page, 'plan-done')
  }
  result.retry = retry
  result.queue = queue
  await ctx.close()
}

const PHASES = { scan, decisions, persist, fix, controls }
try {
  if (!PHASES[phase]) throw new Error(`unknown phase ${phase}`)
  await PHASES[phase]()
  result.ok = true
} catch (e) {
  result.errors.push(`${phase}: ${String(e?.stack || e).slice(0, 800)}`)
  log('failed', e)
} finally {
  result.actions ??= actions
  result.completed_at = new Date().toISOString()
  try { await browser.close() } catch { /* already gone */ }
  fs.writeFileSync(path.join(out, 'phases', `${phase}.json`), JSON.stringify(result, null, 1) + '\n')
}
process.exit(result.ok ? 0 : 1)
