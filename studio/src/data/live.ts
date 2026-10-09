// The live source: the read API of `eaos studio` on 127.0.0.1 (eaos/api/), and its stream of events.
// The launch token arrives in the address the server opens (#token=…); boot.js keeps it for this tab and removes it
// from the address before anything else runs. It is sent as a header, never in a URL, so it reaches no log.
// The stream is read with fetch rather than EventSource, which cannot send a header; a reconnect sends Last-Event-ID
// and the server replays what was missed, or says `reset` when it cannot.
import { SECTIONS, type Manifest, type SectionName, type StudioData } from './types'
import type { Loaded } from './load'

export const TOKEN_KEY = 'eaos.token'
const CONTRACT = 1

declare global {
  interface Window { EAOS_BOOT_TOKEN?: string }
}

/** The launch token of this tab, or null when the Studio was opened as a snapshot (from a file, or with no token). */
export function liveToken(): string | null {
  if (typeof window === 'undefined' || !/^https?:$/.test(location.protocol)) return null
  try { return sessionStorage.getItem(TOKEN_KEY) || window.EAOS_BOOT_TOKEN || null } catch { return window.EAOS_BOOT_TOKEN || null }
}

/** One event of the feed (eaos/api/events.py). */
export interface LiveEvent {
  seq: number
  id: string
  at: string
  kind: string
  source: 'manifest' | 'events' | 'action' | 'progress'
  sections: string[]
  text: { en: string; ar: string }
  data: Record<string, unknown>
}

export type LiveStatus = 'connecting' | 'connected' | 'reconnecting' | 'refused'

let heard = 0
/** When the stream last delivered anything, an event or the server's keep-alive ping (Date.now() ms; 0: never). */
export function streamHeardAt(): number {
  return heard
}

// Same-origin credentials: a remote Studio sits behind a sign-in whose cookie must reach the server with every
// call (omitting it made the sign-in turn each API call away). The API itself trusts only its token headers.
async function get(token: string, path: string): Promise<Response> {
  return fetch(path, { headers: { 'X-EAOS-Token': token }, cache: 'no-store', credentials: 'same-origin' })
}

/** The whole report from the server; a section whose sha256 did not change is kept from `previous`. */
export async function loadLive(token: string, previous?: StudioData | null): Promise<Loaded> {
  const response = await get(token, '/api/manifest')
  if (response.status === 404) return { kind: 'empty' }
  if (!response.ok) throw new Error(`manifest: ${response.status}`)
  const manifest = (await response.json()) as Manifest
  if (manifest.contract !== CONTRACT) return { kind: 'error', contract: manifest.contract }
  const before = new Map((previous?.manifest.sections ?? []).map((s) => [s.name, s.sha256]))
  const listed = manifest.sections.filter((s) => (SECTIONS as readonly string[]).includes(s.name))
  const data = { manifest, missing: [] as SectionName[] } as StudioData
  const slots = data as unknown as Record<string, unknown>
  const kept = previous as unknown as Record<string, unknown> | undefined
  await Promise.all(listed.map(async (section) => {
    if (kept && before.get(section.name) === section.sha256 && kept[section.name] !== undefined) {
      slots[section.name] = kept[section.name]
      return
    }
    try {
      const answer = await get(token, `/api/sections/${encodeURIComponent(section.name)}`)
      if (answer.ok) slots[section.name] = await answer.json()
      else data.missing.push(section.name)
    } catch { data.missing.push(section.name) }
  }))
  return { kind: 'ready', data }
}

interface Frame { id?: string; event: string; data: string }

function frame(block: string): Frame | null {
  const out: Frame = { event: 'message', data: '' }
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (!line || line.startsWith(':')) continue
    const at = line.indexOf(':')
    const field = at < 0 ? line : line.slice(0, at)
    const value = at < 0 ? '' : line.slice(at + 1).replace(/^ /, '')
    if (field === 'id') out.id = value
    else if (field === 'event') out.event = value
    else if (field === 'data') data.push(value)
  }
  out.data = data.join('\n')
  return data.length || out.id ? out : null
}

/** Follow the stream until the returned function is called. `onEvent(null)` asks for a full reload (reset). */
export function subscribe(token: string, onEvent: (event: LiveEvent | null) => void, onStatus: (status: LiveStatus) => void): () => void {
  let last: string | null = null
  let stopped = false
  let controller: AbortController | null = null
  const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

  async function follow() {
    let delay = 500
    while (!stopped) {
      controller = new AbortController()
      try {
        const headers: Record<string, string> = { 'X-EAOS-Token': token, Accept: 'text/event-stream' }
        if (last) headers['Last-Event-ID'] = last
        const response = await fetch('/api/events', { headers, cache: 'no-store', credentials: 'same-origin', signal: controller.signal })
        if (response.status === 401) { onStatus('refused'); return }
        if (!response.ok || !response.body) throw new Error(`events: ${response.status}`)
        onStatus('connected')
        delay = 500
        const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
        let buffer = ''
        for (;;) {
          const { value, done } = await reader.read()
          if (done) break
          heard = Date.now()
          buffer += value
          const held = buffer.endsWith('\r') ? '\r' : ''        // a \r\n split across two chunks
          let text = (held ? buffer.slice(0, -1) : buffer).replace(/\r\n?/g, '\n')
          let end: number
          while ((end = text.indexOf('\n\n')) >= 0) {
            const got = frame(text.slice(0, end))
            text = text.slice(end + 2)
            if (!got) continue
            if (got.id) last = got.id
            if (got.event === 'reset') onEvent(null)
            else if (got.event === 'studio') { try { onEvent(JSON.parse(got.data) as LiveEvent) } catch { onEvent(null) } }
          }
          buffer = text + held
        }
      } catch {
        if (stopped) return
      }
      if (stopped) return
      onStatus('reconnecting')
      await wait(delay)
      delay = Math.min(delay * 2, 8000)
    }
  }
  onStatus('connecting')
  void follow()
  return () => { stopped = true; controller?.abort() }
}
