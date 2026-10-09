// studio/history.json (contract v2, eaos/studio/history.py): every check the ledger recorded, the progress of the fixes
// taken in, the events and the cards that closed or appeared. This file only reads it: what was not recorded stays
// null and is shown as such, and a chart is drawn only when there are two points to draw between.
import type { StudioData } from '../../data/types'

export const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'] as const
export type Sev = (typeof SEVERITIES)[number]

export interface Scan {
  id: string
  commit: string | null
  branch?: string | null
  at: string
  event?: string
  score: number | null
  open: Partial<Record<Sev, number | null>>
  open_total?: number | null
  closed?: number | null
  total?: number | null
  added?: number | null
  resolved?: number | null
}
export interface ProgressPoint { at: string; event: string; closed: number; total: number; percent: number | null; commit?: string | null }
export interface HistoryEvent { at: string; kind: 'scan' | 'batch' | 'merge' | 'decision' | 'release'; title: string; ref?: string | null; count?: number | null }
export interface ChangedCard { key: string; id?: string | null; title: string; state: string; at?: string | null; new: boolean; batch?: number | null }
export interface Missing { id: string; state: string; step: string; detail: { ar: string; en: string } }
export interface HistoryData { scans: Scan[]; progress?: ProgressPoint[]; events: HistoryEvent[]; cards?: ChangedCard[]; missing?: Missing[] }

export function historyOf(data: StudioData): HistoryData | undefined {
  return data.history as HistoryData | undefined
}

/** Every severity known for this check (the ledger recorded them, or it is the check in hand). */
export function openKnown(scan: Scan): boolean {
  return SEVERITIES.every((s) => typeof scan.open[s] === 'number')
}

export function openTotal(scan: Scan): number | null {
  if (typeof scan.open_total === 'number') return scan.open_total
  return openKnown(scan) ? SEVERITIES.reduce((sum, s) => sum + (scan.open[s] ?? 0), 0) : null
}

export function scored(scans: Scan[]): Scan[] {
  return scans.filter((s) => typeof s.score === 'number')
}

export function last<T>(items: T[]): T | undefined {
  return items[items.length - 1]
}

/** #/history/compare/<a>..<b> */
export function parseRange(range: string): [string, string] | null {
  const at = range.indexOf('..')
  return at > 0 && at < range.length - 2 ? [range.slice(0, at), range.slice(at + 2)] : null
}

export function rangePath(a: Scan, b: Scan): string {
  return `/history/compare/${encodeURIComponent(a.id)}..${encodeURIComponent(b.id)}`
}

export function scanPath(scan: Scan): string {
  return `/history/${encodeURIComponent(scan.id)}`
}

const delta = (a: number | null | undefined, b: number | null | undefined): number | null =>
  typeof a === 'number' && typeof b === 'number' ? Math.round((b - a) * 10000) / 10000 : null

export interface Comparison {
  from: Scan
  to: Scan
  score: number | null
  open: number | null
  severity: Record<Sev, number | null>
  closed: number | null
  total: number | null
  /** cards the ledger closed after the first check and up to the second */
  closedBetween: ChangedCard[]
  /** cards a later check found new, when the second is the last check (the ledger does not say which check found them) */
  appeared: ChangedCard[] | null
}

/** Two checks side by side, older first, from what the history recorded. */
export function compare(history: HistoryData, aId: string, bId: string): Comparison | null {
  const scans = history.scans
  let a = scans.findIndex((s) => s.id === aId)
  let b = scans.findIndex((s) => s.id === bId)
  if (a < 0 || b < 0 || a === b) return null
  if (a > b) [a, b] = [b, a]
  const from = scans[a], to = scans[b]
  const severity = Object.fromEntries(SEVERITIES.map((s) => [s, delta(from.open[s], to.open[s])])) as Record<Sev, number | null>
  const cards = history.cards ?? []
  return {
    from, to, severity,
    score: delta(from.score, to.score), open: delta(openTotal(from), openTotal(to)),
    closed: delta(from.closed, to.closed), total: delta(from.total, to.total),
    closedBetween: cards.filter((c) => (c.state === 'done' || c.state === 'resolved') && c.at && c.at > from.at && c.at <= to.at),
    appeared: b === scans.length - 1 ? cards.filter((c) => c.new) : null,
  }
}

// ---------------------------------------------------------------- chart geometry

export interface Plot { width: number; height: number; pad: { start: number; end: number; top: number; bottom: number } }
export interface Point { x: number; y: number; value: number; at: string }

/** Times to x (the earliest at inline-start: mirrored in right-to-left) and 0..1 to y, inside the plot's padding. */
export function place(values: { at: string; value: number }[], plot: Plot, rtl: boolean): Point[] {
  const times = values.map((v) => Date.parse(v.at))
  const t0 = Math.min(...times), t1 = Math.max(...times)
  const span = t1 - t0
  const inner = plot.width - plot.pad.start - plot.pad.end
  const tall = plot.height - plot.pad.top - plot.pad.bottom
  return values.map((v, i) => {
    // equal steps when the times are equal or unknown, else by time
    const share = span > 0 && Number.isFinite(span) ? (times[i] - t0) / span : values.length > 1 ? i / (values.length - 1) : 0.5
    const x = plot.pad.start + share * inner
    return { x: rtl ? plot.width - x : x, y: plot.pad.top + (1 - Math.max(0, Math.min(1, v.value))) * tall, value: v.value, at: v.at }
  })
}

/** The bands of a stacked chart, one per severity from the most severe at the bottom: each a closed polygon. */
export function bands(scans: Scan[], plot: Plot, rtl: boolean): { sev: Sev; points: string }[] {
  const totals = scans.map((s) => openTotal(s) ?? 0)
  const top = Math.max(1, ...totals)
  const base = scans.map(() => 0)
  const out: { sev: Sev; points: string }[] = []
  for (const sev of SEVERITIES) {
    const lower = place(scans.map((s, i) => ({ at: s.at, value: base[i] / top })), plot, rtl)
    scans.forEach((s, i) => { base[i] += s.open[sev] ?? 0 })
    const upper = place(scans.map((s, i) => ({ at: s.at, value: base[i] / top })), plot, rtl)
    const ring = [...upper, ...lower.reverse()].map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
    out.push({ sev, points: ring })
  }
  return out
}

/** The labels a line can carry without crowding: every point up to `most`, else evenly picked, always the last. */
export function labelled(count: number, most = 8): Set<number> {
  if (count <= most) return new Set(Array.from({ length: count }, (_, i) => i))
  const step = (count - 1) / (most - 1)
  return new Set(Array.from({ length: most }, (_, i) => Math.round(i * step)))
}
