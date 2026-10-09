// The screens gallery's reading model (studio/screens.json, eaos/studio/screens.py): every screen with its shots per
// viewport and phase, its inputs and its usability issues pinned to a region of a shot; and what is not measured yet
// (`missing`), which the pages show as a designed state rather than as "no issues".
import type { Gap, Measure } from '../functions/model'

export interface Shot { path: string; width: number; phase: 'before' | 'after' | 'baseline' | null; batch: string | null }
export interface Box { x: number; y: number; w: number; h: number }
export interface Issue { id: string; rule: string; severity: 'critical' | 'high' | 'medium' | 'low' | 'info'; summary: string; element?: string | null;
  width?: number | null; box?: Box | null; card?: string | null; state: 'open' | 'fixed' }
export interface Input { id: string; label?: string | null; kind: string; labelled?: boolean | null; validated?: boolean | null; required?: boolean | null }
export type Flag = 'no_way_in' | 'dead_end' | 'duplicate' | 'broken_link'

export interface Screen {
  id: string
  route: string
  title: string
  component?: string | null
  file?: string | null
  router?: string | null
  line?: number | null
  fact?: string | null
  flags?: Flag[]
  shots: Shot[]
  inputs: Input[]
  issues: Issue[]
}

export interface ScreensData { screens: Screen[]; missing?: Gap[]; counts?: Record<string, Measure> }

/** Whether a part of the section (shots, issues, inputs) was measured: a part named in `missing` was not. */
export function measured(data: ScreensData, part: 'shots' | 'issues' | 'inputs'): boolean {
  return !(data.missing ?? []).some((gap) => gap.id === part && gap.state === 'not_measured')
}

export const FILTERS = ['all', 'issues', 'flagged', 'shot'] as const
export type ScreenFilter = (typeof FILTERS)[number]

export function filterScreens(screens: Screen[], filter: ScreenFilter): Screen[] {
  const kept = screens.filter((s) => filter === 'all' ? true : filter === 'issues' ? s.issues.some((i) => i.state === 'open')
    : filter === 'flagged' ? (s.flags ?? []).length > 0 : s.shots.length > 0)
  return kept.sort((a, b) => b.issues.filter((i) => i.state === 'open').length - a.issues.filter((i) => i.state === 'open').length || a.route.localeCompare(b.route))
}

/** The widths a screen was shot at, narrowest first. */
export function widths(screen: Screen): number[] {
  return [...new Set(screen.shots.map((s) => s.width))].sort((a, b) => a - b)
}

/** The shots of one width, by phase: before and after a batch when both exist, else the baseline (or the only one). */
export function shotsAt(screen: Screen, width: number): { before?: Shot; after?: Shot; one?: Shot } {
  const at = screen.shots.filter((s) => s.width === width)
  const before = at.find((s) => s.phase === 'before') ?? at.find((s) => s.phase === 'baseline')
  const after = [...at].reverse().find((s) => s.phase === 'after')
  return before && after ? { before, after } : { one: after ?? before ?? at[0] }
}

/** The issues pinned on a width's shot, numbered in reading order (top to bottom, then along the line). */
export function pins(screen: Screen, width: number): (Issue & { n: number })[] {
  return screen.issues.filter((i) => i.box && (i.width ?? width) === width)
    .sort((a, b) => a.box!.y - b.box!.y || a.box!.x - b.box!.x)
    .map((issue, index) => ({ ...issue, n: index + 1 }))
}

/** The thumbnail of a screen: its phone shot after the last batch, else its first. */
export function thumbnail(screen: Screen): Shot | undefined {
  const narrow = widths(screen)[0]
  if (narrow === undefined) return undefined
  const at = shotsAt(screen, narrow)
  return at.after ?? at.one ?? at.before
}
