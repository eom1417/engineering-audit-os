import { describe, expect, it } from 'vitest'
import type { Card, StudioData } from '../../data/types'
import { activeCount, assistantFixes, filterRows, groupRows, itemsOf, prepare, queryWords, readFilters } from './model'

const SEV = ['critical', 'high', 'medium', 'low'] as const
const AREAS = ['security', 'structure', 'quality', 'maintainability']
const STATES = ['open', 'open', 'in_batch', 'done'] as const

function card(i: number, extra: Partial<Card> = {}): Card {
  return {
    id: `TASK-${String(i).padStart(5, '0')}`, key: `k${i}`, title: `Problem ${i}`, kind: 'dead_code', category: AREAS[i % 4],
    severity: SEV[i % 4], state: STATES[i % 4], fixable: i % 3 === 0, needs_decision: i % 5 === 0, milestone: `M0${(i % 3) + 1}`,
    paths: [`src/c${i % 7}/m${i % 3}.ts`], evidence: [], scope: 'place', confidence: 1, ...extra,
  }
}

function data(cards: Card[]): StudioData {
  return {
    manifest: { contract: 1, built: { built: '', commit: '', digest: '', version: '' }, project: { name: 't' }, scanned: { at: null, branch: null, commit: null }, sections: [] },
    cards: { cards },
    story: { current: { components: Array.from({ length: 7 }, (_, i) => ({ name: `src/c${i}`, files: 3, layer: 'x' })) }, target: { components: [] }, gap: [] },
    plans: { plans: [{ id: 'fix', kind: 'fix', state: 'todo', progress: { value: 0, src: 'x' }, steps: ['M03', 'M01', 'M02'].map((id) => ({ id, state: 'todo', gate: '', tasks: [] })) }] },
    missing: [],
  }
}

const twelve = Array.from({ length: 12 }, (_, i) => card(i))

function run(cards: Card[], search: Record<string, string>) {
  const list = prepare(data(cards), 'ar')
  return { result: filterRows(list, readFilters(search)), order: list.order }
}

describe('filters', () => {
  it('reads the filters from the address and keeps the cards matching every facet, in report order', () => {
    const f = readFilters({ severity: 'high,critical', who: 'nobody', group: 'step', q: 'x' })
    expect(f.chosen.severity).toEqual(['high', 'critical'])
    expect(f.who).toBe('all')
    expect(f.group).toBe('step')
    expect(activeCount(f)).toBe(2)
    expect(readFilters({ group: 'colour' }).group).toBeNull()
    const { result } = run(twelve, { severity: 'critical,high', state: 'open' })
    expect(result.rows.map((r) => r.card.id)).toEqual(['TASK-00000', 'TASK-00001', 'TASK-00004', 'TASK-00005', 'TASK-00008', 'TASK-00009'])
    expect(run(twelve, { who: 'you' }).result.rows.every((r) => r.card.needs_decision)).toBe(true)
    expect(run(twelve, { who: 'eaos' }).result.rows.every((r) => !r.card.needs_decision)).toBe(true)
    expect(run(twelve, { component: 'src/c2' }).result.rows.map((r) => r.card.id)).toEqual(['TASK-00002', 'TASK-00009'])
  })

  it('counts each facet value as what choosing it would show, a chosen value kept at zero, in a stable order', () => {
    const { result } = run(twelve, { severity: 'critical', state: 'open' })
    const sev = Object.fromEntries(result.facets.severity.map((f) => [f.value, f.count]))
    // severity counts ignore the severity filter but apply the state filter (states open, open, in_batch, done)
    expect(sev).toEqual({ critical: 3, high: 3, medium: 0, low: 0 })
    const state = Object.fromEntries(result.facets.state.map((f) => [f.value, f.count]))
    expect(state).toEqual({ open: 3, in_batch: 0, done: 0 })   // cards 0, 4, 8 are critical, all open
    for (const value of result.facets.severity) {
      const picked = run(twelve, { severity: value.value, state: 'open' }).result.rows.length
      expect(picked).toBe(value.count)
    }
    const { result: result2 } = run(twelve, { severity: 'low', state: 'in_batch' })
    expect(result2.facets.severity.map((f) => f.value)).toEqual(['critical', 'high', 'medium', 'low'])
    expect(result2.facets.severity.find((f) => f.value === 'low')?.count).toBe(0)
    const a = run(twelve, {}).result.facets.component.map((f) => f.value)
    expect(run(twelve, { severity: 'critical' }).result.facets.component.map((f) => f.value)).toEqual(a)
    expect(run(twelve, { component: 'src/gone' }).result.facets.component.map((f) => f.value)).toEqual([...a, 'src/gone'])
  })
})

describe('Arabic search', () => {
  const cards = [
    card(1, { title: 'المشكلة في الإصلاح الأول' }),
    card(2, { title: 'مسار الصفحة يتوقف عند استدعاءات غير محلولة' }),
    card(3, { title: 'Dead module', why: { ar: 'كود لا يشغّله أحد يبقى يُقرأ ويُصان', en: 'Code nobody runs is still read' } }),
  ]
  const ids = (q: string) => run(cards, { q }).result.rows.map((r) => r.card.id)

  it('folds Arabic on both sides, needs every word and finds ids, paths and why it matters', () => {
    expect(ids('مشكله')).toEqual(['TASK-00001'])
    expect(ids('اصلاح')).toEqual(['TASK-00001'])
    expect(ids('الإِصْلاح')).toEqual(['TASK-00001'])
    expect(ids('الصفحه')).toEqual(['TASK-00002'])
    expect(ids('مسار محلوله')).toEqual(['TASK-00002'])
    expect(ids('مسار الإصلاح')).toEqual([])
    expect(ids('task-00003')).toEqual(['TASK-00003'])
    expect(ids('c3/m0')).toEqual(['TASK-00003'])
    expect(ids('يشغله')).toEqual(['TASK-00003'])
    expect(queryWords('  المشاكل والمكونات ')).toEqual(['مشاكل', 'مكونات'])
  })
})

describe('grouping', () => {
  it('groups by plan step in plan order, the cards without a step last, headings before their rows', () => {
    const cards = [...twelve, card(99, { milestone: null })]
    const { result, order } = run(cards, {})
    expect(groupRows(result.rows, 'step', order).map((g) => g.key)).toEqual(['M03', 'M01', 'M02', ''])
    const { result: result2, order: order2 } = run(twelve, { severity: 'critical' })
    const items = itemsOf(result2.rows, 'area', order2)
    expect(items.map((i) => (i.kind === 'group' ? `#${i.key}:${i.count}` : i.row.card.id))).toEqual(['#security:3', 'TASK-00000', 'TASK-00004', 'TASK-00008'])
  })
})

describe('5,000 cards', () => {
  it('filters, counts and groups within the budget (100 ms)', () => {
    const cards = Array.from({ length: 5000 }, (_, i) => card(i, { title: i % 2 ? `مشكلة رقم ${i} في المكوّن` : `Problem ${i} in component` }))
    const list = prepare(data(cards), 'ar')
    const searches = [{}, { severity: 'high,critical' }, { q: 'مشكله' }, { q: 'component 12', group: 'area' }, { state: 'open', who: 'you', group: 'step' }]
    const times: number[] = []
    for (const search of searches) {
      const started = performance.now()
      const filters = readFilters(search)
      const result = filterRows(list, filters)
      itemsOf(result.rows, filters.group, list.order)
      times.push(performance.now() - started)
    }
    expect(Math.max(...times)).toBeLessThan(100)
  })
})

describe('what your assistant will fix', () => {
  it('is the open cards the assistant decided to fix itself, most severe first; never its questions to the owner nor closed cards', () => {
    const fix = { kind: 'fix' as const, by: 'assistant', words: 'Remove it', why: 'unused' }
    const cards = [card(3, { severity: 'low', state: 'open', resolution: fix }), card(1, { severity: 'high', state: 'open', resolution: fix }),
      card(2, { state: 'done', resolution: fix }), card(4, { state: 'open', resolution: { ...fix, kind: 'owner' } }), card(5, { state: 'open' })]
    expect(assistantFixes(cards)).toEqual(['TASK-00001', 'TASK-00003'])
  })
})
