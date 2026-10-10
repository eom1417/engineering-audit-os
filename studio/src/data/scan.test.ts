import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { links, place } from '../pages/scan/geometry'
import { apply, clock, emptyProgress, fold, opened, summarize, toolsOf, verdict, type ProgressRow, type ScanProgress } from './scan'

const STAGES = [
  { name: 'facts', requires: [], layer: 0, order: 0 },
  { name: 'engines', requires: ['facts'], layer: 1, order: 0 },
  { name: 'measure', requires: ['facts'], layer: 1, order: 1 },
  { name: 'claims', requires: ['engines', 'measure'], layer: 2, order: 0 },
  { name: 'semantic', requires: ['claims'], layer: 3, order: 0 },
]
/** The recorded real runs the Python fold is held to (tests/fixtures/progress, tools/progress_golden.py). */
const GOLDEN = path.resolve(__dirname, '../../../tests/fixtures/progress')

function recording(name: string): ProgressRow[] {
  return fs.readFileSync(path.join(GOLDEN, `${name}.jsonl`), 'utf-8').split('\n').filter(Boolean).map((line) => JSON.parse(line))
}

/** The folded state the server gives right after `run.started` (eaos/progress/fold.py, with places). */
function started(requested = STAGES.map((s) => s.name)): ScanProgress {
  const stages = STAGES.map(({ name, requires }) => ({ name, requires, produces: [`${name}.json`], necessity: 'required', description: '', absent_when: '' }))
  const state = apply(emptyProgress(), { seq: 1, run: 'r1', at: '2026-10-09T10:00:00.000+00:00', event: 'run.started', stages, requested })
  return { ...state, stages: state.stages.map((s, i) => ({ ...s, layer: STAGES[i].layer, order: STAGES[i].order })) }
}

const row = (seq: number, event: string, extra: Record<string, unknown> = {}): ProgressRow => ({ seq, run: 'r1', at: `2026-10-09T10:00:${String(seq).padStart(2, '0')}.000+00:00`, event, ...extra })

function replay(state: ScanProgress, rows: ProgressRow[]): ScanProgress {
  for (const r of rows) if (verdict(state, r) === 'apply') state = apply(state, r)
  return state
}

describe('one fold, two languages (plan 4.4, I4)', () => {
  for (const name of fs.readdirSync(GOLDEN).filter((f) => f.endsWith('.jsonl')).map((f) => f.replace(/\.jsonl$/, ''))) {
    it(`folds the recorded run "${name}" exactly as eaos/progress/fold.py does`, () => {
      const expected = JSON.parse(fs.readFileSync(path.join(GOLDEN, `${name}.fold.json`), 'utf-8'))
      expect(JSON.parse(JSON.stringify(fold(recording(name))))).toStrictEqual(expected)
    })
  }

  it('leaves out the lines of another run, and starts over on a new one', () => {
    const rows = recording('complete')
    const state = fold(rows)
    expect(apply(state, { ...rows[5], run: 'other', seq: 999 })).toBe(state)
    expect(fold([...rows, { ...rows[0], run: 'next', seq: 1 }])).toMatchObject({ run: 'next', state: 'running', last_seq: 1 })
  })
})

describe('the live check fold', () => {
  it('applies starts, counted steps, programs and ends in order', () => {
    const state = replay(started(), [
      row(2, 'stage.started', { stage: 'facts' }),
      row(3, 'stage.step', { stage: 'facts', step: 'syntax', done: 0, total: 2, status: 'waiting' }),
      row(4, 'stage.step', { stage: 'facts', step: 'homes', kind: 'count', done: 37, total: 156, status: 'running' }),
      row(5, 'stage.activity', { stage: 'facts', programs: [{ name: 'semgrep-core', pid: 7, since: '2026-10-09T10:00:04+00:00' }] }),
      row(6, 'stage.step', { stage: 'facts', step: 'syntax', done: 1, total: 2, status: 'ok', seconds: 0.4 }),
      row(7, 'stage.ended', { stage: 'facts', status: 'ok', seconds: 3.2, reason: '', artifacts: ['facts/index.json'], detail: { facts: 9 } }),
      row(8, 'stage.started', { stage: 'engines' }),
    ])
    const facts = state.stages[0]
    expect([facts.state, facts.seconds, facts.artifacts, facts.detail, facts.programs]).toEqual(['ok', 3.2, ['facts/index.json'], { facts: 9 }, []])
    expect(facts.steps.map((s) => [s.name, s.kind, s.status, s.done, s.total])).toEqual([['syntax', 'item', 'ok', 1, 2], ['homes', 'count', 'running', 37, 156]])
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

  it('carries the reason and its code of a stage that did not run, and the run\'s end', () => {
    const state = replay(started(), [
      row(2, 'stage.ended', { stage: 'semantic', status: 'unavailable', reason: 'no model provider was configured', reason_code: 'no_model_provider', seconds: 0 }),
      row(3, 'run.ended', { status: 'INCOMPLETE', seconds: 12, counts: { ok: 3 } }),
    ])
    expect(state.stages.find((s) => s.name === 'semantic')).toMatchObject({ state: 'unavailable', reason_code: 'no_model_provider' })
    expect([state.state, state.status, state.seconds]).toEqual(['done', 'INCOMPLETE', 12])
  })

  it('sends the light only to the stages whose needs are all met', () => {
    let state = replay(started(), [row(2, 'stage.ended', { stage: 'facts', status: 'ok' })])
    expect(opened(state, 'facts')).toEqual(['engines', 'measure'])
    state = replay(state, [row(3, 'stage.ended', { stage: 'engines', status: 'ok' })])
    expect(opened(state, 'engines')).toEqual([])
    state = replay(state, [row(4, 'stage.ended', { stage: 'measure', status: 'ok' })])
    expect(opened(state, 'measure')).toEqual(['claims'])
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

describe('preparing the tools (eaos/toolchain.py readiness)', () => {
  const tools = ['semgrep', 'knip', 'k6'].map((name) => ({ name, requires: [], produces: [], necessity: 'required', description: '1.0.0', absent_when: '' }))
  const install = (...rows: ProgressRow[]) => fold([{ seq: 0, run: 'r1', at: '2026-10-09T10:00:00.000+00:00', event: 'run.started', flow: 'tools', stages: tools,
    requested: tools.map((t) => t.name) }, ...rows])
  const at = Date.parse('2026-10-09T10:00:30.000+00:00')

  it('unlocks the check once every tool it needs here is ready, the others still installing', () => {
    const running = install(row(1, 'stage.started', { stage: 'semgrep' }), row(2, 'stage.step', { stage: 'semgrep', step: 'download', done: 50, total: 200, kind: 'count' }))
    const before = toolsOf(running, ['semgrep'], at)
    expect([before.unlocked, before.rows[0].state, before.rows[0].done, before.rows[0].total, before.left]).toEqual([false, 'downloading', 50, 200, null])
    const after = toolsOf(install(row(1, 'stage.started', { stage: 'semgrep' }), row(2, 'stage.ended', { stage: 'semgrep', status: 'ok' })), ['semgrep'], at)
    expect([after.unlocked, after.needed, after.all, after.rows[1].state]).toEqual([true, { ready: 1, total: 1 }, { ready: 1, total: 3 }, 'waiting'])
    expect(after.left).toBe(60)
  })

  it('a failed tool the check needs keeps it locked, with its reason; an install over without a tool is a failure', () => {
    const failed = toolsOf(install(row(1, 'stage.ended', { stage: 'semgrep', status: 'failed', reason: 'no network', reason_code: 'tool_failed' })), ['semgrep'], at)
    expect([failed.unlocked, failed.failed.map((t) => [t.name, t.reason, t.reasonCode])]).toEqual([false, [['semgrep', 'no network', 'tool_failed']]])
    const over = toolsOf(install(row(1, 'run.ended', { status: 'STOPPED' })), ['knip'], at)
    expect([over.unlocked, over.failed.map((t) => t.name)]).toEqual([false, ['knip']])
    expect(toolsOf(emptyProgress(), [], at).unlocked).toBe(true)
  })
})
