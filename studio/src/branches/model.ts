// What the branches page lists, kept apart from drawing it: by default only the person's work branches (made by EAOS
// for a task, durable provenance only) and the branch they work on (open in the project folder, or analysed), on this
// computer and on the remote; every branch only when they ask for all of it. "Default" and "protected" are facts about
// a branch, not a reason to list it: main, origin/main and every other remote's main stay under "all".
import type { BranchRow, RunLink } from '../data/actions/types'
import { normalize } from '../search/normalize'

export type Show = 'work' | 'all'

export interface Shown { local: BranchRow[]; remote: BranchRow[] }

export function shownBranches(rows: BranchRow[], show: Show, query = ''): Shown {
  const words = normalize(query).split(' ').filter(Boolean)
  const working = new Set(rows.filter((r) => r.kind === 'local' && (r.roles.includes('checkout') || r.roles.includes('analysis'))).map((r) => r.name))
  const listed = rows.filter((row) => (show === 'all' || row.work || working.has(row.name))
    && words.every((word) => normalize(`${row.name} ${row.remote ?? ''} ${row.subject}`).includes(word)))
  return { local: listed.filter((r) => r.kind === 'local'), remote: listed.filter((r) => r.kind === 'remote') }
}

/** The latest linked run and how many more: a row names one run, never a column of them. */
export function latestRun(runs: RunLink[]): { run: RunLink | null; more: number } {
  const sorted = runs.slice().sort((a, b) => (b.created ?? '').localeCompare(a.created ?? ''))
  return { run: sorted[0] ?? null, more: Math.max(0, sorted.length - 1) }
}
