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
