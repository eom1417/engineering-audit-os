import { describe, expect, it } from 'vitest'
import type { Infra } from '../../data/dataMap'
import fixture from '../data/fixture.json'
import { find, MAX_ROWS, modeOf, rowsOf } from './model'

const infra = (fixture as unknown as { infra: Infra }).infra

describe('the infrastructure lens model', () => {
  it('shows today without a target, whatever the view asks', () => {
    expect(modeOf('target', infra)).toBe('target')
    expect(modeOf('target', { ...infra, target: null })).toBe('current')
  })

  it('draws today’s items, the target’s decisions, or today’s items with what the target adds', () => {
    expect(rowsOf(infra, 'hosting', 'current').map((r) => r.kind)).toEqual(['node'])
    expect(rowsOf(infra, 'hosting', 'target').map((r) => (r.kind === 'item' ? r.item.op : r.kind))).toEqual(['keep'])
    const change = rowsOf(infra, 'observability', 'change')
    expect(change.filter((r) => r.kind === 'item').map((r) => (r.kind === 'item' ? r.item.area : ''))).toEqual(['observability'])
    expect(rowsOf(infra, 'queues', 'target')).toEqual([])
  })

  it('folds a crowded lane into its last row', () => {
    const many = { ...infra, lanes: infra.lanes.map((l) => l.id === 'services'
      ? { ...l, nodes: Array.from({ length: 12 }, (_, i) => ({ ...l.nodes[0], id: `svc:${i}`, name: `h${i}` })), folded: [] } : l) }
    const rows = rowsOf(many, 'services', 'current')
    expect(rows.length).toBe(MAX_ROWS)
    expect(rows[MAX_ROWS - 1]).toEqual({ kind: 'more', more: 12 - MAX_ROWS + 1 })
  })

  it('finds a node or a target item by the id the map gives it', () => {
    expect(find(infra, 'host:Vercel')?.lane).toBe('hosting')
    expect(find(infra, 'target:observability:observability')?.item?.op).toBe('introduce')
    expect(find(infra, 'nothing')).toBeNull()
  })
})
