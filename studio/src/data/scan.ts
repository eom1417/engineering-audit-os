// The work EAOS is doing, as it records it itself: each flow's progress file (the check, setting the app up, recording
// its screens, fixing) folded into one row per declared stage (eaos/progress/fold.py). The server gives every flow
// folded and placed on its map (/api/progress); after that the page applies the live feed's `progress` events one by
// one with `apply`, the same fold the server does (tested on the same recorded runs), so a page opened mid-run and a
// page that watched from the start show the same thing. Nothing here invents a number.

export type StageState = 'waiting' | 'running' | 'ok' | 'skipped' | 'unavailable' | 'failed' | 'not_reached'
export type RunState = 'none' | 'running' | 'done' | 'interrupted' | 'stalled'

export interface ScanStep {
  name: string
  /** 'count' for a counted loop (37 of 156), 'item' for one named part of the stage */
  kind: string
  status: string
  done: number
  total: number
  seconds: number | null
  reason: string
  reason_code: string
  /** A file the step produced, relative to its flow's folder (a recorded screen) */
  artifact?: string
}

/** An external program the run started, running now (`since`: when it started). */
export interface Program { name: string; pid: number; since: string }

export interface ScanStage {
  name: string
  requires: string[]
  produces: string[]
  necessity: 'required' | 'optional'
  description: string
  absent_when: string
  /** done by the person's assistant (eaos/pipeline/stages.py `ai`) */
  ai?: boolean
  requested: boolean
  state: StageState
  started_at: string | null
  ended_at: string | null
  seconds: number | null
  reason: string
  reason_code: string
  artifacts: string[]
  detail: Record<string, string | number>
  steps: ScanStep[]
  programs: Program[]
  activity_note: string
  resumed: boolean
  /** The place on the map the server computed (absent in a fold the page made itself) */
  layer?: number
  order?: number
}

export interface Estimate { low?: number; high?: number; basis: 'previous_run' | 'first_run'; unknown?: string[] }

export interface ScanProgress {
  contract: number
  flow: string | null
  run: string | null
  state: RunState
  status: string | null
  reason: string
  started_at: string | null
  ended_at: string | null
  heard_at: string | null
  alive_every: number | null
  seconds: number | null
  last_seq: number
  requested: string[]
  previous: Record<string, number>
  previous_steps: Record<string, unknown>
  counts: Record<string, number>
  stages: ScanStage[]
  pid?: number | null
  host?: string | null
  /** The time left the server worked out when it answered (eaos/progress/estimate.py) */
  estimate?: Estimate | null
}

/** One step of the journey (eaos/guided.py journey): its flow, whether it is done, and its flow's judged state. */
export interface JourneyStep { id: string; title: { ar: string; en: string }; flow: string; done: boolean; state: RunState }

/** `GET /api/progress`. */
export interface AllProgress { journey: JourneyStep[]; flows: Record<string, ScanProgress>; now?: string }

/** One line of a progress file, as the feed carries it in the data of a `progress` event (with its flow). */
export interface ProgressRow {
  seq: number
  at?: string
  event: string
  run?: string
  flow?: string
  stage?: string
  [key: string]: unknown
}

export const ENDED: StageState[] = ['ok', 'skipped', 'unavailable', 'failed', 'not_reached']

export function emptyProgress(): ScanProgress {
  return { contract: 1, flow: null, run: null, state: 'none', status: null, reason: '', started_at: null, ended_at: null,
    heard_at: null, alive_every: null, seconds: null, last_seq: 0, requested: [], previous: {}, previous_steps: {}, counts: {},
    stages: [], pid: null, host: null }
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

const text = (value: unknown) => (value ? String(value) : '')

function declared(row: Record<string, unknown>, requested: string[]): ScanStage {
  return { ...(row as unknown as ScanStage), requested: requested.includes(String(row.name)), state: 'waiting', started_at: null,
    ended_at: null, seconds: null, reason: '', reason_code: '', artifacts: [], detail: {}, steps: [], programs: [], activity_note: '',
    resumed: false }
}

function started(row: ProgressRow): ScanProgress {
  const requested = (row.requested as string[]) ?? []
  const stages = ((row.stages as Record<string, unknown>[]) ?? []).filter((s) => s && s.name).map((s) => declared(s, requested))
  return { ...emptyProgress(), flow: text(row.flow) || 'check', run: row.run ?? null, state: 'running', started_at: row.at ?? null,
    requested, previous: (row.previous as Record<string, number>) || {}, previous_steps: (row.previous_steps as Record<string, unknown>) || {},
    alive_every: (row.alive_every as number) ?? null, pid: (row.pid as number) ?? null, host: (row.host as string) ?? null, stages }
}

function stepped(stage: ScanStage, row: ProgressRow): ScanStage {
  const was = stage.steps.find((step) => step.name === row.step)
  const step: ScanStep = { ...(was ?? { name: row.step as string, kind: text(row.kind) || 'item', status: 'waiting', done: 0, total: 0,
    seconds: null, reason: '', reason_code: '' }), status: text(row.status) || 'running', done: (row.done as number) ?? 0, total: (row.total as number) ?? 0 }
  if ('seconds' in row) step.seconds = row.seconds as number | null
  if (row.reason) step.reason = String(row.reason)
  if (row.reason_code) step.reason_code = String(row.reason_code)
  if (row.artifact) step.artifact = String(row.artifact)
  return { ...stage, steps: was ? stage.steps.map((x) => (x === was ? step : x)) : [...stage.steps, step] }
}

function ended(stage: ScanStage, row: ProgressRow): ScanStage {
  return { ...stage, state: row.status as StageState, ended_at: row.at ?? null, seconds: (row.seconds as number) ?? null,
    reason: text(row.reason), reason_code: text(row.reason_code), artifacts: [...((row.artifacts as string[]) ?? [])],
    detail: (row.detail as ScanStage['detail']) || {}, resumed: Boolean(row.resumed), programs: [] }
}

function touched(stage: ScanStage, row: ProgressRow): ScanStage {
  switch (row.event) {
    case 'stage.started': return { ...stage, state: 'running', started_at: row.at ?? null }
    case 'stage.step': return stepped(stage, row)
    case 'stage.activity': return { ...stage, programs: ((row.programs as Program[]) ?? []).filter((p) => p && typeof p === 'object').map((p) => ({ ...p })),
      activity_note: row.reason ? String(row.reason) : stage.activity_note }
    case 'stage.ended': return ended(stage, row)
    default: return stage
  }
}

/** The state after one row, by the rules of eaos/progress/fold.py apply: a new object, the stage it touches a new
 * object, everything else shared. A line of another run than the one folded is left out. */
export function apply(state: ScanProgress, row: ProgressRow): ScanProgress {
  let next: ScanProgress
  if (row.event === 'run.started') next = started(row)
  else if (state.run === null || row.run !== state.run) return state
  else {
    next = { ...state, stages: row.stage ? state.stages.map((s) => (s.name === row.stage ? touched(s, row) : s)) : state.stages }
    if (row.event === 'run.ended') Object.assign(next, { state: 'done', status: row.status ?? null, reason: text(row.reason),
      ended_at: row.at ?? null, seconds: row.seconds ?? null, counts: row.counts || {} })
  }
  next.heard_at = row.at || next.heard_at
  next.last_seq = Math.max(next.last_seq || 0, Number(row.seq) || 0)
  return next
}

/** The whole state after `rows`, from nothing: what eaos/progress/fold.py fold gives for the same lines. */
export function fold(rows: ProgressRow[]): ScanProgress {
  return rows.reduce(apply, emptyProgress())
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

/** The state a stage is drawn in: a running stage of a run nobody hears from any more is `stopped`. */
export function shownState(progress: ScanProgress, stage: ScanStage): StageState | 'stopped' {
  return stage.state === 'running' && (progress.state === 'interrupted' || progress.state === 'stalled') ? 'stopped' : stage.state
}

/** Seconds since `iso`, by the server's clock (`skew` = server minus browser, in ms). */
export function secondsSince(iso: string | null, skew: number, now = Date.now()): number | null {
  if (!iso) return null
  const at = Date.parse(iso)
  return Number.isNaN(at) ? null : Math.max(0, (now + skew - at) / 1000)
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

// ---------------------------------------------------------------- the feed's progress events, apart from the report's

type Listener = (row: ProgressRow | null) => void
const listeners = new Set<Listener>()

/** The data provider hands every `progress` event here (null: the stream was reset) instead of reloading the report. */
export function emitScan(row: ProgressRow | null) {
  for (const listener of listeners) listener(row)
}

export function onScan(listener: Listener): () => void {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}
