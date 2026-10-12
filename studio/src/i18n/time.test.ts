// The one time formatter (NS46.T19): the person's zone, a relative form and the exact time with its zone; stored
// times stay UTC. Pinned to two non-UTC zones, one with a half-hour offset.
import { describe, expect, it } from 'vitest'
import { instruction } from '../branches/ScanSheet'
import { timeFormatter, validZone } from './prefs'

const AT = '2026-10-09T08:00:00+00:00'

describe('timeFormatter', () => {
  it("shows the exact time in the person's zone, half-hour offsets and the day included", () => {
    const text = timeFormatter('en', 'Asia/Dubai').exact(AT)
    expect(text).toContain('12:00')
    expect(text).toMatch(/GMT\+4|GST/)
    const text2 = timeFormatter('en', 'Asia/Kolkata').exact(AT)
    expect(text2).toContain('13:30')
    expect(text2).toMatch(/GMT\+5:30|IST/)
    expect(timeFormatter('ar', 'Pacific/Auckland').exact('2026-10-09T20:00:00Z')).toMatch(/10/)
    expect(timeFormatter('ar', 'Asia/Kolkata').exact(AT)).toContain('13:30')
  })
  it('says how long ago in both languages and never changes what is stored', () => {
    const now = Date.parse(AT) + 8 * 3600 * 1000
    expect(timeFormatter('en', 'Asia/Dubai').ago(AT, now)).toBe('8 hours ago')
    expect(timeFormatter('ar', 'Asia/Dubai').ago(AT, now)).toMatch(/8/)
    expect(new Date(AT).toISOString()).toBe('2026-10-09T08:00:00.000Z')
    expect(validZone('Asia/Kolkata')).toBe(true)
    expect(validZone('Mars/Base')).toBe(false)
  })
})

describe('the copy fallback', () => {
  it('is complete and self-contained', () => {
    const text = instruction('en', { name: 'shop', path: '/Users/o/shop', branch: 'develop', tip: 'a'.repeat(40), scanned: 'b'.repeat(40), at: AT })
    for (const part of ['/Users/o/shop', 'develop', 'a'.repeat(40), 'b'.repeat(40), 'audit', 'Do not change', 'tell me']) expect(text).toContain(part)
    const ar = instruction('ar', { name: 'shop', path: null, branch: null, tip: null, scanned: null, at: null })
    expect(ar).toContain('audit')
    expect(ar).toContain('shop')
  })
})
