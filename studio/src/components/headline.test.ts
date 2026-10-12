import { describe, expect, it } from 'vitest'
import { headlineParts, recommendedOption } from './Story'

describe('headlineParts', () => {
  it('links each number with the word after it, only a whole number that is in the text', () => {
    const parts = headlineParts('217 مشكلة، منها 165 يصلحها EAOS وحده.', [{ value: 217, to: '/problems' }, { value: 165, to: '/problems', search: { who: 'eaos' } }])
    expect(parts).toEqual([
      { value: 217, to: '/problems', word: 'مشكلة' }, '، منها ',
      { value: 165, to: '/problems', search: { who: 'eaos' }, word: 'يصلحها' }, ' EAOS وحده.',
    ])
    expect(headlineParts('No problems.', [{ value: 3, to: '/x' }])).toEqual(['No problems.'])
    expect(headlineParts('1217 items', [{ value: 217, to: '/x' }])).toEqual(['1217 items'])
  })
})

describe('recommendedOption', () => {
  const base = { id: 'd', state: 'waiting' as const, answer: null, tool: null, plan: null, question: 'q', blocks: [] }
  it('promotes only the option the recommendation opens with', () => {
    const d = { ...base, recommendation: 'نعم: يتحقق المساعد من كل بطاقة.', options: [{ id: 'later', label: 'لاحقًا' }, { id: 'yes', label: 'نعم' }] }
    expect(recommendedOption(d)?.id).toBe('yes')
    const d2 = { ...base, recommendation: 'راجع قرارات البنية ثم اعتمدها.', options: [{ id: 'ADR-001', label: 'Move 0 files' }, { id: 'later', label: 'لاحقًا' }] }
    expect(recommendedOption(d2)).toBeUndefined()
    const d3 = { ...base, recommendation: 'نعمل على ذلك', options: [{ id: 'yes', label: 'نعم' }] }
    expect(recommendedOption(d3)).toBeUndefined()
  })
})

describe('decision identity and recommendation', () => {
  const base = { id: 'd', state: 'waiting' as const, answer: null, tool: null, plan: null, question: 'q', blocks: [] }
  it('keeps a stable recommended option and invents none when a label match is ambiguous', () => {
    expect(recommendedOption({ ...base, recommendation: 'unrelated prose', recommended_option: 'yes', options: [{ id: 'yes', label: 'نعم' }] })?.id).toBe('yes')
    expect(recommendedOption({ ...base, recommendation: 'Yes: go on', options: [{ id: 'a', label: 'Yes' }, { id: 'b', label: 'Yes' }] })).toBeUndefined()
  })
})
