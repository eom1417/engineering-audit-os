import { describe, expect, it } from 'vitest'
import type { Plan, Story } from '../../data/types'
import type { Timeline } from '../paths/model'
import { band, bridge, cardState, layers, layout, nextStep, OTHER, REMOVED, registerOrder, stepLinks } from './model'

const story: Story = {
  current: { components: [] },
  target: { components: [{ name: 'features', layer: 'features', responsibility: 'Domains' }, { name: 'lib', layer: 'lib', responsibility: 'Shared' },
    { name: 'home', layer: 'features', responsibility: 'The landing screen' }] },
  gap: [
    { component: 'src/a', relation: 'rebuild', to: 'features', files: 40, cards: [], closed: 0 },
    { component: 'src/b', relation: 'modify', to: 'features', files: 30, cards: [], closed: 0 },
    { component: 'src/c', relation: 'retain', to: 'lib', files: 20, cards: [], closed: 0 },
    { component: 'old', relation: 'delete', to: 'lib', files: 6, cards: [], closed: 0 },
    ...Array.from({ length: 6 }, (_, i) => ({ component: `tiny/${i}`, relation: 'retain' as const, to: 'lib', files: 1, cards: [], closed: 0 })),
  ],
}

describe('the Bridge', () => {
  const b = bridge(story, 0.02, 5)

  it('keeps every file: what leaves today arrives somewhere, deleted files at "Removed"', () => {
    const left = b.left.reduce((s, x) => s + x.files, 0)
    const right = b.right.reduce((s, x) => s + x.files, 0)
    expect(left).toBe(102)
    expect(right).toBe(102)
    expect(b.right.find((r) => r.id === REMOVED)?.files).toBe(6)
    expect(b.flows.find((f) => f.from === 'old')).toMatchObject({ to: REMOVED, op: 'delete', gap: 'old' })
  })

  it('folds the smallest components under 2% of the files into one "Other" source, counted, only past the row limit', () => {
    expect(bridge(story).left.some((s) => s.id === OTHER)).toBe(false)
    const other = b.left.find((s) => s.id === OTHER)!
    expect(other.components).toBe(6)
    expect(other.files).toBe(6)
    expect(b.left.at(-1)!.id).toBe(OTHER)
  })

  it('marks a target fed by several components as a merge and one fed by none as new', () => {
    expect(b.right.find((r) => r.id === 'features')!.op).toBe('merge')
    expect(b.right.find((r) => r.id === 'home')).toMatchObject({ op: 'new', files: 0, components: 0 })
  })

  it('draws each ribbon exactly as thick as its files at one scale', () => {
    const placed = layout(b, 600)
    for (const r of placed.ribbons) expect(r.w).toBeCloseTo(r.files * placed.scale)
    expect(band(0, 100, 0, 50, 10)).toMatch(/^M0,0C50,0 50,50 100,50L100,60/)
  })
})

describe('the plan', () => {
  const timeline = {
    plan: 'fix', waves: [], counts: {},
    steps: [{ id: 'M01', title: '', tasks: 2, first: 1, last: 2 }, { id: 'M02', title: '', tasks: 1, first: 1, last: 1 }],
    tasks: [
      { id: 'T1', step: 'M02', wave: 1, title: '', state: 'open', waits: [], more: 0 },
      { id: 'T2', step: 'M01', wave: 2, title: '', state: 'open', waits: [{ task: 'T1', why: 'same_file' }], more: 0 },
      { id: 'T3', step: 'M01', wave: 2, title: '', state: 'open', waits: [{ task: 'T2', why: 'same_file' }], more: 0 },
    ],
  } as unknown as Timeline
  const plan = {
    id: 'fix', kind: 'fix', state: 'registered', progress: { value: 0, src: '' },
    steps: [{ id: 'M01', state: 'todo', gate: '', tasks: [{ id: 'T2', state: 'todo', title: '' }, { id: 'T3', state: 'todo', title: '' }] },
      { id: 'M02', state: 'todo', gate: '', tasks: [{ id: 'T1', state: 'todo', title: '' }] }],
  } as Plan

  it('links a step to the steps its tasks wait for, counting the waiting tasks, never a step to itself', () => {
    expect(stepLinks(timeline)).toEqual([{ from: 'M02', to: 'M01', tasks: 1 }])
    expect(stepLinks(null)).toEqual([])
  })

  it('lays a step one column after what it waits for', () => {
    expect(layers(['M01', 'M02'], stepLinks(timeline))).toEqual([['M02'], ['M01']])
    expect(layers(['A', 'B'], [{ from: 'A', to: 'B', tasks: 1 }, { from: 'B', to: 'A', tasks: 1 }]).flat().sort()).toEqual(['A', 'B'])
  })

  it('offers next the first open step that waits for nothing open', () => {
    expect(nextStep(plan, stepLinks(timeline))?.id).toBe('M02')
  })

  it('reads a card state and a plan task state alike', () => {
    expect([cardState('resolved'), cardState('on_branch'), cardState('skipped'), cardState('open'), cardState('todo')])
      .toEqual(['done', 'active', 'blocked', 'todo', 'todo'])
  })

  it('orders the register by the weight of the change', () => {
    const gap = (id: string, operation: 'retain' | 'rebuild' | 'delete', cards: number) =>
      ({ id, component: id, operation, files: 1, cards: Array(cards).fill('x'), cards_closed: 0, closed: { value: null, src: '' } })
    expect(registerOrder([gap('a', 'retain', 9), gap('b', 'delete', 1), gap('c', 'rebuild', 0), gap('d', 'rebuild', 2)]).map((g) => g.id))
      .toEqual(['d', 'c', 'b', 'a'])
  })
})
