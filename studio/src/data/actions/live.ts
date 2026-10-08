// The live command centre: the action API of `eaos studio` on 127.0.0.1 (docs/studio-actions.json `endpoints` and
// `security`). Every call carries the launch token (X-EAOS-Token); every POST also the CSRF token GET /api/session
// returned for this launch; the browser adds the Origin the server checks. A run's events come over SSE read with
// fetch, and a dropped stream reconnects with Last-Event-ID, so the server replays exactly what was missed.
import { frameSplitter } from './sse'
import { ActionError, TERMINAL, type ActionsClient, type Control, type Preview, type PreviewBody, type Question, type Run,
  type RunEvent, type StartBody, type StreamStatus } from './types'

export const TOKEN_KEY = 'eaos.token'

declare global {
  interface Window { EAOS_BOOT_TOKEN?: string }
}

/**
 * The launch token of this tab, or null when the Studio was opened as a snapshot (from a file, or with no token).
 * The server opens the Studio at #token=…; it is kept for this tab only and removed from the address at once.
 */
export function takeToken(): string | null {
  if (typeof window === 'undefined' || !/^https?:$/.test(location.protocol)) return null
  const given = /^#token=([A-Za-z0-9_-]{16,128})$/.exec(location.hash)
  if (given) {
    window.EAOS_BOOT_TOKEN = given[1]
    try { sessionStorage.setItem(TOKEN_KEY, given[1]) } catch { /* storage refused: this visit only */ }
    try { history.replaceState(null, '', location.pathname + '#/') } catch { location.hash = '#/' }
  }
  try { return sessionStorage.getItem(TOKEN_KEY) || window.EAOS_BOOT_TOKEN || null } catch { return window.EAOS_BOOT_TOKEN || null }
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

export function liveClient(token: string): ActionsClient {
  let csrf: Promise<string> | null = null
  const session = () => (csrf ??= request('GET', '/api/session').then((s) => String((s as { csrf: string }).csrf)))

  async function request(method: 'GET' | 'POST', path: string, body?: unknown, retried = false): Promise<unknown> {
    const headers: Record<string, string> = { 'X-EAOS-Token': token, Accept: 'application/json' }
    if (method === 'POST') {
      headers['Content-Type'] = 'application/json'
      headers['X-EAOS-CSRF'] = await session()
    }
    const response = await fetch(path, { method, headers, body: method === 'POST' ? JSON.stringify(body ?? {}) : undefined, cache: 'no-store', credentials: 'omit' })
    let payload: Record<string, unknown> = {}
    try { payload = await response.json() } catch { payload = {} }
    if (response.status === 403 && /csrf/i.test(String(payload.error)) && !retried) {
      csrf = null // a new launch: the CSRF token of this page went stale
      return request(method, path, body, true)
    }
    if (!response.ok) throw new ActionError(response.status, String(payload.error ?? response.statusText), payload.needs as string | undefined)
    return payload
  }

  const post = <T>(path: string, body?: unknown) => request('POST', path, body) as Promise<T>
  const get = <T>(path: string) => request('GET', path) as Promise<T>
  const runOf = (payload: { run: Run }) => payload.run

  return {
    mode: 'live',
    preview: (id: string, body: PreviewBody) => post<Preview>(`/api/actions/${encodeURIComponent(id)}/preview`, body),
    start: (body: StartBody) => post<{ run: Run }>('/api/runs', body).then(runOf),
    runs: () => get<{ runs: Run[]; queue: string[] }>('/api/runs?all=1'),
    run: (id: string) => get<{ run: Run }>(`/api/runs/${encodeURIComponent(id)}`).then(runOf),
    control: (id: string, op: Control) => post<{ run: Run }>(`/api/runs/${encodeURIComponent(id)}/${op}`).then(runOf),
    reorder: (order: string[]) => post<{ queue: string[] }>('/api/runs/reorder', { order }).then((r) => r.queue),
    questions: () => get<{ questions: Question[] }>('/api/questions').then((r) => r.questions),
    answer: (question: string, option: string | null, text?: string | null) =>
      post<{ run: Run }>(`/api/questions/${encodeURIComponent(question)}/answer`, { option, text: text ?? null }).then(runOf),
    decide: (id: string, op: 'accept' | 'undo', confirm: string) => post<{ run: Run }>(`/api/runs/${encodeURIComponent(id)}/${op}`, { confirm }).then(runOf),

    follow(id: string, after: number, onEvent: (event: RunEvent) => void, onStatus: (status: StreamStatus) => void) {
      let last = after
      let stopped = false
      let controller: AbortController | null = null
      let ended = false
      async function stream() {
        let delay = 500
        while (!stopped && !ended) {
          controller = new AbortController()
          try {
            const headers: Record<string, string> = { 'X-EAOS-Token': token, Accept: 'text/event-stream' }
            if (last > 0) headers['Last-Event-ID'] = String(last)
            const response = await fetch(`/api/runs/${encodeURIComponent(id)}/events`, { headers, cache: 'no-store', credentials: 'omit', signal: controller.signal })
            if (response.status === 401 || response.status === 404) { onStatus('closed'); return }
            if (!response.ok || !response.body) throw new Error(`events: ${response.status}`)
            onStatus('open')
            delay = 500
            const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
            const feed = frameSplitter((frame) => {
              let event: RunEvent
              try { event = JSON.parse(frame.data) as RunEvent } catch { return }
              if (typeof event.seq !== 'number' || event.seq <= last) return // a replayed event already shown
              last = event.seq
              if (event.kind === 'state' && TERMINAL.includes(event.data.to as never)) ended = true
              onEvent(event)
            })
            for (;;) {
              const { value, done } = await reader.read()
              if (done) break
              feed(value)
            }
          } catch {
            if (stopped) return
          }
          if (stopped) return
          if (ended) break
          onStatus('reconnecting')
          await wait(delay)
          delay = Math.min(delay * 2, 8000)
        }
        if (!stopped) onStatus('closed')
      }
      onStatus('connecting')
      void stream()
      return () => { stopped = true; controller?.abort() }
    },
  }
}
