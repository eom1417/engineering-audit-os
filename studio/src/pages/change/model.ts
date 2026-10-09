// The Change pages' reading of the report: the Bridge's flows (studio/story.json), the gap register and the operations
// (studio/gaps.json, operations.json), and the plan's step dependencies (the waits of studio/paths.json's timeline).
// Nothing here makes a number the exporter did not write: a flow is a component's files, a dependency is a task that
// waits for another, and what the report does not hold is left out, not guessed.
import { useEffect, useState } from 'react'
import type { ChangeOp, Gap, Operation, OpState } from '../../data/change'
import { script } from '../../data/load'
import type { Plan, PlanStep, Relation, Story, StudioData } from '../../data/types'
import type { WordKey } from '../../i18n/catalog'
import type { Timeline } from '../paths/model'

/** The contract's operation as the operation chip names it (the chip predates contract v2's words). */
export const RELATION_OF: Record<ChangeOp, Relation> = {
  retain: 'retain', refactor: 'modify', rebuild: 'rebuild', merge: 'merge', delete: 'delete', new: 'introduce',
}

/** The operation chip's word for each operation of the contract. */
export const OP_LABEL: Record<ChangeOp, WordKey> = {
  retain: 'opKeep', refactor: 'opModify', rebuild: 'opRebuild', merge: 'opMerge', delete: 'opDelete', new: 'opIntroduce',
}
const FROM_STORY: Record<string, ChangeOp> = { retain: 'retain', modify: 'refactor', rebuild: 'rebuild', delete: 'delete', merge: 'merge', missing: 'new', introduce: 'new' }

// ---------------------------------------------------------------- the Bridge

export const REMOVED = '\u0000removed'
export const OTHER = '\u0000other'

export interface Flow { from: string; to: string; files: number; op: ChangeOp; gap: string | null; folded: number }
export interface Side { id: string; files: number; op: ChangeOp | null; components: number; responsibility?: string }
export interface Bridge { left: Side[]; right: Side[]; flows: Flow[]; files: number; components: number; targets: number }

/**
 * The flows of the Bridge: each component of today to its target component (a deleted one to "Removed"), its files as
 * the width; when there are more than `rows_` components, the smallest of those under `fold` of all files gather in one
 * "Other" source, only as many as it takes to keep `rows_` sources. The target column lists every target
 * component, those nothing flows into marked new. Sides are ordered so ribbons cross as little as they can: targets by
 * the files they receive, sources by their target's place, then by size.
 */
export function bridge(story: Story, fold = 0.02, rows_ = 24): Bridge {
  const rows = story.gap.map((g) => {
    const op = FROM_STORY[g.relation] ?? 'refactor'
    return { component: g.component, files: g.files, op, to: op === 'delete' || !g.to ? REMOVED : g.to }
  })
  const files = rows.reduce((sum, r) => sum + r.files, 0)
  // Only as many of the components under `fold` of the files as it takes to keep `rows` sources, smallest first
  const folded = new Set([...rows].filter((r) => files > 0 && r.files / files < fold)
    .sort((a, b) => a.files - b.files || b.component.localeCompare(a.component))
    .slice(0, Math.max(rows.length - (rows_ - 1), 0)).map((r) => r.component))
  const small = (r: { component: string }) => rows.length > rows_ && folded.has(r.component)
  const flows = new Map<string, Flow>()
  for (const r of rows) {
    const from = small(r) ? OTHER : r.component
    const key = `${from}\u0001${r.to}\u0001${r.op}`
    const flow = flows.get(key) ?? { from, to: r.to, files: 0, op: r.op, gap: from === OTHER ? null : r.component, folded: 0 }
    flow.files += r.files
    flow.folded += from === OTHER ? 1 : 0
    flows.set(key, flow)
  }
  const into = new Map<string, Flow[]>()
  for (const f of flows.values()) into.set(f.to, [...(into.get(f.to) ?? []), f])
  const sources = (to: string) => new Set(rows.filter((r) => r.to === to).map((r) => r.component)).size
  const targets = story.target.components.map((t) => t.name)
  const known = [...new Set([...targets, ...rows.map((r) => r.to).filter((to) => to !== REMOVED)])]
  const weight = (id: string) => (into.get(id) ?? []).reduce((s, f) => s + f.files, 0)
  const right: Side[] = known
    .map((id) => {
      const n = sources(id)
      return { id, files: weight(id), op: (n === 0 ? 'new' : n > 1 ? 'merge' : rows.find((r) => r.to === id)!.op) as ChangeOp, components: n,
        responsibility: story.target.components.find((t) => t.name === id)?.responsibility }
    })
    .sort((a, b) => b.files - a.files || a.id.localeCompare(b.id))
  if (into.has(REMOVED)) right.push({ id: REMOVED, files: weight(REMOVED), op: 'delete', components: sources(REMOVED) })
  const place = new Map(right.map((s, i) => [s.id, i]))
  const out = new Map<string, Side>()
  for (const f of flows.values()) {
    const side = out.get(f.from) ?? { id: f.from, files: 0, op: f.from === OTHER ? null : f.op, components: 0 }
    side.files += f.files
    side.components += f.from === OTHER ? f.folded : 1
    out.set(f.from, side)
  }
  const first = (id: string) => Math.min(...[...flows.values()].filter((f) => f.from === id).map((f) => place.get(f.to) ?? 0))
  const left = [...out.values()].sort((a, b) => (a.id === OTHER ? 1 : 0) - (b.id === OTHER ? 1 : 0) || first(a.id) - first(b.id) || b.files - a.files || a.id.localeCompare(b.id))
  for (const side of left) if (side.id !== OTHER) side.components = 1
  const order = new Map(left.map((s, i) => [s.id, i]))
  const sorted = [...flows.values()].sort((a, b) => (order.get(a.from)! - order.get(b.from)!) || (place.get(a.to)! - place.get(b.to)!))
  return { left, right, flows: sorted, files, components: rows.length, targets: targets.length }
}

export interface Placed { id: string; y: number; h: number }
export interface Ribbon extends Flow { y0: number; y1: number; w: number }

/** Places the Bridge in pixels: a ribbon is exactly as thick as its files at one scale; a side's bar is at least
 * `min` tall so its name can sit beside it. */
export function layout(b: Bridge, height: number, gap = 8, min = 18) {
  const rows = Math.max(b.left.length, b.right.length)
  const scale = b.files > 0 ? Math.max((height - gap * (rows - 1) - min * rows * 0.5) / b.files, 0.05) : 0
  const stack = (sides: Side[]) => {
    let y = 0
    const out = new Map<string, Placed>()
    for (const s of sides) {
      const h = Math.max(s.files * scale, min)
      out.set(s.id, { id: s.id, y, h })
      y += h + gap
    }
    return { at: out, height: Math.max(y - gap, 0) }
  }
  const left = stack(b.left)
  const right = stack(b.right)
  const usedL = new Map<string, number>()
  const usedR = new Map<string, number>()
  const ribbons: Ribbon[] = b.flows.map((f) => {
    const w = f.files * scale
    const l = left.at.get(f.from)!
    const r = right.at.get(f.to)!
    const sumL = b.flows.filter((g) => g.from === f.from).reduce((s, g) => s + g.files * scale, 0)
    const sumR = b.flows.filter((g) => g.to === f.to).reduce((s, g) => s + g.files * scale, 0)
    const y0 = l.y + (l.h - sumL) / 2 + (usedL.get(f.from) ?? 0)
    const y1 = r.y + (r.h - sumR) / 2 + (usedR.get(f.to) ?? 0)
    usedL.set(f.from, (usedL.get(f.from) ?? 0) + w)
    usedR.set(f.to, (usedR.get(f.to) ?? 0) + w)
    return { ...f, y0, y1, w }
  })
  return { left: left.at, right: right.at, ribbons, height: Math.max(left.height, right.height), scale }
}

/** A ribbon as a closed band between x0 and x1 (curves at the middle). */
export function band(x0: number, x1: number, y0: number, y1: number, w: number): string {
  const m = (x0 + x1) / 2
  const t = Math.max(w, 1)
  return `M${x0},${y0}C${m},${y0} ${m},${y1} ${x1},${y1}L${x1},${y1 + t}C${m},${y1 + t} ${m},${y0 + t} ${x0},${y0 + t}Z`
}

// ---------------------------------------------------------------- gaps and operations

export function opsMix(gaps: Gap[]): [ChangeOp, number][] {
  const order: ChangeOp[] = ['delete', 'refactor', 'rebuild', 'merge', 'new', 'retain']
  return order.map((op) => [op, gaps.filter((g) => g.operation === op).length] as [ChangeOp, number]).filter(([, n]) => n > 0)
}

/** The register's order: the operations that change most first, then the gaps with the most cards, then by name. */
export function registerOrder(gaps: Gap[]): Gap[] {
  const order: ChangeOp[] = ['rebuild', 'delete', 'refactor', 'merge', 'new', 'retain']
  return [...gaps].sort((a, b) => order.indexOf(a.operation) - order.indexOf(b.operation) || b.cards.length - a.cards.length
    || b.files - a.files || a.component.localeCompare(b.component))
}

export function byId<T extends { id: string }>(rows: T[] | undefined): Map<string, T> {
  return new Map((rows ?? []).map((row) => [row.id, row]))
}

/** The operations that wait for `op` (the inverse of its `after`). */
export function comesBefore(op: Operation, all: Operation[]): Operation[] {
  return all.filter((o) => o.after.includes(op.id))
}

// ---------------------------------------------------------------- the plan's steps

export interface StepLink { from: string; to: string; tasks: number }

/** Step B waits for step A when a task of B waits for a task of A (studio/paths.json's timeline: a prerequisite, or an
 * earlier task on the same file). `tasks` counts the waiting tasks of B. */
export function stepLinks(timeline: Timeline | null): StepLink[] {
  if (!timeline) return []
  const step = new Map(timeline.tasks.map((t) => [t.id, t.step]))
  const out = new Map<string, Set<string>>()
  for (const task of timeline.tasks) {
    for (const wait of task.waits) {
      const from = step.get(wait.task)
      if (!from || !task.step || from === task.step) continue
      const key = `${from}\u0001${task.step}`
      out.set(key, (out.get(key) ?? new Set()).add(task.id))
    }
  }
  return [...out].map(([key, tasks]) => ({ from: key.split('\u0001')[0], to: key.split('\u0001')[1], tasks: tasks.size }))
    .sort((a, b) => a.to.localeCompare(b.to) || a.from.localeCompare(b.from))
}

/** Layers of the step graph: a step sits one layer after the latest step it waits for (a cycle stops at its first
 * repeat), in the plan's order inside a layer. */
export function layers(steps: string[], links: StepLink[]): string[][] {
  const memo = new Map<string, number>()
  const depth = (id: string, seen: Set<string>): number => {
    if (memo.has(id)) return memo.get(id)!
    if (seen.has(id)) return 0
    const next = new Set(seen).add(id)
    const d = Math.max(-1, ...links.filter((l) => l.to === id).map((l) => depth(l.from, next))) + 1
    memo.set(id, d)
    return d
  }
  const out: string[][] = []
  for (const id of steps) (out[depth(id, new Set())] ??= []).push(id)
  return out.filter(Boolean)
}

/** A card's ledger state (or a plan task's state) as a task state. */
export function cardState(state: string): OpState {
  if (state === 'todo' || state === 'active' || state === 'blocked' || state === 'regressed') return state
  return state === 'done' || state === 'resolved' ? 'done' : state === 'in_batch' || state === 'on_branch' ? 'active' : state === 'skipped' ? 'blocked' : 'todo'
}

export const TASK_STATES: OpState[] = ['done', 'active', 'todo', 'blocked']

export function stateCounts(step: PlanStep): Record<OpState, number> {
  const out: Record<OpState, number> = { todo: 0, active: 0, done: 0, blocked: 0, regressed: 0 }
  for (const task of step.tasks) out[(task.state in out ? task.state : 'todo') as OpState] += 1
  return out
}

/** The first step in the plan's order that is not done and waits for no step that is not done: what to start next. */
export function nextStep(plan: Plan, links: StepLink[]): PlanStep | undefined {
  const done = new Set(plan.steps.filter((s) => s.state === 'done').map((s) => s.id))
  return plan.steps.find((s) => !done.has(s.id) && s.tasks.length > 0 && links.filter((l) => l.to === s.id).every((l) => done.has(l.from)))
}

export const PLAN_STATES = ['registered', 'approved', 'active', 'review', 'merged', 'closed'] as const

// ---------------------------------------------------------------- the coverage row

export interface CoverageRow { section: string; state: string; detail: string; step: string | null; tool: string | null }

/** The coverage row of a section (studio/coverage.json, loaded on demand) for the designed "not measured yet" state. */
export function useCoverage(data: StudioData, section: string): CoverageRow | undefined {
  const listed = data.manifest.sections.some((s) => (s.name as string) === 'coverage')
  const find = () => ((window.EAOS_STUDIO?.coverage as { sections?: CoverageRow[] } | undefined)?.sections ?? []).find((r) => r.section === section)
  const [row, setRow] = useState<CoverageRow | undefined>(find)
  useEffect(() => {
    if (!listed || row) return
    let live = true
    script('coverage').then(() => { if (live) setRow(find()) })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listed, section])
  return row
}
