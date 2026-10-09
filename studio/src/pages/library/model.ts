// The Library's data: the documents (studio/docs.json) and images (studio/media.json) the check wrote, and their content
// (studio/library.json, contract v2, eaos/studio/library.py). The content is the largest section, so it is not read
// with the rest at start: the reader asks for it, from the script beside the Studio or from the live server's API.
import { useEffect, useState } from 'react'
import { liveToken } from '../../data/live'
import { script } from '../../data/load'
import type { Doc, StudioData } from '../../data/types'
import { normalize } from '../../search'
import { terms } from '../../search/normalize'

export interface LibraryDoc { id: string; text: string; chars?: number; truncated: boolean }
export interface LibraryImage { id: string; format: string; data: string | null; source: string | null; bytes?: number; embedded: boolean; reason: string | null }
export interface LibraryData { documents: LibraryDoc[]; images: LibraryImage[] }
export interface MediaImage { id: string; path: string; title: string; kind: 'screen' | 'diagram' | 'chart' }

/** A row of studio/coverage.json: why a section is not there, and which step writes it. */
export interface CoverageRow { section: string; state: string; detail?: string; step?: string | null; reason?: string }

export type Lazy<T> = { kind: 'loading' } | { kind: 'ready'; data: T } | { kind: 'absent' }

function preset<T>(name: string): T | undefined {
  return window.EAOS_STUDIO?.[name] as T | undefined
}

async function fetchSection<T>(name: string): Promise<T | undefined> {
  const token = liveToken()
  if (token) {
    const answer = await fetch(`/api/sections/${encodeURIComponent(name)}`, { headers: { 'X-EAOS-Token': token }, cache: 'no-store', credentials: 'omit' })
    return answer.ok ? ((await answer.json()) as T) : undefined
  }
  await script(name)
  return preset<T>(name)
}

/** A section the start does not load (the library, the coverage rows): asked for once, from either data source. */
export function useLazySection<T>(data: StudioData, name: string): Lazy<T> {
  const listed = data.manifest.sections.some((s) => (s.name as string) === name)
  const [state, setState] = useState<Lazy<T>>(() => !listed ? { kind: 'absent' } : preset<T>(name) ? { kind: 'ready', data: preset<T>(name)! } : { kind: 'loading' })
  useEffect(() => {
    if (state.kind !== 'loading') return
    let live = true
    fetchSection<T>(name).then((found) => { if (live) setState(found ? { kind: 'ready', data: found } : { kind: 'absent' }) },
      () => { if (live) setState({ kind: 'absent' }) })
    return () => { live = false }
  }, [state.kind, name])
  return state
}

/** The coverage row of a section, when the report has one. */
export function useCoverageRow(data: StudioData, section: string): CoverageRow | undefined {
  const coverage = useLazySection<{ sections?: CoverageRow[] }>(data, 'coverage')
  return coverage.kind === 'ready' ? (coverage.data.sections ?? []).find((row) => row.section === section) : undefined
}

// ---------------------------------------------------------------- documents

/** The groups in the order a person meets them; a group the report adds later comes after these, by name. */
export const GROUPS = ['start', 'story', 'plan', 'PLAN', 'adr', 'technical', 'handover'] as const

export function groupRank(group: string): number {
  const at = (GROUPS as readonly string[]).indexOf(group)
  return at < 0 ? GROUPS.length : at
}

/** Reading order first (the report's index), then the path. */
export function byReading(a: Doc, b: Doc): number {
  const ao = a.order ?? Number.MAX_SAFE_INTEGER
  const bo = b.order ?? Number.MAX_SAFE_INTEGER
  return ao - bo || a.path.localeCompare(b.path)
}

export function grouped(docs: Doc[]): [string, Doc[]][] {
  const groups = new Map<string, Doc[]>()
  for (const doc of docs) groups.set(doc.group, [...(groups.get(doc.group) ?? []), doc])
  return [...groups].map(([group, rows]) => [group, rows.sort(byReading)] as [string, Doc[]])
    .sort(([a], [b]) => groupRank(a) - groupRank(b) || a.localeCompare(b))
}

/** Every document in reading order: the documents the index names, then the rest group by group. */
export function readingList(docs: Doc[]): Doc[] {
  const named = docs.filter((d) => d.order !== null).sort(byReading)
  const rest = grouped(docs.filter((d) => d.order === null)).flatMap(([, rows]) => rows)
  return [...named, ...rest]
}

export function docPath(path: string): string {
  return `/library/docs/${encodeURIComponent(path)}`
}

export function imagePath(id: string): string {
  return `/library/images/${encodeURIComponent(id)}`
}

/** A route parameter back to the path it names (the router may hand it over encoded or not). */
export function decoded(value: string): string {
  try { return decodeURIComponent(value) } catch { return value }
}

/** A link inside a document, resolved against the document's folder: './a.md', '../b/c.md', 'd.md#part'. */
export function resolveLink(from: string, href: string): { path: string; hash: string } {
  const [target, hash = ''] = href.split('#')
  if (!target) return { path: from, hash }
  const parts = target.startsWith('/') ? [] : from.split('/').slice(0, -1)
  for (const part of target.replace(/^\/+/, '').split('/')) {
    if (part === '..') parts.pop()
    else if (part && part !== '.') parts.push(part)
  }
  return { path: parts.join('/'), hash }
}

/** About how long a document takes to read, in minutes (a page of text is about 1,200 bytes a minute). */
export function minutes(bytes: number): number {
  return Math.max(1, Math.round(bytes / 1200))
}

export interface Hit { doc: Doc; heading?: string }

/** The documents whose title, path or headings hold every word of the query, Arabic spellings folded. */
export function searchDocs(docs: Doc[], query: string): Hit[] {
  // each word in its bare form (without the Arabic article), so 'الخطة' also finds 'خطة'
  const words = normalize(query).split(' ').filter(Boolean).map((word) => terms(word).at(-1)!)
  if (!words.length) return []
  const has = (text: string) => { const folded = normalize(text); return words.every((w) => folded.includes(w)) }
  const hits: Hit[] = []
  for (const doc of readingList(docs)) {
    if (has(`${doc.title} ${doc.path}`)) hits.push({ doc })
    else {
      const heading = (doc.headings ?? []).find((h) => has(h.text))
      if (heading) hits.push({ doc, heading: heading.text })
    }
  }
  return hits
}

/** The same heading in two spellings: compared folded. */
export function sameHeading(a: string, b: string): boolean {
  return normalize(a) === normalize(b)
}
