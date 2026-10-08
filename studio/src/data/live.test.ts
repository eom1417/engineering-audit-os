import { afterEach, describe, expect, it, vi } from 'vitest'
import { subscribe, type LiveEvent } from './live'

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const bytes = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(bytes.encode(chunk))
      controller.close()
    },
  })
}

const event = (seq: number): LiveEvent => ({ seq, id: `e1-${seq}`, at: '', kind: 'scan.done', source: 'manifest', sections: ['head'], text: { en: 'x', ar: 'س' }, data: {} })

afterEach(() => vi.unstubAllGlobals())

describe('the live stream reader', () => {
  it('reads events split across chunks and CRLF lines, and replays from the last id on reconnect', async () => {
    const body = JSON.stringify(event(3))
    const calls: Record<string, string>[] = []
    let round = 0
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init: RequestInit) => {
      calls.push({ ...(init.headers as Record<string, string>) })
      round += 1
      if (round > 1) return new Response(null, { status: 401 })
      const wire = `event: hello\r\nid: e1-2\r\ndata: {}\r\n\r\n: ping\r\n\r\nevent: studio\r\nid: e1-3\r\ndata: ${body}\r\n\r\n`
      const at = wire.indexOf('\r\n\r\nevent: studio') + 1      // a split between \r and \n
      return new Response(streamOf([wire.slice(0, at), wire.slice(at, at + 9), wire.slice(at + 9)]), { status: 200 })
    }))
    const seen: (LiveEvent | null)[] = []
    const statuses: string[] = []
    await new Promise<void>((resolve) => {
      subscribe('tok', (e) => seen.push(e), (s) => { statuses.push(s); if (s === 'refused') resolve() })
    })
    expect(seen).toEqual([event(3)])
    expect(calls[0]['X-EAOS-Token']).toBe('tok')
    expect(calls[0]['Last-Event-ID']).toBeUndefined()
    expect(calls[1]['Last-Event-ID']).toBe('e1-3')
    expect(statuses).toEqual(['connecting', 'connected', 'reconnecting', 'refused'])
  })

  it('asks for a full reload on reset', async () => {
    let round = 0
    vi.stubGlobal('fetch', vi.fn(async () => {
      round += 1
      if (round > 1) return new Response(null, { status: 401 })
      return new Response(streamOf(['event: reset\nid: e2-0\ndata: {}\n\n']), { status: 200 })
    }))
    const seen: (LiveEvent | null)[] = []
    await new Promise<void>((resolve) => { subscribe('tok', (e) => seen.push(e), (s) => { if (s === 'refused') resolve() }) })
    expect(seen).toEqual([null])
  })
})
