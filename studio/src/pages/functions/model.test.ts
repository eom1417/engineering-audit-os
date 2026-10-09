import { describe, expect, it } from 'vitest'
import { callGraph, filterFunctions, level, riskiestNeighbour, searchText, shortName, type Fn } from './model'

const m = (value: number | null, src = 'engines lizard#cyclomatic_complexity') => ({ value, src })

function fn(id: string, extra: Partial<Fn> = {}): Fn {
  const [module, name] = id.split('#')
  return { id, name, module, line: 1, end_line: 2, language: 'TypeScript', kind: 'function', signature: null, summary: null, exported: false,
    lines: m(10, 'lines'), complexity: m(1), callers: [], callees: [], reads: [], writes: [], cards: [], ...extra }
}

const FNS = [
  fn('a.ts#root', { callees: ['a.ts#mid'], complexity: m(3) }),
  fn('a.ts#mid', { callers: ['a.ts#root', 'b.ts#other'], callees: ['b.ts#leaf', 'b.ts#saveOrder'], complexity: m(12) }),
  fn('b.ts#other', { callees: ['a.ts#mid'], complexity: m(null, 'not measured') }),
  fn('b.ts#leaf', { callers: ['a.ts#mid'], callees: ['c.ts#deep'], complexity: m(20) }),
  fn('b.ts#saveOrder', { callers: ['a.ts#mid'], writes: [{ kind: 'table', name: 'orders' }], cards: ['TASK-001'], complexity: m(4) }),
  fn('c.ts#deep', { callers: ['b.ts#leaf'], kind: 'hook', exported: true }),
]
const BY_ID = new Map(FNS.map((f) => [f.id, f]))

describe('the function explorer reads functions.json and invents nothing', () => {
  it('measures complexity against Lizard’s warning line, and says when it was not measured', () => {
    expect(FNS.map(level)).toEqual(['ok', 'watch', 'none', 'high', 'ok', 'ok'])
  })

  it('orders by complexity first, an unmeasured function last', () => {
    expect(filterFunctions(FNS, {}).map((f) => f.name)).toEqual(['leaf', 'mid', 'saveOrder', 'root', 'deep', 'other'])
    expect(filterFunctions(FNS, { sort: 'callers' })[0].name).toBe('mid')
    expect(filterFunctions(FNS, { sort: 'name' }).map((f) => f.name)).toEqual(['deep', 'leaf', 'mid', 'other', 'root', 'saveOrder'])
  })

  it('filters by what it touches, its problems, its kind, its file, and functions nobody calls', () => {
    expect(filterFunctions(FNS, { show: 'data' }).map((f) => f.name)).toEqual(['saveOrder'])
    expect(filterFunctions(FNS, { show: 'problems' }).map((f) => f.name)).toEqual(['saveOrder'])
    expect(filterFunctions(FNS, { kind: 'hook' }).map((f) => f.name)).toEqual(['deep'])
    expect(filterFunctions(FNS, { module: 'b.ts', sort: 'name' }).map((f) => f.name)).toEqual(['leaf', 'other', 'saveOrder'])
    // nobody calls root and other; deep is exported, so something outside the file may
    expect(filterFunctions(FNS, { show: 'unused', sort: 'name' }).map((f) => f.name)).toEqual(['other', 'root'])
  })

  it('finds a function by its name, file or the table it writes, every word in any order', () => {
    expect(filterFunctions(FNS, { q: 'orders' }).map((f) => f.name)).toEqual(['saveOrder'])
    expect(filterFunctions(FNS, { q: 'B.TS leaf' }).map((f) => f.name)).toEqual(['leaf'])
    expect(searchText(FNS[4])).toContain('orders')
  })

  it('draws two steps around a function and counts what it cuts', () => {
    const g = callGraph(BY_ID.get('a.ts#mid')!, BY_ID)
    expect(g.callers.map((f) => f.name)).toEqual(['root', 'other'])
    expect(g.callees.map((f) => f.name)).toEqual(['leaf', 'saveOrder'])
    expect(g.callees2).toEqual([{ fn: BY_ID.get('c.ts#deep'), via: 'b.ts#leaf' }])
    expect(g.callers2).toEqual([])
    const small = callGraph(BY_ID.get('a.ts#mid')!, BY_ID, 1)
    expect(small.more).toEqual({ callers: 1, callees: 1, far: 0 })
  })

  it('opens the most complex neighbour first, and shortens a qualified name', () => {
    expect(riskiestNeighbour(BY_ID.get('a.ts#mid')!, BY_ID)?.name).toBe('leaf')
    expect(shortName({ name: 'OrdersPage.handleSave' })).toBe('handleSave')
    expect(shortName({ name: 'Program::Main' })).toBe('Main')
  })

  it('filters 20,000 functions in well under a frame budget', () => {
    const many = Array.from({ length: 20000 }, (_, i) => fn(`src/m${i % 400}.ts#f${i}`, { complexity: m(i % 30), callers: i % 7 ? [] : ['x'] }))
    const texts = new Map(many.map((f) => [f.id, searchText(f)]))
    const start = performance.now()
    const kept = filterFunctions(many, { q: 'm12', sort: 'risk' }, texts)
    expect(kept.length).toBeGreaterThan(0)
    expect(performance.now() - start).toBeLessThan(150)
  })
})
