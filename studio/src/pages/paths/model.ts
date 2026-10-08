// studio/paths.json (contract v2, schemas/artifacts/studio-paths.schema.json): the code paths EAOS traced, laid out
// by EAOS (eaos/studio/paths.py), and the fix plan's timeline. This file reads it: the section is loaded only when a
// paths page opens (it can be large), and the drawing's geometry turns EAOS's lane order into places. Nothing here
// computes a number the exporter did not write, and no link is added that the data does not hold.
import { useEffect, useState } from 'react'
import { script } from '../../data/load'
import type { Measure, StudioData } from '../../data/types'

export const LANES = ['screen', 'component', 'handler', 'call', 'endpoint', 'service', 'data'] as const
export type Lane = (typeof LANES)[number]
export type How = 'route' | 'contains' | 'call' | 'imports' | 'request' | 'file_route' | 'client' | 'external' | 'defines' | 'package' | 'gap' | 'trace'
export type PathOp = 'retain' | 'refactor' | 'rebuild' | 'merge' | 'delete'
export type GapReason = 'no_server_route' | 'trace_stopped' | 'component_not_found' | 'handler_not_found'
export type PathMode = 'current' | 'target' | 'change'
export const PATH_MODES: PathMode[] = ['current', 'target', 'change']

export interface PathNode {
  id: string
  lane: Lane
  kind: 'step' | 'gap' | 'table' | 'store' | 'external'
  label: string
  fact: string | null
  path: string | null
  line: number | null
  component: string | null
  cards: string[]
  steps: string[]
  paths: number
  reason: GapReason | null
  detail: string | null
  items: { callee: string; path: string | null; line: number | null; resolution?: string }[]
  group?: string | null
  ar?: string
}

export interface PathEdge { from: string; to: string; how: How; fact: string | null; path: string | null; line: number | null }

export interface CodePath {
  id: string
  title: string
  surface: string
  entry: string
  fact: string | null
  flow: string | null
  flow_fact: string | null
  /** The links the path walks, in order: indexes into `edges` */
  steps: number[]
  /** Its nodes, lane by lane, top to bottom: EAOS's layout */
  columns: string[][]
  gaps: number
  capped: number
  unresolved: number | null
  reach: number
  handler?: string | null
}

export interface Cluster { id: string; lane: Lane; kind: string; label: string; component: string | null; reason: GapReason | null; size: number; gaps: number; nodes: string[] }

export interface TimelineTask { id: string; step: string | null; wave: number; title: string; state: string; waits: { task: string; why: 'prerequisite' | 'same_file'; detail?: string }[]; more: number }
export interface Timeline {
  plan: string
  waves: { wave: number; tasks: number; steps: { step: string | null; tasks: number }[] }[]
  steps: { id: string; title: string; name?: string; tasks: number; first: number | null; last: number | null }[]
  tasks: TimelineTask[]
  counts: Record<string, Measure>
}

export interface PathsData {
  lanes: Lane[]
  paths: CodePath[]
  nodes: PathNode[]
  edges: PathEdge[]
  components: Record<string, { op: PathOp; target: string | null; layer?: string | null }>
  new: string[]
  overview: { clusters: Cluster[]; links: { from: string; to: string; n: number }[]; columns: string[][]; level: number; all: boolean }
  counts: Record<string, Measure>
  src: Record<string, string>
  timeline: Timeline | null
}

export type PathsState = { kind: 'loading' } | { kind: 'ready'; paths: PathsData } | { kind: 'absent' }

declare global {
  interface Window { EAOS_STUDIO?: Record<string, unknown> }
}

/** The paths section, loaded on demand from paths.js beside the Studio (like every section: a classic script). */
export function usePaths(data: StudioData): PathsState {
  const listed = data.manifest.sections.some((s) => (s.name as string) === 'paths')
  const preset = () => (window.EAOS_STUDIO?.paths as PathsData | undefined)
  const [state, setState] = useState<PathsState>(() => !listed ? { kind: 'absent' } : preset() ? { kind: 'ready', paths: preset()! } : { kind: 'loading' })
  useEffect(() => {
    if (state.kind !== 'loading') return
    let live = true
    script('paths').then(() => {
      if (!live) return
      const loaded = preset()
      setState(loaded ? { kind: 'ready', paths: loaded } : { kind: 'absent' })
    })
    return () => { live = false }
  }, [state.kind])
  return state
}

export interface Index {
  node: Map<string, PathNode>
  path: Map<string, CodePath>
  /** The paths each node is on, by id */
  on: Map<string, string[]>
}

export function indexOf(data: PathsData): Index {
  const on = new Map<string, string[]>()
  for (const p of data.paths) for (const column of p.columns) for (const id of column) on.set(id, [...(on.get(id) ?? []), p.id])
  return { node: new Map(data.nodes.map((n) => [n.id, n])), path: new Map(data.paths.map((p) => [p.id, p])), on }
}

/** The operation the part owning a node takes toward the target, or null (a gap, or a node no part owns). */
export function opOf(data: PathsData, node: PathNode | undefined): PathOp | null {
  return node?.component ? data.components[node.component]?.op ?? null : null
}

export function targetOf(data: PathsData, node: PathNode | undefined): { target: string | null; layer: string | null } | null {
  const part = node?.component ? data.components[node.component] : undefined
  return part ? { target: part.target, layer: part.layer ?? null } : null
}

/** The links a path walks, in order, with their index. */
export function walk(data: PathsData, path: CodePath): (PathEdge & { index: number })[] {
  return path.steps.map((index) => ({ ...data.edges[index], index }))
}

/** The nodes and links of a path the flow does not confirm: reached only through imports (`imports` links), so
 * they are possible, not traced. The rest is reached from the entry through traced or declared links. */
export function possible(data: PathsData, path: CodePath): { nodes: Set<string>; edges: Set<number> } {
  const out = new Map<string, number[]>()
  for (const index of path.steps) {
    const e = data.edges[index]
    if (e.how !== 'imports') out.set(e.from, [...(out.get(e.from) ?? []), index])
  }
  const sure = new Set([path.entry])
  const queue = [path.entry]
  while (queue.length) {
    const id = queue.shift()!
    for (const index of out.get(id) ?? []) {
      const to = data.edges[index].to
      if (!sure.has(to)) { sure.add(to); queue.push(to) }
    }
  }
  const nodes = new Set(path.columns.flat().filter((id) => !sure.has(id)))
  const edges = new Set(path.steps.filter((i) => nodes.has(data.edges[i].to) || data.edges[i].how === 'imports'))
  return { nodes, edges }
}

// ---------------------------------------------------------------- geometry

export const NODE_W = 150
export const NODE_H = 44
const LANE_W = 168
const EMPTY_W = 48
const ROW = 54
const HEAD = 44
const PAD = 14

export interface Placed { x: number; y: number }
export interface Geometry {
  at: Map<string, Placed>
  lanes: { lane: Lane; x: number; w: number; count: number }[]
  width: number
  height: number
}

/** Places EAOS's columns: each lane a band (narrow when empty), each column centred on the tallest. The drawing's
 * geometry is the same in Arabic and English: lanes run from the screen to the data, like the map's geometry. */
export function geometry(columns: string[][]): Geometry {
  const tallest = Math.max(1, ...columns.map((c) => c.length))
  const height = HEAD + PAD * 2 + tallest * ROW - (ROW - NODE_H)
  const at = new Map<string, Placed>()
  const lanes: Geometry['lanes'] = []
  let x = 0
  LANES.forEach((lane, i) => {
    const column = columns[i] ?? []
    const w = column.length ? LANE_W : EMPTY_W
    const top = HEAD + PAD + ((tallest - column.length) * ROW) / 2
    column.forEach((id, row) => at.set(id, { x: x + (w - NODE_W) / 2, y: top + row * ROW }))
    lanes.push({ lane, x, w, count: column.length })
    x += w
  })
  return { at, lanes, width: x, height }
}

/** A link's curve from the end of one box to the start of the next (the next lane, or further on). */
export function curve(a: Placed, b: Placed): string {
  const x1 = a.x + NODE_W
  const y1 = a.y + NODE_H / 2
  const x2 = b.x
  const y2 = b.y + NODE_H / 2
  if (x2 <= x1) {
    // the same lane (a gap beside its node): a short hook below
    const xm = Math.max(x1, b.x + NODE_W) + 18
    return `M${x1},${y1} C${xm},${y1} ${xm},${y2} ${b.x + NODE_W},${y2}`
  }
  const mid = (x1 + x2) / 2
  return `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`
}

// ---------------------------------------------------------------- the sequence and the steps

export type Participant = 'actor' | Lane

export interface Message {
  n: number
  from: Participant
  to: Participant
  fromNode: string | null
  toNode: string
  how: How | 'opens'
  edge: number | null
  gap: boolean
}

/** The path as an ordered sequence: the person (or the outside caller) starts it, then each link EAOS walked, in its
 * order. The participants are the lanes the path crosses. */
export function sequence(data: PathsData, path: CodePath, index: Index): { participants: Participant[]; messages: Message[] } {
  const entry = index.node.get(path.entry)
  const messages: Message[] = []
  if (entry) messages.push({ n: 1, from: 'actor', to: entry.lane, fromNode: null, toNode: entry.id, how: 'opens', edge: null, gap: false })
  for (const e of walk(data, path)) {
    const a = index.node.get(e.from)
    const b = index.node.get(e.to)
    if (!a || !b) continue
    messages.push({ n: messages.length + 1, from: a.lane, to: b.lane, fromNode: a.id, toNode: b.id, how: e.how, edge: e.index, gap: b.kind === 'gap' })
  }
  const crossed = new Set<Participant>(messages.flatMap((m) => [m.from, m.to]))
  return { participants: (['actor', ...LANES] as Participant[]).filter((p) => crossed.has(p)), messages }
}

/** "src/pages/DriversPage.tsx:150", or the file alone, or null. */
export function where(path: string | null, line: number | null): string | null {
  return path ? (line ? `${path}:${line}` : path) : null
}

/** The paths that pass through a file or a part, for links from a card, a component or a function. */
export function pathsThrough(data: PathsData, index: Index, { file, part }: { file?: string; part?: string }): CodePath[] {
  const hits = new Set<string>()
  for (const n of data.nodes) {
    if ((file && n.path === file) || (part && n.component === part)) for (const p of index.on.get(n.id) ?? []) hits.add(p)
  }
  return data.paths.filter((p) => hits.has(p.id))
}
