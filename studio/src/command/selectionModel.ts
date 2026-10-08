// The selection model, pure: check boxes with shift ranges over the visible order, groups picked whole, and the
// contract's selection (`card`, `cards`, `group` or `step`) the server resolves. Used by the Problems, Change and
// System pages through selection.tsx.
import type { GroupBy, Selection } from '../data/actions/types'

/** The most cards one selection may name (contract `selection.schema.cards.maxItems`). */
export const MAX_CARDS = 500

export type GroupKind = GroupBy | 'step'

/** A group the person picked whole: the cards it holds and how the server can name it again. */
export interface GroupRef { by: GroupKind; value: string; label: string }

export interface SelState {
  ids: string[]
  /** The last box ticked without shift: a shift-tick selects from it */
  anchor: string | null
  group: GroupRef | null
}

export const EMPTY: SelState = { ids: [], anchor: null, group: null }

function cap(ids: string[]): string[] {
  return ids.length > MAX_CARDS ? ids.slice(0, MAX_CARDS) : ids
}

/** Ticks or unticks `id`; with shift, every id between the anchor and `id` in `order` takes the new state of `id`. */
export function toggle(state: SelState, id: string, shift: boolean, order: string[]): SelState {
  const has = new Set(state.ids)
  const on = !has.has(id)
  const from = state.anchor ? order.indexOf(state.anchor) : -1
  const to = order.indexOf(id)
  const span = shift && from >= 0 && to >= 0 ? order.slice(Math.min(from, to), Math.max(from, to) + 1) : [id]
  for (const each of span) { if (on) has.add(each); else has.delete(each) }
  const ids = [...state.ids.filter((x) => has.has(x)), ...span.filter((x) => has.has(x) && !state.ids.includes(x))]
  return { ids: cap(ids), anchor: shift && from >= 0 ? state.anchor : id, group: null }
}

/** Replaces the selection with a whole group (or adds the ids, keeping no group name). */
export function pickGroup(state: SelState, ids: string[], group: GroupRef | null, add = false): SelState {
  if (add) {
    const merged = [...state.ids, ...ids.filter((id) => !state.ids.includes(id))]
    return { ids: cap(merged), anchor: state.anchor, group: null }
  }
  return { ids: cap([...new Set(ids)]), anchor: null, group }
}

/** Ticks or unticks several ids at once (a plan step's cards, the shown list). */
export function setMany(state: SelState, ids: string[], on: boolean): SelState {
  const drop = new Set(ids)
  const next = on ? [...state.ids, ...ids.filter((id) => !state.ids.includes(id))] : state.ids.filter((id) => !drop.has(id))
  return { ids: cap(next), anchor: state.anchor, group: null }
}

/** The contract's selection: the group by name where the server resolves it the same way, else the ids as seen. */
export function toSelection(state: SelState): Selection | null {
  if (!state.ids.length) return null
  const group = state.group
  if (group?.by === 'step') return { kind: 'step', step: group.value }
  if (group && (group.by === 'area' || group.by === 'severity')) return { kind: 'group', group: { by: group.by, value: group.value } }
  if (state.ids.length === 1) return { kind: 'card', cards: [...state.ids] }
  return { kind: 'cards', cards: [...state.ids] }
}
