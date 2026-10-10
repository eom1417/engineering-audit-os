import { readFileSync } from 'node:fs'
import { createElement, Fragment } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { languageOf, tokenKind } from './code'
import { clampZoom, diagramKind, fitScale, floorFor, mermaidConfig, READABLE, renameIds, svgSize, zoomScroll } from './diagram'
import { alertOf, footnotes, isNumeric, numericColumns } from './gfm'
import { drawMarkdown } from './markdown'

// Diagram and CodeBlock draw through the engine and the highlighter in a browser: here they show what they were given
vi.mock('./Diagram', () => ({ Diagram: ({ source, n }: { source: string; n: number }) => `[diagram ${n}: ${diagramKind(source)}]` }))
vi.mock('./CodeBlock', () => ({ CodeBlock: ({ code, info, label }: { code: string; info?: string; label: string }) => `[${label} ${info ?? ''}: ${code}]` }))

const FIXTURE = readFileSync(new URL('./fixtures/every-element.md', import.meta.url), 'utf8')
const w = (key: string, vars?: Record<string, string | number>) => (vars ? `${key}(${Object.values(vars).join(',')})` : key)
const ctx = {
  path: 'technical/EVERY.md', title: 'Every element', docs: new Set<string>(), cards: new Set<string>(),   // a linked card needs the router: model.test.ts covers links
  images: new Map([['technical/map.png', { id: 'technical/map.png', format: 'png', data: 'data:image/png;base64,AA==', source: null, embedded: true, reason: null }]]), w,
}

describe('the reader draws every element of the fixture', () => {
  const drawn = drawMarkdown(FIXTURE, ctx)
  const html = renderToStaticMarkup(createElement(Fragment, null, drawn.body))

  it('draws the five alerts with their names and keeps an ordinary quote', () => {
    for (const kind of ['note', 'tip', 'important', 'warning', 'caution']) {
      expect(html).toContain(`data-kind="${kind}" role="note" aria-label="alert_${kind}"`)
    }
    expect(html).not.toContain('[!NOTE]')
    expect(html).toContain('<blockquote')
  })

  it('draws task boxes with their state named, and no raw checkbox', () => {
    expect(html).toContain('role="img" aria-label="taskDone"')
    expect(html).toContain('role="img" aria-label="taskOpen"')
    expect(html).not.toContain('<input')
  })

  it('hands code to the highlighter block and mermaid to the diagram, numbered apart', () => {
    expect(html).toContain('[codeN(1) python: def add(a, b):')
    expect(html).toContain('[codeN(2) : plain text with [^why] inside a fence')
    expect(html).toContain('[diagram 1: flowchart]')
    expect(html).toContain('[diagram 2: pie]')
  })

  it('aligns the number columns of a table and gives it a direction and a header', () => {
    expect(html).toContain('aria-label="tableN(1)" dir="ltr"')
    expect(html).toContain('scope="col"')
    expect((html.match(/class="[^"]*num[^"]*"/g) ?? []).length).toBe(8)   // Files and Share: header and three cells each
    expect(html).toContain('<bdi dir="ltr">1,204</bdi>')
  })

  it('draws an image alone in its paragraph as a figure with its caption', () => {
    expect(html).toMatch(/<figure[^>]*><img src="data:image\/png;base64,AA==" alt="The system map"[^>]*\/><figcaption[^>]*>The system map today<\/figcaption><\/figure>/)
  })

  it('numbers footnotes by first citation, lists them at the end, and leaves fenced text alone', () => {
    expect(html).toContain('id="fnref-1" aria-label="footnoteN(1)"')
    expect(html).toContain('id="fnref-2" aria-label="footnoteN(2)"')
    expect(html).toContain('id="fn-1"')
    expect(html).toContain('Because the reader needs one.')
    expect(html).toContain('on two lines.')
    expect(html).toContain('[^fake]: not a footnote')
    expect(html).not.toContain('[^why]: Because')
  })

  it('collects the headings and injects no HTML', () => {
    expect(drawn.headings.map((h) => h.text)).toEqual(['Callouts', 'Tasks', 'Code', 'Diagrams', 'Table', 'Figure'])
    expect(html).toContain('TASK-001')
    expect(html).not.toContain('<script')
  })
})

describe('GitHub additions', () => {
  it('reads an alert marker only at the start of a quote', () => {
    expect(alertOf('[!warning]\nCareful')).toEqual({ kind: 'warning', body: 'Careful' })
    expect(alertOf('[!NOTE]')).toEqual({ kind: 'note', body: '' })
    expect(alertOf('Text [!NOTE]')).toBeNull()
    expect(alertOf('[!OTHER]\nx')).toBeNull()
  })

  it('takes footnote definitions out, outside fences only', () => {
    const found = footnotes('a[^1]\n\n```\n[^2]: kept\n```\n[^1]: one\n  more\n')
    expect([...found.notes]).toEqual([['1', 'one\nmore']])
    expect(found.text).toContain('[^2]: kept')
    expect(footnotes('no notes').text).toBe('no notes')
  })

  it('tells numbers from words', () => {
    for (const yes of ['1,204', '-3.5%', '12 ms', '٣٫٥', '$40', '2.1 MB', '0', '+7']) expect(isNumeric(yes), yes).toBe(true)
    for (const no of ['v1.2.3a', 'TASK-1', 'abc', '', '1 file', '2026-10-10T10:00']) expect(isNumeric(no), no).toBe(false)
    expect(numericColumns([['a', '1', ''], ['b', '—', 'x']], 3)).toEqual([false, true, false])
  })
})

describe('code', () => {
  it('names a fence language the highlighter knows', () => {
    expect(languageOf('ts')).toBe('typescript')
    expect(languageOf('Python {linenos}')).toBe('python')
    expect(languageOf('yml')).toBe('yaml')
    expect(languageOf('mermaid')).toBeNull()
    expect(languageOf('')).toBeNull()
  })

  it('folds highlight.js scopes into the Studio colours', () => {
    expect(tokenKind(['hljs-keyword'])).toBe('keyword')
    expect(tokenKind(['hljs-title', 'function_'])).toBe('title')
    expect(tokenKind(['hljs-title', 'class_'])).toBe('type')
    expect(tokenKind(['hljs-unknown'])).toBeNull()
  })
})

describe('diagrams', () => {
  it('knows the kind of a diagram past front matter and comments', () => {
    expect(diagramKind('---\ntitle: x\n---\n%% note\ngraph TD\nA-->B')).toBe('flowchart')
    expect(diagramKind('xychart-beta\n x-axis [a]')).toBe('xychart')
    expect(diagramKind('C4Context\n')).toBe('c4')
    expect(diagramKind('sequenceDiagram')).toBe('sequence')
    expect(diagramKind('nonsense')).toBe('diagram')
  })

  it('configures Mermaid from the tokens: strict, base theme, chart palette, natural size', () => {
    const config = mermaidConfig({ dark: true, tokens: { '--font-sans': 'Plex', '--diagram-node': '#152844', '--chart-1': '#3987e5', '--chart-2': '#d95926' } })
    expect(config.securityLevel).toBe('strict')
    expect(config.theme).toBe('base')
    const vars = config.themeVariables as Record<string, unknown>
    expect(vars.darkMode).toBe(true)
    expect(vars.primaryColor).toBe('#152844')
    expect(vars.pie1).toBe('#3987e5')
    expect((vars.xyChart as Record<string, string>).plotColorPalette).toBe('#3987e5,#d95926')
    expect(vars).not.toHaveProperty('lineColor')   // a token the page lacks is left to Mermaid
    expect(config.flowchart?.useMaxWidth).toBe(false)
  })

  it('reads the natural size and fits it, keeping large drawings readable', () => {
    expect(svgSize('<svg id="x" viewBox="-8 -8 3000 800" style="">')).toEqual({ width: 3000, height: 800 })
    expect(svgSize('<svg width="120" height="40">')).toEqual({ width: 120, height: 40 })
    expect(fitScale({ width: 400, height: 200 }, { width: 800, height: 0 })).toBe(1)        // never above natural size
    expect(fitScale({ width: 1600, height: 200 }, { width: 800, height: 0 })).toBe(0.5)
    expect(fitScale({ width: 3000, height: 800 }, { width: 600, height: 0 }, { floor: READABLE })).toBe(READABLE)
    expect(fitScale({ width: 1000, height: 2000 }, { width: 1000, height: 1000 })).toBe(0.5) // full screen fits the height too
    expect(clampZoom(100)).toBe(4)
    expect([floorFor('pie'), floorFor('xychart'), floorFor('flowchart'), floorFor('c4')]).toEqual([0, 0, READABLE, READABLE])
  })

  it('zooms around the pointer and renames a copy\'s ids', () => {
    expect(zoomScroll({ left: 0, top: 0 }, { x: 100, y: 50 }, 1, 2)).toEqual({ left: 100, top: 50 })
    expect(renameIds('<svg id="eaos-diagram-3"><marker id="eaos-diagram-3_arrow"/></svg>', 'eaos-diagram-3', '-full'))
      .toBe('<svg id="eaos-diagram-3-full"><marker id="eaos-diagram-3-full_arrow"/></svg>')
  })
})
