import { describe, expect, it } from 'vitest'
import { active, idle, notMeasured, tally, type Detector, type QualityData } from './model'

const m = (value: number | null) => ({ value, src: 's' })
const d = (id: string, status: Detector['status'], here: Detector['here'], applies = true): Detector =>
  ({ id, name: id, applies, precision: m(status === 'not_measured' ? null : 0.9), recall: m(0.8), status, here })
const DETECTORS = [d('b', 'below_bar', { shown: 0, withheld: 5, facts: 0 }), d('a', 'meets_bar', { shown: 10, withheld: 0, facts: 0 }),
  d('n', 'not_measured', { shown: 0, withheld: 1, facts: 0 }), d('i', 'meets_bar', { shown: 0, withheld: 0, facts: 0 }, false)]

describe('the quality page', () => {
  it('puts the detectors whose findings are shown first, the idle ones apart', () => {
    expect(active(DETECTORS).map((x) => x.id)).toEqual(['a', 'b', 'n'])
    expect(idle(DETECTORS).map((x) => x.id)).toEqual(['i'])
  })

  it('counts what was shown, held back and not measured', () => {
    expect(tally(DETECTORS)).toEqual({ shown: 10, withheld: 6, facts: 0, meeting: 1, under: 1, unmeasured: 1 })
    const q: QualityData = { detectors: DETECTORS, capabilities: [], indicators: [{ id: 'S5', name: 'x', value: m(null), target: 0.9 }, { id: 'S1', name: 'y', value: m(0.9), target: 0.8 }] }
    expect(notMeasured(q)).toBe(2)
  })
})
