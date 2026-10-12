import { describe, expect, it } from 'vitest'
import { filterScreens, gallery, marks, measured, pins, shotsAt, thumbnail, widths, type PicturedPage, type Screen, type ScreensData } from './model'

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
  it('says which parts were not measured and pairs before and after at one width', () => {
    const data: ScreensData = { screens: [], missing: [{ id: 'shots', state: 'not_measured', step: 'NS41.T1', count: { value: 0, src: 's' }, detail: { ar: 'أ', en: 'a' } }] }
    expect(measured(data, 'shots')).toBe(false)
    expect(measured(data, 'inputs')).toBe(true)
    expect(widths(ORDERS)).toEqual([390, 1440])
    expect(shotsAt(ORDERS, 390)).toEqual({ before: ORDERS.shots[1], after: ORDERS.shots[2] })
    expect(shotsAt(ORDERS, 1440)).toEqual({ one: ORDERS.shots[0] })
    expect(thumbnail(ORDERS)?.path).toBe('screens/orders-390-after.png')
    expect(thumbnail(screen('empty'))).toBeUndefined()
  })

  it('numbers the pins in reading order and puts screens with open issues first', () => {
    expect(pins(ORDERS, 390).map((p) => [p.id, p.n])).toEqual([['i1', 1], ['i2', 2]])
    expect(pins(ORDERS, 1440).map((p) => p.id)).toEqual(['i3'])
    const list = [screen('b'), screen('a', { flags: ['dead_end'] }), ORDERS]
    expect(filterScreens(list, 'all').map((s) => s.id)).toEqual(['orders', 'a', 'b'])
    expect(filterScreens(list, 'issues').map((s) => s.id)).toEqual(['orders'])
    expect(filterScreens(list, 'flagged').map((s) => s.id)).toEqual(['a'])
    expect(filterScreens(list, 'shot').map((s) => s.id)).toEqual(['orders'])
  })
})

describe('the gallery shows only the pictures with problems, the problem marked where it is', () => {
  const picture = (path: string, width: number, findings: PicturedPage['pictures'][number]['findings']) =>
    ({ path, viewport: width < 768 ? 'phone' : 'desktop', width, height: 900, checks: [], findings })
  const at = (x: number, y: number) => ({ x, y, width: 0.2, height: 0.1 })
  const page = (path: string, state: PicturedPage['state'], pictures: PicturedPage['pictures']): PicturedPage =>
    ({ path, template: path, same_as: [], state, findings: pictures.reduce((n, p) => n + p.findings.length, 0), pictures })
  it('puts the most severe pages first, drops their clean pictures, counts the rest, and numbers marks in reading order', () => {
    const low = page('/a', 'findings', [picture('a-390.png', 390, [{ title: 'Faint', severity: 'low', region: at(0, 0) }])])
    const high = page('/b', 'findings', [picture('b-390.png', 390, []),
      picture('b-1440.png', 1440, [{ title: 'Crowded', severity: 'medium', region: at(0.5, 0.6) }, { title: 'Hidden', severity: 'high', region: at(0.1, 0.2) },
        { title: 'Whole page', severity: 'low', region: null }])])
    const out = gallery([low, page('/c', 'clean', [picture('c.png', 390, [])]), high, page('/d', 'not_reviewed', [picture('d.png', 390, [])])])
    expect(out.shown.map((p) => p.path)).toEqual(['/b', '/a'])
    expect(out.shown[0].pictures.map((p) => p.path)).toEqual(['b-1440.png'])
    expect([out.clean.length, out.notReviewed.length]).toEqual([1, 1])
    expect(marks(out.shown[0].pictures[0]).map((m) => [m.title, m.n])).toEqual([['Hidden', 1], ['Crowded', 2], ['Whole page', 3]])
  })
})
