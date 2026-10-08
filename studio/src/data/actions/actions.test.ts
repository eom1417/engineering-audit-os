import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ACTIONS, CONTRACT, VERBS } from './contract'
import { demoClient, resolveSelection, type DemoCard } from './demo'
import { deriveRun, duration, share } from './derive'
import { frameSplitter, parseFrame, type Frame } from './sse'
import type { RunEvent } from './types'

const CARDS: DemoCard[] = Array.from({ length: 12 }, (_, i) => ({
  id: `TASK-${String(i + 1).padStart(3, '0')}`, title: `Finding ${i + 1}`, paths: [`src/f${i}.ts`], state: i === 11 ? 'done' : 'open',
  category: i % 2 ? 'security' : 'quality', severity: i < 3 ? 'high' : 'low', milestone: i < 6 ? 'M01' : 'M02',
}))

describe('the contract', () => {
  it('is the action contract, with the four verbs and every action labelled in both languages', () => {
    expect(CONTRACT.contract).toBe('studio-actions')
    expect(VERBS.map((v) => v.id)).toEqual(['fix', 'verify', 'explain', 'plan'])
    for (const action of ACTIONS) expect(action.label.ar && action.label.en).toBeTruthy()
    expect(ACTIONS.find((a) => a.id === 'accept')?.irreversible).toBe(true)
  })
})

describe('the SSE reader', () => {
  it('reads id, event and data, skips comments and joins data lines', () => {
    expect(parseFrame('id: 7\nevent: step\ndata: {"a":1}')).toEqual({ id: '7', event: 'step', data: '{"a":1}' })
    expect(parseFrame(': ping')).toBeNull()
    expect(parseFrame('data: a\ndata: b')?.data).toBe('a\nb')
  })

  it('waits for the rest of a frame split across chunks, CRLF included', () => {
    const frames: Frame[] = []
    const feed = frameSplitter((f) => frames.push(f))
    feed('id: 1\r\ndata: {"seq"')
    expect(frames).toHaveLength(0)
    feed(':1}\r\n\r')
    feed('\n: ping\n\nid: 2\ndata: x\n\n')
    expect(frames.map((f) => f.id)).toEqual(['1', '2'])
    expect(frames[0].data).toBe('{"seq":1}')
  })
})

describe('selections in the demo', () => {
  it('resolves cards, groups and steps, leaving out what is not open', () => {
    expect(resolveSelection({ kind: 'cards', cards: ['TASK-001', 'TASK-012'] }, CARDS)).toEqual({
      chosen: [CARDS[0]], left: [{ id: 'TASK-012', why: 'already done' }],
    })
    expect(resolveSelection({ kind: 'group', group: { by: 'severity', value: 'high' } }, CARDS).chosen.map((c) => c.id)).toEqual(['TASK-001', 'TASK-002', 'TASK-003'])
    expect(resolveSelection({ kind: 'step', step: 'M02' }, CARDS).chosen).toHaveLength(5)
  })
})

describe('the run view', () => {
  const event = (seq: number, kind: RunEvent['kind'], data: Record<string, unknown> = {}): RunEvent =>
    ({ seq, id: `r-${seq}`, run: 'r', at: '2026-10-08T20:00:00Z', kind, text: { en: `${kind} ${seq}`, ar: `${kind} ${seq}` }, data })

  it('derives the state, the batches, the folded reads and the result from the events alone', () => {
    const view = deriveRun([
      event(1, 'action'), event(2, 'state', { from: 'queued', to: 'running' }),
      event(3, 'progress', { batch: 1, done: 0, total: 2 }), event(4, 'read', { path: 'a' }), event(5, 'read', { path: 'b' }),
      event(6, 'edit', { card: 'T', paths: ['a'], diff: '+x', kept: true }), event(7, 'check', { passed: false }),
      event(8, 'progress', { batch: 1, done: 2, total: 2 }), event(9, 'progress', { batch: 2, done: 1, total: 4 }),
      event(10, 'screenshot', { when: 'before' }), event(11, 'screenshot', { when: 'after' }),
      event(12, 'result', { branch: 'eaos/wave-1', cards_closed: ['T'], indicators: [] }), event(13, 'state', { from: 'running', to: 'done' }),
    ])
    expect(view.state).toBe('done')
    expect(view.batches).toEqual([{ number: 1, done: 2, total: 2 }, { number: 2, done: 1, total: 4 }])
    expect(share(view.batches)).toBeCloseTo(0.5)
    expect(view.items.filter((i) => i.kind === 'reads')).toHaveLength(1)
    expect(view.items.some((i) => i.kind === 'event' && i.event.kind === 'progress')).toBe(false)
    expect(view.screens).toHaveLength(1)
    expect(view.result?.branch).toBe('eaos/wave-1')
    expect(view.checks).toEqual({ passed: 0, failed: 1 })
    expect(view.last).toBe(13)
  })

  it('keeps the handed-over result when accept or undo is recorded after it', () => {
    const view = deriveRun([event(1, 'result', { branch: 'eaos/wave-2', cards_closed: [], indicators: [] }), event(2, 'result', { branch: 'eaos/wave-2', outcome: 'accept' })])
    expect(view.result?.cards_closed).toEqual([])
  })

  it('says durations in the language', () => {
    expect(duration('2026-10-08T20:00:00Z', '2026-10-08T20:03:20Z', 'en')).toBe('3 m 20 s')
    expect(duration('2026-10-08T20:00:00Z', '2026-10-08T21:04:00Z', 'ar')).toBe('1 س 4 د')
    expect(duration(null, null, 'en')).toBeNull()
  })
})

describe('the demo client', () => {
  /** Lets the demo's short delay pass; the outcome is caught first, so a refusal is not an unhandled rejection. */
  const settle = async <T>(p: Promise<T>): Promise<T> => {
    const out = p.then((value) => ({ value }), (error: unknown) => ({ error }))
    await vi.advanceTimersByTimeAsync(200)
    const got = await out
    if ('error' in got) throw got.error
    return got.value
  }
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('opens with a run waiting for an answer, two queued and a history', async () => {
    const client = demoClient(() => CARDS)
    client.seed()
    const { runs, queue } = await settle(client.runs())
    expect(runs.filter((r) => r.state === 'waiting_for_person')).toHaveLength(1)
    expect(queue).toHaveLength(2)
    expect(runs.some((r) => r.state === 'done' && r.result?.branch && !r.outcome)).toBe(true)
    expect(runs.some((r) => r.state === 'failed')).toBe(true)
  })

  it('needs the confirm token of its preview, then runs one at a time and goes on after the answer', async () => {
    const client = demoClient(() => CARDS)
    client.seed()
    await expect(settle(client.start({ action: 'fix', verb: 'fix', selection: { kind: 'cards', cards: ['TASK-010', 'TASK-011'] } }))).rejects.toThrow(/confirmation/)
    const preview = await settle(client.preview('fix', { verb: 'fix', selection: { kind: 'cards', cards: ['TASK-010', 'TASK-011'] } }))
    expect(preview.cards).toHaveLength(2)
    expect(preview.batches.length).toBeGreaterThan(0)
    const run = await settle(client.start({ action: 'fix', verb: 'fix', selection: { kind: 'cards', cards: ['TASK-010', 'TASK-011'] }, confirm: preview.confirm?.token }))
    expect(run.state).toBe('queued')
    expect(run.position).toBe(3)
    const [question] = await settle(client.questions())
    const seen: RunEvent[] = []
    const stop = client.follow(question.run, 0, (e) => seen.push(e), () => undefined)
    await vi.advanceTimersByTimeAsync(0)
    const before = seen.length
    await settle(client.answer(question.id, 'yes'))
    await vi.advanceTimersByTimeAsync(120_000)
    stop()
    expect(seen.length).toBeGreaterThan(before)
    expect(seen.map((e) => e.seq)).toEqual(seen.map((_, i) => i + 1))
    expect(seen.at(-1)?.data.to).toBe('done')
    const after = await settle(client.runs())
    expect(after.runs.find((r) => r.id === question.run)?.state).toBe('done')
    expect(after.runs.filter((r) => ['running', 'waiting_for_person', 'paused'].includes(r.state)).length).toBeLessThanOrEqual(1)
  })

  it('pauses, resumes, stops, retries, reorders and decides only with the confirm token', async () => {
    const client = demoClient(() => CARDS)
    client.seed()
    const { runs, queue } = await settle(client.runs())
    expect(await settle(client.reorder([...queue].reverse()))).toEqual([...queue].reverse())
    await expect(settle(client.reorder([queue[0]]))).rejects.toThrow()
    const waiting = runs.find((r) => r.state === 'waiting_for_person')!
    expect((await settle(client.control(waiting.id, 'stop'))).state).toBe('stopped')
    expect((await settle(client.control(waiting.id, 'retry'))).attempt).toBe(2)
    const running = (await settle(client.runs())).runs.find((r) => r.state === 'running')!
    expect((await settle(client.control(running.id, 'pause'))).state).toBe('paused')
    expect((await settle(client.control(running.id, 'resume'))).state).toBe('running')
    const done = runs.find((r) => r.state === 'done' && r.result?.branch && !r.outcome)!
    await expect(settle(client.decide(done.id, 'accept', 'wrong'))).rejects.toThrow(/confirmation/)
    const confirm = (await settle(client.preview('accept', { inputs: {} }))).confirm!.token
    expect((await settle(client.decide(done.id, 'accept', confirm))).outcome).toBe('accepted')
    await expect(settle(client.decide(done.id, 'undo', confirm))).rejects.toThrow(/already/)
  })
})
