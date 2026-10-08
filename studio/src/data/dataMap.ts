// studio/data_paths.json and studio/infra.json (contract v2, schemas/artifacts/studio-{data_paths,infra}.schema.json):
// the data paths map and the infrastructure lens, laid out by EAOS (eaos/studio/data_paths.py, infra.py).
import type { Measure } from './measure'

export interface Site { path: string; line: number | null; fact: string | null }

export type Tier = 'field' | 'form' | 'key' | 'caller' | 'endpoint' | 'handler' | 'column'
export const TIERS: Tier[] = ['field', 'form', 'key', 'caller', 'endpoint', 'handler', 'column']

export interface TierRow {
  id: Tier
  state: 'measured' | 'empty' | 'partial' | 'not_measured'
  known: Measure
  gaps: { reason: string; paths: number; step: string }[]
}

export type StoreKind = 'table' | 'resource' | 'bucket' | 'rpc' | 'auth'
export type StoreChange = 'single_already' | 'merged_in_target' | 'still_multiple'

export interface Store {
  id: string
  kind: StoreKind
  name: string
  client: string | null
  declared: (Site & { rls?: boolean | null }) | null
  endpoints: string[]
  sites: number
  writers: string[]
  readers: string[]
  multi_writer: boolean
  today: { writers: number; components: string[] }
  target: { components: string[]; single: boolean | null; unmapped: string[] } | null
  change: StoreChange | null
}

export interface Endpoint {
  id: string
  label: string
  store: string
  operation: string
  method: string | null
  writers: string[]
  readers: string[]
  keys: string[] | null
  multi_writer: boolean
  sites: Site[]
}

export interface Step {
  state: 'known' | 'gap' | 'direct'
  reason?: string
  keys?: string[]
  partial?: boolean
  component?: string | null
  handler?: string | null
  path?: string
  line?: number | null
  columns?: string[] | null
  stores?: string[]
}

export interface WritePath { store: string; endpoint: string; site: Site; steps: Record<Tier, Step> }

export interface DataView {
  lanes: { caller: string[]; store: string[] }
  place: Record<string, [number, number]>
  size: [number, number]
  box: [number, number]
  edges: { from: string; to: string; kind: 'write' | 'read'; modules: number }[]
  clusters: { id: string; lane: 'caller' | 'store'; members: string[] }[]
}

export interface DataPaths {
  counts: Record<string, Measure>
  tiers: TierRow[]
  stores: Store[]
  endpoints: Endpoint[]
  paths: WritePath[]
  violations: { id: string; subject: string; kind: 'endpoint' | 'table'; tier: string; writers: string[] }[]
  current: DataView
  target: DataView | null
  src: Record<string, string>
}

export type Lane = 'hosting' | 'ci' | 'environments' | 'databases' | 'queues' | 'services' | 'observability'
export const LANES: Lane[] = ['hosting', 'ci', 'environments', 'databases', 'queues', 'services', 'observability']

export interface InfraNode {
  id: string
  lane: Lane
  name: string
  kind: string
  detail: Record<string, number | boolean | null>
  items: string[]
  sites: Site[]
  evidence: number
}

export interface TargetItem { area: string; present: boolean; op: 'keep' | 'introduce'; decision: string; tool: string | null; evidence: string }

export interface Infra {
  app: { reference: string | null; src: string }
  lanes: { id: Lane; relation: string; state: 'measured' | 'empty'; reason: string; count: Measure; nodes: InfraNode[]; folded: InfraNode[] }[]
  counts: Record<string, Measure>
  target: { reference: string | null; status: string | null; lanes: { id: Lane; state: 'measured' | 'not_measured'; reason: string; items: TargetItem[] }[] } | null
  src: Record<string, string>
}
