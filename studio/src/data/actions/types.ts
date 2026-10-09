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
  outcome?: 'accepted' | 'undone' | 'merged' | 'deleted' | 'restored' | null
  position?: number
  /** The branches the run was made on, recorded when it was created: a later change of branch never retargets it */
  context?: RunContext | null
  /** The run's own work branch as it is now (eaos/studio/actions/branches.py work_branch) */
  work_branch?: WorkBranch | null
  /** A branch operation (select, merge, delete, restore, fetch, protect): the branches it acted on */
  branch_op?: { branches: string[] } | null
}

export interface RunContext { analysis_branch: string | null; analysis_commit: string | null; checkout: string | null; detached: boolean | null; at: string }

export interface WorkBranch {
  state: 'exists' | 'deleted' | 'merged_and_deleted' | 'not_created_yet' | 'not_required' | 'none_created'
  name?: string
  tip?: string | null
  recorded_tip?: string | null
  recovery?: string | null
  base?: string | null
  acted_on?: string[]
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
export interface ReportDecision {
  id: string
  scope: string
  response: { option: string | null; text: string | null; label: string; at: string; status: string; run: string } | null
  execution: Run | null
}

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
  decisions?(): Promise<ReportDecision[]>
  answerDecision?(id: string, scope: string, option: string | null, text?: string): Promise<ReportDecision>
  questions(): Promise<Question[]>
  answer(question: string, option: string | null, text?: string | null): Promise<Run>
  decide(id: string, op: 'accept' | 'undo', confirm: string): Promise<Run>
  /** Called when the client's runs change by themselves (demo); the live client is polled instead. */
  watch?(onChange: () => void): () => void
  /** Branch control and live freshness (live only: eaos/studio/actions/branches.py) */
  branches?: BranchApi
}

/** A reason in both languages, with a stable code */
export interface Reason extends Bi { code: string }
export interface Confirm { token: string; expires?: number }

export type FreshState = 'fresh' | 'behind' | 'rewritten' | 'dirty' | 'other_branch' | 'unknown'

export interface LiveFreshness {
  state: FreshState
  reason: string | null
  scanned_commit: string | null
  scanned_branch: string | null
  scanned_detached: boolean | null
  scanned_dirty: boolean | null
  scanned_at: string | null
  recorded: boolean
  branch: string | null
  tip: string | null
  behind: { commits: number | null; files: number; file_list: string[]; truncated: boolean; eaos_only: boolean } | null
  dirty: { tracked: number; untracked: number } | null
  since_common?: number | null
  eaos_updated: boolean
  report_built?: string | null
  checked_at: string
  project?: string
  project_path?: string
}

export interface Head { branch: string | null; detached: boolean; commit: string | null; unborn: boolean }

export interface BranchContext {
  checkout: Head
  analysis: { branch: string | null; selected: boolean; tip: string | null; detached: boolean }
  report: { branch: string | null; commit: string | null; at: string | null; recorded: boolean; detached: boolean | null }
  scan: { branch: string | null; commit: string | null; at: string | null }
  dirty: { tracked: number; untracked: number } | null
}

export interface Ownership {
  owner: 'eaos' | 'shared' | 'unknown'
  kind: string | null
  evidence: string | null
  base: string | null
  base_commit: string | null
  foreign_commits: number | null
  recorded_tip?: string | null
  run?: string | null
  wave?: number
  status?: string
}

export interface RunLink { id: string; state: RunState; label: Bi; created: string; action: string; role: 'work' | 'base' | 'operation' }

export interface BranchRow {
  id: string
  name: string
  kind: 'local' | 'remote'
  remote: string | null
  ref: string
  tip: string
  last_commit: string | null
  subject: string
  upstream: string | null
  tracking: string | null
  roles: ('checkout' | 'analysis' | 'report' | 'base' | 'default')[]
  protected: Reason | null
  ownership: Ownership
  work: boolean
  compare: { base: string | null; ahead: number | null; behind: number | null; merged: boolean | null }
  worktree: { path: string; current: boolean; dirty: { tracked: number; untracked: number } | null } | null
  runs: RunLink[]
  remote_as_of: string | null
}

export interface Recovery { id: string; ref: string; branch: string; where: 'local' | 'remote'; remote: string | null; tip: string; at: string; run: string; restored: { at: string; as: string; run: string } | null }

export interface Inventory {
  git: boolean
  reason?: Reason
  project?: string
  head?: Head
  context?: BranchContext
  base?: string | null
  base_tip?: string | null
  default?: { name: string | null; source: string | null }
  remotes?: string[]
  has_origin?: boolean
  last_fetch?: string | null
  worktrees?: { path: string; branch: string | null; head: string | null; detached: boolean; current: boolean; dirty: { tracked: number; untracked: number } | null }[]
  protected?: Record<string, Reason>
  branches: BranchRow[]
  truncated?: boolean
  recovery?: Recovery[]
  missing_linked?: { name: string; runs: RunLink[] }[]
  checked_at?: string
}

export interface Commit { commit: string; author: string; email?: string; at: string; subject: string }

export interface BranchDetail {
  branch: BranchRow
  base: string | null
  base_tip: string | null
  commits: Commit[]
  commits_truncated: boolean
  files: { status: string; path: string }[]
  files_total: number
  diff: string
  diff_cut: boolean
  checks: { status: 'passed' | 'failed' | 'not_recorded'; commit: string; at?: string; summary?: string; source?: string }
  runs: RunLink[]
  lineage: { parent: string | null; parent_commit: string | null; evidence: string | null } | null
  destination: { recommended: string | null; confirmed: { branch: string; at?: string; via?: string; commit?: string } | null }
  commands: Record<string, { available: boolean; blocked: Reason[] }>
}

export interface MergePreview {
  source: string
  target: string
  source_head: string
  target_head: string
  path: 'accept' | 'transaction'
  fast_forward: boolean
  commits: Commit[]
  files: { status: string; path: string }[]
  conflicts: string[]
  checks: BranchDetail['checks']
  needs_unchecked_ack: boolean
  target_checked_out: boolean
  blocked: Reason[]
  recommended_target: string | null
  protected: Reason | null
  confirm: Confirm | null
}

export interface DeletePreview {
  branch: string
  where: 'local' | 'remote'
  remote?: string | null
  tip: string
  as_of?: string | null
  merged_into?: string[]
  unmerged?: boolean
  lost_commits?: { commit: string; subject: string; author: string }[]
  lost_truncated?: boolean
  local_kept?: boolean
  remote_kept?: boolean
  blocked: Reason[]
  confirm: Confirm | null
  confirm_unmerged?: Confirm | null
}

export interface BranchApi {
  freshness(): Promise<LiveFreshness>
  context(): Promise<BranchContext | null>
  inventory(base?: string | null): Promise<Inventory>
  detail(name: string, kind: 'local' | 'remote', remote?: string | null, base?: string | null): Promise<BranchDetail>
  select(branch: string, scan: boolean, expectedTip?: string | null): Promise<{ run: Run; scan: Run | null; context: BranchContext }>
  previewMerge(source: string, target?: string | null): Promise<MergePreview>
  merge(preview: MergePreview, uncheckedAck: boolean): Promise<{ run: Run }>
  proposeResolution(source: string, target: string, assistant?: string): Promise<{ run: Run }>
  previewDelete(branch: string, where: 'local' | 'remote', remote?: string | null): Promise<DeletePreview>
  remove(preview: DeletePreview, second?: boolean): Promise<{ run: Run }>
  restore(recovery: string, as?: string): Promise<{ run: Run }>
  fetch(remote?: string): Promise<{ run: Run }>
}
