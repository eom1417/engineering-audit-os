import { describe, expect, it } from 'vitest'
import { filterScreens, measured, pins, shotsAt, thumbnail, widths, type Screen, type ScreensData } from './model'

const screen = (id: string, extra: Partial<Screen> = {}): Screen => ({ id, route: `/${id}`, title: id, shots: [], inputs: [], issues: [], ...extra })

const ORDERS = screen('orders', {
  shots: [
    { path: 'screens/orders-1440.png', width: 1440, phase: 'baseline', batch: null },
    { path: 'screens/orders-390.png', width: 390, phase: 'before', batch: 'wave-1' },
    { path: 'screens/orders-390-after.png', width: 390, phase: 'after', batch: 'wave-1' },
  ],
  issues: [
    { id: 'i2', rule: 'target-size', severity: 'medium', summary: 'Small button', width: 390, box: { x: 200, y: 300, w: 20, h: 20 }, state: 'open' },
    { id: 'i1', rule: 'label', severity: 'high', summary: 'No label', width: 390, box: { x: 16, y: 120, w: 300, h: 40 }, state: 'open' },
    { id: 'i3', rule: 'contrast', severity: 'low', summary: 'Faint text', width: 1440, box: { x: 10, y: 10, w: 100, h: 20 }, state: 'fixed' },
  ],
})

describe('the screens gallery reads screens.json and never shows "not measured" as "none"', () => {
  it('says which parts were not measured', () => {
    const data: ScreensData = { screens: [], missing: [{ id: 'shots', state: 'not_measured', step: 'NS41.T1', count: { value: 0, src: 's' }, detail: { ar: 'أ', en: 'a' } }] }
    expect(measured(data, 'shots')).toBe(false)
    expect(measured(data, 'inputs')).toBe(true)
  })

  it('pairs before and after at one width, else shows the one shot there is', () => {
    expect(widths(ORDERS)).toEqual([390, 1440])
    expect(shotsAt(ORDERS, 390)).toEqual({ before: ORDERS.shots[1], after: ORDERS.shots[2] })
    expect(shotsAt(ORDERS, 1440)).toEqual({ one: ORDERS.shots[0] })
    expect(thumbnail(ORDERS)?.path).toBe('screens/orders-390-after.png')
    expect(thumbnail(screen('empty'))).toBeUndefined()
  })

  it('numbers the pins of one width in reading order', () => {
    expect(pins(ORDERS, 390).map((p) => [p.id, p.n])).toEqual([['i1', 1], ['i2', 2]])
    expect(pins(ORDERS, 1440).map((p) => p.id)).toEqual(['i3'])
  })

  it('puts screens with open issues first and filters by issues, journey flags and shots', () => {
    const list = [screen('b'), screen('a', { flags: ['dead_end'] }), ORDERS]
    expect(filterScreens(list, 'all').map((s) => s.id)).toEqual(['orders', 'a', 'b'])
    expect(filterScreens(list, 'issues').map((s) => s.id)).toEqual(['orders'])
    expect(filterScreens(list, 'flagged').map((s) => s.id)).toEqual(['a'])
    expect(filterScreens(list, 'shot').map((s) => s.id)).toEqual(['orders'])
  })
})
