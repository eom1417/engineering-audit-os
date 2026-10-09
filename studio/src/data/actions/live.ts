// The live command centre: the action API of `eaos studio` on 127.0.0.1 (docs/studio-actions.json `endpoints` and
// `security`). Every call carries the launch token (X-EAOS-Token); every POST also the CSRF token GET /api/session
// returned for this launch; the browser adds the Origin the server checks. A run's events come over SSE read with
// fetch, and a dropped stream reconnects with Last-Event-ID, so the server replays exactly what was missed.
import { frameSplitter } from './sse'
import { ActionError, TERMINAL, type ActionsClient, type BranchApi, type BranchContext, type BranchDetail, type Control, type DeletePreview,
  type Inventory, type LiveFreshness, type MergePreview, type Preview, type PreviewBody, type Question, type Run, type RunEvent,
  type StartBody, type StreamStatus, type ReportDecision } from './types'

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
  let mounted: Promise<boolean> | null = null

  async function request(method: 'GET' | 'POST', path: string, body?: unknown, retried = false): Promise<unknown> {
    const headers: Record<string, string> = { 'X-EAOS-Token': token, Accept: 'application/json' }
    if (method === 'POST') {
      headers['Content-Type'] = 'application/json'
      headers['X-EAOS-CSRF'] = await session()
    }
    const response = await fetch(path, { method, headers, body: method === 'POST' ? JSON.stringify(body ?? {}) : undefined, cache: 'no-store', credentials: 'same-origin' })
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
  const query = (values: Record<string, string | null | undefined>) =>
    Object.entries(values).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(v as string)}`).join('&')
  const branches: BranchApi = {
    freshness: () => get<{ freshness: LiveFreshness }>('/api/freshness').then((r) => r.freshness),
    context: () => get<{ context: BranchContext | null }>('/api/context').then((r) => r.context),
    inventory: (base) => get<Inventory>(`/api/branches?${query({ base })}`),
    detail: (name, kind, remote, base) => get<BranchDetail>(`/api/branches/detail?${query({ name, kind, remote, base })}`),
    select: (branch, scan, expectedTip) => post('/api/branches/analysis', { branch, scan, expected_tip: expectedTip ?? null }),
    previewMerge: (source, target) => post<MergePreview>('/api/branches/merge/preview', { source, target: target ?? null }),
    merge: (p, uncheckedAck) => post('/api/branches/merge', { source: p.source, target: p.target, source_head: p.source_head, target_head: p.target_head,
      unchecked: p.needs_unchecked_ack, unchecked_ack: uncheckedAck, confirm: p.confirm?.token ?? null }),
    proposeResolution: (source, target, assistant) => post('/api/branches/conflict', { source, target, assistant: assistant ?? null }),
    previewDelete: (branch, where, remote) => post<DeletePreview>('/api/branches/delete/preview', { branch, where, remote: remote ?? null }),
    remove: (p, second) => post('/api/branches/delete', { branch: p.branch, where: p.where, remote: p.remote ?? null, tip: p.tip, unmerged: Boolean(p.unmerged),
      confirm: p.confirm?.token ?? null, confirm_unmerged: second ? p.confirm_unmerged?.token ?? null : null }),
    restore: (recovery, as) => post('/api/branches/restore', { recovery, as: as ?? null }),
    fetch: (remote) => post('/api/branches/fetch', { remote: remote ?? 'origin' }),
  }

  return {
    mode: 'live',
    // a read-only server (no project known) has no action API: nothing to poll, nothing to start
    available: () => (mounted ??= request('GET', '/api/session').then((s) => (s as { actions?: boolean }).actions !== false, () => true)),
    preview: (id: string, body: PreviewBody) => post<Preview>(`/api/actions/${encodeURIComponent(id)}/preview`, body),
    start: (body: StartBody) => post<{ run: Run }>('/api/runs', body).then(runOf),
    runs: () => get<{ runs: Run[]; queue: string[] }>('/api/runs?all=1'),
    run: (id: string) => get<{ run: Run }>(`/api/runs/${encodeURIComponent(id)}`).then(runOf),
    control: (id: string, op: Control) => post<{ run: Run }>(`/api/runs/${encodeURIComponent(id)}/${op}`).then(runOf),
    reorder: (order: string[]) => post<{ queue: string[] }>('/api/runs/reorder', { order }).then((r) => r.queue),
    decisions: () => get<{ decisions: ReportDecision[] }>('/api/decisions').then((r) => r.decisions),
    answerDecision: (id, scope, option, text) => post<{ decision: ReportDecision }>(`/api/decisions/${encodeURIComponent(id)}/answer`, { scope, option, text: text ?? null }).then((r) => r.decision),
    questions: () => get<{ questions: Question[] }>('/api/questions').then((r) => r.questions),
    answer: (question: string, option: string | null, text?: string | null) =>
      post<{ run: Run }>(`/api/questions/${encodeURIComponent(question)}/answer`, { option, text: text ?? null }).then(runOf),
    decide: (id: string, op: 'accept' | 'undo', confirm: string) => post<{ run: Run }>(`/api/runs/${encodeURIComponent(id)}/${op}`, { confirm }).then(runOf),
    branches,

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
            const response = await fetch(`/api/runs/${encodeURIComponent(id)}/events`, { headers, cache: 'no-store', credentials: 'same-origin', signal: controller.signal })
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
