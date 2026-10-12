import { describe, expect, it } from 'vitest'
import { geometry, indexOf, opOf, pathsThrough, possible, sequence, type PathsData } from './model'
import { PATHS_FIXTURE } from './fixture'

const data = PATHS_FIXTURE as PathsData
const orders = data.paths.find((p) => p.id === 'orders-orderspage')!

describe('the code paths model', () => {
  it('places every node once in its lane and orders the sequence as EAOS walked it', () => {
    const g = geometry(orders.columns)
    expect(g.at.size).toBe(orders.columns.flat().length)
    const lane = (id: string) => g.lanes.find((l) => g.at.get(id)!.x >= l.x && g.at.get(id)!.x < l.x + l.w)!.lane
    for (const n of data.nodes.filter((n) => g.at.has(n.id))) expect(lane(n.id)).toBe(n.lane)
    const empty = geometry([['a'], [], [], [], [], [], []])
    expect(empty.lanes[1].w).toBeLessThan(empty.lanes[0].w)
    const index = indexOf(data)
    const { participants, messages } = sequence(data, orders, index)
    expect(participants[0]).toBe('actor')
    expect(messages[0]).toMatchObject({ from: 'actor', to: 'screen', how: 'opens' })
    expect(messages.slice(1).map((m) => m.edge)).toEqual(orders.steps)
    expect(messages.find((m) => m.toNode === 'G:endpoint:POST /api/audit')?.gap).toBe(true)
  })

  it("tells import links from traced ones, reads a node's operation and finds paths through a file", () => {
    const maybe = possible(data, orders)
    expect(maybe.nodes.has('H:src/api/orders.ts#fetchOrders')).toBe(false)   // the flow reaches it: traced
    const about = data.paths.find((p) => p.id === 'about-aboutpage')!
    expect(possible(data, about).nodes.size).toBe(0)
    const index = indexOf(data)
    expect(opOf(data, index.node.get('C:src/pages/OrdersPage.tsx'))).toBe('rebuild')
    expect(opOf(data, index.node.get('G:endpoint:POST /api/audit'))).toBeNull()
    const index2 = indexOf(data)
    expect(pathsThrough(data, index2, { file: 'src/api/orders.ts' }).map((p) => p.id)).toEqual(['orders-orderspage'])
    expect(pathsThrough(data, index2, { part: 'server/routes' }).map((p) => p.id).sort()).toEqual(['api-orders-listorders', 'orders-orderspage'])
  })
})
