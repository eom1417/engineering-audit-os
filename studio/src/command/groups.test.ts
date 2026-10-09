import { describe, expect, it } from 'vitest'
import type { StudioData } from '../data/types'
import { groupsOf, stepCards } from './groups'

describe('report selection groups', () => {
  it('preserves order, duplicate card IDs, operation unions and step fallbacks', () => {
    const data = {
      cards: { cards: [
        { id: 'A', category: 'quality', severity: 'high', paths: ['src/ui/a'], milestone: 'M1' },
        { id: 'B', category: 'quality', severity: 'low', paths: ['src/b'], milestone: 'M1' },
        { id: 'A', category: 'quality', severity: 'high', paths: ['src/ui/a'], milestone: 'M1' },
        { id: 'C', category: 'security', severity: 'critical', paths: [], milestone: 'M2' },
      ] },
      story: { current: { components: [{ name: 'src' }, { name: 'src/ui' }] }, gap: [
        { component: 'src/ui', relation: 'modify', cards: ['A', 'missing', 'A'] },
        { component: 'src', relation: 'modify', cards: ['B', 'A'] },
        { component: 'unchanged', relation: 'retain', cards: ['C'] },
      ] },
      plans: { plans: [{ steps: [
        { id: 'M1', title: 'First', tasks: [] }, { id: 'M2', tasks: [] },
        { id: 'M3', gate: 'Fallback', tasks: [{ id: 'B' }, { id: 'missing' }, { id: 'B' }] },
      ] }] },
    } as unknown as StudioData
    const groups = groupsOf(data)
    expect(groups.area.map((g) => [g.value, g.ids])).toEqual([['quality', ['A', 'B', 'A']], ['security', ['C']]])
    expect(groups.component.map((g) => [g.value, g.ids])).toEqual([['src/ui', ['A', 'A']], ['src', ['B']]])
    expect(groups.gap.map((g) => g.ids)).toEqual([['B', 'A'], ['A', 'A']])
    expect(groups.operation.map((g) => [g.value, g.ids])).toEqual([['modify', ['A', 'B']]])
    expect(groups.step.map((g) => [g.value, g.ids])).toEqual([['M1', ['A', 'B', 'A']], ['M2', ['C']], ['M3', ['B', 'B']]])
    expect(stepCards(data, 'M3')).toEqual(['B', 'B'])
    expect(stepCards(data, 'missing')).toEqual([])
  })
})
