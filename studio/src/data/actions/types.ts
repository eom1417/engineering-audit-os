// The command centre's shapes, as docs/studio-actions.json defines them (NS46.T9's contract): actions, verbs,
// selections, runs, their events, questions and previews. The pages read only these.

/** A sentence in both languages: every event and label carries one. */
export interface Bi { en: string; ar: string }

export type RunState = 'queued' | 'running' | 'paused' | 'waiting_for_person' | 'done' | 'failed' | 'stopped'
export const TERMINAL: readonly RunState[] = ['done', 'failed', 'stopped']
/** A run that holds the project's one slot: running, paused or waiting for the person. */
export const ACTIVE: readonly RunState[] = ['running', 'paused', 'waiting_for_person']

export type VerbId = 'fix' | 'verify' | 'explain' | 'plan'
export type GroupBy = 'area' | 'severity' | 'component' | 'gap' | 'operation'

/** What the person selected, resolved to card ids on the server (contract `selection`). */
export interface Selection {
  kind: 'card' | 'cards' | 'group' | 'step'
  cards?: string[]
  group?: { by: GroupBy; value: string }
  step?: string
}

export interface JsonSchema {
  type?: string | string[]
  enum?: unknown[]
  description?: string
  properties?: Record<string, JsonSchema>
  required?: string[]
  items?: JsonSchema
  default?: unknown
  minimum?: number
  maximum?: number
}

export interface ActionDef {
  id: string
  tool: string
  group: string
  label: Bi
  description: Bi
  mode: 'direct' | 'assistant'
  needs_assistant: boolean
  irreversible: boolean
  needs_consent: boolean
  returns_job: boolean
  changes_code: boolean
  inputs: JsonSchema
}

export interface VerbDef { id: VerbId; label: Bi; needs_assistant: boolean; changes_code: boolean; tools: string[]; result: Bi }

export interface Assistant { id: string; name: string; installed: boolean; logged_in: boolean; version?: string | null }

export interface Question {
  id: string
  run: string
  asked?: string
  text: Bi
  options: { id: string; label: Bi }[]
  recommendation: string | null
  why?: string
}

export interface RunResult {
  branch: string | null
  diff_stat: { files: number; insertions: number; deletions: number } | null
  tests: { passed: boolean | null; summary: string } | null
  cards_closed: string[]
  indicators: { id: string; before: number | null; after: number | null }[]
  answer?: unknown
}

export interface Run {
  id: string
  action: string
  verb: VerbId | null
  label: Bi
  selection: Selection | null
  cards: string[]
  cards_detail?: { id: string; title?: string | null; paths?: string[] }[]
  left_out?: { id: string; why: string }[]
  assistant: string | null
  mode: 'direct' | 'assistant' | 'handoff'
  state: RunState
  attempt: number
  created: string
  queued_at?: string
  started?: string | null
  ended?: string | null
  result?: RunResult | null
  question?: Question | null
  outcome?: 'accepted' | 'undone' | null
  position?: number
}

export type EventKind = 'state' | 'step' | 'read' | 'edit' | 'check' | 'screenshot' | 'progress' | 'question' | 'answer'
  | 'result' | 'error' | 'action' | 'say'

/** One event of a run: `seq` is gapless per run and is the SSE id, so Last-Event-ID replays exactly. */
export interface RunEvent {
  seq: number
  id: string
  run: string
  at: string
  kind: EventKind
  text: Bi
  data: Record<string, unknown>
  detail?: string | null
  prev?: string
  hash?: string
}

export interface Preview {
  action: string
  verb: VerbId | null
  selection: Selection | null
  cards: { id: string; title?: string | null; severity?: string | null; paths?: string[] }[]
  left_out: { id: string; why: string }[]
  files: string[]
  batches: { number: number; cards: string[] }[]
  estimate: { minutes_low: number | null; minutes_high: number | null; basis: Bi }
  risk: { level: 'low' | 'medium' | 'high'; why: Bi }
  on_failure: Bi
  assistant: Assistant | null
  assistants?: Assistant[]
  handoff: { available: boolean; request: Bi | null }
  irreversible: boolean
  needs_consent: boolean
  confirm: { token: string; expires?: string } | null
}

export interface PreviewBody { inputs?: Record<string, unknown>; selection?: Selection; verb?: VerbId; assistant?: string }
export interface StartBody extends PreviewBody { action: string; confirm?: string | null }

export type Mode = 'live' | 'demo' | 'snapshot'

/** The connection of a run's event stream: what the run page says while it reconnects. */
export type StreamStatus = 'connecting' | 'open' | 'reconnecting' | 'closed'

export type Control = 'pause' | 'resume' | 'stop' | 'retry'

/** A refusal or failure of the action API, with the server's reason. */
export class ActionError extends Error {
  status: number
  needs?: string
  constructor(status: number, message: string, needs?: string) {
    super(message)
    this.status = status
    this.needs = needs
  }
}

/** The command centre as the pages use it; live (the server), demo (a recorded run replayed) or snapshot. */
export interface ActionsClient {
  mode: Mode
  /** Whether the server mounted the action API (GET /api/session `actions`); a client without it always has one. */
  available?(): Promise<boolean>
  preview(id: string, body: PreviewBody): Promise<Preview>
  start(body: StartBody): Promise<Run>
  runs(): Promise<{ runs: Run[]; queue: string[] }>
  run(id: string): Promise<Run>
  /** Every event after `after`, then live until the run ends; returns the stop function. */
  follow(id: string, after: number, onEvent: (event: RunEvent) => void, onStatus: (status: StreamStatus) => void): () => void
  control(id: string, op: Control): Promise<Run>
  reorder(order: string[]): Promise<string[]>
  questions(): Promise<Question[]>
  answer(question: string, option: string | null, text?: string | null): Promise<Run>
  decide(id: string, op: 'accept' | 'undo', confirm: string): Promise<Run>
  /** Called when the client's runs change by themselves (demo); the live client is polled instead. */
  watch?(onChange: () => void): () => void
}
