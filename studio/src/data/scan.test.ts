import { describe, expect, it } from 'vitest'
import { links, place } from '../pages/scan/geometry'
import { apply, clock, emptyProgress, opened, secondsLeft, summarize, verdict, type ProgressRow, type ScanProgress } from './scan'

const STAGES = [
  { name: 'facts', requires: [], layer: 0, order: 0 },
  { name: 'engines', requires: ['facts'], layer: 1, order: 0 },
  { name: 'measure', requires: ['facts'], layer: 1, order: 1 },
  { name: 'claims', requires: ['engines', 'measure'], layer: 2, order: 0 },
  { name: 'semantic', requires: ['claims'], layer: 3, order: 0 },
]

/** The folded state the server gives right after `run.started` (eaos/pipeline/progress.py fold, with places). */
function started(requested = STAGES.map((s) => s.name), previous: Record<string, number> = {}): ScanProgress {
  return {
    ...emptyProgress(), run: 'r1', state: 'running', started_at: '2026-10-09T10:00:00.000+00:00', last_seq: 1, requested, previous,
    stages: STAGES.map((s) => ({ ...s, produces: [`${s.name}.json`], necessity: 'required' as const, description: '', absent_when: '',
      requested: requested.includes(s.name), state: 'waiting' as const, started_at: null, ended_at: null, seconds: null, reason: '',
      artifacts: [], detail: {}, steps: [], resumed: false })),
  }
}

const row = (seq: number, event: string, extra: Record<string, unknown> = {}): ProgressRow => ({ seq, run: 'r1', at: `2026-10-09T10:00:${String(seq).padStart(2, '0')}.000+00:00`, event, ...extra })

function replay(state: ScanProgress, rows: ProgressRow[]): ScanProgress {
  for (const r of rows) if (verdict(state, r) === 'apply') state = apply(state, r)
  return state
}

describe('the live check fold', () => {
  it('applies starts, steps and ends in order, as the server folds them', () => {
    const state = replay(started(), [
      row(2, 'stage.started', { stage: 'facts' }),
      row(3, 'stage.step', { stage: 'facts', step: 'syntax', done: 0, total: 2, status: 'waiting' }),
      row(4, 'stage.step', { stage: 'facts', step: 'graph', done: 0, total: 2, status: 'waiting' }),
      row(5, 'stage.step', { stage: 'facts', step: 'syntax', done: 0, total: 2, status: 'running' }),
      row(6, 'stage.step', { stage: 'facts', step: 'syntax', done: 1, total: 2, status: 'ok', seconds: 0.4 }),
      row(7, 'stage.ended', { stage: 'facts', status: 'ok', seconds: 3.2, reason: '', artifacts: ['facts/index.json'], detail: { facts: 9 } }),
      row(8, 'stage.started', { stage: 'engines' }),
    ])
    const facts = state.stages[0]
    expect([facts.state, facts.seconds, facts.artifacts, facts.detail]).toEqual(['ok', 3.2, ['facts/index.json'], { facts: 9 }])
    expect(facts.steps.map((s) => [s.name, s.status, s.seconds])).toEqual([['syntax', 'ok', 0.4], ['graph', 'waiting', null]])
    expect(state.stages[1].state).toBe('running')
    expect(state.last_seq).toBe(8)
    expect(summarize(state)).toMatchObject({ total: 5, ended: 1, position: 2 })
  })

  it('ignores what it already shows, and reads again on a gap, a new run or another run', () => {
    const state = replay(started(), [row(2, 'stage.started', { stage: 'facts' })])
    expect(verdict(state, row(2, 'stage.started', { stage: 'facts' }))).toBe('ignore')
    expect(verdict(state, row(4, 'stage.ended', { stage: 'facts' }))).toBe('reload')
    expect(verdict(state, { ...row(1, 'run.started'), run: 'r2' })).toBe('reload')
    expect(verdict(state, { ...row(3, 'stage.started'), run: 'r2' })).toBe('reload')
    expect(verdict(emptyProgress(), row(5, 'stage.started', { stage: 'facts' }))).toBe('reload')
  })

  it('carries the reason of a stage that was blocked or unavailable, and the run\'s end', () => {
    const state = replay(started(), [
      row(2, 'stage.ended', { stage: 'semantic', status: 'unavailable', reason: 'no model provider was configured', seconds: 0 }),
      row(3, 'stage.ended', { stage: 'claims', status: 'not_reached', reason: 'Prerequisites not completed: engines', seconds: 0 }),
      row(4, 'run.ended', { status: 'INCOMPLETE', seconds: 12, counts: { ok: 3 } }),
    ])
    expect(state.stages.find((s) => s.name === 'semantic')).toMatchObject({ state: 'unavailable', reason: 'no model provider was configured' })
    expect(state.stages.find((s) => s.name === 'claims')).toMatchObject({ state: 'not_reached', reason: 'Prerequisites not completed: engines' })
    expect([state.state, state.status, state.seconds]).toEqual(['done', 'INCOMPLETE', 12])
  })

  it('sends the light only to the stages whose needs are all met', () => {
    let state = replay(started(), [row(2, 'stage.ended', { stage: 'facts', status: 'ok' })])
    expect(opened(state, 'facts')).toEqual(['engines', 'measure'])
    state = replay(state, [row(3, 'stage.ended', { stage: 'engines', status: 'ok' })])
    expect(opened(state, 'engines')).toEqual([], )
    state = replay(state, [row(4, 'stage.ended', { stage: 'measure', status: 'ok' })])
    expect(opened(state, 'measure')).toEqual(['claims'])
  })

  it('gives a time left only from a known last run, and never on a first run', () => {
    const now = Date.parse('2026-10-09T10:01:00.000+00:00')
    let state = replay(started(undefined, { facts: 100, engines: 50, measure: 10, claims: 5, semantic: 1 }),
      [row(2, 'stage.started', { stage: 'facts', at: '2026-10-09T10:00:00.000+00:00' })])
    expect(secondsLeft(state, 0, now)).toBe(40 + 50 + 10 + 5 + 1)
    state = replay(started(), [row(2, 'stage.started', { stage: 'facts' })])
    expect(secondsLeft(state, 0, now)).toBeNull()
    expect(clock(3725)).toBe('1:02:05')
    expect(clock(65)).toBe('1:05')
  })
})

describe('the live check geometry', () => {
  it('places the layers along the flow and draws one link per requirement', () => {
    const across = place(STAGES, true)
    expect(across.at.get('engines')!.x).toBeGreaterThan(across.at.get('facts')!.x)
    expect(across.at.get('measure')!.y).toBeGreaterThan(across.at.get('engines')!.y)
    const down = place(STAGES, false)
    expect(down.at.get('engines')!.y).toBeGreaterThan(down.at.get('facts')!.y)
    expect(links(STAGES, across).map((l) => `${l.from}>${l.to}`)).toEqual(['facts>engines', 'facts>measure', 'engines>claims', 'measure>claims', 'claims>semantic'])
  })
})
