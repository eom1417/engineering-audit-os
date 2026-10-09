import { describe, expect, it } from 'vitest'
import { asIdeal, counts, differenceOf, viewOf, type View } from './model'

const view: View = {
  provenance: { method: 'planned', state: 'planned', assistant: 'Claude Code', model: 'm', at: '2026-10-09', confidence: 0.7,
    message: { en: 'e', ar: 'a' }, departures: [], open_questions: [] },
  rules: { summary: 'r', count: { value: 3 }, elements: [
    { id: 'A', kind: 'component', title: 'a', operation: 'retain', subject: null, detail: '', cites: [] },
    { id: 'B', kind: 'component', title: 'b', operation: 'refactor', subject: null, detail: '', cites: [] },
    { id: 'C', kind: 'component', title: 'c', operation: 'delete', subject: null, detail: '', cites: [] }] },
  planned: { summary: 'p', confidence: 0.7, count: { value: 3 }, elements: [
    { id: 'p1', kind: 'component', title: 'a', operation: 'retain', subject: 'A', detail: '', cites: ['FACT-1'] },
    { id: 'p2', kind: 'component', title: 'b', operation: 'rebuild', subject: 'B', detail: '', cites: ['FACT-2'] },
    { id: 'p3', kind: 'component', title: 'n', operation: 'new', subject: null, detail: '', cites: ['TASK-1'] }] },
  differences: [
    { element: 'p1', kind: 'same', subject: 'A', rules: 'retain', planned: 'retain' },
    { element: 'p2', kind: 'changed', subject: 'B', rules: 'refactor', planned: 'rebuild' },
    { element: 'p3', kind: 'added', subject: null, rules: null, planned: 'new' }],
}

describe('the planned ideal model', () => {
  it('counts same, changed, added and what only the rules hold', () => {
    expect(counts(view)).toEqual({ same: 1, changed: 1, added: 1, rulesOnly: 1 })
  })
  it('finds an element\'s difference and keeps an unknown view on system', () => {
    expect(differenceOf(view, view.planned!.elements[1])?.rules).toBe('refactor')
    expect(viewOf('pipeline')).toBe('pipeline')
    expect(viewOf('nope')).toBe('system')
    expect(viewOf(undefined)).toBe('system')
  })
  it('refuses a body that is not the section', () => {
    expect(asIdeal(undefined)).toBeNull()
    expect(asIdeal({ views: {} })).toBeNull()
  })
})
