// What each view draws from the same nodes in the same places: Current (the code as it is), Target (the part each
// step goes to in the target architecture) and Change (each step coloured by its part's operation).
import type { DrawEdge, DrawNode } from './Lanes'
import { opOf, possible, targetOf, type Cluster, type CodePath, type Index, type PathMode, type PathNode, type PathsData } from './model'
import { GAP_WORD, LANE_WORD, OP_WORD, type PathWord } from './words'

type Words = (key: PathWord, vars?: Record<string, string | number>) => string

function base(path: string | null, line: number | null): string | null {
  if (!path) return null
  const name = path.split('/').pop() ?? path
  return line ? `${name}:${line}` : name
}

/** A node as a view draws it: its title and second line, its operation, faded when the target deletes it. */
export function drawNode(data: PathsData, n: PathNode, mode: PathMode, w: Words): DrawNode {
  const op = opOf(data, n)
  const to = targetOf(data, n)
  const gap = n.kind === 'gap'
  let title = n.reason === 'trace_stopped' ? w('callsNotResolved', { n: Number(n.detail) || n.items.length }) : n.label
  let sub: string | null = gap && n.reason ? w(GAP_WORD[n.reason].title) : base(n.path, n.line)
  if (mode === 'target' && !gap) {
    title = to?.target ?? (n.component ? w('noTarget') : n.label)
    sub = op === 'delete' ? w('removed') : to?.layer ? `${w('layer')}: ${to.layer}` : n.label
  } else if (mode === 'change' && !gap && op) {
    sub = `${w(OP_WORD[op])}${to?.target ? ` → ${to.target}` : ''}`
  }
  const aria = [w(LANE_WORD[n.lane]), title, sub, gap && n.reason ? w(GAP_WORD[n.reason].why) : null].filter(Boolean).join(' · ')
  return { id: n.id, lane: n.lane, title, sub, kind: n.kind, op: mode === 'current' ? null : op, aria }
}

/** One path: every step it walks, the links only the imports support drawn as possible (or faded when the person
 * asks for only what the trace confirms). */
export function drawPath(data: PathsData, index: Index, path: CodePath, mode: PathMode, w: Words, onlyTraced: boolean) {
  const maybe = possible(data, path)
  const nodes = new Map<string, DrawNode>()
  for (const id of path.columns.flat()) {
    const n = index.node.get(id)
    if (n) nodes.set(id, { ...drawNode(data, n, mode, w), dim: onlyTraced && maybe.nodes.has(id) })
  }
  const edges: DrawEdge[] = path.steps.map((i) => {
    const e = data.edges[i]
    const to = index.node.get(e.to)
    const style = to?.kind === 'gap' ? 'gap' : maybe.edges.has(i) || e.how === 'file_route' ? 'possible' : 'solid'
    return { key: String(i), from: e.from, to: e.to, style, dim: onlyTraced && maybe.edges.has(i) }
  })
  return { nodes, edges }
}

/** The overview: one box per cluster, its size the number of steps it groups, links weighted by their count. */
export function drawOverview(data: PathsData, mode: PathMode, w: Words) {
  const nodes = new Map<string, DrawNode>()
  for (const c of data.overview.clusters) nodes.set(c.id, drawCluster(data, c, mode, w))
  const edges: DrawEdge[] = data.overview.links.map((l) => ({
    key: `${l.from}>${l.to}`, from: l.from, to: l.to, style: l.to.includes(':no_server_route') || l.to.includes(':trace_stopped')
      || l.to.includes(':component_not_found') || l.to.includes(':handler_not_found') ? 'gap' : 'solid',
    width: Math.min(5, 0.8 + Math.log1p(l.n) * 0.7),
  }))
  return { nodes, edges }
}

function drawCluster(data: PathsData, c: Cluster, mode: PathMode, w: Words): DrawNode {
  const part = c.component ? data.components[c.component] : undefined
  const op = mode === 'current' ? null : part?.op ?? null
  const gap = c.kind === 'gap'
  const kinds: Record<string, PathWord> = { table: 'kindTables', external: 'kindExternal', store: 'kindStores' }
  let title = gap && (c.label === c.reason || !c.label) ? '?' : c.size > 1 && kinds[c.label] ? w(kinds[c.label]) : c.label
  let sub: string | null = gap && c.reason ? w(GAP_WORD[c.reason].title) : c.size > 1 ? w('nodesN', { n: c.size }) : null
  if (mode === 'target' && part) {
    title = part.target ?? w('noTarget')
    sub = part.op === 'delete' ? w('removed') : part.layer ? `${w('layer')}: ${part.layer}` : c.label
  } else if (mode === 'change' && op) {
    sub = `${w(OP_WORD[op])}${part?.target ? ` → ${part.target}` : ''}`
  }
  return { id: c.id, lane: c.lane, title, sub, kind: gap ? 'gap' : c.size > 1 ? 'group' : (c.kind as DrawNode['kind']), op, count: c.size,
    aria: [w(LANE_WORD[c.lane]), title, sub, w('nodesN', { n: c.size })].filter(Boolean).join(' · ') }
}
