// The command centre's shapes, as docs/studio-actions.json defines them (NS46.T9's contract): actions, verbs,
// selections, runs, their events, questions and previews. The pages read only these.

/** A sentence in both languages: every event and label carries one. */
export interface Bi { en: string; ar: string }

export type RunState = 'queued' | 'running' | 'paused' | 'waiting_for_person' | 'done' | 'failed' | 'stopped' | 'unchanged'
export const TERMINAL: readonly RunState[] = ['done', 'failed', 'stopped', 'unchanged']
/** A run that may be tried again: one that did not finish, was stopped, or kept no change. */
export const RETRYABLE: readonly RunState[] = ['failed', 'stopped', 'unchanged']
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

export interface VerbDef { id: VerbId; label: Bi; needs_assistant: boolean; changes_code: boolean; tools: string[]; result: Bi; inputs?: JsonSchema }

export interface Assistant { id: string; name: string; installed: boolean; logged_in: boolean; version?: string | null; model?: string | null }

/** What the assistant used (eaos/usage.py): tokens, the cost at API prices when the assistant gives it, time, turns. */
export interface Usage { input: number; cache_write: number; cache_read: number; output: number; thinking: number
  cost_usd: number | null; duration_ms: number; turns: number; calls: number; models: string[] }
export interface UsageRun { id: string; verb?: string | null; action?: string | null; label?: Bi | null; state?: RunState
  assistant?: string | null; created?: string | null; cards: number; usage: Usage | null }
export interface UsageReport { check: { stages: Record<string, Usage>; total: Usage | null } | null; runs: UsageRun[]; chat?: Usage | null }

/** One turn of the conversation with the person's assistant (eaos/studio/actions/chat.py): it proposes, the person runs. */
export interface ChatProposal { kind: 'action' | 'control'; action: string; inputs?: Record<string, unknown>; run?: string; why: string }
export interface ChatTurn { session: string | null; answer: string; proposals: ChatProposal[]; assistant: string; usage: Usage | null
  /** What direct control set going: each proposal's run, or why it could not */
  done: { proposal: ChatProposal; run?: string; error?: string }[] }
export interface ChatProgress { done: boolean; reading: string[]; partial: string; result: ChatTurn | null; error: string | null }
export interface ChatControl { on: boolean; until: string | null; actions: string[] }
export type ChatModel = 'quick' | 'balanced' | 'deep'

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
  /** A Fix delivered directly: the base branch its fixes landed on (no branch is left to accept) */
  landed_on?: string | null
  diff_stat: { files: number; insertions: number; deletions: number } | null
  tests: { passed: boolean | null; summary: string } | null
  cards_closed: string[]
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
  /** when its details were removed, keeping this record alone (eaos/studio/actions/store.py trim) */
  trimmed?: string | null
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
  left_out: { id: string; why: string; why_ar?: string }[]
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
  /** Fix only: where the batch is built, the branch it arrives on, and the branch Accept merges it into. */
  where?: FixWhere | null
  /** Fix only: this preview's confirmation carries the person's choice to accept the batch when its checks pass */
  auto_accept?: boolean
  /** Accept only: the waiting branch, where it merges and the person's branches to choose from */
  merge?: AcceptWhere | null
  /** A check only: the paths it may follow and the kept mode (eaos/check_choices.py offered) */
  check?: CheckOffer
}

/** What the start of a check offers: each path with what it looks at, the mode and sign-in kept for the project, and the
 * sign-in its code shows (the ways to sign in are offered when it shows one, or one was chosen). */
export interface CheckOffer {
  paths: { id: string; name: Bi; looks_at: Bi }[]
  mode: 'normal' | 'speed'
  sign_in: SignInWay | null
  sign_in_seen: string[]
}

export type SignInWay = 'hand' | 'test_user' | 'none'

/** What Accept shows before merging (eaos/studio/actions/branches.py accept_where). */
export interface AcceptWhere {
  branch: string | null
  target: string | null
  delete_after: boolean
  targets: { name: string; short: string; blocked: Reason | null }[]
}

/** The person's choice in the Accept sheet. */
export interface AcceptChoice { merge_into?: string; delete_after?: boolean }

/** A Fix preview's place (eaos/studio/actions/branches.py fix_where): every part editable; the base commit is pinned. */
export interface FixWhere {
  base: { branch: string; commit: string; short: string; when: string | null; checked_out: boolean } | null
  /** new: a new branch; continue: an EAOS work branch still waiting; direct: on the base branch itself */
  mode: 'new' | 'continue' | 'direct'
  deliver_as: string | null
  /** The EAOS work branches not merged yet that this group may continue on */
  continuable: { name: string; short: string }[]
  /** Why the fixes cannot land directly on the base (a protected branch), or null */
  direct_blocked: Reason | null
  merge_into: string | null
  branches: { name: string; short: string; blocked: Reason | null }[]
  problem: Reason | null
}

/** What the person changed in the place: sent with the preview, and with the start (plus the base commit it showed). */
export interface WhereChoice { base?: string; deliver_as?: string; merge_into?: string; base_commit?: string }

export interface PreviewBody { inputs?: Record<string, unknown>; selection?: Selection; verb?: VerbId; assistant?: string; where?: WhereChoice }
export interface StartBody extends PreviewBody { action: string; confirm?: string | null }

export type Mode = 'live' | 'snapshot'

/** The connection of a run's event stream: what the run page says while it reconnects. */
export type StreamStatus = 'connecting' | 'open' | 'reconnecting' | 'closed'

export type Control = 'pause' | 'resume' | 'stop' | 'retry'

/** A refusal or failure of the action API, with the server's reason. */
export class ActionError extends Error {
  status: number
  needs?: string
  reasons: Reason[]
  constructor(status: number, message: string, needs?: string, reasons: Reason[] = []) {
    super(message)
    this.status = status
    this.needs = needs
    this.reasons = reasons
  }
}

/** The command centre as the pages use it; live (the server) or snapshot. */
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
  decide(id: string, op: 'accept' | 'undo', confirm: string, choice?: AcceptChoice): Promise<Run>
  /** The assistants on this computer and what they used (live only) */
  assistants?(): Promise<Assistant[]>
  usage?(): Promise<UsageReport>
  chat?(message: string, session: string | null, context: Record<string, unknown>, model: ChatModel): Promise<{ turn: string }>
  chatProgress?(turn: string): Promise<ChatProgress>
  chatControl?(on?: boolean): Promise<ChatControl>
  /** A new project from its plan, its blueprint drawn by the person's assistant; or, with mode extend, a feature planned
   *  into this project (live only) */
  plan?(body: { name: string; text: string; files: { name: string; data: string }[]; mode?: 'extend' }): Promise<Run>
  /** Branch control and live freshness (live only: eaos/studio/actions/branches.py) */
  branches?: BranchApi
  /** The sign-in a check waits for, and the browser the person signs in with (live only: eaos/api/sign_in.py) */
  signIn?: SignInApi
  /** The projects on this computer, and the address of one's own Studio, started when it is not (live only:
   *  eaos/api/projects.py) */
  projects?(): Promise<ProjectRow[]>
  openProject?(workspace: string): Promise<{ studio: string; name: string }>
}

/** What a check asks while it waits for the person to sign in to their app, and what the app sent them meanwhile. */
export interface SignInStatus {
  asked: { asked: string; until: string; base: string; why: 'needed' | 'expired' | 'published'; published: boolean } | null
  open: boolean
  /** a session the person made by hand is kept for this project */
  kept: boolean
  codes: { output: string[]; mail: { to: string; subject: string; text: string; at: string }[] } | null
}

/** The sign-in browser as it is now: its address, its title and its picture (a JPEG in base64). */
export interface SignInView { url: string; title: string; picture: string | null }

export type SignInInput = { do: 'look' | 'back' } | { do: 'click'; x: number; y: number } | { do: 'type'; text: string } | { do: 'key'; key: string } | { do: 'scroll'; dy: number }

export interface SignInApi {
  status(): Promise<SignInStatus>
  open(): Promise<SignInView>
  input(command: SignInInput): Promise<SignInView>
  done(): Promise<SignInStatus>
  skip(): Promise<SignInStatus>
  forget(): Promise<SignInStatus>
}

/** A project EAOS knows on this computer, for the switcher. */
export interface ProjectRow { workspace: string; name: string; path: string; current: boolean; score: number | null; checked: string | null; studio: boolean }

/** A reason in both languages, with a stable code */
/** Why a change cannot happen now; `runs` are the queued or working runs it waits for (each can be stopped). */
export interface Reason extends Bi { code: string; runs?: { id: string; label: Bi }[] }
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
  lineage: { parent: string | null; parent_commit: string | null; evidence: string | null; recorded_at?: string | null } | null
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
  /** whose branch it is (eaos, shared, yours): told before confirming; it never blocks the person's own change */
  whose?: Reason
  /** the clean worktree (not the project folder) removed together with the branch */
  worktree?: string | null
}

/** The one-step cleanup: merged branches and old clean worktrees that go, what stays and why. */
export interface CleanupPreview {
  base: string | null
  kept_branches: string[]
  branches: { branch: string; tip: string; merged_into: string; whose: Reason; worktree: string | null }[]
  worktrees: { path: string; head: string; prunable: boolean }[]
  kept: { branch: string; reasons: Reason[] }[]
  digest: string
  blocked: Reason[]
  confirm: Confirm | null
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
  previewCleanup(): Promise<CleanupPreview>
  cleanup(preview: CleanupPreview): Promise<{ run: Run }>
  fetch(remote?: string): Promise<{ run: Run }>
}
