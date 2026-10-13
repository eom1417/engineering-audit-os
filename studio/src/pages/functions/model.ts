// The function explorer's reading model (studio/functions.json, eaos/studio/functions.py): the section loaded when the
// page opens (it is the largest section, so the report's other pages never wait for it), the coverage row it is
// shown with, the list's filters and orders, and the two-hop call graph around one function. The Studio computes no
// fact here: every number is the exporter's, with its source.
import { normalize } from '../../search/normalize'

export interface Measure { value: number | null; src: string; unit?: string }
export interface Touch { kind: 'table' | 'file' | 'env' | 'network' | 'store' | 'storage'; name: string }
export type FnKind = 'function' | 'method' | 'component' | 'hook' | 'handler' | 'class'

export interface Fn {
  id: string
  name: string
  module: string
  line: number | null
  end_line: number | null
  language: string | null
  kind: FnKind
  signature: string | null
  summary: string | null
  exported: boolean | null
  lines: Measure
  complexity: Measure
  callers: string[]
  callees: string[]
  reads?: Touch[]
  writes?: Touch[]
  cards?: string[]
}

export interface Gap { id: string; state: string; step: string; count: Measure; detail: { ar: string; en: string } }
export interface LanguageRow { id: string; state: 'measured' | 'partial' | 'not_measured' | 'empty' | 'failed'; functions: Measure }

export interface FunctionsData {
  modules: { id: string; component: string | null; language: string | null; functions: number }[]
  functions: Fn[]
  languages?: LanguageRow[]
  missing?: Gap[]
  counts?: Record<string, Measure>
}

// ---------------------------------------------------------------- the list

export const SORTS = ['risk', 'callers', 'size', 'name'] as const
export type Sort = (typeof SORTS)[number]
export const SHOWS = ['all', 'problems', 'data', 'unused'] as const
export type Show = (typeof SHOWS)[number]
export const KINDS = ['component', 'hook', 'handler', 'function', 'method'] as const satisfies readonly FnKind[]

/** Lizard's own warning line for cyclomatic complexity (eaos/engines/lizard.py THRESHOLD); half of it is "watch". */
export const COMPLEX = 15
export const WATCH = 10

export function level(fn: Fn): 'high' | 'watch' | 'ok' | 'none' {
  const c = fn.complexity.value
  return c === null ? 'none' : c > COMPLEX ? 'high' : c >= WATCH ? 'watch' : 'ok'
}

export interface Filter { q?: string; sort?: Sort; show?: Show; kind?: FnKind; module?: string }

/** The text a function is found by: its name, file, kind and what it touches, normalised once. */
export function searchText(fn: Fn): string {
  return normalize([fn.name, fn.module, fn.kind, fn.signature ?? '', ...(fn.reads ?? []).map((t) => t.name), ...(fn.writes ?? []).map((t) => t.name)].join(' '))
}

const ORDER: Record<Sort, (a: Fn, b: Fn) => number> = {
  risk: (a, b) => (b.complexity.value ?? -1) - (a.complexity.value ?? -1) || (b.cards?.length ?? 0) - (a.cards?.length ?? 0) || b.callers.length - a.callers.length,
  callers: (a, b) => b.callers.length - a.callers.length || (b.complexity.value ?? -1) - (a.complexity.value ?? -1),
  size: (a, b) => (b.lines.value ?? -1) - (a.lines.value ?? -1),
  name: () => 0,
}

/** The functions the filter keeps, in its order (ties keep the file order the exporter wrote). */
export function filterFunctions(fns: Fn[], filter: Filter, texts?: Map<string, string>): Fn[] {
  const words = normalize(filter.q ?? '').split(' ').filter(Boolean)
  const kept = fns.filter((fn) => {
    if (filter.module && fn.module !== filter.module) return false
    if (filter.kind && fn.kind !== filter.kind) return false
    if (filter.show === 'problems' && !fn.cards?.length) return false
    if (filter.show === 'data' && !fn.reads?.length && !fn.writes?.length) return false
    if (filter.show === 'unused' && (fn.callers.length || fn.kind === 'component' || fn.exported)) return false
    if (!words.length) return true
    const text = texts?.get(fn.id) ?? searchText(fn)
    return words.every((w) => text.includes(w))
  })
  const sort = filter.sort ?? 'risk'
  return sort === 'name' ? kept.sort((a, b) => a.name.localeCompare(b.name) || a.module.localeCompare(b.module)) : kept.sort(ORDER[sort])
}

// ---------------------------------------------------------------- one function

/** The last segment of a function's name (OrdersPage.handleSave -> handleSave), for tight labels. */
export function shortName(fn: Pick<Fn, 'name'>): string {
  const parts = fn.name.split(/[.:]+/)
  return parts[parts.length - 1] || fn.name
}

export interface Hop { fn: Fn; via?: string }
export interface CallGraph { callers2: Hop[]; callers: Fn[]; callees: Fn[]; callees2: Hop[]; more: { callers: number; callees: number; far: number } }

/** Two hops around one function: who calls it and who calls them, what it calls and what those call. Each column is
 * capped (`per`), the riskiest first, and what is cut is counted, never hidden. */
export function callGraph(fn: Fn, byId: Map<string, Fn>, per = 5): CallGraph {
  const pick = (ids: string[]) => ids.map((id) => byId.get(id)).filter((f): f is Fn => Boolean(f) && f!.id !== fn.id).sort(ORDER.risk)
  const callers = pick(fn.callers)
  const callees = pick(fn.callees)
  const near = new Set([fn.id, ...fn.callers, ...fn.callees])
  const far = (from: Fn[], side: 'callers' | 'callees') => {
    const out = new Map<string, Hop>()
    for (const f of from.slice(0, per)) for (const id of f[side]) if (!near.has(id) && !out.has(id) && byId.has(id)) out.set(id, { fn: byId.get(id)!, via: f.id })
    return [...out.values()].sort((a, b) => ORDER.risk(a.fn, b.fn))
  }
  const callers2 = far(callers, 'callers')
  const callees2 = far(callees, 'callees')
  return {
    callers: callers.slice(0, per), callees: callees.slice(0, per), callers2: callers2.slice(0, per), callees2: callees2.slice(0, per),
    more: { callers: Math.max(0, callers.length - per), callees: Math.max(0, callees.length - per),
      far: Math.max(0, callers2.length - per) + Math.max(0, callees2.length - per) },
  }
}

/** The neighbour to open first: the riskiest caller or callee. */
export function riskiestNeighbour(fn: Fn, byId: Map<string, Fn>): Fn | undefined {
  return [...fn.callers, ...fn.callees].map((id) => byId.get(id)).filter((f): f is Fn => Boolean(f) && f!.id !== fn.id).sort(ORDER.risk)[0]
}
