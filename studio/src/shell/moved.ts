// The addresses that moved when the Studio was regrouped (docs/STUDIO-REDESIGN.md): each old page now lives on another
// one, so an old link (a bookmark, the back end's #/scan and #/tools, a document) opens the new place. router.tsx turns
// each row into a redirect.
type Search = Record<string, string | undefined>

export interface Moved { from: string; to: string; extra?: Search; keep?: string[] }

export const MOVED: Moved[] = [
  { from: '/scan', to: '/checks', keep: ['flow', 'stage'] },
  { from: '/tools', to: '/checks' },
  { from: '/runs', to: '/checks', extra: { tab: 'runs' }, keep: ['q', 'show'] },
  { from: '/history', to: '/checks', extra: { tab: 'checks' } },
]

/** Where an old address goes, with the search the new page reads. */
export function movedTo(row: Moved, search: Search): { to: string; search: Search } {
  const kept = Object.fromEntries((row.keep ?? []).filter((name) => search[name] !== undefined).map((name) => [name, search[name]]))
  return { to: row.to, search: { ...row.extra, ...kept } }
}
