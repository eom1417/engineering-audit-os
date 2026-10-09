import { describe, expect, it } from 'vitest'
import { localizeReport, type ReportLocale } from './localization'
import type { Loaded } from './load'
const locale: ReportLocale = { schema_version: 1, source_locale: 'ar', translations: { en: { 'هل تعتمد الخطة؟': 'Do you approve the plan?', 'نعم': 'Yes', 'لاحقًا': 'Later', 'المكوّن': 'Component' } } }
const source = { kind: 'ready', data: { manifest: { project: { name: 'EAOS' } }, decisions: { decisions: [{ id: 'المكوّن', question: 'هل تعتمد الخطة؟', options: [{ id: 'yes', label: 'نعم' }, { id: 'later', label: 'لاحقًا' }] }] }, evidence: { facts: [{ path: 'المكوّن', summary: 'المكوّن' }] } } } as unknown as Loaded
describe('Report display language', () => {
  it('switches questions and options together without changing decision identity or source locations', () => {
    const english = localizeReport(source, 'en', locale)
    if (english.kind !== 'ready') throw Error('Expected report')
    expect(english.data.decisions?.decisions[0]).toEqual({ id: 'المكوّن', question: 'Do you approve the plan?', options: [{ id: 'yes', label: 'Yes' }, { id: 'later', label: 'Later' }] })
    expect(english.data.evidence?.facts[0]).toEqual({ path: 'المكوّن', summary: 'Component' })
  })
  it('can switch back without mutating the source or its copied decision meaning', () => {
    localizeReport(source, 'en', locale)
    expect(localizeReport(source, 'ar', locale)).toBe(source)
    if (source.kind === 'ready') expect(source.data.decisions?.decisions[0].options[0].id).toBe('yes')
  })
})
