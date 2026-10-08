import { describe, expect, it } from 'vitest'
import type { Journeys, Screen } from '../../../data/journeys'
import { byDepth, captions, clip, litSet, pathEdges, shownEdges, shownScreens, stepsOf } from './model'

const screen = (id: string, col: number, row: number, depth: number | null, extra: Partial<Screen> = {}): Screen => ({
  id, route: id, title: id, kind: 'page', file: null, router: 'src/App.tsx', fact: null, op: null, decided: false, flags: [],
  col, row, x: col * 212, y: row * 84, depth, ...extra,
})

const J: Journeys = {
  counts: {} as Journeys['counts'], src: {},
  grid: { cols: 4, rows: 2, col_w: 212, row_h: 84, box_w: 168, box_h: 60, pad: 24, width: 900, height: 200 },
  starts: ['/'],
  screens: [screen('/', 0, 0, 0), screen('/app', 1, 0, 1), screen('/app/x', 2, 0, 2), screen('/lost', 3, 0, null, { flags: ['no_way_in'] }),
    screen('/app/*', 3, 1, null, { kind: 'layout' })],
  menus: [],
  edges: [
    { from: '/', to: '/app', via: 'redirect', evidence: [{ file: 'src/App.tsx', line: 9, via: 'redirect' }], count: 1, d: 'M0,0' },
    { from: '/app', to: '/app/x', via: 'link', evidence: [{ file: 'src/A.tsx', line: 3, via: 'link' }], count: 1, d: 'M0,0' },
    { from: '/app/*', to: '/app', via: 'link', evidence: [], count: 0, d: 'M0,0' },
  ],
  broken: [], tasks: [], missing: [],
}

describe('journeys model', () => {
  it('shows hidden routes and their links only with the lens on', () => {
    expect(shownScreens(J, false).map((s) => s.id)).not.toContain('/app/*')
    expect(shownEdges(J, false)).toHaveLength(2)
    expect(shownEdges(J, true)).toHaveLength(3)
  })
  it('captions each column by clicks from the start, and the unreached last', () => {
    expect(captions(J).map((c) => [c.kind, c.n])).toEqual([['start', 0], ['clicks', 1], ['clicks', 2], ['none', 0]])
  })
  it('walks a task path with the evidence of each link', () => {
    const task = { id: 't', name: { ar: 'م', en: 'T' }, kind: 'route' as const, screen: '/app/x', path: ['/', '/app', '/app/x'], dead: false, src: 'route' }
    expect([...pathEdges(task)]).toEqual(['/>/app', '/app>/app/x'])
    expect(stepsOf(J, task).map((s) => s.via?.evidence[0]?.line ?? null)).toEqual([null, 9, 3])
    expect([...litSet(J, undefined, task)!].sort()).toEqual(['/', '/app', '/app/x'])
  })
  it('groups pages by distance, the unreached last, and lights a flag', () => {
    expect(byDepth(J).map((g) => g.depth)).toEqual([0, 1, 2, null])
    expect([...litSet(J, undefined, undefined, 'no_way_in')!]).toEqual(['/lost'])
  })
  it('clips a long identifier from the start', () => {
    expect(clip('src/pages/settings/tabs/AccountTab', 12)).toBe('…/AccountTab')
  })
})
