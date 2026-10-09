// Loads the Studio's data with classic scripts (<name>.js beside index.html, written by eaos/studio/export.py): a
// browser opening the Studio from a file refuses fetch(), but runs a script from the same folder. The content
// security policy allows scripts from 'self' only, so nothing is ever loaded from elsewhere.
import { SECTIONS, type Manifest, type SectionName, type StudioData } from './types'

declare global {
  interface Window {
    EAOS_STUDIO?: Record<string, unknown>
    EAOS_DATA?: Promise<void>
    /** The sections public/boot.js read first for the page being opened, or null when it read every section */
    EAOS_FIRST?: string[] | null
  }
}

export const CONTRACT = 1

export function script(name: string): Promise<boolean> {
  return new Promise((resolve) => {
    const tag = document.createElement('script')
    tag.src = `./${name}.js`
    tag.onload = () => resolve(true)
    tag.onerror = () => resolve(false)
    document.head.appendChild(tag)
  })
}

export type Loaded =
  | { kind: 'loading' }
  | { kind: 'ready'; data: StudioData }
  | { kind: 'empty' }
  | { kind: 'error'; contract: number }

export async function load(): Promise<Loaded> {
  await window.EAOS_DATA // public/boot.js started the data scripts before this script arrived; what failed is retried below
  window.EAOS_STUDIO = window.EAOS_STUDIO || {}
  if (!window.EAOS_STUDIO.manifest && !(await script('manifest'))) return { kind: 'empty' }
  const manifest = window.EAOS_STUDIO.manifest as Manifest | undefined
  if (!manifest) return { kind: 'empty' }
  if (manifest.contract !== CONTRACT) return { kind: 'error', contract: manifest.contract }
  const listed = manifest.sections.map((s) => s.name).filter((name) => (SECTIONS as readonly string[]).includes(name)) as SectionName[]
  // The sections boot.js chose to read first; the others wait in `pending` until something asks for them
  const first = window.EAOS_FIRST
  const now = first ? listed.filter((name) => first.includes(name)) : listed
  await Promise.all(now.filter((name) => !window.EAOS_STUDIO![name]).map(script))
  const raw = window.EAOS_STUDIO
  const data = { manifest, missing: now.filter((name) => !raw[name]), pending: listed.filter((name) => !now.includes(name)) } as StudioData
  for (const name of now) if (raw[name]) (data as unknown as Record<string, unknown>)[name] = raw[name]
  return { kind: 'ready', data }
}

/** Reads sections still pending, each by its classic script; withSections then puts them into the report. */
export async function readSections(names: readonly SectionName[]): Promise<void> {
  window.EAOS_STUDIO = window.EAOS_STUDIO || {}
  await Promise.all(names.filter((name) => !window.EAOS_STUDIO![name]).map(script))
}

/** The report with `names` moved from pending to loaded; one that did not load joins `missing`, so the page shows it
 * as missing exactly as when it fails at start. */
export function withSections(data: StudioData, names: readonly SectionName[], raw: Record<string, unknown>): StudioData {
  const next = { ...data, pending: (data.pending ?? []).filter((name) => !names.includes(name)), missing: [...data.missing] } as StudioData
  for (const name of names) {
    if (raw[name] !== undefined) (next as unknown as Record<string, unknown>)[name] = raw[name]
    else if (!next.missing.includes(name)) next.missing.push(name)
  }
  return next
}
