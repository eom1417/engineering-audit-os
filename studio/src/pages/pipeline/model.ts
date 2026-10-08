// studio/pipeline.json (contract v2, schemas/artifacts/studio-pipeline.schema.json): the pipeline map EAOS found
// (eaos/studio/pipeline.py), its stages laid out by EAOS (each stage's `layer` and `order`). This file reads it: the
// section is loaded only when the pipeline page opens, and the drawing's geometry turns EAOS's layer and order into
// places. Nothing here computes a number the exporter did not write, and no link is added that the data does not hold.
import { useEffect, useState } from 'react'
import { script } from '../../data/load'
import type { Measure, StudioData } from '../../data/types'

export interface Site { path: string | null; line: number | null; fact?: string | null; text?: string | null }
export type StageKind = 'stage' | 'router' | 'fork' | 'join' | 'ai' | 'source' | 'sink' | 'external'
export type Op = 'retain' | 'refactor' | 'rebuild' | 'merge' | 'delete' | 'new'
export type Mark = 'slow' | 'risky' | 'ai' | 'external'
export interface Port { name: string; kind: string; shape?: string | null }

export interface Stage {
  id: string
  pipeline: string
  label: string
  kind: StageKind
  entry: Site
  symbol?: string | null
  tools: string[]
  inputs: Port[]
  outputs: Port[]
  side_effects: (Site & { kind: string; name: string })[]
  optional?: boolean
  marks?: Mark[]
  sub_pipeline?: string | null
  coverage: string
  layer: number
  order: number
  cards: string[]
  steps: string[]
}

export interface Edge {
  id: string
  pipeline: string
  from: string
  to: string
  kind: 'data' | 'control' | 'error' | 'hidden'
  data: { names: string[]; shape: string | null }
  matched_by: string
  condition?: string | null
  evidence: Site
}

export interface Router {
  id: string
  pipeline: string
  stage: string
  kind: string
  on: string
  entry: Site
  branches: { condition: string; to: string | null; evidence: Site }[]
  total: boolean | null
  default?: string | null
  unhandled: string[]
}

export interface Fan { id: string; pipeline: string; fork: string; join: string | null; branches: string[]; matched: boolean; kind: string; evidence: Site }
export interface Control { id: string; pipeline: string; stage: string; kind: string; condition?: string | null; evidence: Site }
export interface ErrorLane { id: string; pipeline: string; from: string; to: string; kind: string; condition?: string | null; evidence: Site }
export interface Hidden { id: string; pipeline: string; kind: 'side_channel' | 'dead_stage' | 'unread_output'; channel?: string | null; name: string; stages: string[]; evidence: Site }
export interface Unresolved { id: string; pipeline: string; stage: string; call: string; reason: string; evidence: Site }
export interface Rule { id: string; title: string; why: string; source: string; broken: number }
export interface Pipeline {
  id: string
  title: string
  kind: string
  role: 'product' | 'tooling'
  confidence: number
  entry: Site
  evidence: Site[]
  parent: string | null
  stages: string[]
  counts?: Record<string, number>
}
export interface IdealStage { id: string; op: Op; label: string; pipeline: string; why?: string | null; rule?: string | null; contract?: { inputs: string[]; outputs: string[] }; marks?: Mark[] }
export interface IdealEdge { from: string; to: string; op: Op; pipeline: string; rule?: string | null }
export interface GapEntry {
  id: string
  rule: string
  pipeline: string
  subject: string
  subject_kind: 'pipeline' | 'stage' | 'edge' | 'router' | 'fan' | 'hidden' | 'unresolved'
  operation: Op
  detail: string
  evidence: Site
  card: string | null
  step: string | null
}

export interface PipelineData {
  detected: boolean
  confidence: { value: number | null; src: string }
  verdict: string
  kinds: string[]
  evidence: Site[]
  looked_for: { kind: string; label: string; found: number; how: string }[]
  pipelines: Pipeline[]
  stages: Stage[]
  edges: Edge[]
  routers: Router[]
  fans: Fan[]
  control: Control[]
  error_lanes: ErrorLane[]
  hidden: Hidden[]
  unresolved: Unresolved[]
  rules: Rule[]
  views: { current: { stages: string[]; edges: string[] }; ideal: { stages: IdealStage[]; edges: IdealEdge[]; made_by: string }; gap: GapEntry[] }
  counts: Record<string, Measure>
  src: Record<string, string>
}

export type PipelineState = { kind: 'loading' } | { kind: 'ready'; pipeline: PipelineData } | { kind: 'absent' }

/** The pipeline section, loaded on demand from pipeline.js beside the Studio (like every section: a classic script). */
export function usePipeline(data: StudioData): PipelineState {
  const listed = data.manifest.sections.some((s) => (s.name as string) === 'pipeline')
  const preset = () => (window.EAOS_STUDIO?.pipeline as PipelineData | undefined)
  const [state, setState] = useState<PipelineState>(() => !listed ? { kind: 'absent' } : preset() ? { kind: 'ready', pipeline: preset()! } : { kind: 'loading' })
  useEffect(() => {
    if (state.kind !== 'loading') return
    let live = true
    script('pipeline').then(() => {
      if (!live) return
      const loaded = preset()
      setState(loaded ? { kind: 'ready', pipeline: loaded } : { kind: 'absent' })
    })
    return () => { live = false }
  }, [state.kind])
  return state
}

export type View = 'current' | 'ideal' | 'gap'
export const VIEWS: View[] = ['current', 'ideal', 'gap']

/** One pipeline of the section, everything that belongs to it, looked up by id. */
export interface Scope {
  pipeline: Pipeline
  stages: Stage[]
  stage: Map<string, Stage>
  edges: Edge[]
  routers: Router[]
  routerOf: Map<string, Router>
  fans: Fan[]
  control: Control[]
  errors: ErrorLane[]
  hidden: Hidden[]
  unresolved: Unresolved[]
  ideal: Map<string, IdealStage>
  idealEdges: IdealEdge[]
  /** The ideal's stages that have no place today (the ideal adds them; EAOS lays out only what exists) */
  added: IdealStage[]
  gap: GapEntry[]
}

export function scopeOf(data: PipelineData, id: string): Scope | null {
  const pipeline = data.pipelines.find((p) => p.id === id)
  if (!pipeline) return null
  const mine = <T extends { pipeline: string }>(rows: T[]) => rows.filter((r) => r.pipeline === id)
  const stages = mine(data.stages)
  const stage = new Map(stages.map((s) => [s.id, s]))
  const routers = mine(data.routers)
  const ideal = mine(data.views.ideal.stages)
  return {
    pipeline, stages, stage, edges: mine(data.edges), routers, routerOf: new Map(routers.map((r) => [r.stage, r])), fans: mine(data.fans),
    control: mine(data.control), errors: mine(data.error_lanes), hidden: mine(data.hidden), unresolved: mine(data.unresolved),
    ideal: new Map(ideal.map((s) => [s.id, s])), idealEdges: mine(data.views.ideal.edges), added: ideal.filter((s) => !stage.has(s.id)),
    gap: mine(data.views.gap),
  }
}

/** The pipeline shown first: the first product pipeline at the top, else the first one. */
export function firstPipeline(data: PipelineData): string | undefined {
  return (data.pipelines.find((p) => !p.parent && p.role === 'product') ?? data.pipelines.find((p) => !p.parent) ?? data.pipelines[0])?.id
}

/** The pipeline's ancestors, outermost first, for the breadcrumb. */
export function trail(data: PipelineData, id: string): Pipeline[] {
  const out: Pipeline[] = []
  let at = data.pipelines.find((p) => p.id === id)
  const seen = new Set<string>()
  while (at && !seen.has(at.id)) {
    seen.add(at.id)
    out.unshift(at)
    const parent = at.parent ? data.stages.find((s) => s.id === at!.parent) : undefined
    at = parent ? data.pipelines.find((p) => p.id === parent.pipeline) : undefined
  }
  return out
}

/** The stages in EAOS's reading order: by layer, then by order in the layer. */
export function ordered(stages: Stage[]): Stage[] {
  return [...stages].sort((a, b) => a.layer - b.layer || a.order - b.order)
}

/** Follow the data: the stages producing `name` and everything their edges reach downstream, with the edges walked.
 * A name no stage writes starts from the stages reading it. */
export function follow(scope: Scope, name: string): { stages: Set<string>; edges: Set<string> } {
  const starts = scope.stages.filter((s) => s.outputs.some((o) => o.name === name)).map((s) => s.id)
  const from = starts.length ? starts : scope.stages.filter((s) => s.inputs.some((i) => i.name === name)).map((s) => s.id)
  const out = new Map<string, Edge[]>()
  for (const e of scope.edges) if (e.kind !== 'hidden') out.set(e.from, [...(out.get(e.from) ?? []), e])
  const stages = new Set(from)
  const edges = new Set<string>()
  const queue = [...from]
  while (queue.length) {
    const id = queue.shift()!
    for (const e of out.get(id) ?? []) {
      edges.add(e.id)
      if (!stages.has(e.to)) { stages.add(e.to); queue.push(e.to) }
    }
  }
  return { stages, edges }
}

/** Every value the pipeline's stages give or take, named once, in reading order: what "Follow the data" offers. */
export function dataNames(scope: Scope): string[] {
  const seen = new Set<string>()
  for (const s of ordered(scope.stages)) for (const p of [...s.outputs, ...s.inputs]) seen.add(p.name)
  return [...seen]
}

/** "eaos/pipeline/run.py:35", or the file alone, or null. */
export function where(site: Site | null | undefined): string | null {
  return site?.path ? (site.line ? `${site.path}:${site.line}` : site.path) : null
}

/** The gap entries about one subject (a stage, a router's stage, a hidden channel, the pipeline). */
export function gapsAbout(scope: Scope, ids: string[]): GapEntry[] {
  const set = new Set(ids)
  return scope.gap.filter((g) => set.has(g.subject))
}

// ---------------------------------------------------------------- geometry

export const NODE_W = 156
export const NODE_H = 52
const STEP_X = 250        // one layer to the next along a left-to-right flow
const STEP_Y = 82         // one place to the next inside a layer
const DOWN_X = 184        // one place to the next on the phone's top-to-bottom flow
const DOWN_Y = 132        // one layer to the next on the phone
const PAD = 28
const LANE_GAP = 40
export const PILL_W = 140

export interface At { x: number; y: number }
export interface Geometry {
  at: Map<string, At>
  /** Along the flow: left to right on a wide screen, top to bottom on the phone */
  across: boolean
  width: number
  height: number
  /** The failure lane under the stages, when the pipeline has failure routes */
  lane: { x: number; y: number; w: number; h: number } | null
  /** Places of the failure lane's ends ("failed", "skipped"...) in the order the data names them */
  ends: Map<string, At>
}

/** Places EAOS's layers and orders. The geometry is the same in Arabic and English (the map's rule: geometry does not
 * mirror); on the phone the flow runs top to bottom. The failure lane's ends take the lane in the order the data lists
 * them: the only places drawn that EAOS does not write, because the contract gives an end no layer. */
export function geometry(stages: Stage[], errors: ErrorLane[], down: boolean): Geometry {
  const at = new Map<string, At>()
  let layers = 0
  let rows = 0
  for (const s of stages) {
    layers = Math.max(layers, s.layer + 1)
    rows = Math.max(rows, s.order + 1)
    at.set(s.id, down ? { x: PAD + s.order * DOWN_X, y: PAD + s.layer * DOWN_Y } : { x: PAD + s.layer * STEP_X, y: PAD + s.order * STEP_Y })
  }
  let width = PAD * 2 + NODE_W + Math.max(0, (down ? rows : layers) - 1) * (down ? DOWN_X : STEP_X)
  let height = PAD * 2 + NODE_H + Math.max(0, (down ? layers : rows) - 1) * (down ? DOWN_Y : STEP_Y)
  const ends = new Map<string, At>()
  let lane: Geometry['lane'] = null
  const names = [...new Set(errors.map((e) => e.to))]
  if (names.length) {
    // across: the lane's title on its start, the ends in a row after it; down: the title above the ends
    const first = down ? 12 : 168
    const top = down ? 34 : 12
    lane = { x: PAD, y: height + LANE_GAP / 2, w: Math.max(width - PAD * 2, first + names.length * (PILL_W + 28)), h: top + 66 }
    names.forEach((n, i) => ends.set(n, { x: lane!.x + first + i * (PILL_W + 28), y: lane!.y + top }))
    width = Math.max(width, lane.x + lane.w + PAD)
    height = lane.y + lane.h + PAD
  }
  return { at, across: !down, width, height, lane, ends }
}

/** The point where a link leaves a stage and where it enters the next one, along the flow. */
function ports(g: Geometry, a: At, b: At): [number, number, number, number] {
  if (g.across) return [a.x + NODE_W, a.y + NODE_H / 2, b.x, b.y + NODE_H / 2]
  return [a.x + NODE_W / 2, a.y + NODE_H, b.x + NODE_W / 2, b.y]
}

/** A link's curve and its middle (where the data's shape is written). A link going back, or inside one layer, bows
 * out of the way of the stages between. */
export function link(g: Geometry, a: At, b: At): { d: string; mx: number; my: number } {
  const [x1, y1, x2, y2] = ports(g, a, b)
  const forward = g.across ? x2 > x1 + 4 : y2 > y1 + 4
  if (forward) {
    if (g.across) {
      const m = (x1 + x2) / 2
      return { d: `M${x1},${y1} C${m},${y1} ${m},${y2} ${x2},${y2}`, mx: m, my: (y1 + y2) / 2 }
    }
    const m = (y1 + y2) / 2
    return { d: `M${x1},${y1} C${x1},${m} ${x2},${m} ${x2},${y2}`, mx: (x1 + x2) / 2, my: m }
  }
  // backwards or sideways: leave and enter from the far sides, bowing round
  if (g.across) {
    const bow = Math.max(a.y, b.y) + NODE_H + 22
    const sx = a.x + NODE_W / 2
    const ex = b.x + NODE_W / 2
    return { d: `M${sx},${a.y + NODE_H} C${sx},${bow} ${ex},${bow} ${ex},${b.y + NODE_H}`, mx: (sx + ex) / 2, my: bow - 6 }
  }
  const bow = Math.max(a.x, b.x) + NODE_W + 22
  const sy = a.y + NODE_H / 2
  const ey = b.y + NODE_H / 2
  return { d: `M${a.x + NODE_W},${sy} C${bow},${sy} ${bow},${ey} ${b.x + NODE_W},${ey}`, mx: bow - 6, my: (sy + ey) / 2 }
}

/** The window of the drawing first shown: the whole pipeline when it is small, its start when it is long (the person
 * pans along it; the stages outside the view are not drawn). */
export function frame(g: Geometry, phone: boolean): { w: number; h: number } {
  const most = phone ? { w: 560, h: 1100 } : { w: 2000, h: 1100 }
  return { w: Math.min(g.width, most.w), h: Math.min(g.height, most.h) }
}
