import { describe, expect, it } from 'vitest'
import { ACTIONS, CONTRACT, VERBS } from './contract'
import { deriveRun, duration, share } from './derive'
import { frameSplitter, parseFrame, type Frame } from './sse'
import type { RunEvent } from './types'

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
      event(12, 'result', { branch: 'eaos/wave-1', cards_closed: ['T'] }), event(13, 'state', { from: 'running', to: 'done' }),
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
    const view = deriveRun([event(1, 'result', { branch: 'eaos/wave-2', cards_closed: [] }), event(2, 'result', { branch: 'eaos/wave-2', outcome: 'accept' })])
    expect(view.result?.cards_closed).toEqual([])
  })

  it('says durations in the language', () => {
    expect(duration('2026-10-08T20:00:00Z', '2026-10-08T20:03:20Z', 'en')).toBe('3 m 20 s')
    expect(duration('2026-10-08T20:00:00Z', '2026-10-08T21:04:00Z', 'ar')).toBe('1 س 4 د')
    expect(duration(null, null, 'en')).toBeNull()
  })
})
