import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { RunResult } from '../../data/actions/types'
import { ResultFacts } from './parts'

vi.mock('../../i18n/prefs', () => ({ usePrefs: () => ({ lang: 'ar', num: String, zone: 'UTC', date: String, ago: String }) }))
vi.mock('../library/CodeBlock', () => ({ CodeBlock: ({ code }: { code: string }) => code }))
vi.mock('../library/Diagram', () => ({ Diagram: () => null }))

describe('a run result', () => {
  // The incident (run r20261012-024616): the answer showed literal **السبب:** and "| الطريقة | وش تسوي | |---|---|"
  it('draws the assistant’s Markdown, its tables as tables, never the raw marks', () => {
    const answer = '**السبب:** الدفعة عالقة.\n\n| الطريقة | وش تسوي |\n|---|---|\n| fix_abandon | يقفل الدفعة |\n'
    const html = renderToStaticMarkup(createElement(ResultFacts, { result: { answer, branch: null, diff_stat: null, tests: null, cards_closed: [] } as unknown as RunResult }))
    expect(html).toContain('<strong>السبب:</strong>')
    expect(html).toContain('<table')
    expect(html).not.toContain('|---|')
    expect(html).not.toContain('**')
  })
})
