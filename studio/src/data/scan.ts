// The running check, as EAOS itself records it: run-progress.jsonl folded into one row per stage (eaos/pipeline/
// progress.py). The server gives the folded state (/api/scan-progress) with each stage's place on the map; after that
// the page applies the live feed's `progress` events of the check one by one with `apply`, the same fold the server does, so
// a page opened mid-run and a page that watched from the start show the same thing. Nothing here invents a number:
// the time left is the last run's seconds of the stages still to come, and only when that run is known.

export type StageState = 'waiting' | 'running' | 'ok' | 'skipped' | 'unavailable' | 'failed' | 'not_reached'
export type RunState = 'none' | 'running' | 'done' | 'interrupted'

export interface ScanStep {
  name: string
  status: string
  done: number
  total: number
  seconds: number | null
  reason: string
}

export interface ScanStage {
  name: string
  requires: string[]
  produces: string[]
  necessity: 'required' | 'optional'
  description: string
  absent_when: string
  requested: boolean
  state: StageState
  started_at: string | null
  ended_at: string | null
  seconds: number | null
  reason: string
  artifacts: string[]
  detail: Record<string, string | number>
  steps: ScanStep[]
  resumed: boolean
  layer: number
  order: number
}

export interface ScanProgress {
  contract: number
  run: string | null
  state: RunState
  status: string | null
  started_at: string | null
  ended_at: string | null
  seconds: number | null
  last_seq: number
  requested: string[]
  previous: Record<string, number>
  counts: Record<string, number>
  stages: ScanStage[]
  /** The server's clock when it answered: the page's timers count from it, not from the browser's clock */
  now?: string
}

/** One line of run-progress.jsonl, as the feed carries it in the data of a `progress` event of the check. */
export interface ProgressRow {
  seq: number
  at?: string
  event: 'run.started' | 'stage.started' | 'stage.step' | 'stage.ended' | 'run.ended' | string
  run?: string
  stage?: string
  [key: string]: unknown
}

export const ENDED: StageState[] = ['ok', 'skipped', 'unavailable', 'failed', 'not_reached']

export function emptyProgress(): ScanProgress {
  return { contract: 1, run: null, state: 'none', status: null, started_at: null, ended_at: null, seconds: null, last_seq: 0,
    requested: [], previous: {}, counts: {}, stages: [] }
}

/** What the page does with one row: apply it, ignore it (already shown), or read the whole state again (a gap in the
 * numbers, or a new run whose places the server must compute). */
export function verdict(state: ScanProgress, row: ProgressRow): 'apply' | 'ignore' | 'reload' {
  if (row.event === 'run.started') return row.run === state.run ? 'ignore' : 'reload'
  if (!state.run || row.run !== state.run) return 'reload'
  if (row.seq <= state.last_seq) return 'ignore'
  if (row.seq > state.last_seq + 1) return 'reload'
  return 'apply'
}

/** The state after one row: a new object, the stage it touches a new object, everything else shared. */
export function apply(state: ScanProgress, row: ProgressRow): ScanProgress {
  const next: ScanProgress = { ...state, last_seq: Math.max(state.last_seq, row.seq) }
  const touch = (name: string | undefined, change: (stage: ScanStage) => ScanStage) => {
    next.stages = state.stages.map((s) => (s.name === name ? change(s) : s))
  }
  if (row.event === 'stage.started') {
    touch(row.stage, (s) => ({ ...s, state: 'running', started_at: row.at ?? null }))
  } else if (row.event === 'stage.step') {
    touch(row.stage, (s) => {
      const name = String(row.step ?? '')
      const was = s.steps.find((step) => step.name === name)
      const step: ScanStep = { ...(was ?? { name, status: 'waiting', done: 0, total: 0, seconds: null, reason: '' }),
        status: String(row.status ?? 'running'), done: Number(row.done ?? 0), total: Number(row.total ?? 0) }
      if (typeof row.seconds === 'number') step.seconds = row.seconds
      if (row.reason) step.reason = String(row.reason)
      return { ...s, steps: was ? s.steps.map((x) => (x === was ? step : x)) : [...s.steps, step] }
    })
  } else if (row.event === 'stage.ended') {
    touch(row.stage, (s) => ({ ...s, state: row.status as StageState, ended_at: row.at ?? null, seconds: (row.seconds as number) ?? null,
      reason: String(row.reason ?? ''), artifacts: (row.artifacts as string[]) ?? [], detail: (row.detail as ScanStage['detail']) ?? {},
      resumed: Boolean(row.resumed) }))
  } else if (row.event === 'run.ended') {
    Object.assign(next, { state: 'done', status: (row.status as string) ?? null, ended_at: row.at ?? null,
      seconds: (row.seconds as number) ?? null, counts: (row.counts as Record<string, number>) ?? {} })
  }
  return next
}

export interface Summary {
  /** Stages this run asked for, and how many of them have ended */
  total: number
  ended: number
  running: ScanStage[]
  /** 1-based place of the running stage among the requested ones, for "stage n of N" */
  position: number
}

export function summarize(state: ScanProgress): Summary {
  const asked = state.stages.filter((s) => s.requested)
  const running = state.stages.filter((s) => s.state === 'running')
  const ended = asked.filter((s) => ENDED.includes(s.state)).length
  return { total: asked.length, ended, running, position: Math.min(asked.length, ended + (running.length ? 1 : 0)) }
}

/** Seconds since `iso`, by the server's clock (`skew` = server minus browser, in ms). */
export function secondsSince(iso: string | null, skew: number, now = Date.now()): number | null {
  if (!iso) return null
  const at = Date.parse(iso)
  return Number.isNaN(at) ? null : Math.max(0, (now + skew - at) / 1000)
}

/** About how many seconds are left: the last run's seconds of every requested stage not ended yet, less what the
 * running one has already spent. null on a first run, or when the last run knew under half of what is left. */
export function secondsLeft(state: ScanProgress, skew: number, now = Date.now()): number | null {
  if (state.state !== 'running') return null
  const left = state.stages.filter((s) => s.requested && !ENDED.includes(s.state))
  if (!left.length) return null
  const known = left.filter((s) => typeof state.previous[s.name] === 'number')
  if (known.length * 2 < left.length) return null
  let total = 0
  for (const s of known) {
    const before = state.previous[s.name]
    total += s.state === 'running' ? Math.max(0, before - (secondsSince(s.started_at, skew, now) ?? 0)) : before
  }
  return total
}

/** The stages whose requirements are all met once `name` ended ok: where the light travels to. */
export function opened(state: ScanProgress, name: string): string[] {
  const done = new Set(state.stages.filter((s) => s.state === 'ok').map((s) => s.name))
  return state.stages.filter((s) => s.requires.includes(name) && s.requested && s.requires.every((r) => done.has(r))).map((s) => s.name)
}

/** "m:ss" under an hour, "h:mm:ss" above. */
export function clock(seconds: number | null): string {
  if (seconds === null) return ''
  const s = Math.floor(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const pad = (n: number) => String(n).padStart(2, '0')
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`
}

// ---------------------------------------------------------------- the feed's scan events, apart from the report's

type Listener = (row: ProgressRow | null) => void
const listeners = new Set<Listener>()

/** The data provider hands every `progress` event of the check here (null: the stream was reset) instead of reloading the report. */
export function emitScan(row: ProgressRow | null) {
  for (const listener of listeners) listener(row)
}

export function onScan(listener: Listener): () => void {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}
