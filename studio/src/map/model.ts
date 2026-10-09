// What the map pages read from studio/system.json: neighbours of a component, the findings bins, the ranked list and
// the counterpart of a component in the other map. Nothing here computes a number the exporter did not write.
import type { CurrentNode, MapEdge, MapView, Operation, SystemMap, TargetNode } from '../data/system'

export type MapMode = 'current' | 'change' | 'target'
export const MODES: MapMode[] = ['current', 'change', 'target']

/** The view a mode draws: today's map for current and change, the target's for target. */
export function viewOf(system: SystemMap, mode: MapMode): MapView<CurrentNode> | MapView<TargetNode> {
  return mode === 'target' ? system.target : system.current
}

/** DESIGN.md §6: five bins of findings, 0, 1–3, 4–9, 10–19, 20+. */
export function findingsBin(n: number): 0 | 1 | 2 | 3 | 4 {
  return n === 0 ? 0 : n <= 3 ? 1 : n <= 9 ? 2 : n <= 19 ? 3 : 4
}
export const BINS: { label: string; bin: number }[] = [
  { label: '0', bin: 0 }, { label: '1–3', bin: 1 }, { label: '4–9', bin: 2 }, { label: '10–19', bin: 3 }, { label: '20+', bin: 4 },
]

export interface Neighbour { id: string; imports: number }

/** Who a node imports and who imports it, heaviest first. */
export function neighbours(edges: MapEdge[], id: string): { uses: Neighbour[]; usedBy: Neighbour[] } {
  const order = (a: Neighbour, b: Neighbour) => b.imports - a.imports || a.id.localeCompare(b.id)
  return {
    uses: edges.filter((e) => e.from === id).map((e) => ({ id: e.to, imports: e.imports })).sort(order),
    usedBy: edges.filter((e) => e.to === id).map((e) => ({ id: e.from, imports: e.imports })).sort(order),
  }
}

const WEIGHT = { critical: 8, high: 4, medium: 2, low: 1 }

export function severityWeight(node: CurrentNode): number {
  const f = node.findings
  return f.critical * WEIGHT.critical + f.high * WEIGHT.high + f.medium * WEIGHT.medium + f.low * WEIGHT.low
}

/** Today's components by what they need: severity weight, then findings, then files. */
export function ranked(view: MapView<CurrentNode>): CurrentNode[] {
  return [...view.nodes].sort((a, b) => severityWeight(b) - severityWeight(a) || b.findings.total - a.findings.total
    || b.files - a.files || a.id.localeCompare(b.id))
}

/** The ids lit on the other map when `id` is focused on `mode`'s map: a component's target, or a target's sources. */
export function counterpart(system: SystemMap, mode: MapMode, id: string | undefined): string[] {
  if (!id) return []
  if (mode === 'target') return system.target.nodes.find((n) => n.id === id)?.sources ?? []
  const target = system.current.nodes.find((n) => n.id === id)?.target
  return target ? [target] : []
}

export function opCount(system: SystemMap, op: Operation): number {
  return system.operations[op]?.value ?? 0
}

/** The component a card belongs to: the deepest one holding its first path, else (root). The exporter counts
 * findings by the same rule (eaos/studio/system.py owner_of), so the map, the list and the problems page agree. */
export function ownerOf(names: string[]): (path: string) => string | undefined {
  const components = new Set(names.filter((n) => n !== '(root)'))
  const root = names.includes('(root)') ? '(root)' : undefined
  return (path) => {
    // Only slash-boundary ancestors can own a path; inspect deepest first.
    let ancestor = path
    while (true) {
      if (components.has(ancestor)) return ancestor
      const slash = ancestor.lastIndexOf('/')
      if (slash < 0) return root
      ancestor = ancestor.slice(0, slash)
    }
  }
}
