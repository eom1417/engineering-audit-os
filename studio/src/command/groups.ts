// The groups a person can select whole, from the open report: by area (the card's category), severity, component
// (the map's owner of the card's first path, one number on every page), gap and operation (story.json's gap rows),
// and plan step (the cards whose milestone is the step).
import type { Relation, StudioData } from '../data/types'
import { ownerOf } from '../map/model'
import type { GroupKind } from './selectionModel'

export interface Group { by: GroupKind; value: string; label: string; ids: string[] }

const SEVERITIES = ['critical', 'high', 'medium', 'low'] as const

function bucket(entries: [string, string][]): Map<string, string[]> {
  const out = new Map<string, string[]>()
  for (const [key, id] of entries) {
    const ids = out.get(key)
    if (ids) ids.push(id)
    else out.set(key, [id])
  }
  return out
}

export function componentOwner(data: StudioData): (path: string) => string | undefined {
  const nodes = data.system?.current.nodes.map((n) => n.id) ?? []
  if (nodes.length) return ownerOf(nodes)
  const names = (data.story?.current.components ?? []).map((c) => c.name)
  return ownerOf(names)
}

export function groupsOf(data: StudioData): Record<GroupKind, Group[]> {
  const cards = data.cards?.cards ?? []
  const known = new Set(cards.map((c) => c.id))
  const sorted = (groups: Group[]) => groups.filter((g) => g.ids.length).sort((a, b) => b.ids.length - a.ids.length || a.label.localeCompare(b.label))
  const area = [...bucket(cards.map((c) => [c.category, c.id])).entries()].map(([value, ids]) => ({ by: 'area' as const, value, label: value, ids }))
  const severity = SEVERITIES.map((value) => ({ by: 'severity' as const, value, label: value, ids: cards.filter((c) => c.severity === value).map((c) => c.id) }))
    .filter((g) => g.ids.length)
  const owner = componentOwner(data)
  const component = [...bucket(cards.filter((c) => c.paths[0]).map((c) => [owner(c.paths[0]) ?? '', c.id])).entries()]
    .filter(([value]) => value).map(([value, ids]) => ({ by: 'component' as const, value, label: value, ids }))
  const gaps = (data.story?.gap ?? []).filter((row) => row.relation !== 'retain')
  const gap = gaps.map((row) => ({ by: 'gap' as const, value: row.component, label: row.component, ids: row.cards.filter((id) => known.has(id)) }))
  const byRelation = new Map<Relation, Set<string>>()
  for (const row of gaps) {
    let ids = byRelation.get(row.relation)
    if (!ids) { ids = new Set(); byRelation.set(row.relation, ids) }
    for (const id of row.cards) if (known.has(id)) ids.add(id)
  }
  const operation = [...byRelation.entries()].map(([value, ids]) => ({ by: 'operation' as const, value, label: value, ids: [...ids] }))
  const steps = data.plans?.plans[0]?.steps ?? []
  const milestones = bucket(cards.map((c) => [c.milestone ?? '', c.id]))
  const step = steps.map((s) => {
    const ids = milestones.get(s.id) ?? []
    return { by: 'step' as const, value: s.id, label: s.title ?? s.gate ?? s.id, ids: ids.length ? ids : s.tasks.map((t) => t.id).filter((id) => known.has(id)) }
  }).filter((g) => g.ids.length)
  return {
    area: sorted(area), severity, component: sorted(component), gap: sorted(gap),
    operation: sorted(operation), step,
  }
}

/** The cards of one plan step, as the Change page selects them. */
export function stepCards(data: StudioData, step: string): string[] {
  return groupsOf(data).step.find((g) => g.value === step)?.ids ?? []
}
