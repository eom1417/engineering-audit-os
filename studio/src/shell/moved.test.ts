import { describe, expect, it } from 'vitest'
import { MOVED, movedTo } from './moved'

const row = (from: string) => MOVED.find((m) => m.from === from)!

describe('the addresses that moved', () => {
  it('opens the Checks page for every old page of a check, on the tab that holds it', () => {
    expect(movedTo(row('/scan'), { flow: 'check', stage: 'facts' })).toEqual({ to: '/checks', search: { flow: 'check', stage: 'facts' } })
    expect(movedTo(row('/tools'), {})).toEqual({ to: '/checks', search: {} })
    expect(movedTo(row('/runs'), { q: 'fix', other: 'x' })).toEqual({ to: '/checks', search: { tab: 'runs', q: 'fix' } })
    expect(movedTo(row('/history'), {})).toEqual({ to: '/checks', search: { tab: 'checks' } })
  })
  it('opens Settings for the old Assistant page', () => {
    expect(movedTo(row('/assistant'), {})).toEqual({ to: '/settings', search: {} })
  })
})
