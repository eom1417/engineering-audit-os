import { describe, expect, it } from 'vitest'
import { EMPTY, MAX_CARDS, pickGroup, setMany, toSelection, toggle } from './selectionModel'

const ORDER = ['A', 'B', 'C', 'D', 'E']

describe('the selection model', () => {
  it('ticks one box, then shift-ticks the range from it over the shown order', () => {
    let state = toggle(EMPTY, 'B', false, ORDER)
    expect(state.ids).toEqual(['B'])
    state = toggle(state, 'D', true, ORDER)
    expect(state.ids).toEqual(['B', 'C', 'D'])
    expect(state.anchor).toBe('B')
    state = toggle(state, 'C', false, ORDER)
    expect(state.ids).toEqual(['B', 'D'])
  })

  it('a shift-untick clears the range', () => {
    let state = setMany(EMPTY, ORDER, true)
    state = toggle(state, 'B', false, ORDER)
    state = toggle(state, 'D', true, ORDER)
    expect(state.ids).toEqual(['A', 'E'])
  })

  it('names a group the way the server resolves it, else the ids as seen', () => {
    expect(toSelection(EMPTY)).toBeNull()
    expect(toSelection(toggle(EMPTY, 'A', false, ORDER))).toEqual({ kind: 'card', cards: ['A'] })
    expect(toSelection(setMany(EMPTY, ['A', 'B'], true))).toEqual({ kind: 'cards', cards: ['A', 'B'] })
    expect(toSelection(pickGroup(EMPTY, ['A'], { by: 'severity', value: 'high', label: 'High' }))).toEqual({ kind: 'group', group: { by: 'severity', value: 'high' } })
    expect(toSelection(pickGroup(EMPTY, ['A', 'B'], { by: 'step', value: 'M01', label: 'M01' }))).toEqual({ kind: 'step', step: 'M01' })
    // a component's cards are sent as the ids the map counts for it
    expect(toSelection(pickGroup(EMPTY, ['A', 'B'], { by: 'component', value: 'src', label: 'src' }))?.kind).toBe('cards')
    // changing a group by hand drops its name
    expect(toggle(pickGroup(EMPTY, ['A', 'B'], { by: 'area', value: 'x', label: 'x' }), 'C', false, ORDER).group).toBeNull()
  })

  it('holds at most the contract’s 500 cards', () => {
    const many = Array.from({ length: 700 }, (_, i) => `T${i}`)
    expect(pickGroup(EMPTY, many, null).ids).toHaveLength(MAX_CARDS)
    expect(setMany(EMPTY, many, true).ids).toHaveLength(MAX_CARDS)
  })
})
