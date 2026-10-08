// The Problems list as data: the filters read from the address, the facets with their counts, the search with the
// Studio's Arabic normaliser, and the grouping by area, component or plan step. Pure functions, so the page renders
// what they return and the 5,000-card budget is measured on them and in the browser (tools/studio_budgets.py).
import type { Card, CardState, StudioData } from '../../data/types'
import { normalize, terms, tokenize } from '../../search/normalize'
import { componentOwner } from '../../command/groups'

export type Who = 'all' | 'you' | 'eaos'
export type Facet = 'severity' | 'area' | 'state' | 'step' | 'component'
export type GroupBy = 'area' | 'component' | 'step'

export const FACETS: Facet[] = ['severity', 'area', 'state', 'step', 'component']
export const GROUPS: GroupBy[] = ['area', 'component', 'step']
export const SEVERITY_ORDER: string[] = ['critical', 'high', 'medium', 'low', 'info']
export const STATE_ORDER: CardState[] = ['open', 'in_batch', 'on_branch', 'done', 'resolved', 'skipped']

/** The address of the list: every filter, the grouping, the search words and the open card. */
export interface ProblemsSearch {
  card?: string
  q?: string
  who?: string
  severity?: string
  area?: string
  state?: string
  step?: string
  component?: string
  group?: string
  demo?: string
}

export const SEARCH_KEYS = ['card', 'q', 'who', 'severity', 'area', 'state', 'step', 'component', 'group', 'demo'] as const

export interface Filters {
  q: string
  who: Who
  chosen: Record<Facet, string[]>
  group: GroupBy | null
}

/** One card with what the list filters and groups it by, computed once per report. */
export interface Row {
  card: Card
  component: string | null
  step: string | null
  /** The card's words normalised for search: title, id, paths, kind, area and why it matters */
  text: string
}

const list = (value: string | undefined) => (value ? value.split(',').filter(Boolean) : [])

export function readFilters(search: ProblemsSearch): Filters {
  const who: Who = search.who === 'you' || search.who === 'eaos' ? search.who : 'all'
  const group = GROUPS.includes(search.group as GroupBy) ? (search.group as GroupBy) : null
  const chosen = Object.fromEntries(FACETS.map((facet) => [facet, list(search[facet])])) as Record<Facet, string[]>
  return { q: search.q ?? '', who, chosen, group }
}

/** The address for one facet's values: the list joined, or nothing when empty. */
export function facetParam(values: string[]): string | undefined {
  return values.length ? values.join(',') : undefined
}

export function activeCount(filters: Filters): number {
  return FACETS.reduce((sum, facet) => sum + filters.chosen[facet].length, 0) + (filters.who !== 'all' ? 1 : 0)
}

export function rowsOf(data: StudioData, lang: 'ar' | 'en'): Row[] {
  const cards = data.cards?.cards ?? []
  const owner = componentOwner(data)
  return cards.map((card) => ({
    card,
    component: (card.paths[0] && owner(card.paths[0])) || null,
    step: card.milestone,
    text: normalize([card.title, card.id, card.paths.join(' '), card.kind, card.category, card.why?.[lang] ?? ''].join(' ')),
  }))
}

function valueOf(row: Row, facet: Facet): string | null {
  switch (facet) {
    case 'severity': return row.card.severity
    case 'area': return row.card.category || null
    case 'state': return row.card.state
    case 'step': return row.step
    case 'component': return row.component
  }
}

/** The query as the normalised words that must all appear: each word without its article, so "المشاكل" finds
 * "مشاكل" and "مشكلة" finds "مشكله". */
export function queryWords(q: string): string[] {
  return tokenize(normalize(q)).map((word) => terms(word).at(-1)!).filter(Boolean)
}

function matchesText(row: Row, words: string[]): boolean {
  for (const word of words) if (!row.text.includes(word)) return false
  return true
}

function matchesWho(row: Row, who: Who): boolean {
  return who === 'all' || (who === 'you') === row.card.needs_decision
}

function matchesFacet(row: Row, facet: Facet, values: string[]): boolean {
  if (!values.length) return true
  const value = valueOf(row, facet)
  return value !== null && values.includes(value)
}

export interface FacetCount { value: string; count: number }

export interface Filtered {
  rows: Row[]
  /** For each facet, every value with the number of cards it would show given the other filters */
  facets: Record<Facet, FacetCount[]>
}

/** The cards the filters keep, in the report's order (the plan's priority), and each facet's counts. A facet's
 * counts apply every filter but its own, so a count is always what pressing that value would show. */
export function filterRows(list: List, filters: Filters): Filtered {
  const { rows, values } = list
  const words = queryWords(filters.q)
  const base = words.length || filters.who !== 'all' ? rows.filter((row) => matchesWho(row, filters.who) && matchesText(row, words)) : rows
  const active = FACETS.filter((facet) => filters.chosen[facet].length)
  const counts = Object.fromEntries(FACETS.map((facet) => [facet, new Map<string, number>()])) as Record<Facet, Map<string, number>>
  const kept: Row[] = []
  for (const row of base) {
    // which active facets this row fails: none -> kept; exactly one -> it still counts for that facet
    let failed: Facet | null = null
    let failures = 0
    for (const facet of active) {
      if (!matchesFacet(row, facet, filters.chosen[facet])) { failures += 1; failed = facet; if (failures > 1) break }
    }
    if (failures > 1) continue
    if (failures === 0) kept.push(row)
    for (const facet of FACETS) {
      if (failures === 1 && facet !== failed) continue
      const value = valueOf(row, facet)
      if (value === null) continue
      counts[facet].set(value, (counts[facet].get(value) ?? 0) + 1)
    }
  }
  const facets = Object.fromEntries(FACETS.map((facet) => {
    // every value of the report, in its fixed order, so none appears or vanishes as the person filters; a chosen
    // value the report does not hold (an old link) stays visible with 0
    const all = [...values[facet], ...filters.chosen[facet].filter((v) => !values[facet].includes(v))]
    return [facet, all.map((value) => ({ value, count: counts[facet].get(value) ?? 0 }))]
  })) as Record<Facet, FacetCount[]>
  return { rows: kept, facets }
}

export type Order = Record<Facet, (a: string, b: string) => number>

/** The cards ready to filter: their rows, each facet's order and every value it takes in the report. */
export interface List { rows: Row[]; order: Order; values: Record<Facet, string[]> }

/** The order of each facet's values: severity and state in their own order, plan steps in the plan's order, areas
 * and components by how many cards the whole report holds there (then by name). Fixed for a report, so no value
 * moves under the person's finger while they filter. */
export function prepare(data: StudioData, lang: 'ar' | 'en'): List {
  const rows = rowsOf(data, lang)
  const steps = (data.plans?.plans[0]?.steps ?? []).map((s) => s.id)
  const totals = Object.fromEntries(FACETS.map((facet) => [facet, new Map<string, number>()])) as Record<Facet, Map<string, number>>
  for (const row of rows) {
    for (const facet of FACETS) {
      const value = valueOf(row, facet)
      if (value !== null) totals[facet].set(value, (totals[facet].get(value) ?? 0) + 1)
    }
  }
  const rank = (ordered: readonly string[]) => {
    const at = new Map(ordered.map((value, i) => [value, i]))
    return (a: string, b: string) => (at.get(a) ?? 1e6) - (at.get(b) ?? 1e6) || a.localeCompare(b)
  }
  const bySize = (facet: Facet) => (a: string, b: string) => (totals[facet].get(b) ?? 0) - (totals[facet].get(a) ?? 0) || a.localeCompare(b)
  const order: Order = { severity: rank(SEVERITY_ORDER), state: rank(STATE_ORDER), step: rank(steps), area: bySize('area'), component: bySize('component') }
  const values = Object.fromEntries(FACETS.map((facet) => [facet, [...totals[facet].keys()].sort(order[facet])])) as Record<Facet, string[]>
  return { rows, order, values }
}

export interface Group { key: string; rows: Row[] }

/** The kept rows in groups, in the facet's fixed order (facetOrder); a card without the value goes last, in its own
 * group. Rows keep their order inside each group. */
export function groupRows(rows: Row[], by: GroupBy, order: Order): Group[] {
  const facet: Facet = by
  const buckets = new Map<string, Row[]>()
  for (const row of rows) {
    const key = valueOf(row, facet) ?? ''
    const bucket = buckets.get(key)
    if (bucket) bucket.push(row)
    else buckets.set(key, [row])
  }
  const groups = [...buckets.entries()].map(([key, rows]) => ({ key, rows }))
  return groups.sort((a, b) => (a.key === '' ? 1 : 0) - (b.key === '' ? 1 : 0) || order[by](a.key, b.key))
}

/** The list as it is drawn: group headings and rows in one sequence, so the page shows the first `limit` items and
 * "show more" adds to the end (nothing above moves). */
export type Item = { kind: 'group'; key: string; count: number } | { kind: 'row'; row: Row }

export function itemsOf(rows: Row[], group: GroupBy | null, order: Order): Item[] {
  if (!group) return rows.map((row) => ({ kind: 'row', row }))
  const out: Item[] = []
  for (const g of groupRows(rows, group, order)) {
    out.push({ kind: 'group', key: g.key, count: g.rows.length })
    for (const row of g.rows) out.push({ kind: 'row', row })
  }
  return out
}

/** Confidence in words (the check's claim confidence: CONFIRMED 1.0, LIKELY 0.7, HYPOTHESIS 0.4, eaos/studio/export.py). */
export function confidenceWord(value: number | null | undefined): 'confirmed' | 'likely' | 'hypothesis' | null {
  if (typeof value !== 'number') return null
  return value >= 0.9 ? 'confirmed' : value >= 0.6 ? 'likely' : 'hypothesis'
}
