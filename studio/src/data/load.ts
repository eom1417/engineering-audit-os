// Loads the Studio's data with classic scripts (<name>.js beside index.html, written by eaos/studio/export.py): a
// browser opening the Studio from a file refuses fetch(), but runs a script from the same folder. The content
// security policy allows scripts from 'self' only, so nothing is ever loaded from elsewhere.
import { SECTIONS, type Manifest, type StudioData } from './types'

declare global {
  interface Window { EAOS_STUDIO?: Record<string, unknown> }
}

export const CONTRACT = 1

function script(name: string): Promise<boolean> {
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
  window.EAOS_STUDIO = window.EAOS_STUDIO || {}
  if (!window.EAOS_STUDIO.manifest && !(await script('manifest'))) return { kind: 'empty' }
  const manifest = window.EAOS_STUDIO.manifest as Manifest | undefined
  if (!manifest) return { kind: 'empty' }
  if (manifest.contract !== CONTRACT) return { kind: 'error', contract: manifest.contract }
  const listed = manifest.sections.map((s) => s.name).filter((name) => (SECTIONS as readonly string[]).includes(name))
  await Promise.all(listed.filter((name) => !window.EAOS_STUDIO![name]).map(script))
  const raw = window.EAOS_STUDIO
  const data = { manifest, missing: listed.filter((name) => !raw[name]) } as StudioData
  for (const name of listed) if (raw[name]) (data as unknown as Record<string, unknown>)[name] = raw[name]
  return { kind: 'ready', data }
}
