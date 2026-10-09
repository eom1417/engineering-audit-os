import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { StudioData } from '../data/types'
import { counts } from '../data/context'
import { SeverityGlyph } from './Chip'
vi.mock('../i18n/prefs', () => ({ usePrefs: () => ({ t: (key: string) => key }) }))
describe('informational findings from the Studio contract', () => {
  it('renders an accessible informational glyph without an ordinal severity bar', () => {
    const html = renderToStaticMarkup(createElement(SeverityGlyph, { severity: 'info', word: false }))
    expect(html).toContain('aria-label="sevInfo"')
    expect(html).toContain('role="img"')
    expect(html).not.toContain('data-on')
  })
  it('counts informational cards without NaN or adding them to low severity', () => {
    const data = { cards: { cards: [{ severity: 'info', fixable: true, needs_decision: false }] } } as StudioData
    expect(counts(data).bySeverity).toEqual({ critical: 0, high: 0, medium: 0, low: 0, info: 1 })
    expect(counts(data).cards).toBe(1)
  })
})
