// The diagram reader's own logic, kept apart from the engine so it is in the document page and tested without a
// browser: which kind of Mermaid diagram a block is, Mermaid's configuration from the Studio's tokens, a drawing's
// natural size, and the scale and scroll of pan and zoom. The engine itself (Mermaid) is diagramEngine.ts, its own
// chunks, read only when a document holding a diagram is opened.
import type { MermaidConfig } from 'mermaid'

export type DiagramKind = 'flowchart' | 'sequence' | 'class' | 'state' | 'er' | 'gantt' | 'pie' | 'xychart' | 'mindmap' | 'c4'
  | 'timeline' | 'journey' | 'quadrant' | 'git' | 'sankey' | 'block' | 'architecture' | 'requirement' | 'diagram'

const KINDS: [RegExp, DiagramKind][] = [
  [/^(flowchart|graph)\b/, 'flowchart'], [/^sequenceDiagram\b/, 'sequence'], [/^classDiagram\b/, 'class'],
  [/^stateDiagram\b/, 'state'], [/^erDiagram\b/, 'er'], [/^gantt\b/, 'gantt'], [/^pie\b/, 'pie'], [/^xychart\b/, 'xychart'],
  [/^mindmap\b/, 'mindmap'], [/^C4\w*/, 'c4'], [/^timeline\b/, 'timeline'], [/^journey\b/, 'journey'],
  [/^quadrantChart\b/, 'quadrant'], [/^gitGraph\b/, 'git'], [/^sankey\b/, 'sankey'], [/^block\b/, 'block'],
  [/^architecture\b/, 'architecture'], [/^requirementDiagram\b/, 'requirement'],
]

/** The first line that says what the diagram is: after a front matter block, %% comments and blank lines. */
export function diagramKind(source: string): DiagramKind {
  const lines = source.replace(/^\s*---\n[\s\S]*?\n---\s*\n/, '').split('\n')
  const first = lines.map((line) => line.trim()).find((line) => line && !line.startsWith('%%')) ?? ''
  return KINDS.find(([test]) => test.test(first))?.[1] ?? 'diagram'
}

/** The tokens Mermaid draws with (design/tokens.css), read from the page so the drawing follows the theme. */
export const DIAGRAM_TOKENS = ['--font-sans', '--bg-surface', '--bg-sunken', '--text-primary', '--text-secondary', '--border-default',
  '--diagram-node', '--diagram-node-border', '--diagram-line', '--diagram-cluster', '--diagram-cluster-border', '--diagram-note',
  '--diagram-note-border', '--chart-1', '--chart-2', '--chart-3', '--chart-4', '--chart-5', '--chart-6', '--chart-7', '--chart-8'] as const

export type DiagramToken = typeof DIAGRAM_TOKENS[number]
export interface DiagramTheme { dark: boolean; tokens: Partial<Record<DiagramToken, string>> }

/** The tokens' values as the page computes them under `element` (its theme). */
export function readTheme(element: Element, dark: boolean): DiagramTheme {
  const style = getComputedStyle(element)
  const tokens: DiagramTheme['tokens'] = {}
  for (const name of DIAGRAM_TOKENS) {
    const value = style.getPropertyValue(name).trim()
    if (value) tokens[name] = value
  }
  return { dark, tokens }
}

/** Mermaid's configuration: its neutral "base" theme coloured by the Studio's tokens, strict security (labels are
 * text, no click handlers or scripts), errors thrown to the reader instead of drawn into the page, and drawings at
 * their natural size, which the reader then fits, zooms and pans. */
export function mermaidConfig({ dark, tokens: t }: DiagramTheme): MermaidConfig {
  const chart = (['--chart-1', '--chart-2', '--chart-3', '--chart-4', '--chart-5', '--chart-6', '--chart-7', '--chart-8'] as const)
    .map((name) => t[name]).filter((value): value is string => !!value)
  const pies = Object.fromEntries(chart.map((colour, i) => [`pie${i + 1}`, colour]))
  const scale = Object.fromEntries(chart.map((colour, i) => [`cScale${i}`, colour]))
  const vars: Record<string, unknown> = {
    darkMode: dark, fontFamily: t['--font-sans'], fontSize: '14px',
    background: t['--bg-surface'], mainBkg: t['--diagram-node'], primaryColor: t['--diagram-node'],
    primaryBorderColor: t['--diagram-node-border'], nodeBorder: t['--diagram-node-border'], primaryTextColor: t['--text-primary'],
    textColor: t['--text-primary'], titleColor: t['--text-primary'], lineColor: t['--diagram-line'], defaultLinkColor: t['--diagram-line'],
    secondaryColor: t['--diagram-cluster'], tertiaryColor: t['--diagram-cluster'], clusterBkg: t['--diagram-cluster'],
    clusterBorder: t['--diagram-cluster-border'], edgeLabelBackground: t['--bg-surface'],
    noteBkgColor: t['--diagram-note'], noteBorderColor: t['--diagram-note-border'], noteTextColor: t['--text-primary'],
    actorBkg: t['--diagram-node'], actorBorder: t['--diagram-node-border'], actorTextColor: t['--text-primary'],
    actorLineColor: t['--diagram-line'], signalColor: t['--text-primary'], signalTextColor: t['--text-primary'],
    labelBoxBkgColor: t['--diagram-cluster'], labelBoxBorderColor: t['--diagram-cluster-border'], labelTextColor: t['--text-primary'],
    loopTextColor: t['--text-primary'], sequenceNumberColor: t['--bg-surface'],
    pieTitleTextColor: t['--text-primary'], pieSectionTextColor: t['--bg-surface'], pieLegendTextColor: t['--text-primary'],
    pieStrokeColor: t['--bg-surface'], pieOuterStrokeColor: t['--border-default'], pieStrokeWidth: '2px', pieOpacity: '1',
    ...pies, ...scale,
    xyChart: {
      backgroundColor: t['--bg-surface'], titleColor: t['--text-primary'], xAxisLabelColor: t['--text-secondary'],
      xAxisTitleColor: t['--text-primary'], xAxisTickColor: t['--border-default'], xAxisLineColor: t['--border-default'],
      yAxisLabelColor: t['--text-secondary'], yAxisTitleColor: t['--text-primary'], yAxisTickColor: t['--border-default'],
      yAxisLineColor: t['--border-default'], plotColorPalette: chart.join(','),
    },
  }
  const themeVariables = Object.fromEntries(Object.entries(vars).filter(([, value]) => value !== undefined && value !== ''))
  return {
    startOnLoad: false, securityLevel: 'strict', theme: 'base', themeVariables, suppressErrorRendering: true,
    fontFamily: t['--font-sans'], htmlLabels: false,
    flowchart: { useMaxWidth: false, wrappingWidth: 320, padding: 12, nodeSpacing: 40, rankSpacing: 56, curve: 'basis' },
    sequence: { useMaxWidth: false }, class: { useMaxWidth: false }, state: { useMaxWidth: false }, er: { useMaxWidth: false },
    gantt: { useMaxWidth: false, useWidth: 760, fontSize: 13, sectionFontSize: 13, barHeight: 24, barGap: 6 }, pie: { useMaxWidth: false }, xyChart: { useMaxWidth: false }, mindmap: { useMaxWidth: false },
    c4: { useMaxWidth: false }, journey: { useMaxWidth: false }, timeline: { useMaxWidth: false }, quadrantChart: { useMaxWidth: false },
    gitGraph: { useMaxWidth: false }, requirement: { useMaxWidth: false }, sankey: { useMaxWidth: false }, block: { useMaxWidth: false },
  } as MermaidConfig
}

export interface Size { width: number; height: number }

/** A drawing's natural size, from its viewBox (else its width and height attributes). */
export function svgSize(svg: string): Size {
  const box = /<svg[^>]*\sviewBox="\s*[-\d.e]+[\s,]+[-\d.e]+[\s,]+([\d.e]+)[\s,]+([\d.e]+)\s*"/i.exec(svg)
  if (box) return { width: Number(box[1]), height: Number(box[2]) }
  const width = /<svg[^>]*\swidth="([\d.]+)(px)?"/i.exec(svg)
  const height = /<svg[^>]*\sheight="([\d.]+)(px)?"/i.exec(svg)
  return { width: width ? Number(width[1]) : 0, height: height ? Number(height[1]) : 0 }
}

export const ZOOM = { min: 0.1, max: 4, step: 1.25 }
/** Below this scale a drawing's 14 px words become hard to read: the reader keeps it and pans instead of shrinking. */
export const READABLE = 0.62

/** Charts read as a whole (axes, legend, a timeline): they fit their box at any scale; a graph keeps its words
 * readable and pans. */
const CHARTS: ReadonlySet<DiagramKind> = new Set(['pie', 'xychart', 'gantt', 'quadrant', 'sankey', 'journey', 'timeline', 'git', 'mindmap'])

export function floorFor(kind: DiagramKind): number {
  return CHARTS.has(kind) ? 0 : READABLE
}

/** The scale that fits a drawing in a box: never larger than its natural size; inline, never below the readable
 * scale (a large map then pans inside its box rather than shrinking to a picture of dots). */
export function fitScale(natural: Size, box: Size, { floor = 0, fill = 1 }: { floor?: number; fill?: number } = {}): number {
  if (natural.width <= 0 || natural.height <= 0 || box.width <= 0) return 1
  const byWidth = (box.width * fill) / natural.width
  const byHeight = box.height > 0 ? (box.height * fill) / natural.height : byWidth
  return clampZoom(Math.max(floor, Math.min(1, byWidth, byHeight)))
}

export function clampZoom(k: number): number {
  return Math.min(ZOOM.max, Math.max(ZOOM.min, Math.round(k * 1000) / 1000))
}

/** The scroll that keeps the point under (x, y) of the view still while the scale goes from `from` to `to`. */
export function zoomScroll(scroll: { left: number; top: number }, at: { x: number; y: number }, from: number, to: number) {
  return { left: ((scroll.left + at.x) / from) * to - at.x, top: ((scroll.top + at.y) / from) * to - at.y }
}

/** Where a drawing larger than its box opens: centred on the window of the box's size that holds the most of its
 * nodes (`points`, their centres at the current scale), so a large map opens on its busiest part, readable, rather
 * than on an empty corner; its middle when no node is known. */
export function busiest(points: readonly { x: number; y: number }[], view: Size, drawn: Size): { left: number; top: number } {
  let best = { x: drawn.width / 2, y: drawn.height / 2 }
  let most = 0
  for (const p of points) {
    const near = points.filter((q) => Math.abs(q.x - p.x) <= view.width / 2 && Math.abs(q.y - p.y) <= view.height / 2)
    if (near.length > most) {
      most = near.length
      best = { x: near.reduce((s, q) => s + q.x, 0) / near.length, y: near.reduce((s, q) => s + q.y, 0) / near.length }
    }
  }
  const clamp = (v: number, max: number) => Math.max(0, Math.min(max, v))
  return { left: clamp(best.x - view.width / 2, drawn.width - view.width), top: clamp(best.y - view.height / 2, drawn.height - view.height) }
}

/** A second copy of a drawing (the full screen view) with its ids renamed, so the page holds each id once. */
export function renameIds(svg: string, id: string, suffix: string): string {
  return svg.split(id).join(`${id}${suffix}`)
}
