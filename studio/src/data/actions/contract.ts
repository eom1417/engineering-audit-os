// The action contract the Studio is built against: docs/studio-actions.json itself, bundled at build time (its
// bytes are part of the source fingerprint, scripts/ship.mjs). The live server serves the same file at /api/actions.
import { actions, contract, lifecycle, revision, snapshot, verbs } from '../../../../docs/studio-actions.json'
import type { ActionDef, Bi, RunState, VerbDef, VerbId } from './types'

interface Contract {
  contract: string
  revision: number
  actions: ActionDef[]
  verbs: VerbDef[]
  lifecycle: { states: Record<RunState, Bi>; terminal: RunState[] }
  snapshot: { command: string; text: Bi }
}

// Named parts only, so the build leaves out what the pages never read (the endpoints, the security notes, the schemas)
export const CONTRACT = { contract, revision, actions, verbs, lifecycle, snapshot } as unknown as Contract

export const ACTIONS: ActionDef[] = CONTRACT.actions
export const VERBS: VerbDef[] = CONTRACT.verbs
export const STATE_WORDS: Record<RunState, Bi> = CONTRACT.lifecycle.states
export const SNAPSHOT = CONTRACT.snapshot

const BY_ID = new Map(ACTIONS.map((action) => [action.id, action]))

export function actionOf(id: string): ActionDef | undefined {
  return BY_ID.get(id)
}

export function verbOf(id: VerbId): VerbDef {
  return VERBS.find((verb) => verb.id === id)!
}

/** The inputs the person fills in: every input but `project`, which the Studio fills with the project it serves. */
export function personInputs(action: ActionDef): [string, NonNullable<ActionDef['inputs']['properties']>[string]][] {
  return Object.entries(action.inputs.properties ?? {}).filter(([name]) => name !== 'project')
}
