import { describe, expect, it } from 'vitest'
import { buildIndex, type Entry } from './search'

const entries: Entry[] = [
  { id: 'page:home', kind: 'page', title: 'الرئيسية', keywords: 'Home', to: '/' },
  { id: 'page:problems', kind: 'page', title: 'المشاكل', keywords: 'Problems findings', to: '/problems' },
  { id: 'card:TASK-001', kind: 'card', title: 'مسار الصفحة يتوقف عند استدعاءات غير محلولة', keywords: 'TASK-001 src/App.tsx', to: '/problems?card=TASK-001' },
  { id: 'comp:src/components/account', kind: 'component', title: 'src/components/account', to: '/system?focus=src/components/account' },
  { id: 'decision:investigations', kind: 'decision', title: '52 بطاقة تحتاج تحققًا قبل أي تغيير. هل يتولاها المساعد؟', to: '/decisions' },
  { id: 'doc:plan', kind: 'doc', title: 'خطة الإصلاح', keywords: 'FIX-PLAN.md', to: '/library' },
]
const index = buildIndex(entries)
const ids = (query: string) => index.search(query).map((entry) => entry.id)

describe('search', () => {
  it('finds Arabic whatever the alef, ta marbuta or ya form typed', () => {
    expect(ids('خطه الاصلاح')).toContain('doc:plan')
    expect(ids('خطة الإصلاح')).toContain('doc:plan')
    expect(ids('بطاقه')).toContain('decision:investigations')
  })

  it('ignores diacritics and tatweel in the query', () => {
    expect(ids('الـمَشاكِل')).toEqual(['page:problems'])
  })

  it('matches Arabic-Indic digits against Western ones', () => {
    expect(ids('٥٢')).toContain('decision:investigations')
  })

  it('finds a path by any of its segments and by prefix', () => {
    expect(ids('account')).toContain('comp:src/components/account')
    expect(ids('compon acc')).toContain('comp:src/components/account')
  })

  it('finds a card by its id', () => {
    expect(ids('TASK-001')[0]).toBe('card:TASK-001')
    expect(ids('task 001')[0]).toBe('card:TASK-001')
  })

  it('finds a page by its other language', () => {
    expect(ids('home')).toEqual(['page:home'])
  })

  it('shows the pages when the query is empty', () => {
    expect(ids('  ')).toEqual(['page:home', 'page:problems'])
  })

  it('finds a word with or without the Arabic article', () => {
    expect(ids('مشاكل')).toEqual(['page:problems'])
    expect(ids('الخطة')).toContain('doc:plan')
  })

  it('finds nothing for an unrelated word', () => {
    expect(ids('kubernetes')).toEqual([])
  })
})
