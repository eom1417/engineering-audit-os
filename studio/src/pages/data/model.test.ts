import { describe, expect, it } from 'vitest'
import type { DataPaths, Store } from '../../data/dataMap'
import { labelOf, membersOf, modeOf, nodeOf, ranked, tierCounts, toneOf, viewOf } from './model'
import fixture from './fixture.json'

const dp = (fixture as unknown as { data_paths: DataPaths }).data_paths
const byId = new Map(dp.stores.map((s) => [s.id, s]))

describe('the data paths model', () => {
  it('falls back to today when the report has no target', () => {
    expect(modeOf('target', dp)).toBe('target')
    expect(modeOf('target', { ...dp, target: null })).toBe('current')
    expect(modeOf('nonsense', dp)).toBe('current')
  })

  it('keeps every store in its place between today and the target', () => {
    for (const id of viewOf(dp, 'current').lanes.store) expect(viewOf(dp, 'target').place[id]).toEqual(viewOf(dp, 'current').place[id])
  })

  it('colours a store by what the target does to its writers', () => {
    expect(toneOf(byId.get('table:stock'), 'change')).toBe('rebuild')
    expect(toneOf(byId.get('api:/notes'), 'change')).toBe('keep')
    expect(toneOf(byId.get('table:audit_log'), 'change')).toBe('none')
    expect(toneOf(byId.get('table:stock'), 'current')).toBe('rebuild')
  })

  it('lists stores written from several places first', () => {
    const order = ranked(dp.stores).map((s: Store) => s.id)
    expect(order.slice(0, 2).sort()).toEqual(['api:/orders', 'table:stock'])
    expect(order[order.length - 1]).toBe('table:audit_log')
  })

  it('counts the writes that reach each tier and those that stop', () => {
    expect(tierCounts(dp.paths, 'caller')).toEqual({ known: dp.paths.length, gaps: 0 })
    expect(tierCounts(dp.paths, 'field')).toEqual({ known: 0, gaps: dp.paths.length })
  })

  it('opens a cluster into its members and finds the cluster of a member', () => {
    const view = { ...dp.current, clusters: [{ id: 'cluster:table:s', lane: 'store' as const, members: ['table:stock'] }] }
    expect(membersOf(view, 'cluster:table:s')).toEqual(['table:stock'])
    expect(nodeOf(view, 'table:stock')).toBe('cluster:table:s')
    expect(labelOf('table:stock', byId)).toBe('stock')
  })
})
