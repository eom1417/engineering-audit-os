// What the journeys page computes from studio/journeys.json without inventing anything: the screens shown, the
// columns' captions, a task's path as edges and as steps, a screen's links in and out, and the screens by distance.
import type { JourneyEdge, Journeys, Screen, ScreenFlag, Task } from '../../../data/journeys'

export type JourneyMode = 'current' | 'change' | 'target'
export const JOURNEY_MODES: JourneyMode[] = ['current', 'change', 'target']
export const FLAGS: ScreenFlag[] = ['broken_link', 'no_way_in', 'dead_end', 'duplicate']

export const edgeKey = (from: string, to: string) => `${from}>${to}`

/** Pages always; layouts, redirects and catch-alls only with the "show hidden" lens on. */
export function shownScreens(j: Journeys, showHidden: boolean): Screen[] {
  return j.screens.filter((s) => showHidden || s.kind === 'page')
}

/** The edges between shown nodes. */
export function shownEdges(j: Journeys, showHidden: boolean): JourneyEdge[] {
  const ids = new Set([...shownScreens(j, showHidden).map((s) => s.id), ...j.menus.map((m) => m.id)])
  return j.edges.filter((e) => ids.has(e.from) && ids.has(e.to))
}

export type Caption = { col: number; kind: 'start' | 'clicks' | 'none'; n: number }

/** Each grid column's caption: the start, n clicks from it, or no way in; a wrapped column keeps its first caption. */
export function captions(j: Journeys): Caption[] {
  const out: Caption[] = []
  let last: string | null = null
  for (let col = 0; col < j.grid.cols; col++) {
    const here = j.screens.filter((s) => s.col === col)
    const depths = here.map((s) => s.depth ?? null)
    const menu = j.menus.some((m) => m.col === col)
    if (!here.length && !menu) continue
    const known = depths.filter((d): d is number => d !== null)
    const caption: Caption = known.length === 0 && !menu ? { col, kind: 'none', n: 0 }
      : { col, kind: known.length && Math.min(...known) === 0 ? 'start' : 'clicks', n: known.length ? Math.min(...known) : col }
    const key = `${caption.kind}${caption.n}`
    if (key !== last) out.push(caption)
    last = key
  }
  return out
}

/** The edges a task's path walks, as keys. */
export function pathEdges(task: Task | undefined): Set<string> {
  const out = new Set<string>()
  if (!task) return out
  for (let i = 1; i < task.path.length; i++) out.add(edgeKey(task.path[i - 1], task.path[i]))
  return out
}

export interface Step { node: string; via?: JourneyEdge; index: number }

/** A task's path as steps: each node with the edge (and its evidence) that leads to it. */
export function stepsOf(j: Journeys, task: Task): Step[] {
  const byKey = new Map(j.edges.map((e) => [edgeKey(e.from, e.to), e]))
  return task.path.map((node, index) => ({ node, index, via: index ? byKey.get(edgeKey(task.path[index - 1], node)) : undefined }))
}

export interface Links { out: JourneyEdge[]; in: JourneyEdge[] }

export function linksOf(j: Journeys, id: string): Links {
  return { out: j.edges.filter((e) => e.from === id && e.via !== 'menu_of'), in: j.edges.filter((e) => e.to === id && e.via !== 'menu_of') }
}

/** The ids lit by a focus (the node and its neighbours), a task (its path) or a flag (the screens carrying it). */
export function litSet(j: Journeys, focus?: string, task?: Task, flag?: ScreenFlag): Set<string> | null {
  if (task) return new Set(task.path.concat(task.screen ? [task.screen] : []))
  if (focus) {
    const out = new Set([focus])
    for (const e of j.edges) {
      if (e.from === focus) out.add(e.to)
      if (e.to === focus) out.add(e.from)
    }
    return out
  }
  if (flag) return new Set(j.screens.filter((s) => s.flags.includes(flag)).map((s) => s.id))
  return null
}

/** The pages grouped by clicks from the start; the unreached last. */
export function byDepth(j: Journeys): { depth: number | null; screens: Screen[] }[] {
  const groups = new Map<number | null, Screen[]>()
  for (const s of j.screens.filter((x) => x.kind === 'page')) {
    const d = s.depth ?? null
    groups.set(d, [...(groups.get(d) ?? []), s])
  }
  return [...groups.entries()].sort(([a], [b]) => (a === null ? 1 : b === null ? -1 : a - b))
    .map(([depth, screens]) => ({ depth, screens: screens.sort((a, b) => a.route.localeCompare(b.route)) }))
}

/** "…/tail" of a long identifier for a fixed-width box (the full value goes in the title). */
export function clip(text: string, max: number): string {
  return text.length <= max ? text : '…' + text.slice(text.length - max + 1)
}

/** The unseen items each screen sets in motion (hidden.json items whose areas hold the screen's area). */
export function unseenBy(j: Journeys, areaItems: Map<string, number>): Map<string, number> {
  const out = new Map<string, number>()
  for (const s of j.screens) {
    const n = areaItems.get(`area:${s.group}`)
    if (n && s.kind === 'page') out.set(s.id, n)
  }
  return out
}

// ---------------------------------------------------------------- clusters: a map of 1,000 screens and more

/** Above this many screens the map opens on its areas (one frame per area); choosing an area expands its screens. */
export const CLUSTER_AT = 250
const CLUSTER_ROWS = 10

export interface Cluster { id: string; screens: Screen[]; depth: number | null; flags: Record<ScreenFlag, number>; x: number; y: number }
export interface ClusterEdge { from: string; to: string; count: number; d: string }

function curve(ax: number, ay: number, bx: number, by: number, w: number, h: number): string {
  if (bx > ax) {
    const x1 = ax + w, y1 = ay + h / 2, x2 = bx, y2 = by + h / 2, mid = (x1 + x2) / 2
    return `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`
  }
  const x1 = ax + w / 2, x2 = bx + w / 2, top = Math.min(ay, by) - 40
  return `M${x1},${ay} C${x1},${top} ${x2},${top} ${x2},${by}`
}

/** The areas as frames on the same grid (columns = the nearest member's clicks from the start), and the links
 * between areas, counted. Deterministic: the order comes from the data, so an area keeps its place. */
export function clusters(j: Journeys): { nodes: Cluster[]; edges: ClusterEdge[]; width: number; height: number } {
  const g = j.grid
  const byId = new Map(j.screens.map((s) => [s.id, s]))
  const groups = (j.groups ?? []).map((grp) => {
    const screens = grp.screens.map((id) => byId.get(id)).filter((s): s is Screen => Boolean(s) && s!.kind === 'page')
    const depths = screens.map((s) => s.depth).filter((d): d is number => d !== null && d !== undefined)
    const flags = { broken_link: 0, no_way_in: 0, dead_end: 0, duplicate: 0 } as Record<ScreenFlag, number>
    for (const s of screens) for (const f of s.flags) flags[f] += 1
    return { id: grp.id, screens, depth: depths.length ? Math.min(...depths) : null, flags }
  }).filter((c) => c.screens.length)
  const levels = [...new Set(groups.map((c) => c.depth))].sort((a, b) => (a === null ? 1 : b === null ? -1 : a - b))
  const nodes: Cluster[] = []
  let col = 0
  for (const level of levels) {
    const here = groups.filter((c) => c.depth === level).sort((a, b) => a.id.localeCompare(b.id))
    here.forEach((c, i) => nodes.push({ ...c, x: g.pad + (col + Math.floor(i / CLUSTER_ROWS)) * g.col_w, y: g.pad + (i % CLUSTER_ROWS) * g.row_h }))
    col += Math.max(1, Math.ceil(here.length / CLUSTER_ROWS))
  }
  const groupOf = new Map<string, string>()
  for (const c of nodes) for (const s of c.screens) groupOf.set(s.id, c.id)
  const at = new Map(nodes.map((c) => [c.id, c]))
  const counts = new Map<string, number>()
  for (const e of j.edges) {
    const a = groupOf.get(e.from), b = groupOf.get(e.to)
    if (a && b && a !== b) counts.set(`${a}>${b}`, (counts.get(`${a}>${b}`) ?? 0) + e.count)
  }
  const edges = [...counts.entries()].map(([key, count]) => {
    const [from, to] = key.split('>')
    const a = at.get(from)!, b = at.get(to)!
    return { from, to, count, d: curve(a.x, a.y, b.x, b.y, g.box_w, g.box_h) }
  })
  const rows = Math.min(CLUSTER_ROWS, Math.max(1, ...levels.map((l) => groups.filter((c) => c.depth === l).length)))
  return { nodes, edges, width: g.pad * 2 + Math.max(col - 1, 0) * g.col_w + g.box_w, height: g.pad * 2 + (rows - 1) * g.row_h + g.box_h }
}

/** An expanded area: its screens and the screens they link with. */
export function areaScreens(j: Journeys, group: string): Set<string> {
  const members = new Set((j.groups ?? []).find((g) => g.id === group)?.screens ?? [])
  const out = new Set(members)
  for (const e of j.edges) {
    if (members.has(e.from)) out.add(e.to)
    if (members.has(e.to)) out.add(e.from)
  }
  return out
}
