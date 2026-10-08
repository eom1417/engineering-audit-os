// What the infrastructure lens draws in each view, from studio/infra.json: the rows of a lane (today's items, the
// target's decisions, or today's items with what the target adds), and a node's readable name.
import type { Infra, InfraNode, Lane, TargetItem } from '../../data/dataMap'
import type { DataWord } from '../data/words'

export type Mode = 'current' | 'change' | 'target'
export const MAX_ROWS = 8

export type Row =
  | { kind: 'node'; node: InfraNode }
  | { kind: 'item'; item: TargetItem }
  | { kind: 'more'; more: number }

export function modeOf(view: string | undefined, infra: Infra): Mode {
  const mode = view === 'change' || view === 'target' ? view : 'current'
  return mode !== 'current' && !infra.target ? 'current' : mode
}

/** The rows a lane shows: at most MAX_ROWS, the last one saying how many more there are. */
export function rowsOf(infra: Infra, lane: Lane, mode: Mode): Row[] {
  const today = infra.lanes.find((l) => l.id === lane)
  const items = infra.target?.lanes.find((l) => l.id === lane)?.items ?? []
  const nodes = today ? [...today.nodes, ...today.folded] : []
  const rows: Row[] = mode === 'target' ? items.map((item) => ({ kind: 'item', item }))
    : [...nodes.map((node): Row => ({ kind: 'node', node })),
       ...(mode === 'change' ? items.filter((i) => i.op === 'introduce').map((item): Row => ({ kind: 'item', item })) : [])]
  return rows.length > MAX_ROWS ? [...rows.slice(0, MAX_ROWS - 1), { kind: 'more', more: rows.length - MAX_ROWS + 1 }] : rows
}

/** Every row of a lane, unfolded: the steps view and the inspector list them all. */
export function allRows(infra: Infra, lane: Lane, mode: Mode): Row[] {
  const rows = rowsOf(infra, lane, mode)
  if (rows[rows.length - 1]?.kind !== 'more') return rows
  const today = infra.lanes.find((l) => l.id === lane)
  const nodes = today ? [...today.nodes, ...today.folded] : []
  const items = (infra.target?.lanes.find((l) => l.id === lane)?.items ?? []).filter((i) => mode === 'target' || i.op === 'introduce')
  return mode === 'target' ? items.map((item) => ({ kind: 'item', item })) : [...nodes.map((node): Row => ({ kind: 'node', node })),
    ...(mode === 'change' ? items.map((item): Row => ({ kind: 'item', item })) : [])]
}

/** A node's name in the page's language where it is a kind of thing (signals, the variables), else as found. */
export function nodeName(node: InfraNode, w: (key: DataWord, vars?: Record<string, string | number>) => string): string {
  if (node.kind === 'signal') return SIGNALS.has(node.name) ? w(`sig_${node.name}` as DataWord) : node.name
  if (node.id === 'env:variables') return w('kind_variables')
  if (node.id === 'db:schema') return w('kind_schema')
  if (node.id === 'db:migrations') return w('kind_migrations')
  if (node.id === 'db:pool') return w('kind_pool')
  return node.name
}
const SIGNALS = new Set(['log', 'metric', 'trace', 'error_capture', 'sentry'])

/** The node or target item a row id names (the map and the steps view share the ids). */
export function find(infra: Infra, id: string): { lane: Lane; node?: InfraNode; item?: TargetItem } | null {
  for (const lane of infra.lanes) {
    const node = [...lane.nodes, ...lane.folded].find((n) => n.id === id)
    if (node) return { lane: lane.id, node }
  }
  const [, lane, area] = id.split(':')
  const item = infra.target?.lanes.find((l) => l.id === lane)?.items.find((i) => i.area === area)
  return id.startsWith('target:') && item ? { lane: lane as Lane, item } : null
}
