// studio/gaps.json and studio/operations.json (contract v2, schemas/artifacts/studio-{gaps,operations}.schema.json):
// what separates each component from the ideal, and the operations that close it in the order the plan runs them
// (eaos/studio/change.py). A closure the cards do not measure is null, never 0.
import type { Measure } from './measure'

export type ChangeOp = 'retain' | 'refactor' | 'rebuild' | 'merge' | 'delete' | 'new'
export type OpState = 'todo' | 'active' | 'done' | 'blocked' | 'regressed'

export interface Gap {
  id: string
  component: string
  operation: ChangeOp
  to?: string | null
  responsibility?: string | null
  reason?: string | null
  files: number
  cards: string[]
  cards_closed: number
  /** How far the plan's cards cover the change (gap-matrix.json) */
  cover?: 'covered' | 'partial' | 'missing' | null
  steps?: string[]
  operations?: string[]
  decision?: string | null
  closed: Measure
}

export interface Operation {
  id: string
  op: ChangeOp
  subject: string
  subject_kind: string
  target?: string | null
  reason: string
  plan?: string | null
  step?: string | null
  order: number
  after: string[]
  gap?: string | null
  cards?: string[]
  files?: number
  sources?: string[]
  branch?: string | null
  state: OpState
}
