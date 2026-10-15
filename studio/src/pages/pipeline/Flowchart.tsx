// The pipeline drawn as a flowchart: the stages where EAOS placed them (layer, order), left to right on a wide screen
// and top to bottom on the phone. Stages are cards with their tools; routers are diamonds whose branches carry their
// condition; forks and joins are marked on the card's sides; failures run in their own lane; hidden side channels are
// dotted and appear only when asked; what EAOS could not follow is a gap beside its stage. Pan with a drag, zoom with
// the wheel, a pinch or the buttons (the map's useZoom); a long pipeline draws only what is in view.
import { useEffect, useMemo, useRef, type ReactNode } from 'react'
import { clip, fit, useBox, useLinked } from '../../map/draw'
import { useZoom } from '../../map/useZoom'
import { usePrefs } from '../../i18n/prefs'
import { LanesToolbar } from '../paths/Lanes'
import { stageTitle } from './names'
import { geometry, link, NODE_H, NODE_W, PILL_W, type At, type Op, type Scope, type Stage, type View } from './model'
import { KIND_WORD, OP_WORD, usePipelineWords, type PipelineWord } from './words'
import frame from '../paths/paths.module.css'
import css from './pipeline.module.css'

export interface Lit { stages: Set<string>; edges: Set<string> }

export interface FlowchartProps {
  scope: Scope
  view: View
  down: boolean
  selected?: string
  onSelect: (id: string) => void
  hidden: boolean
  lit?: Lit | null
  label: string
  title?: ReactNode
  head?: ReactNode
  legend?: boolean
  className?: string
}

const MARGIN = 260

type Geometry = ReturnType<typeof geometry>
type Transform = { k: number; x: number; y: number }
type Size = { w: number; h: number }

/** What each view says about a stage: its operation in the ideal, the gap entries' numbers in the gap view. */
function stageState(scope: Scope, view: View) {
  const op = new Map<string, Op>()
  const gapNo = new Map<string, number[]>()
  if (view === 'ideal') for (const [id, s] of scope.ideal) op.set(id, s.op)
  if (view === 'gap') {
    scope.gap.forEach((g, i) => {
      const hidden = scope.hidden.find((h) => h.id === g.subject)
      const router = scope.routers.find((r) => r.id === g.subject)
      const fan = scope.fans.find((f) => f.id === g.subject)
      const gap = scope.unresolved.find((u) => u.id === g.subject)
      const ids = hidden ? hidden.stages : router ? [router.stage] : fan ? [fan.fork] : gap ? [gap.stage] : scope.stage.has(g.subject) ? [g.subject] : []
      for (const id of ids) { gapNo.set(id, [...(gapNo.get(id) ?? []), i + 1]); if (!op.has(id)) op.set(id, g.operation) }
    })
  }
  return { op, gapNo }
}

/** The ideal's new stages have no place today: they stand after the last layer, one under the other. */
function useAdded(scope: Scope, view: View, down: boolean, g: Geometry) {
  return useMemo(() => {
    const at = new Map<string, At>()
    if (view !== 'ideal') return at
    const end = down ? g.height : g.width
    scope.added.forEach((s, i) => at.set(s.id, down ? { x: 28 + i * (NODE_W + 24), y: end + 24 } : { x: end + 24, y: 28 + i * (NODE_H + 30) }))
    return at
  }, [scope.added, view, down, g.width, g.height])
}

/** The first view: the whole pipeline when it reads at that size, else its start, readable, to pan along; and the
 * whole of it, which the fit button always shows. */
function useFirstView(g: Geometry, added: Map<string, At>, size: Size, down: boolean) {
  const world = useMemo(() => {
    if (!added.size) return { w: g.width, h: g.height }
    const xs = [...added.values()]
    return { w: Math.max(g.width, ...xs.map((p) => p.x + NODE_W + 28)), h: Math.max(g.height, ...xs.map((p) => p.y + NODE_H + 28)) }
  }, [added, g.width, g.height])
  return useMemo(() => {
    if (!size.w) return { fitView: { k: 1, x: 0, y: 0 }, wholeView: { k: 1, x: 0, y: 0 } }
    const k = Math.min(1, (size.w - 16) / world.w, (size.h - 16) / world.h)
    const whole = { k, x: Math.max(8, (size.w - world.w * k) / 2), y: Math.max(8, (size.h - world.h * k) / 2) }
    if (k >= (down ? 0.62 : 0.6)) return { fitView: whole, wholeView: whole }
    const start = down ? Math.min(1, Math.max(0.62, (size.w - 16) / world.w)) : 0.85
    return { fitView: { k: start, x: 8, y: 8 }, wholeView: whole }
  }, [size.w, size.h, world.w, world.h, down])
}

interface Marks { outLabels: Map<string, string[]>; forks: Map<string, Scope['fans'][number]>; joins: Set<string> }

/** The forks and joins on the stages' sides, and the data each stage gives, written once beside its output port. */
function useMarks(scope: Scope): Marks {
  const forks = useMemo(() => new Map(scope.fans.map((f) => [f.fork, f])), [scope.fans])
  const joins = useMemo(() => new Set(scope.fans.map((f) => f.join).filter(Boolean) as string[]), [scope.fans])
  const outLabels = useMemo(() => {
    const out = new Map<string, string[]>()
    for (const e of scope.edges) {
      if (e.kind === 'hidden') continue
      const text = e.data.shape && e.data.shape !== 'files' ? e.data.shape : e.data.names[0] ?? e.data.shape
      if (!text) continue
      const row = out.get(e.from) ?? []
      if (!row.includes(text)) row.push(text)
      out.set(e.from, row)
    }
    return out
  }, [scope.edges])
  return { outLabels, forks, joins }
}

/** A stage drawn as a button when it is wholly in the visible box; one cut by the canvas's edge is still drawn and
 * clickable, but not a keyboard stop, so no target hides under the page's chrome (the steps list reaches every stage). */
function targetOf(whole: boolean, label: string, pressed: boolean | undefined, act: () => void) {
  return whole
    ? { role: 'button', tabIndex: 0, 'aria-label': label, 'aria-pressed': pressed, onKeyDown: (ev: React.KeyboardEvent) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); act() } } }
    : { 'aria-hidden': true }
}

/** What every part of the drawing reads: the layout, the view, what is chosen and lit, and what is in view. */
interface Ctx {
  scope: Scope
  view: View
  g: Geometry
  selected?: string
  lit?: Lit | null
  showHidden: boolean
  culled: boolean
  w: ReturnType<typeof usePipelineWords>
  lang: ReturnType<typeof usePrefs>['lang']
  onSelect: (id: string) => void
  op: Map<string, Op>
  gapNo: Map<string, number[]>
  dead: Set<string>
  place: (id: string) => At | undefined
  inView: (p: At | undefined) => boolean
  target: (p: At, label: string, act: () => void, opts?: { pressed?: boolean; w?: number; h?: number }) => ReturnType<typeof targetOf>
  dim: (id: string) => boolean
}

type CtxParts = Omit<Ctx, 'place' | 'inView' | 'target' | 'dim' | 'culled'> & { added: Map<string, At>; t: Transform; size: Size }

function drawContext({ added, t, size, ...c }: CtxParts): Ctx {
  // the window in view, in the drawing's units: only what crosses it is drawn
  const v = { x0: -t.x / t.k - MARGIN, y0: -t.y / t.k - MARGIN, x1: (size.w - t.x) / t.k + MARGIN, y1: (size.h - t.y) / t.k + MARGIN }
  const whole = (p: At, w = NODE_W, h = NODE_H) => size.w > 0 && p.x * t.k + t.x >= 0 && (p.x + w) * t.k + t.x <= size.w && p.y * t.k + t.y >= 0 && (p.y + h) * t.k + t.y <= size.h
  return {
    ...c,
    culled: c.scope.stages.length > 200,
    place: (id) => c.g.at.get(id) ?? added.get(id),
    inView: (p) => !!p && p.x + NODE_W >= v.x0 && p.x <= v.x1 && p.y + NODE_H >= v.y0 && p.y <= v.y1,
    target: (p, label, act, opts = {}) => targetOf(whole(p, opts.w, opts.h), label, opts.pressed, act),
    dim: (id) => Boolean((c.lit && !c.lit.stages.has(id)) || (c.view === 'gap' && c.gapNo.size > 0 && !c.gapNo.has(id))),
  }
}

export function Flowchart({ scope, view, down, selected, onSelect, hidden, lit, label, title, head, legend = true, className }: FlowchartProps) {
  const w = usePipelineWords()
  const { lang } = usePrefs()
  const svg = useRef<SVGSVGElement>(null)
  const [attach, size] = useBox()
  const zoom = useZoom(svg)
  const { setT } = zoom
  const showHidden = hidden || view === 'gap'
  const g = useMemo(() => geometry(scope.stages, scope.errors, down), [scope.stages, scope.errors, down])
  const { op, gapNo } = useMemo(() => stageState(scope, view), [scope, view])
  const added = useAdded(scope, view, down, g)
  const { fitView, wholeView } = useFirstView(g, added, size, down)
  useEffect(() => { setT(fitView) }, [fitView, setT])
  const near = useLinked(scope.edges, selected, 'id')
  const dead = useMemo(() => new Set(scope.hidden.filter((h) => h.kind === 'dead_stage').flatMap((h) => h.stages)), [scope.hidden])
  const marks = useMarks(scope)

  const t = zoom.t
  const c = drawContext({ scope, view, g, selected, lit, showHidden, w, lang, onSelect, op, gapNo, dead, added, t, size })
  const drawn: Drawn = { edges: [], labels: [] }
  if (view === 'ideal') drawIdealEdges(c, drawn)
  else drawCurrentEdges(c, drawn, near)
  drawBranches(c, drawn)
  const laneParts = drawLane(c, drawn)
  const hiddenParts = showHidden && view !== 'ideal' ? drawHidden(c) : []
  const gapParts = view !== 'ideal' ? drawGaps(c) : []
  const nodes = drawNodes(c, added, marks)
  const kinds = new Set(scope.stages.map((s) => s.kind))
  return (
    <div className={[frame.canvasWrap, className].filter(Boolean).join(' ')}>
      {(title || head) && <LanesToolbar title={title} head={head} zoom={zoom} fitView={wholeView} />}
      <div className={frame.canvas} ref={attach}>
        <svg ref={svg} className={frame.canvasSvg} viewBox={`0 0 ${Math.max(size.w, 1)} ${Math.max(size.h, 1)}`} preserveAspectRatio="xMinYMin meet"
          direction="ltr" role="group" aria-label={label} data-dragging={zoom.dragging ? '' : undefined}>
          <Defs />
          <g transform={`translate(${t.x},${t.y}) scale(${t.k})`}>
            {laneParts}
            {hiddenParts}
            {drawn.edges}
            {gapParts}
            {nodes}
            {drawn.labels}
          </g>
        </svg>
        {legend && <Legend kinds={kinds} scope={scope} view={view} hidden={showHidden} />}
      </div>
    </div>
  )
}

function Defs() {
  return (
    <defs>
      <pattern id="pp-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="6" height="6" className={frame.hatchBg} /><line x1="0" y1="0" x2="0" y2="6" className={frame.hatchLine} />
      </pattern>
      <pattern id="pp-ghost" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
        <line x1="0" y1="0" x2="0" y2="8" className={css.ghostLine} />
      </pattern>
      {(['', '-on', '-err', '-new'] as const).map((k) => (
        <marker key={k} id={`pp-arrow${k}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0 L8,4 L0,8 z" className={css[`arrow${k.replace('-', '_')}`]} />
        </marker>
      ))}
    </defs>
  )
}

/** The links drawn so far, and the conditions written beside them (drawn last, over the stages). */
interface Drawn { edges: ReactNode[]; labels: ReactNode[] }

/** One link to draw: its two stages, its look and arrow, and the condition or title it carries. */
interface LinkSpec { key: string; from: string; to: string; cls: string; marker: string; condition?: string | null; title?: string }

function drawLink(c: Ctx, out: Drawn, l: LinkSpec) {
  const a = c.place(l.from)
  const b = c.place(l.to)
  if (!a || !b || (c.culled && !c.inView(a) && !c.inView(b))) return
  out.edges.push(<path key={l.key} d={link(c.g, a, b).d} className={l.cls} markerEnd={'url(#' + l.marker + ')'}>{l.title && <title>{l.title}</title>}</path>)
  if (l.condition) out.labels.push(conditionLabel(c.g, b, l.key, l.condition))
}

/** A branch's condition, written beside the stage it leads to. */
function conditionLabel(g: Geometry, b: At, key: string, condition: string): ReactNode {
  const [x, y, anchor] = g.across ? [b.x - 6, b.y + NODE_H / 2 - 7, 'end'] as const : [b.x + NODE_W / 2 + 6, b.y - 8, 'start'] as const
  return <text key={'c' + key} x={x} y={y} textAnchor={anchor} className={css.cond}>{clip(condition, 18)}</text>
}

function drawIdealEdges(c: Ctx, out: Drawn) {
  c.scope.idealEdges.forEach((e, i) => {
    const on = c.selected && (e.from === c.selected || e.to === c.selected)
    drawLink(c, out, { key: 'i' + i, from: e.from, to: e.to, cls: [css.edge, e.op !== 'retain' && css['eop_' + e.op], on && css.on].filter(Boolean).join(' '),
      marker: on ? 'pp-arrow-on' : e.op === 'new' ? 'pp-arrow-new' : 'pp-arrow' })
  })
}

function drawCurrentEdges(c: Ctx, out: Drawn, near: Set<string>) {
  for (const e of c.scope.edges) if (e.kind !== 'hidden' || c.showHidden) drawLink(c, out, currentLink(c, e, near))
}

/** A link of today: lit when chosen or on the lit path, dimmed when something else is. */
function currentLink(c: Ctx, e: Scope['edges'][number], near: Set<string>): LinkSpec {
  const { lit, selected } = c
  const on = near.has(e.id) || (lit?.edges.has(e.id) ?? false)
  const off = (lit && !lit.edges.has(e.id)) || (selected && !near.has(e.id) && !lit)
  const cls = [css.edge, css['ek_' + e.kind], e.matched_by === 'order' && css.orderOnly, on && css.on, off && css.edgeDim].filter(Boolean).join(' ')
  const marker = on ? 'pp-arrow-on' : e.kind === 'error' ? 'pp-arrow-err' : 'pp-arrow'
  return { key: e.id, from: e.from, to: e.to, cls, marker, title: [e.data.shape, ...e.data.names].filter(Boolean).join(' · ') }
}

/** Router branches: drawn when few, or when the router is chosen (a crowded router folds, DESIGN: above 8). */
function drawBranches(c: Ctx, out: Drawn) {
  for (const r of c.scope.routers) {
    if (r.branches.length > 8 && c.selected !== r.stage) continue
    r.branches.forEach((b, i) => {
      if (!b.to || b.to === r.stage) return
      const on = c.selected === r.stage
      drawLink(c, out, { key: r.id + '#' + i, from: r.stage, to: b.to, cls: [css.branch, on && css.on, c.lit && !c.lit.stages.has(b.to) && css.edgeDim].filter(Boolean).join(' '),
        marker: on ? 'pp-arrow-on' : 'pp-arrow', condition: b.condition })
    })
  }
}

/** The failure lane: its ends in a row, a short stub into an end reached from any stage, a curve from each stage whose
 * failures go there. */
function drawLane(c: Ctx, out: Drawn): ReactNode[] {
  const lane = c.g.lane
  if (!lane) return []
  const parts: ReactNode[] = [
    <g key="lane">
      <rect x={lane.x} y={lane.y} width={lane.w} height={lane.h} rx={10} className={css.lane} />
      <text x={lane.x + 14} y={lane.y + 24} className={css.laneTitle}>{c.w('failureLane')}</text>
    </g>,
  ]
  for (const [name, at] of c.g.ends) parts.push(laneEnd(c, name, at))
  for (const e of c.scope.errors) errorEdge(c, out, e)
  return parts
}

function laneEnd(c: Ctx, name: string, at: At): ReactNode {
  const routes = c.scope.errors.filter((e) => e.to === name)
  const conds = routes.map((e) => e.condition || c.w.known('err_', e.kind))
  const any = routes.some((e) => e.from === '*')
  return (
    <g key={`end${name}`} transform={`translate(${at.x},${at.y})`}>
      {any && <path d="M-26,16 L-2,16" className={[css.edge, css.ek_error].join(' ')} markerEnd="url(#pp-arrow-err)" />}
      <rect width={PILL_W} height={32} rx={16} className={css.endPill} />
      <text x={PILL_W / 2} y={21} textAnchor="middle" className={css.endText}>{fit(name, 18)}</text>
      <text x={PILL_W / 2} y={48} textAnchor="middle" className={css.endCond}>{any ? `${c.w('fromAny')} · ` : ''}{clip(conds.join(' · '), any ? 16 : 26)}<title>{conds.join(' · ')}</title></text>
    </g>
  )
}

function errorEdge(c: Ctx, out: Drawn, e: Scope['errors'][number]) {
  const end = c.g.ends.get(e.to)
  const a = e.from === '*' ? undefined : c.g.at.get(e.from)
  if (!end || !a || (c.culled && !c.inView(a))) return
  const sx = a.x + NODE_W / 2
  const sy = a.y + NODE_H
  const ex = end.x + PILL_W / 2
  const my = (sy + end.y) / 2
  out.edges.push(<path key={`err${e.id}`} d={`M${sx},${sy} C${sx},${my} ${ex},${my} ${ex},${end.y}`}
    className={[css.edge, css.ek_error, c.selected && c.selected !== e.from && css.edgeDim].filter(Boolean).join(' ')} markerEnd="url(#pp-arrow-err)" />)
}

/** Hidden: side channels as a dotted thread through their stages, unread outputs as a dotted stub to nowhere. */
function drawHidden(c: Ctx): ReactNode[] {
  const parts: ReactNode[] = []
  const starts = new Map<string, number>()
  for (const h of c.scope.hidden) {
    const pts = h.stages.map((id) => c.g.at.get(id)).filter(Boolean) as At[]
    if (!pts.length || (c.culled && !pts.some(c.inView))) continue
    if (h.kind === 'side_channel' && pts.length > 1) parts.push(sideChannel(h, pts, starts))
    else if (h.kind === 'unread_output') parts.push(unreadOutput(c, h, pts[0]))
  }
  return parts
}

function sideChannel(h: Scope['hidden'][number], pts: At[], starts: Map<string, number>): ReactNode {
  const centre = (p: At) => `${p.x + NODE_W / 2},${p.y + NODE_H / 2}`
  const nth = starts.get(h.stages[0]) ?? 0
  starts.set(h.stages[0], nth + 1)
  return (
    <g key={h.id} className={css.hiddenThread}>
      <path d={`M${pts.map(centre).join(' L')}`} />
      <text x={pts[0].x + 4} y={pts[0].y - 8 - nth * 14} className={css.hiddenTag}>{clip(h.name, 26)}</text>
    </g>
  )
}

function unreadOutput(c: Ctx, h: Scope['hidden'][number], p: At): ReactNode {
  const { across } = c.g
  const x = across ? p.x + NODE_W : p.x + NODE_W / 2
  const y = across ? p.y + NODE_H - 8 : p.y + NODE_H
  return (
    <g key={h.id} className={css.hiddenThread}>
      <path d={across ? `M${x},${y} l34,22` : `M${x},${y} l22,30`} />
      <circle cx={across ? x + 40 : x + 26} cy={across ? y + 26 : y + 36} r={5} className={css.voidDot} />
      <text x={across ? x + 50 : x + 36} y={across ? y + 30 : y + 40} className={css.hiddenTag}>{clip(h.name, 24)}</text>
    </g>
  )
}

/** What EAOS could not follow: a gap box hanging under (or beside) its stage. */
function drawGaps(c: Ctx): ReactNode[] {
  const parts: ReactNode[] = []
  for (const u of c.scope.unresolved) {
    const p = c.g.at.get(u.stage)
    if (!p || (c.culled && !c.inView(p))) continue
    parts.push(gapNode(c, u, p))
  }
  return parts
}

function gapNode(c: Ctx, u: Scope['unresolved'][number], p: At): ReactNode {
  const { across } = c.g
  const gx = across ? p.x + 18 : p.x + NODE_W + 14
  const gy = across ? p.y + NODE_H + 14 : p.y + 8
  return (
    <g key={u.id} className={css.gapNode} {...c.target({ x: gx, y: gy }, `${c.w('gapNode')}: ${u.call}. ${u.reason}`, () => c.onSelect(u.stage), { w: NODE_W - 36, h: 28 })} onClick={() => c.onSelect(u.stage)}>
      <path d={across ? `M${p.x + 30},${p.y + NODE_H} L${gx + 12},${gy}` : `M${p.x + NODE_W},${p.y + NODE_H / 2} L${gx},${gy + 14}`} className={css.gapLink} />
      <rect x={gx} y={gy} width={NODE_W - 36} height={28} rx={6} />
      <text x={gx + 10} y={gy + 18} className={css.gapText}>? {fit(u.call, 15)}</text>
    </g>
  )
}

/** The data a stage gives, beside its output port; none when a chosen router writes its conditions there. */
function outPorts(c: Ctx, s: Stage, labels: string[] | undefined): ReactNode[] {
  const crowded = !!c.selected && (c.scope.routerOf.get(c.selected)?.branches.length ?? 0) > 0
  if (!labels || c.view === 'ideal' || c.dim(s.id) || crowded) return []
  return labels.slice(0, 2).map((text, i) => {
    const x = c.g.across ? NODE_W + 6 : NODE_W / 2 + 8
    const y = c.g.across ? NODE_H / 2 - 4 - i * 14 : NODE_H + 14 + i * 13
    return <text key={`o${i}`} x={x} y={y} className={css.shape}>{clip(text, c.g.across ? 13 : 20)}</text>
  })
}

const FAN = {
  fork: { across: [NODE_W, NODE_H / 2], down: [NODE_W / 2, NODE_H], d: 'M-3,0 L3,-3 M-3,0 L3,3 M-3,0 L3,0' },
  join: { across: [0, NODE_H / 2], down: [NODE_W / 2, 0], d: 'M-3,-3 L3,0 M-3,3 L3,0 M-3,0 L3,0' },
} as const

/** A fork's or a join's mark on the stage's side; an open fork (no join found) is drawn open. */
function fanMark(c: Ctx, kind: 'fork' | 'join', open: boolean): ReactNode {
  const { across, down, d } = FAN[kind]
  const [cx, cy] = c.g.across ? across : down
  return (
    <g key={kind} className={[css.fanMark, open && css.fanOpen].filter(Boolean).join(' ')} transform={`translate(${cx},${cy})${c.g.across ? '' : ' rotate(90)'}`}>
      <circle r={7} /><path d={d} />
    </g>
  )
}

function ports(c: Ctx, s: Stage, m: Marks): ReactNode[] {
  const out = outPorts(c, s, m.outLabels.get(s.id))
  const fan = m.forks.get(s.id)
  if (fan) out.push(fanMark(c, 'fork', !fan.matched))
  if (m.joins.has(s.id)) out.push(fanMark(c, 'join', false))
  return out
}

/** An AI node's card: its corners cut by `c`, inset by `i` (docs/STUDIO.md D11). */
function chamfer(i: number, c: number): string {
  const corners = [[i + c, i], [NODE_W - i - c, i], [NODE_W - i, i + c], [NODE_W - i, NODE_H - i - c], [NODE_W - i - c, NODE_H - i],
    [i + c, NODE_H - i], [i, NODE_H - i - c], [i, i + c]]
  return corners.map(String).join(' ')
}

/** Where a stage starts in the code: its file's name, and its line when known. */
function entryOf(s: Stage): string | null {
  if (!s.entry.path) return null
  const file = s.entry.path.split('/').pop() ?? ''
  return s.entry.line ? file + ':' + s.entry.line : file
}

interface StageDraw { id: string; s: Stage | null; label: string; kind: Stage['kind']; at: At; sub: string | null; op: Op | undefined; isNew?: boolean }

function drawNodes(c: Ctx, added: Map<string, At>, m: Marks): ReactNode[] {
  const out: ReactNode[] = []
  for (const s of c.scope.stages) {
    const at = c.g.at.get(s.id)
    if (at) out.push(drawStage(c, m, stageDraw(c, s, at)))
  }
  for (const s of c.scope.added) {
    const at = added.get(s.id)
    if (at) out.push(drawStage(c, m, { id: s.id, s: null, label: s.label, kind: 'stage', at, sub: s.rule ? `${c.w('rule')} ${s.rule}` : null, op: s.op, isNew: true }))
  }
  return out
}

/** A stage of today: its name in this view, and the line under it (a router's question, the tools, or its file). */
function stageDraw(c: Ctx, s: Stage, at: At): StageDraw {
  const ideal = c.view === 'ideal' ? c.scope.ideal.get(s.id) : undefined
  const router = s.kind === 'router' ? c.scope.routerOf.get(s.id) : undefined
  const sub = router ? `${router.on} · ${c.w('branchesN', { n: router.branches.length })}` : s.tools.length ? s.tools.join(' · ') : entryOf(s)
  return { id: s.id, s, label: ideal?.label && ideal.label !== s.label ? ideal.label : stageTitle(s, c.lang), kind: s.kind, at, sub, op: c.op.get(s.id) }
}

function drawStage(c: Ctx, m: Marks, d: StageDraw): ReactNode {
  const { id, at } = d
  if (c.culled && !c.inView(at)) return null
  return (
    <g key={id} className={stageClass(c, d)} transform={`translate(${at.x},${at.y})`} {...c.target(at, stageAria(c, d), () => c.onSelect(id), { pressed: id === c.selected })} onClick={() => c.onSelect(id)}>
      {stageShape(d.kind)}
      {d.kind === 'ai' && <polygon className={css.aiRing} points={chamfer(3, 10)} />}
      {d.op === 'delete' && <rect width={NODE_W} height={NODE_H} rx={10} fill="url(#pp-hatch)" opacity={0.5} />}
      {c.dead.has(id) && c.showHidden && <rect width={NODE_W} height={NODE_H} rx={10} fill="url(#pp-ghost)" />}
      {stageText(c, d)}
      {stageBadges(c, d, m)}
    </g>
  )
}

function stageClass(c: Ctx, d: StageDraw): string {
  const { id, s, kind, op } = d
  return [css.node, css[`k_${kind}`], op && op !== 'retain' && css[`op_${op}`], op === 'retain' && c.view === 'ideal' && css.op_retain,
    c.dead.has(id) && c.showHidden && css.dead, s?.optional && css.optional, id === c.selected && css.sel, c.dim(id) && css.dim].filter(Boolean).join(' ')
}

function stageAria(c: Ctx, d: StageDraw): string {
  const { kind, op, s } = d
  const router = kind === 'router' ? c.scope.routerOf.get(d.id) : undefined
  return [c.w(KIND_WORD[kind]), d.label, d.sub, op && c.view !== 'current' ? c.w(OP_WORD[op]) : null,
    router ? c.w('branchesN', { n: router.branches.length }) : null, s?.sub_pipeline ? c.w('lgSub') : null].filter(Boolean).join(' · ')
}

function stageShape(kind: Stage['kind']): ReactNode {
  if (kind === 'router') return <polygon className={css.box} points={`${NODE_W / 2},-6 ${NODE_W + 4},${NODE_H / 2} ${NODE_W / 2},${NODE_H + 6} -4,${NODE_H / 2}`} />
  if (kind === 'ai') return <polygon className={css.box} points={chamfer(0, 12)} />
  return <rect className={css.box} width={NODE_W} height={NODE_H} rx={kind === 'source' || kind === 'sink' ? NODE_H / 2 : 10} />
}

/** The stage's name and, under it, its line: centred in a router's diamond, else from the reading side. */
function stageText(c: Ctx, d: StageDraw): ReactNode {
  const { kind, sub } = d
  const router = kind === 'router'
  const ar = c.lang === 'ar'
  return <>
    <text x={router ? NODE_W / 2 : ar ? NODE_W - 12 : 12} direction={ar ? 'rtl' : 'ltr'} y={sub ? 22 : 31} textAnchor={router ? 'middle' : 'start'} className={css.title}>
      {kind === 'ai' && <tspan className={css.aiGlyph}>✦ </tspan>}{fit(d.label, router ? 15 : 18)}
    </text>
    {sub && <text x={router ? NODE_W / 2 : 12} y={39} textAnchor={router ? 'middle' : 'start'} className={css.sub}>{clip(sub, router ? 20 : 24)}</text>}
  </>
}

/** The stage's marks: a sub-pipeline, up to two marks, new in the ideal, its gap numbers, and its ports. */
function stageBadges(c: Ctx, d: StageDraw, m: Marks): ReactNode {
  const { s } = d
  const nos = c.gapNo.get(d.id)
  const width = nos ? Math.max(22, 14 + nos.length * 9) : 0
  return <>
    {s?.sub_pipeline && <g className={css.subMark} transform={`translate(${NODE_W - 22},8)`}><rect width={14} height={10} rx={2} /><rect x={3} y={3} width={14} height={10} rx={2} /></g>}
    {(s?.marks ?? []).filter((mark) => mark !== 'ai').slice(0, 2).map((mark, i) => <circle key={mark} cx={NODE_W - 12 - i * 10} cy={NODE_H - 10} r={3.2} className={css[`mark_${mark}`]}><title>{c.w.known('mark_', mark)}</title></circle>)}
    {d.isNew && <text x={NODE_W - 10} y={16} textAnchor="end" className={css.newTag}>+</text>}
    {nos && <g className={css.gapBadge} transform={`translate(${d.kind === 'router' ? NODE_W / 2 - 11 : -9},-9)`}><rect width={width} height={18} rx={9} /><text x={width / 2} y={13} textAnchor="middle">{nos.slice(0, 3).join(',')}</text></g>}
    {s && ports(c, s, m)}
  </>
}

/** The legend's box: inline under the phone's preview, or a folding panel over the canvas's corner. */
function Wrap({ inline, label, children }: { inline?: boolean; label: string; children: ReactNode }) {
  if (inline) return <div className={[frame.legend, frame.legendInline].join(' ')} role="note" aria-label={label}>{children}</div>
  return (
    <details className={[frame.legend, css.fold].join(' ')} open>
      <summary className={css.foldHead}>{label}</summary>
      {children}
    </details>
  )
}

/** The legend's rows in order: whether this drawing holds it, its word and its sample. */
function legendRows(kinds: Set<string>, scope: Scope, view: View, hidden: boolean): [boolean, PipelineWord, ReactNode][] {
  const line = (cls: string) => <svg className={frame.lgLine} aria-hidden="true"><path d="M1,5h28" className={cls} /></svg>
  const box = (...cls: string[]) => <span className={cls.join(' ')} />
  return [
    [true, 'lgStage', box(css.lgBox)],
    [kinds.has('router'), 'lgRouter', box(css.lgDiamond)],
    [kinds.has('ai'), 'lgAi', box(css.lgBox, css.lgAi)],
    [scope.fans.length > 0, 'lgFork', box(css.lgFork)],
    [scope.stages.some((s) => s.sub_pipeline), 'lgSub', box(css.lgSub)],
    [true, 'lgData', line(css.lgData)],
    [scope.routers.length > 0 || scope.edges.some((e) => e.kind === 'control' || e.matched_by === 'order'), 'lgControl', line(css.lgControl)],
    [scope.errors.length > 0, 'lgError', line(css.lgError)],
    [hidden && scope.hidden.some((h) => h.kind !== 'dead_stage'), 'lgHidden', line(css.lgHidden)],
    [hidden && scope.hidden.some((h) => h.kind === 'dead_stage'), 'lgDead', box(css.lgBox, css.lgDead)],
    [scope.unresolved.length > 0 && view !== 'ideal', 'lgGap', box(css.lgGap)],
  ]
}

/** The legend: only what this drawing holds. */
export function Legend({ kinds, scope, view, hidden, inline }: { kinds: Set<string>; scope: Scope; view: View; hidden: boolean; inline?: boolean }) {
  const w = usePipelineWords()
  const ops = view === 'current' ? [] : [...new Set([...(view === 'ideal' ? [...scope.ideal.values()].map((s) => s.op) : scope.gap.map((g) => g.operation))])].filter((o) => o !== 'retain')
  return (
    <Wrap inline={inline} label={w('legend')}>
      {legendRows(kinds, scope, view, hidden).map(([shown, word, sample]) => shown && <div key={word} className={frame.lgRow}>{sample}{w(word)}</div>)}
      {ops.map((o) => <div key={o} className={frame.lgRow}><span className={[frame.sw, css[`sw_${o}`] ?? frame[`sw_${o}`]].join(' ')} />{w(OP_WORD[o])}</div>)}
    </Wrap>
  )
}
