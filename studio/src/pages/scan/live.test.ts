import fs from 'node:fs'
import path from 'node:path'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { apply, emptyProgress, fold, type ProgressRow, type ScanProgress } from '../../data/scan'
import { LiveMap } from './LiveMap'
import { follow, MAX_LIGHTS, nextDue, release, SLOT_MS, still, type Motion } from './motion'
import { StagePanel } from './StagePanel'

// The page's words in English, without the browser the preferences read
vi.mock('../../i18n/prefs', () => ({ usePrefs: () => ({ lang: 'en', dir: 'ltr', t: (key: string) => key, num: String, date: String, ago: String }) }))

const GOLDEN = path.resolve(__dirname, '../../../../tests/fixtures/progress')
const recording = (name: string): ProgressRow[] =>
  fs.readFileSync(path.join(GOLDEN, `${name}.jsonl`), 'utf-8').split('\n').filter(Boolean).map((line) => JSON.parse(line))

interface Seen { at: number; kind: 'glow' | 'end' | 'light'; stage: string; state?: string; to?: string; line: string | null }

/** The stages whose shown state changed from `before` to `after`: a glow when one is shown running, else an end. */
function shownChanges(before: Motion, after: Motion, state: ScanProgress, now: number): Seen[] {
  return Object.entries(after.shown).filter(([stage, shown]) => before.shown[stage] !== shown).map(([stage, shown]) => {
    const s = state.stages.find((x) => x.name === stage)
    const glow = shown === 'running'
    return { at: now, kind: glow ? 'glow' : 'end', stage, state: shown, line: (glow ? s?.started_at : s?.ended_at) ?? null }
  })
}

/** A recorded run played at its own pace through the fold and the map's motion, as the page does: every visible
 * change and every light, with the time it was shown. */
function watch(rows: ProgressRow[]): { seen: Seen[]; last: Motion; state: ScanProgress; lightsAtOnce: number } {
  const t0 = Date.parse(rows[0].at as string)
  let state = emptyProgress()
  let motion = still(state)
  let now = 0
  let lightsAtOnce = 0
  const seen: Seen[] = []
  const look = (next: Motion) => {
    if (motion.run === next.run) seen.push(...shownChanges(motion, next, state, now))
    for (const light of next.lights) if (!motion.lights.includes(light)) seen.push({ at: now, kind: 'light', stage: light.from, to: light.to, line: light.at })
    lightsAtOnce = Math.max(lightsAtOnce, next.lights.length)
    motion = next
  }
  const pump = (until: number) => {
    for (let due = nextDue(motion, now); due !== null && now + due <= until; due = nextDue(motion, now)) {
      now += due
      look(release(motion, state, now))
    }
  }
  for (const row of rows) {
    pump(Date.parse(row.at as string) - t0)
    now = Date.parse(row.at as string) - t0
    state = apply(state, row)
    look(row.event === 'run.started' ? still(state) : release(follow(motion, state), state, now))
  }
  pump(Infinity)
  return { seen, last: motion, state, lightsAtOnce }
}

describe('the map moves only on a line of the run (plan 4.2, I9)', () => {
  for (const name of ['complete', 'stopped', 'killed']) {
    it(`matches every glow, end and light of "${name}" to its line`, () => {
      const rows = recording(name)
      const { seen, last, state, lightsAtOnce } = watch(rows)
      const line = (event: string, stage: string, at: string | null, status?: string) =>
        rows.some((r) => r.event === event && r.stage === stage && r.at === at && (status === undefined || r.status === status))
      const unmatched = seen.filter((s) => !(s.kind === 'glow' ? line('stage.started', s.stage, s.line)
        : s.kind === 'end' ? line('stage.ended', s.stage, s.line, s.state)
          : line('stage.ended', s.stage, s.line, 'ok') && state.stages.find((x) => x.name === s.to)?.requires.includes(s.stage)))
      expect(unmatched).toEqual([])
      expect(seen.filter((s) => s.kind === 'glow').length).toBe(rows.filter((r) => r.event === 'stage.started').length)
      expect(seen.some((s) => s.kind === 'light')).toBe(name !== 'killed' || rows.some((r) => r.event === 'stage.ended' && r.status === 'ok'))
      expect(lightsAtOnce).toBeLessThanOrEqual(MAX_LIGHTS)
      // the queue drains: in the end the map shows exactly the folded state
      expect(last.shown).toEqual(Object.fromEntries(state.stages.map((s) => [s.name, s.state])))
    })
  }

  it('shows each change at least 400 ms after the one before, so a 50 ms stage is seen, and the stages that never ran together', () => {
    const { seen } = watch(recording('complete'))
    const changes = seen.filter((s) => s.kind !== 'light')
    const gaps = changes.slice(1).map((s, i) => s.at - changes[i].at).filter((gap) => gap > 0)
    expect(Math.min(...gaps)).toBeGreaterThanOrEqual(SLOT_MS)
    expect(changes.filter((s) => s.stage === 'features').map((s) => s.kind)).toEqual(['glow', 'end'])
    const stopped = watch(recording('stopped')).seen.filter((s) => s.state === 'not_reached')
    expect(new Set(stopped.map((s) => s.at)).size).toBe(1)
  })

  it('starts over with nothing queued on a new run, and with reduced motion shows the state as it is', () => {
    const state = fold(recording('complete'))
    expect(follow(still(emptyProgress()), state)).toMatchObject({ run: state.run, queue: [], lights: [] })
  })
})

describe('a stage EAOS adds appears with no front-end change (I3)', () => {
  it('draws a stage the page has no words for, by its own name, needs and description', () => {
    const rows = recording('complete').slice(0, 2)
    const fixture = { name: 'fixture_stage', requires: ['facts'], produces: ['fixture.json'], necessity: 'optional', description: 'A stage a test added', absent_when: 'never' }
    rows[0] = { ...rows[0], stages: [...(rows[0].stages as object[]), fixture], requested: [...(rows[0].requested as string[]), 'fixture_stage'] }
    const state = fold([...rows, { seq: 3, at: rows[1].at, run: rows[0].run, event: 'stage.started', stage: 'fixture_stage' }])
    const placed = { ...state, stages: state.stages.map((s, i) => ({ ...s, layer: s.name === 'fixture_stage' ? 1 : 0, order: i })) }
    const stage = placed.stages.find((s) => s.name === 'fixture_stage')!
    const html = renderToStaticMarkup(createElement('div', null,
      createElement(LiveMap, { progress: placed, skew: 0, selected: null, onSelect: () => undefined, summary: '' }),
      createElement(StagePanel, { stage, progress: placed, skew: 0, onSelect: () => undefined })))
    expect(html).toContain('data-stage="fixture_stage" data-state="running"')
    expect(html).toContain('fixture stage')
    expect(html).toContain('A stage a test added')
    expect(html).toContain('fixture.json')
    expect(html).toContain('data-glow=""')
  })
})
