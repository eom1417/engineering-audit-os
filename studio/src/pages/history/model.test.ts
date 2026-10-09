import { describe, expect, it } from 'vitest'
import { bands, compare, labelled, openTotal, parseRange, place, type HistoryData, type Scan } from './model'

const scan = (id: string, at: string, score: number | null, open: Scan['open'], extra: Partial<Scan> = {}): Scan =>
  ({ id, commit: id, at, score, open, ...extra })
const FULL = { critical: 1, high: 2, medium: 3, low: 4, info: 0 }
const HISTORY: HistoryData = {
  scans: [scan('a', '2026-10-01T00:00:00Z', null, { critical: null, high: null, medium: null, low: null, info: null }, { open_total: 12, closed: 0, total: 12 }),
          scan('b', '2026-10-05T00:00:00Z', 0.5, FULL, { closed: 3, total: 13 }),
          scan('c', '2026-10-09T00:00:00Z', 0.6, { ...FULL, high: 0 }, { closed: 6, total: 14 })],
  events: [],
  cards: [{ key: '1', title: 'x', state: 'done', at: '2026-10-03T00:00:00Z', new: false }, { key: '2', title: 'y', state: 'resolved', at: '2026-10-07T00:00:00Z', new: false },
          { key: '3', title: 'z', state: 'open', at: null, new: true }],
}

describe('the history', () => {
  it('compares two checks from what they recorded, never guessing the rest', () => {
    const found = compare(HISTORY, 'c', 'a')!
    expect([found.from.id, found.to.id]).toEqual(['a', 'c'])
    expect(found.score).toBeNull()
    expect(found.open).toBe(-4)
    expect(found.severity.high).toBeNull()
    expect(found.closedBetween.map((c) => c.key)).toEqual(['1', '2'])
    expect(found.appeared!.map((c) => c.key)).toEqual(['3'])
    expect(compare(HISTORY, 'a', 'b')!.appeared).toBeNull()
    expect(compare(HISTORY, 'b', 'b')).toBeNull()
    expect(compare(HISTORY, 'b', 'nope')).toBeNull()
  })

  it('counts the open problems only when every severity is known, or the ledger counted them', () => {
    expect(openTotal(HISTORY.scans[1])).toBe(10)
    expect(openTotal(HISTORY.scans[0])).toBe(12)
    expect(openTotal(scan('d', 'x', null, { critical: 1 }))).toBeNull()
  })

  it('reads a range of two checks', () => {
    expect(parseRange('a1..b2')).toEqual(['a1', 'b2'])
    expect(parseRange('..b')).toBeNull()
    expect(parseRange('ab')).toBeNull()
  })

  it('runs time from inline-start: mirrored in right-to-left', () => {
    const plot = { width: 300, height: 200, pad: { start: 40, end: 20, top: 10, bottom: 30 } }
    const values = [{ at: '2026-10-01T00:00:00Z', value: 0 }, { at: '2026-10-11T00:00:00Z', value: 1 }]
    const ltr = place(values, plot, false), rtl = place(values, plot, true)
    expect([ltr[0].x, ltr[1].x]).toEqual([40, 280])
    expect([rtl[0].x, rtl[1].x]).toEqual([260, 20])
    expect([ltr[0].y, ltr[1].y]).toEqual([170, 10])
    expect(bands(HISTORY.scans.slice(1), plot, false)).toHaveLength(5)
  })

  it('labels every point of a short line and some of a long one, always the last', () => {
    expect([...labelled(3)]).toEqual([0, 1, 2])
    const many = labelled(30, 5)
    expect(many.size).toBe(5)
    expect(many.has(29)).toBe(true)
  })
})
