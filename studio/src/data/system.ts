// studio/system.json (contract v1, schemas/artifacts/studio-system.schema.json): the project as two territory maps,
// today and the target, laid out by EAOS (eaos/studio/system.py, territory.py) so the Studio only draws them.
import type { Measure } from './measure'

export type Operation = 'retain' | 'modify' | 'rebuild' | 'delete' | 'merge' | 'introduce'
export const OPERATIONS: Operation[] = ['retain', 'modify', 'rebuild', 'delete', 'merge', 'introduce']

export interface MapLabel { x: number; y: number; anchor: 'start' | 'middle' | 'end'; size: number; placed: boolean; big?: boolean }

export interface MapRegion {
  id: string
  kind: 'dir' | 'rest' | 'top' | 'layer'
  folder: string | null
  name: { ar: string; en: string; ident: boolean }
  components: number
  files: number
  findings: number | null
  /** The region's largest component: where a link to the region focuses */
  lead: string
  /** x, y: the name on the full map (counts below); tx, ty: on the preview */
  label: { x: number; y: number; tx: number; ty: number }
  land: { level: number; d: string }[]
}

export interface MapEdge { from: string; to: string; imports: number; cycle?: boolean; d: string; mid?: [number, number]; width: number }

interface Placed { id: string; short: string; region: string; files: number; op: Operation; x: number; y: number; r: number; label: MapLabel }

export interface SeverityCount { critical: number; high: number; medium: number; low: number; total: number }

export interface CurrentNode extends Placed {
  kind?: string
  fan_in: number | null
  fan_out: number | null
  findings: SeverityCount
  target: string | null
  merged_with: number
  reason: string
  decision: { id: string; chosen: string } | null
}

export interface TargetNode extends Placed {
  layer: string | null
  responsibility: string
  sources: string[]
  carried: number
}

export interface MapView<N extends Placed = Placed> {
  regions: MapRegion[]
  nodes: N[]
  edges: MapEdge[]
  scale?: number
  /** x, y, width, height of the drawn land, in world units */
  bounds: [number, number, number, number]
}

export interface SystemMap {
  world: { width: number; height: number }
  graph?: string
  counts: { components: Measure; regions: Measure; edges: Measure; imports: Measure; target_components: Measure; target_edges: Measure; target_regions?: Measure }
  operations: Partial<Record<Operation, Measure>>
  src: Record<string, string>
  capped?: number
  current: MapView<CurrentNode>
  target: MapView<TargetNode>
}
