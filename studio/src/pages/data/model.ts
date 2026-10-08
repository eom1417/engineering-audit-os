// What the data paths page draws, computed from studio/data_paths.json: the view for each mode, the colour of a store
// in the Change view, the order of the steps view, the chain of each write and what a cluster holds. No position is
// computed here: EAOS laid the map out (eaos/studio/data_paths.py), so a store keeps its place across views.
import type { DataPaths, DataView, Store, StoreChange, Tier, WritePath } from '../../data/dataMap'

export type Mode = 'current' | 'change' | 'target'
export const MODES: Mode[] = ['current', 'change', 'target']

export function modeOf(view: string | undefined, dp: DataPaths): Mode {
  const mode = MODES.includes(view as Mode) ? (view as Mode) : 'current'
  return mode !== 'current' && !dp.target ? 'current' : mode
}

/** The laid-out overview a mode draws: the target's lanes in Target, today's otherwise (Change colours today's). */
export function viewOf(dp: DataPaths, mode: Mode): DataView {
  return mode === 'target' && dp.target ? dp.target : dp.current
}

/** A store's tone in the Change view: one source already (keep), made one by the target (merge), still several
 * writers (rebuild), or nothing to say (no writes, or no target). */
export type Tone = 'keep' | 'merge' | 'rebuild' | 'none'
export const CHANGE_TONE: Record<StoreChange, Tone> = { single_already: 'keep', merged_in_target: 'merge', still_multiple: 'rebuild' }

export function toneOf(store: Store | undefined, mode: Mode): Tone {
  if (!store) return 'none'
  if (mode === 'change') return store.change ? CHANGE_TONE[store.change] : 'none'
  return store.multi_writer ? 'rebuild' : 'none'
}

/** The steps view's order: stores written from several places first, then by how many write them, then by name. */
export function ranked(stores: Store[]): Store[] {
  return [...stores].sort((a, b) => Number(b.multi_writer) - Number(a.multi_writer) || b.writers.length - a.writers.length
    || b.readers.length - a.readers.length || a.name.localeCompare(b.name))
}

export function pathsOf(dp: DataPaths, store: string): WritePath[] {
  return dp.paths.filter((p) => p.store === store)
}

/** The members of a cluster node, or the node itself. */
export function membersOf(view: DataView, id: string): string[] {
  return view.clusters.find((c) => c.id === id)?.members ?? [id]
}

/** The cluster node that holds a store on this view, or the store itself when its lane is not clustered. */
export function nodeOf(view: DataView, id: string): string {
  return view.clusters.find((c) => c.members.includes(id))?.id ?? id
}

export const isCluster = (id: string) => id.startsWith('cluster:')

/** A store's short label on the map: the table or resource name, without the id's kind prefix. */
export function labelOf(id: string, stores: Map<string, Store>): string {
  if (isCluster(id)) return id.slice('cluster:'.length).replace(/(^|…)\w+:/g, '$1') + '…' // cluster:table:work -> work…
  return stores.get(id)?.name ?? id
}

/** How many write paths reach each tier with evidence (known or direct), and how many stop there. */
export function tierCounts(paths: WritePath[], tier: Tier): { known: number; gaps: number } {
  let known = 0
  for (const p of paths) if (p.steps[tier].state !== 'gap') known += 1
  return { known, gaps: paths.length - known }
}

/** Edges at or around a focused node: those that touch it, or any member of the cluster it is. */
export function touches(view: DataView, focus: string | undefined): Set<string> {
  const lit = new Set<string>()
  if (!focus) return lit
  for (const e of view.edges) if (e.from === focus || e.to === focus) { lit.add(e.from); lit.add(e.to) }
  return lit
}
