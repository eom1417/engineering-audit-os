// What the run page shows, derived from the run's events alone: its state, the sentence of what happens now, the
// progress of every batch, the open question, the result or the error, the before/after screens, and the timeline
// with consecutive reads folded into one line. Pure, so a replayed stream and a live one look the same.
import type { Bi, Question, Run, RunEvent, RunResult, RunState } from './types'

export interface Batch { number: number; done: number; total: number }
export interface Screens { batch: number | null; before?: RunEvent; after?: RunEvent }
export type Item =
  | { kind: 'event'; event: RunEvent }
  | { kind: 'reads'; events: RunEvent[] }

export interface RunView {
  state: RunState | null
  now: Bi | null
  batches: Batch[]
  question: Question | null
  result: RunResult | null
  error: { text: Bi; reason: string; what_now: Bi | null; recoverable: boolean; detail: string | null } | null
  screens: Screens[]
  items: Item[]
  edits: number
  checks: { passed: number; failed: number }
  last: number
}

const NOW_KINDS = new Set(['step', 'read', 'edit', 'check', 'say', 'question', 'answer', 'result', 'error'])
/** Kinds the timeline leaves out: progress is drawn as bars, screenshots as pairs. */
const HIDDEN = new Set(['progress', 'screenshot'])

export function deriveRun(events: RunEvent[], run?: Run | null): RunView {
  const view: RunView = { state: run?.state ?? null, now: null, batches: [], question: run?.question ?? null, result: run?.result ?? null,
    error: null, screens: [], items: [], edits: 0, checks: { passed: 0, failed: 0 }, last: 0 }
  const batches = new Map<number, Batch>()
  let batch: number | null = null
  for (const event of events) {
    view.last = Math.max(view.last, event.seq)
    const data = event.data
    if (NOW_KINDS.has(event.kind)) view.now = event.text
    switch (event.kind) {
      case 'state': {
        view.state = data.to as RunState
        if (data.to === 'running' || data.to === 'queued') view.error = null
        if (data.to !== 'waiting_for_person') view.question = null
        if (data.to === 'queued') { view.result = null; batches.clear(); view.screens = [] }
        break
      }
      case 'progress': {
        const number = typeof data.batch === 'number' ? data.batch : 0
        batch = number || null
        batches.set(number, { number, done: Number(data.done) || 0, total: Number(data.total) || 0 })
        break
      }
      case 'question': view.question = data as unknown as Question; break
      case 'answer': view.question = null; break
      case 'result':
        if ('outcome' in data) break // accept or undo recorded on a done run: the handed-over result stays
        view.result = data as unknown as RunResult
        break
      case 'error': {
        const what = data.what_now as Bi | undefined
        view.error = { text: event.text, reason: String(data.reason ?? ''), what_now: what && (what.en || what.ar) ? what : null,
          recoverable: data.recoverable !== false, detail: event.detail ?? null }
        break
      }
      case 'edit': view.edits += 1; break
      case 'check': if (data.passed === false) view.checks.failed += 1; else view.checks.passed += 1; break
      case 'screenshot': {
        const key = typeof data.batch === 'number' ? data.batch : batch
        let pair = view.screens.find((s) => s.batch === key && !(data.when === 'before' ? s.before : s.after))
        if (!pair) { pair = { batch: key }; view.screens.push(pair) }
        if (data.when === 'before') pair.before = event
        else pair.after = event
        break
      }
      default: break
    }
    if (HIDDEN.has(event.kind)) continue
    const previous = view.items[view.items.length - 1]
    if (event.kind === 'read' && previous?.kind === 'reads') previous.events.push(event)
    else if (event.kind === 'read') view.items.push({ kind: 'reads', events: [event] })
    else view.items.push({ kind: 'event', event })
  }
  view.batches = [...batches.values()].sort((a, b) => a.number - b.number)
  return view
}

/** The overall share done, 0..1, from the batches (each weighs its cards); null before any progress. */
export function share(batches: Batch[]): number | null {
  const total = batches.reduce((sum, b) => sum + b.total, 0)
  if (!total) return null
  return Math.min(1, batches.reduce((sum, b) => sum + Math.min(b.done, b.total), 0) / total)
}

/** A run's label in the language: an Arabic list takes the Arabic comma, so its ids read in order. */
export function labelOf(label: Bi, lang: 'ar' | 'en'): string {
  return lang === 'ar' ? label.ar.replaceAll(', ', '، ') : label.en
}

/** "3 m 20 s", "1 h 4 m": the time between two instants, in the language's units. */
export function duration(from: string | null | undefined, to: string | null | undefined, lang: 'ar' | 'en', now = Date.now()): string | null {
  if (!from) return null
  const start = Date.parse(from)
  const end = to ? Date.parse(to) : now
  if (Number.isNaN(start) || Number.isNaN(end)) return null
  const seconds = Math.max(0, Math.round((end - start) / 1000))
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  const unit = lang === 'ar' ? { h: 'س', m: 'د', s: 'ث' } : { h: 'h', m: 'm', s: 's' }
  if (h) return `${h} ${unit.h} ${m} ${unit.m}`
  if (m) return `${m} ${unit.m} ${s} ${unit.s}`
  return `${s} ${unit.s}`
}
