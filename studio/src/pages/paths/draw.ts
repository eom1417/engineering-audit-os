// What each view draws from the same nodes in the same places: Current (the code as it is), Target (the part each
// step goes to in the target architecture) and Change (each step coloured by its part's operation).
import type { DrawEdge, DrawNode } from './Lanes'
import { opOf, possible, targetOf, type Cluster, type CodePath, type Index, type PathMode, type PathNode, type PathsData } from './model'
import { GAP_WORD, LANE_WORD, OP_WORD, type PathWord } from './words'

type Words = (key: PathWord, vars?: Record<string, string | number>) => string
type Op = ReturnType<typeof opOf>
type Target = ReturnType<typeof targetOf>
type Lines = [string, string | null]

function base(path: string | null, line: number | null): string | null {
  if (!path) return null
  const name = path.split('/').pop() ?? path
  return line ? `${name}:${line}` : name
}

/** The second line of the Change view: the operation, and where the part goes when it has a target. */
function changeSub(op: NonNullable<Op>, target: string | null | undefined, w: Words): string {
  return `${w(OP_WORD[op])}${target ? ` → ${target}` : ''}`
}

/** A node's lines as the code is: its label (or how many calls stopped the trace) and its file and line. */
function plainLines(n: PathNode, w: Words): Lines {
  const title = n.reason === 'trace_stopped' ? w('callsNotResolved', { n: Number(n.detail) || n.items.length }) : n.label
  return [title, n.kind === 'gap' && n.reason ? w(GAP_WORD[n.reason].title) : base(n.path, n.line)]
}

/** A node's lines in the Target view: the part it goes to, and its layer, or that it is removed. */
function targetLines(n: PathNode, op: Op, to: Target, w: Words): Lines {
  const title = to?.target ?? (n.component ? w('noTarget') : n.label)
  return [title, op === 'delete' ? w('removed') : to?.layer ? `${w('layer')}: ${to.layer}` : n.label]
}

function nodeLines(n: PathNode, op: Op, to: Target, mode: PathMode, w: Words): Lines {
  const plain = plainLines(n, w)
  if (n.kind === 'gap') return plain
  if (mode === 'target') return targetLines(n, op, to, w)
  if (mode === 'change' && op) return [plain[0], changeSub(op, to?.target, w)]
  return plain
}

/** A node as a view draws it: its title and second line, its operation, faded when the target deletes it. */
export function drawNode(data: PathsData, n: PathNode, mode: PathMode, w: Words): DrawNode {
  const op = opOf(data, n)
  const [title, sub] = nodeLines(n, op, targetOf(data, n), mode, w)
  const why = n.kind === 'gap' && n.reason ? w(GAP_WORD[n.reason].why) : null
  const aria = [w(LANE_WORD[n.lane]), title, sub, why].filter(Boolean).join(' · ')
  return { id: n.id, lane: n.lane, title, sub, kind: n.kind, op: mode === 'current' ? null : op, aria }
}

/** How a path view is drawn: the view, its words, and whether only what the trace confirms is shown in full. */
export type PathView = { mode: PathMode; w: Words; onlyTraced: boolean }

function edgeStyle(gap: boolean, maybe: boolean, how: string | undefined): DrawEdge['style'] {
  if (gap) return 'gap'
  return maybe || how === 'file_route' ? 'possible' : 'solid'
}

/** One path: every step it walks, the links only the imports support drawn as possible (or faded when the person
 * asks for only what the trace confirms). */
export function drawPath(data: PathsData, index: Index, path: CodePath, { mode, w, onlyTraced }: PathView) {
  const maybe = possible(data, path)
  const nodes = new Map<string, DrawNode>()
  for (const id of path.columns.flat()) {
    const n = index.node.get(id)
    if (n) nodes.set(id, { ...drawNode(data, n, mode, w), dim: onlyTraced && maybe.nodes.has(id) })
  }
  const edges: DrawEdge[] = path.steps.map((i) => {
    const e = data.edges[i]
    const style = edgeStyle(index.node.get(e.to)?.kind === 'gap', maybe.edges.has(i), e.how)
    return { key: String(i), from: e.from, to: e.to, style, dim: onlyTraced && maybe.edges.has(i) }
  })
  return { nodes, edges }
}

const GAP_ENDS = [':no_server_route', ':trace_stopped', ':component_not_found', ':handler_not_found']

/** The overview: one box per cluster, its size the number of steps it groups, links weighted by their count. */
export function drawOverview(data: PathsData, mode: PathMode, w: Words) {
  const nodes = new Map<string, DrawNode>()
  for (const c of data.overview.clusters) nodes.set(c.id, drawCluster(data, c, mode, w))
  const edges: DrawEdge[] = data.overview.links.map((l) => ({
    key: `${l.from}>${l.to}`, from: l.from, to: l.to, style: GAP_ENDS.some((end) => l.to.includes(end)) ? 'gap' : 'solid',
    width: Math.min(5, 0.8 + Math.log1p(l.n) * 0.7),
  }))
  return { nodes, edges }
}

const KINDS: Record<string, PathWord> = { table: 'kindTables', external: 'kindExternal', store: 'kindStores' }

/** A cluster's lines as the code is: its label (or its kind's name when it groups several) and its size. */
function plainClusterLines(c: Cluster, w: Words): Lines {
  const gap = c.kind === 'gap'
  const title = gap && (c.label === c.reason || !c.label) ? '?' : c.size > 1 && KINDS[c.label] ? w(KINDS[c.label]) : c.label
  return [title, gap && c.reason ? w(GAP_WORD[c.reason].title) : c.size > 1 ? w('nodesN', { n: c.size }) : null]
}

function clusterLines(c: Cluster, part: PathsData['components'][string] | undefined, op: Op, mode: PathMode, w: Words): Lines {
  const plain = plainClusterLines(c, w)
  if (mode === 'target' && part) {
    return [part.target ?? w('noTarget'), part.op === 'delete' ? w('removed') : part.layer ? `${w('layer')}: ${part.layer}` : c.label]
  }
  if (mode === 'change' && op) return [plain[0], changeSub(op, part?.target, w)]
  return plain
}

function drawCluster(data: PathsData, c: Cluster, mode: PathMode, w: Words): DrawNode {
  const part = c.component ? data.components[c.component] : undefined
  const op = mode === 'current' ? null : part?.op ?? null
  const [title, sub] = clusterLines(c, part, op, mode, w)
  const kind = c.kind === 'gap' ? 'gap' : c.size > 1 ? 'group' : (c.kind as DrawNode['kind'])
  return { id: c.id, lane: c.lane, title, sub, kind, op, count: c.size,
    aria: [w(LANE_WORD[c.lane]), title, sub, w('nodesN', { n: c.size })].filter(Boolean).join(' · ') }
}
