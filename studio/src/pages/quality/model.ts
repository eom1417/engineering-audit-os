// studio/quality.json (contract v2, eaos/studio/quality.py): how far EAOS's own analysis of this project can be trusted:
// each detector's precision and recall on EAOS's labelled set and whether it meets the bar the product shows it at, what
// it produced in this report, and the plan's indicators that judge the analysis. Nothing is computed here but counts.
import type { Measure } from '../../data/types'
import type { StudioData } from '../../data/types'

export type Status = 'meets_bar' | 'below_bar' | 'not_measured'

export interface Detector {
  id: string
  name: string
  names?: { ar: string; en: string }
  applies: boolean
  precision: Measure
  recall: Measure
  labelled?: number | null
  shown?: boolean
  status?: Status
  why?: string
  judged?: number
  here?: { shown: number; withheld: number; facts: number }
  project?: { tp: number; fp: number; unjudged: number } | null
}
export interface Capability { id: string; name: string; names?: { ar: string; en: string }; value: Measure; measured?: number; indicators?: number }
export interface Indicator { id: string; name: string; names?: { ar: string; en: string }; value: Measure; target: number; capability?: string; how?: 'automated' | 'recorded' }
export interface QualityData {
  detectors: Detector[]
  capabilities: Capability[]
  indicators: Indicator[]
  bar?: { precision?: number; recall?: number; judged?: number }
  labelled?: { items?: number | null; projects?: string[]; this_project?: string | null }
  counts?: Record<string, Measure>
  measured_at?: string | null
}

export function qualityOf(data: StudioData): QualityData | undefined {
  return data.quality as QualityData | undefined
}

export function statusOf(d: Detector): Status {
  return d.status ?? (d.precision.value === null ? 'not_measured' : d.shown ? 'meets_bar' : 'below_bar')
}

/** The detectors that produced something in this report, the ones the product shows first, then by how much they produced. */
export function active(detectors: Detector[]): Detector[] {
  const rank: Record<Status, number> = { meets_bar: 0, below_bar: 1, not_measured: 2 }
  const size = (d: Detector) => (d.here?.shown ?? 0) + (d.here?.withheld ?? 0) + (d.here?.facts ?? 0)
  return detectors.filter((d) => d.applies).sort((a, b) => rank[statusOf(a)] - rank[statusOf(b)] || size(b) - size(a) || a.name.localeCompare(b.name))
}

export function idle(detectors: Detector[]): Detector[] {
  return detectors.filter((d) => !d.applies).sort((a, b) => a.name.localeCompare(b.name))
}

export interface Tally { shown: number; withheld: number; facts: number; meeting: number; under: number; unmeasured: number }

export function tally(detectors: Detector[]): Tally {
  const here = detectors.filter((d) => d.applies)
  return {
    shown: here.reduce((n, d) => n + (d.here?.shown ?? 0), 0),
    withheld: here.reduce((n, d) => n + (d.here?.withheld ?? 0), 0),
    facts: here.reduce((n, d) => n + (d.here?.facts ?? 0), 0),
    meeting: here.filter((d) => statusOf(d) === 'meets_bar').length,
    under: here.filter((d) => statusOf(d) === 'below_bar').length,
    unmeasured: here.filter((d) => statusOf(d) === 'not_measured').length,
  }
}

/** The "not measured yet" states this page shows: detectors here with no measure, and indicators with no value. */
export function notMeasured(q: QualityData): number {
  return q.detectors.filter((d) => d.applies && statusOf(d) === 'not_measured').length + q.indicators.filter((i) => i.value.value === null).length
}

export function byCapability(q: QualityData): { capability: Capability; indicators: Indicator[] }[] {
  return q.capabilities.map((capability) => ({ capability, indicators: q.indicators.filter((i) => i.capability === capability.id) }))
}

/** A name in the person's language when the data carries both, else as the report wrote it. */
export function nameIn(row: { name: string; names?: { ar: string; en: string } }, lang: 'ar' | 'en'): string {
  return row.names?.[lang] ?? row.name
}
