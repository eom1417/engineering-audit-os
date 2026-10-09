import { createElement, Fragment } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { Doc } from '../../data/types'
import { drawMarkdown, plain, unescape } from './markdown'
import { byReading, grouped, readingList, resolveLink, searchDocs } from './model'

const doc = (path: string, group: string, order: number | null, title = path, headings: Doc['headings'] = []): Doc =>
  ({ id: path, path, group, order, title, bytes: 2400, headings })

const DOCS = [doc('adr/ADR-001.md', 'adr', null), doc('README.md', 'start', 1, 'الفهرس'), doc('START-HERE.md', 'start', 0, 'ابدأ هنا'),
  doc('FLOWS.md', 'technical', 12, 'Flows', [{ level: 2, text: 'الخطة والمسارات' }]), doc('PLAN/TASK-001.md', 'PLAN', null), doc('zeta/x.md', 'zeta', null)]

const ctx = {
  path: 'docs/a.md', title: 'Title', docs: new Set<string>(), cards: new Set<string>(), images: new Map(),
  label: { table: (n: number) => `Table ${n}`, code: (n: number) => `Code ${n}`, diagram: 'Mermaid', diagramNote: 'note' },
}

describe('the library', () => {
  it('reads in the report index order, then group by group', () => {
    expect(readingList(DOCS).map((d) => d.path)).toEqual(['START-HERE.md', 'README.md', 'FLOWS.md', 'PLAN/TASK-001.md', 'adr/ADR-001.md', 'zeta/x.md'])
    expect(grouped(DOCS).map(([g]) => g)).toEqual(['start', 'PLAN', 'adr', 'technical', 'zeta'])
    expect([...DOCS].sort(byReading)[0].path).toBe('START-HERE.md')
  })

  it('resolves a link against the document folder', () => {
    expect(resolveLink('adr/ADR-002.md', '../PLAN/TASK-001.md#why')).toEqual({ path: 'PLAN/TASK-001.md', hash: 'why' })
    expect(resolveLink('README.md', './FLOWS.md')).toEqual({ path: 'FLOWS.md', hash: '' })
    expect(resolveLink('a/b.md', '#part')).toEqual({ path: 'a/b.md', hash: 'part' })
  })

  it('finds a document by a heading inside it, Arabic spellings folded', () => {
    const hits = searchDocs(DOCS, 'خطه')
    expect(hits.map((h) => [h.doc.path, h.heading])).toEqual([['FLOWS.md', 'الخطة والمسارات']])
    expect(searchDocs(DOCS, 'ابدا').map((h) => h.doc.path)).toEqual(['START-HERE.md'])
    expect(searchDocs(DOCS, '   ')).toEqual([])
  })
})

describe('the reader', () => {
  it('collects the headings, skips the title it repeats, and injects no HTML', () => {
    const text = '# Title\n\n## One &amp; two\n\ntext <script>alert(1)</script>\n\n<div onclick="x">raw</div>\n\n### Three\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```mermaid\nflowchart LR\n```\n'
    const drawn = drawMarkdown(text, ctx)
    expect(drawn.headings).toEqual([{ id: 'h-1', depth: 2, text: 'One & two' }, { id: 'h-2', depth: 3, text: 'Three' }])
    const html = renderToStaticMarkup(createElement(Fragment, null, drawn.body))
    expect(html).not.toContain('<script')
    expect(html).not.toContain('<div onclick')
    expect(html).toContain('&lt;script&gt;')
    expect(html).toContain('aria-label="Table 1"')
    expect(html).toContain('Mermaid · note')
    expect(html).not.toContain('<h1')
  })

  it('reads plain text and character references', () => {
    expect(unescape('a &lt;b&gt; &amp; &quot;c&quot;')).toBe('a <b> & "c"')
    expect(plain(drawMarkdown('## A **b** `c`', ctx).headings.length ? [{ type: 'text', raw: 'x', text: 'x' }] : [])).toBe('x')
  })
})
