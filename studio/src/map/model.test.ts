import { describe, expect, it } from 'vitest'
import type { SystemMap } from '../data/system'
import { counterpart, findingsBin, neighbours, ownerOf } from './model'

describe('the map model', () => {
  it('gives a card to the deepest component holding its path, else to (root)', () => {
    const owner = ownerOf(['(root)', 'src', 'src/ui', 'src/ui/old'])
    expect(owner('src/ui/old/a.ts')).toBe('src/ui/old')
    expect(owner('src/ui/a.ts')).toBe('src/ui')
    expect(owner('src/uix/a.ts')).toBe('src')
    expect(owner('README.md')).toBe('(root)')
    expect(ownerOf(['src'])('README.md')).toBeUndefined()
  })

  it('bins findings as DESIGN.md says: 0, 1–3, 4–9, 10–19, 20+', () => {
    expect([0, 1, 3, 4, 9, 10, 19, 20, 99].map(findingsBin)).toEqual([0, 1, 1, 2, 2, 3, 3, 4, 4])
  })

  it('lists who a component uses and who uses it, heaviest first', () => {
    const edges = [{ from: 'a', to: 'b', imports: 1 }, { from: 'a', to: 'c', imports: 5 }, { from: 'd', to: 'a', imports: 2 }].map((e) => ({ ...e, d: '', width: 1 }))
    expect(neighbours(edges, 'a')).toEqual({ uses: [{ id: 'c', imports: 5 }, { id: 'b', imports: 1 }], usedBy: [{ id: 'd', imports: 2 }] })
  })

  it('lights a component’s target, and a target’s sources', () => {
    const system = {
      current: { nodes: [{ id: 'src/ui', target: 'features' }] },
      target: { nodes: [{ id: 'features', sources: ['src/ui', 'src/old'] }] },
    } as unknown as SystemMap
    expect(counterpart(system, 'change', 'src/ui')).toEqual(['features'])
    expect(counterpart(system, 'target', 'features')).toEqual(['src/ui', 'src/old'])
    expect(counterpart(system, 'current', undefined)).toEqual([])
  })
})
