// Contract v1 (docs/STUDIO.md, schemas/artifacts/studio-*.schema.json): the fields the Studio reads today. Types
// generated from the schemas replace this file with contract v2 (NS39.T3).
import type { Gap, Operation } from './change'
import type { DataPaths, Infra } from './dataMap'
import type { Hidden, Journeys } from './journeys'
import type { Measure } from './measure'
import type { SystemMap } from './system'

export type { Measure } from './measure'

export interface Manifest {
  contract: number
  language?: 'ar' | 'en'
  locales?: { en?: { file: 'locale.js'; sha256: string } }
  built: { built: string; commit: string; digest: string; studio_digest?: string; version: string }
  project: { name: string }
  scanned: { at: string | null; branch: string | null; commit: string | null }
  sections: { name: SectionName; file: string; sha256: string; bytes: number }[]
}

export interface Meta {
  files: Measure
  lines: Measure
  languages: { name: string; files: number; share: number }[]
  stages: { id: string; state: string; title: string }[]
}

export type Freshness = 'fresh' | 'branch_moved' | 'eaos_updated' | 'unknown'

export interface Head {
  freshness: Freshness
  verdict: string
  next: { action: string; tool: string | null } | null
  scanned: { at: string | null; branch: string | null; commit: string | null }
  eaos: { version: string; commit: string; digest: string }
}

export interface Health {
  score: Measure
  formula: string
  domains: { id: string; name: string; cards: number; score: Measure }[]
  history: { at: string; commit: string | null; score: number | null }[]
}

export type Severity = 'critical' | 'high' | 'medium' | 'low'
export type CardState = 'open' | 'in_batch' | 'on_branch' | 'done' | 'resolved' | 'skipped'

export interface Card {
  id: string
  key: string
  title: string
  kind: string
  category: string
  severity: Severity
  state: CardState
  fixable: boolean
  needs_decision: boolean
  milestone: string | null
  paths: string[]
  evidence: string[]
  scope: 'place' | 'group'
  confidence: number
  /** Why it matters, in both languages (absent when the plan gives no impact) */
  why?: { ar: string; en: string }
}

/** The lines of code around a fact's place as the check read them; a line where a secret was found is empty and in `hidden`. */
export interface CodeExcerpt { start: number; line: number; lines: string[]; hidden: number[] }

export interface Fact {
  id: string; kind: string; engine: string | null; path: string | null; line: number | null; summary: string
  sites: { path: string; line?: number | null }[]
  /** Absent in older reports; null when there is no line, the file could not be read, or the fact is a secret */
  code?: CodeExcerpt | null
}

export type Relation = 'retain' | 'modify' | 'rebuild' | 'delete' | 'merge' | 'missing' | 'introduce'

export interface Story {
  current: { components: { name: string; files: number; layer: string }[] }
  target: { components: { name: string; layer: string; responsibility: string }[] }
  gap: { component: string; relation: Relation; to: string | null; files: number; cards: string[]; closed: number }[]
}

export interface Doc { id: string; title: string; group: string; order: number | null; path: string; bytes: number; headings?: { level: number; text: string }[] }

export interface PlanStep { id: string; state: string; title?: string; gate: string; tasks: { id: string; state: string; title: string }[] }
export interface Plan { id: string; kind: string; title?: string; state: string; progress: Measure; steps: PlanStep[] }

export interface Decision {
  id: string
  question: string
  recommendation: string
  options: { id: string; label: string }[]
  blocks: string[]
  state: 'waiting' | 'answered'
  answer: string | null
  tool: string | null
  plan: string | null
}

export const SECTIONS = ['meta', 'head', 'health', 'cards', 'evidence', 'story', 'docs', 'plans', 'decisions', 'media', 'system', 'paths', 'journeys', 'hidden', 'data_paths', 'infra', 'pipeline', 'gaps', 'operations', 'ideal', 'history', 'quality'] as const
export type SectionName = (typeof SECTIONS)[number]

export interface StudioData {
  manifest: Manifest
  meta?: Meta
  head?: Head
  health?: Health
  cards?: { cards: Card[] }
  evidence?: { facts: Fact[] }
  story?: Story
  docs?: { docs: Doc[] }
  plans?: { plans: Plan[] }
  decisions?: { decisions: Decision[] }
  media?: unknown
  system?: SystemMap
  journeys?: Journeys
  hidden?: Hidden
  data_paths?: DataPaths
  infra?: Infra
  /** studio/paths.json, typed by its pages (pages/paths/model.ts) */
  paths?: unknown
  /** studio/pipeline.json, typed by its page (pages/pipeline/model.ts) */
  pipeline?: unknown
  gaps?: { gaps: Gap[] }
  operations?: { operations: Operation[] }
  /** studio/ideal.json, typed by its page (pages/ideal/model.ts) */
  ideal?: unknown
  /** studio/history.json and studio/quality.json, typed by their pages (pages/history/model.ts, pages/quality/model.ts);
   * studio/library.json (the documents' text) is loaded only when the reader opens (pages/library/model.ts) */
  history?: unknown
  quality?: unknown
  /** Sections the manifest lists but whose file did not load */
  missing: SectionName[]
}
