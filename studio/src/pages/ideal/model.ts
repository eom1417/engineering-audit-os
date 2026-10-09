// The planned ideal against the rules' target (studio/ideal.json, contract studio-ideal, docs/STUDIO.md D10): the
// types of the section and the small derivations the page draws from.
import type { Relation } from '../../data/types'

export const VIEWS = ['system', 'change', 'journeys', 'paths', 'data_paths', 'infra', 'pipeline', 'plan_order'] as const
export type ViewName = (typeof VIEWS)[number]
export type Operation = 'retain' | 'refactor' | 'rebuild' | 'merge' | 'delete' | 'new'
type Words = { en: string; ar: string }

export interface Element {
  id: string; kind: string; title: string; operation: Operation; subject: string | null; detail: string; cites: string[]
}
export interface Departure { rule_says: string; plan_chose: string; because: string; element?: string | null; cites?: string[] }
export interface Question { id: string; question: string; recommendation?: string | null }
export interface Provenance {
  method: 'rules' | 'planned'; state: string; assistant: string | null; model: string | null; at: string | null
  confidence: number | null; message: Words; departures: Departure[]; open_questions: Question[]
}
export interface Difference { element: string; kind: 'same' | 'changed' | 'added'; subject: string | null; rules: Operation | null; planned: Operation }
export interface View {
  provenance: Provenance
  rules: { summary: string; elements: Element[]; count: { value: number } }
  planned: { summary: string; confidence: number | null; elements: Element[]; count: { value: number } } | null
  differences: Difference[]
}
export interface Ideal {
  state: 'planned' | 'not_planned' | 'stale' | 'failed'
  message: Words
  provenance: Provenance
  views: Record<ViewName, View>
  evidence: { share: { value: number | null }; elements: { value: number | null }; dropped: { view: string; id: string; title?: string; why: string }[] }
  questions: { id: string; view: string; question: string; options: string[]; recommendation?: string | null; why: string }[]
}

/** The ideal's operation as the Studio's operation chip names it. */
export const RELATION: Record<Operation, Relation> = {
  retain: 'retain', refactor: 'modify', rebuild: 'rebuild', merge: 'merge', delete: 'delete', new: 'introduce',
}

export function asIdeal(raw: unknown): Ideal | null {
  const body = raw as Ideal | undefined
  return body && typeof body === 'object' && body.views && body.message ? body : null
}

export function viewOf(name: string | undefined): ViewName {
  return (VIEWS as readonly string[]).includes(name ?? '') ? (name as ViewName) : 'system'
}

/** Same, changed and added among the planned elements, and the rules' elements the plan did not name. */
export function counts(view: View) {
  const named = new Set(view.differences.map((d) => d.subject).filter(Boolean))
  const of = (kind: Difference['kind']) => view.differences.filter((d) => d.kind === kind).length
  return { same: of('same'), changed: of('changed'), added: of('added'), rulesOnly: view.rules.elements.filter((e) => !named.has(e.id)).length }
}

/** The difference row of a planned element, by its id. */
export function differenceOf(view: View, element: Element): Difference | undefined {
  return view.differences.find((d) => d.element === element.id)
}
