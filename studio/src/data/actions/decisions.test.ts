import { afterEach, describe, expect, it, vi } from 'vitest'
import { liveClient } from './live'
import type { ActionError } from './types'

afterEach(() => vi.unstubAllGlobals())
describe('live report decisions', () => {
  it('gets the authoritative scope and sends ids and exact custom text with launch and CSRF tokens', async () => {
    const calls: { path: string; init?: RequestInit }[] = []
    const response = { id: 'd', scope: 'scope', response: { option: null, text: '  custom\nanswer  ', label: '  custom\nanswer  ', at: 'now', status: 'queued', run: 'r1' }, execution: { id: 'r1', state: 'queued' } }
    vi.stubGlobal('fetch', async (path: string, init?: RequestInit) => {
      calls.push({ path, init })
      const value = path === '/api/session' ? { csrf: 'csrf' } : init?.method === 'POST' ? { decision: response } : { decisions: [response] }
      return new Response(JSON.stringify(value), { status: 200 })
    })
    const client = liveClient('launch')
    expect((await client.decisions!())[0].scope).toBe('scope')
    expect((await client.answerDecision!('d', 'scope', null, '  custom\nanswer  ')).response?.text).toBe('  custom\nanswer  ')
    const sent = calls.find((c) => c.init?.method === 'POST')!
    expect(JSON.parse(String(sent.init?.body))).toEqual({ scope: 'scope', option: null, text: '  custom\nanswer  ' })
    expect(sent.init?.headers).toMatchObject({ 'X-EAOS-Token': 'launch', 'X-EAOS-CSRF': 'csrf' })
    expect(JSON.parse(String(sent.init?.body))).not.toHaveProperty('label')
  })
  it('surfaces a save failure instead of inventing a saved response', async () => {
    vi.stubGlobal('fetch', async (path: string) => new Response(JSON.stringify(path === '/api/session' ? { csrf: 'c' } : { error: 'invalid option' }), { status: path === '/api/session' ? 200 : 400 }))
    await expect(liveClient('launch').answerDecision!('d', 'scope', 'invalid')).rejects.toThrow('invalid option')
  })
})

describe('live refusals', () => {
  it('says a blocked change in the page language and names the runs it waits for', async () => {
    const reasons = [{ code: 'in_flight', en: 'Work is still open: Review owner answer.', ar: 'فيه شغل ما خلص: مراجعة إجابة المالك.',
      runs: [{ id: 'r1', label: { en: 'Review owner answer', ar: 'مراجعة إجابة المالك' } }] }]
    vi.stubGlobal('fetch', async (path: string) => new Response(JSON.stringify(path === '/api/session' ? { csrf: 'c' }
      : { error: 'Work is still open: Review owner answer.', reasons, needs: 'in_flight' }), { status: path === '/api/session' ? 200 : 409 }))
    for (const lang of ['ar', 'en'] as const) {
      vi.stubGlobal('document', { documentElement: { lang } })
      const refused = await liveClient('launch').branches!.select('develop', true).then(() => null, (problem: ActionError) => problem) as ActionError
      expect([refused.message, refused.needs, refused.reasons[0].runs?.[0].id]).toEqual([reasons[0][lang], 'in_flight', 'r1'])
    }
  })
})
