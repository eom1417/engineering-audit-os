// The pipeline drawn as a flowchart: the stages where EAOS placed them (layer, order), left to right on a wide screen
// and top to bottom on the phone. Stages are cards with their tools; routers are diamonds whose branches carry their
// condition; forks and joins are marked on the card's sides; failures run in their own lane; hidden side channels are
// dotted and appear only when asked; what EAOS could not follow is a gap beside its stage. Pan with a drag, zoom with
// the wheel, a pinch or the buttons (the map's useZoom); a long pipeline draws only what is in view.
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { FitIcon } from '../../map/parts'
import zoomCss from '../../map/parts.module.css'
import { useZoom } from '../../map/useZoom'
import { useMapWords } from '../../map/words'
import { geometry, link, NODE_H, NODE_W, PILL_W, type At, type Op, type Scope, type Stage, type View } from './model'
import { KIND_WORD, OP_WORD, usePipelineWords } from './words'
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

/** The box a stage's text must fit in: a long identifier keeps its end. */
function fit(text: string, room: number): string {
  return text.length <= room ? text : '…' + text.slice(-(room - 1))
}

function clip(text: string, room: number): string {
  return text.length <= room ? text : text.slice(0, room - 1) + '…'
}

/** The pixel size of the drawing's box, followed as it changes. */
function useBox(): [(el: HTMLDivElement | null) => void, { w: number; h: number }] {
  const [size, setSize] = useState({ w: 0, h: 0 })
  const watcher = useRef<ResizeObserver | null>(null)
  const attach = useCallback((el: HTMLDivElement | null) => {
    watcher.current?.disconnect()
    if (!el) return
    watcher.current = new ResizeObserver(([entry]) => setSize({ w: entry.contentRect.width, h: entry.contentRect.height }))
    watcher.current.observe(el)
  }, [])
  return [attach, size]
}

const MARGIN = 260

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

export function Flowchart({ scope, view, down, selected, onSelect, hidden, lit, label, title, head, legend = true, className }: FlowchartProps) {
  const w = usePipelineWords()
  const mw = useMapWords()
  const svg = useRef<SVGSVGElement>(null)
  const [attach, size] = useBox()
  const zoom = useZoom(svg)
  const { setT } = zoom
  const showHidden = hidden || view === 'gap'
  const g = useMemo(() => geometry(scope.stages, scope.errors, down), [scope.stages, scope.errors, down])
  const { op, gapNo } = useMemo(() => stageState(scope, view), [scope, view])

  // the ideal's new stages have no place today: they stand after the last layer, one under the other
  const added = useMemo(() => {
    const at = new Map<string, At>()
    if (view !== 'ideal') return at
    const end = down ? g.height : g.width
    scope.added.forEach((s, i) => at.set(s.id, down ? { x: 28 + i * (NODE_W + 24), y: end + 24 } : { x: end + 24, y: 28 + i * (NODE_H + 30) }))
    return at
  }, [scope.added, view, down, g.width, g.height])
  const world = useMemo(() => {
    if (!added.size) return { w: g.width, h: g.height }
    const xs = [...added.values()]
    return { w: Math.max(g.width, ...xs.map((p) => p.x + NODE_W + 28)), h: Math.max(g.height, ...xs.map((p) => p.y + NODE_H + 28)) }
  }, [added, g.width, g.height])
  const place = (id: string) => g.at.get(id) ?? added.get(id)

  // the first view: the whole pipeline when it reads at that size, else its start, readable, to pan along;
  // the fit button always shows the whole of it
  const { fitView, wholeView } = useMemo(() => {
    if (!size.w) return { fitView: { k: 1, x: 0, y: 0 }, wholeView: { k: 1, x: 0, y: 0 } }
    const k = Math.min(1, (size.w - 16) / world.w, (size.h - 16) / world.h)
    const whole = { k, x: Math.max(8, (size.w - world.w * k) / 2), y: Math.max(8, (size.h - world.h * k) / 2) }
    if (k >= (down ? 0.62 : 0.6)) return { fitView: whole, wholeView: whole }
    const start = down ? Math.min(1, Math.max(0.62, (size.w - 16) / world.w)) : 0.85
    return { fitView: { k: start, x: down ? Math.max(8, (size.w - world.w * start) / 2) : 8, y: 8 }, wholeView: whole }
  }, [size.w, size.h, world.w, world.h, down])
  useEffect(() => { setT(fitView) }, [fitView, setT])

  // the window in view, in the drawing's units: only what crosses it is drawn
  const t = zoom.t
  const view0 = { x0: -t.x / t.k - MARGIN, y0: -t.y / t.k - MARGIN, x1: (size.w - t.x) / t.k + MARGIN, y1: (size.h - t.y) / t.k + MARGIN }
  const inView = (p: At | undefined) => !!p && p.x + NODE_W >= view0.x0 && p.x <= view0.x1 && p.y + NODE_H >= view0.y0 && p.y <= view0.y1
  // a stage wholly in the visible box is a button; one cut by the canvas's edge is still drawn and clickable, but not a
  // keyboard stop, so no target hides under the page's chrome (the steps list reaches every stage)
  const whole = (p: At, w = NODE_W, h = NODE_H) => size.w > 0 && p.x * t.k + t.x >= 0 && (p.x + w) * t.k + t.x <= size.w && p.y * t.k + t.y >= 0 && (p.y + h) * t.k + t.y <= size.h
  const target = (p: At, label: string, pressed: boolean | undefined, act: () => void, w?: number, h?: number) => whole(p, w, h)
    ? { role: 'button', tabIndex: 0, 'aria-label': label, 'aria-pressed': pressed, onKeyDown: (ev: React.KeyboardEvent) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); act() } } }
    : { 'aria-hidden': true }
  const culled = scope.stages.length > 200

  const near = useMemo(() => {
    const on = new Set<string>()
    if (selected) for (const e of scope.edges) if (e.from === selected || e.to === selected) on.add(e.id)
    return on
  }, [scope.edges, selected])
  const dead = useMemo(() => new Set(scope.hidden.filter((h) => h.kind === 'dead_stage').flatMap((h) => h.stages)), [scope.hidden])
  const forks = useMemo(() => new Map(scope.fans.map((f) => [f.fork, f])), [scope.fans])
  const joins = useMemo(() => new Set(scope.fans.map((f) => f.join).filter(Boolean) as string[]), [scope.fans])
  const dim = (id: string) => (lit && !lit.stages.has(id)) || (view === 'gap' && gapNo.size > 0 && !gapNo.has(id))

  // the data each stage gives, written once beside its output port (the shape on the link)
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

  const edgesDrawn: ReactNode[] = []
  const labelsDrawn: ReactNode[] = []
  const drawLink = (key: string, from: string, to: string, cls: string, marker: string, extra?: { condition?: string | null; title?: string }) => {
    const a = place(from)
    const b = place(to)
    if (!a || !b) return
    if (culled && !inView(a) && !inView(b)) return
    const { d } = link(g, a, b)
    edgesDrawn.push(<path key={key} d={d} className={cls} markerEnd={marker ? `url(#${marker})` : undefined}>{extra?.title && <title>{extra.title}</title>}</path>)
    if (extra?.condition) {
      const x = g.across ? b.x - 6 : b.x + NODE_W / 2 + 6
      const y = g.across ? b.y + NODE_H / 2 - 7 : b.y - 8
      labelsDrawn.push(<text key={`c${key}`} x={x} y={y} textAnchor={g.across ? 'end' : 'start'} className={css.cond}>{clip(extra.condition, 18)}</text>)
    }
  }

  if (view === 'ideal') {
    scope.idealEdges.forEach((e, i) => {
      const on = selected && (e.from === selected || e.to === selected)
      drawLink(`i${i}`, e.from, e.to, [css.edge, e.op !== 'retain' && css[`eop_${e.op}`], on && css.on].filter(Boolean).join(' '), on ? 'pp-arrow-on' : e.op === 'new' ? 'pp-arrow-new' : 'pp-arrow')
    })
  } else {
    for (const e of scope.edges) {
      if (e.kind === 'hidden' && !showHidden) continue
      const on = near.has(e.id) || (lit?.edges.has(e.id) ?? false)
      const off = (lit && !lit.edges.has(e.id)) || (selected && !near.has(e.id) && !lit)
      const cls = [css.edge, css[`ek_${e.kind}`], e.matched_by === 'order' && css.orderOnly, on && css.on, off && css.edgeDim].filter(Boolean).join(' ')
      drawLink(e.id, e.from, e.to, cls, on ? 'pp-arrow-on' : e.kind === 'error' ? 'pp-arrow-err' : 'pp-arrow',
        { title: [e.data.shape, ...e.data.names].filter(Boolean).join(' · ') })
    }
  }

  // router branches: drawn when few, or when the router is chosen (a crowded router folds, DESIGN: above 8)
  for (const r of scope.routers) {
    if (r.branches.length > 8 && selected !== r.stage) continue
    r.branches.forEach((b, i) => {
      if (!b.to || b.to === r.stage) return
      const on = selected === r.stage
      drawLink(`${r.id}#${i}`, r.stage, b.to, [css.branch, on && css.on, lit && !lit.stages.has(b.to) && css.edgeDim].filter(Boolean).join(' '),
        on ? 'pp-arrow-on' : 'pp-arrow', { condition: b.condition })
    })
  }

  // the failure lane: its ends in a row, a short stub into an end reached from any stage, a curve from each stage
  // whose failures go there
  const lane = g.lane
  const laneParts: ReactNode[] = []
  if (lane) {
    laneParts.push(
      <g key="lane">
        <rect x={lane.x} y={lane.y} width={lane.w} height={lane.h} rx={10} className={css.lane} />
        <text x={lane.x + 14} y={lane.y + 24} className={css.laneTitle}>{w('failureLane')}</text>
      </g>,
    )
    for (const [name, at] of g.ends) {
      const routes = scope.errors.filter((e) => e.to === name)
      const conds = routes.map((e) => e.condition || w.known('err_', e.kind))
      const any = routes.some((e) => e.from === '*')
      laneParts.push(
        <g key={`end${name}`} transform={`translate(${at.x},${at.y})`}>
          {any && <path d="M-26,16 L-2,16" className={[css.edge, css.ek_error].join(' ')} markerEnd="url(#pp-arrow-err)" />}
          <rect width={PILL_W} height={32} rx={16} className={css.endPill} />
          <text x={PILL_W / 2} y={21} textAnchor="middle" className={css.endText}>{fit(name, 18)}</text>
          <text x={PILL_W / 2} y={48} textAnchor="middle" className={css.endCond}>{any ? `${w('fromAny')} · ` : ''}{clip(conds.join(' · '), any ? 16 : 26)}<title>{conds.join(' · ')}</title></text>
        </g>,
      )
    }
    for (const e of scope.errors) {
      const end = g.ends.get(e.to)
      const a = e.from === '*' ? undefined : g.at.get(e.from)
      if (!end || !a || (culled && !inView(a))) continue
      const sx = a.x + NODE_W / 2
      const sy = a.y + NODE_H
      const ex = end.x + PILL_W / 2
      const my = (sy + end.y) / 2
      edgesDrawn.push(<path key={`err${e.id}`} d={`M${sx},${sy} C${sx},${my} ${ex},${my} ${ex},${end.y}`}
        className={[css.edge, css.ek_error, selected && selected !== e.from && css.edgeDim].filter(Boolean).join(' ')} markerEnd="url(#pp-arrow-err)" />)
    }
  }

  // hidden: side channels as a dotted thread through their stages, unread outputs as a dotted stub to nowhere
  const hiddenParts: ReactNode[] = []
  if (showHidden && view !== 'ideal') {
    const starts = new Map<string, number>()
    for (const h of scope.hidden) {
      const pts = h.stages.map((id) => g.at.get(id)).filter(Boolean) as At[]
      if (!pts.length || (culled && !pts.some(inView))) continue
      const centre = (p: At) => `${p.x + NODE_W / 2},${p.y + NODE_H / 2}`
      if (h.kind === 'side_channel' && pts.length > 1) {
        const nth = starts.get(h.stages[0]) ?? 0
        starts.set(h.stages[0], nth + 1)
        hiddenParts.push(
          <g key={h.id} className={css.hiddenThread}>
            <path d={`M${pts.map(centre).join(' L')}`} />
            <text x={pts[0].x + 4} y={pts[0].y - 8 - nth * 14} className={css.hiddenTag}>{clip(h.name, 26)}</text>
          </g>,
        )
      } else if (h.kind === 'unread_output') {
        const p = pts[0]
        const x = g.across ? p.x + NODE_W : p.x + NODE_W / 2
        const y = g.across ? p.y + NODE_H - 8 : p.y + NODE_H
        hiddenParts.push(
          <g key={h.id} className={css.hiddenThread}>
            <path d={g.across ? `M${x},${y} l34,22` : `M${x},${y} l22,30`} />
            <circle cx={g.across ? x + 40 : x + 26} cy={g.across ? y + 26 : y + 36} r={5} className={css.voidDot} />
            <text x={g.across ? x + 50 : x + 36} y={g.across ? y + 30 : y + 40} className={css.hiddenTag}>{clip(h.name, 24)}</text>
          </g>,
        )
      }
    }
  }

  // what EAOS could not follow: a gap box hanging under (or beside) its stage
  const gapParts: ReactNode[] = []
  if (view !== 'ideal') {
    for (const u of scope.unresolved) {
      const p = g.at.get(u.stage)
      if (!p || (culled && !inView(p))) continue
      const gx = g.across ? p.x + 18 : p.x + NODE_W + 14
      const gy = g.across ? p.y + NODE_H + 14 : p.y + 8
      gapParts.push(
        <g key={u.id} className={css.gapNode} {...target({ x: gx, y: gy }, `${w('gapNode')}: ${u.call}. ${u.reason}`, undefined, () => onSelect(u.stage), NODE_W - 36, 28)} onClick={() => onSelect(u.stage)}>
          <path d={g.across ? `M${p.x + 30},${p.y + NODE_H} L${gx + 12},${gy}` : `M${p.x + NODE_W},${p.y + NODE_H / 2} L${gx},${gy + 14}`} className={css.gapLink} />
          <rect x={gx} y={gy} width={NODE_W - 36} height={28} rx={6} />
          <text x={gx + 10} y={gy + 18} className={css.gapText}>? {fit(u.call, 15)}</text>
        </g>,
      )
    }
  }

  const ports = (s: Stage) => {
    const out: ReactNode[] = []
    const labels = outLabels.get(s.id)
    const crowded = !!selected && (scope.routerOf.get(selected)?.branches.length ?? 0) > 0   // a chosen router writes its conditions there
    if (labels && view !== 'ideal' && !dim(s.id) && !crowded) {
      labels.slice(0, 2).forEach((text, i) => {
        const x = g.across ? NODE_W + 6 : NODE_W / 2 + 8
        const y = g.across ? NODE_H / 2 - 4 - i * 14 : NODE_H + 14 + i * 13
        out.push(<text key={`o${i}`} x={x} y={y} className={css.shape}>{clip(text, g.across ? 13 : 20)}</text>)
      })
    }
    const fan = forks.get(s.id)
    if (fan) {
      const [cx, cy] = g.across ? [NODE_W, NODE_H / 2] : [NODE_W / 2, NODE_H]
      out.push(<g key="fork" className={[css.fanMark, !fan.matched && css.fanOpen].filter(Boolean).join(' ')} transform={`translate(${cx},${cy})${g.across ? '' : ' rotate(90)'}`}>
        <circle r={7} /><path d="M-3,0 L3,-3 M-3,0 L3,3 M-3,0 L3,0" /></g>)
    }
    if (joins.has(s.id)) {
      const [cx, cy] = g.across ? [0, NODE_H / 2] : [NODE_W / 2, 0]
      out.push(<g key="join" className={css.fanMark} transform={`translate(${cx},${cy})${g.across ? '' : ' rotate(90)'}`}><circle r={7} /><path d="M-3,-3 L3,0 M-3,3 L3,0 M-3,0 L3,0" /></g>)
    }
    return out
  }

  const nodes: ReactNode[] = []
  const drawStage = (id: string, s: Stage | null, labelText: string, kind: Stage['kind'], at: At, sub: string | null, opOf: Op | undefined, extra?: { isNew?: boolean }) => {
    if (culled && !inView(at)) return
    const cls = [css.node, css[`k_${kind}`], opOf && opOf !== 'retain' && css[`op_${opOf}`], opOf === 'retain' && view === 'ideal' && css.op_retain,
      dead.has(id) && showHidden && css.dead, s?.optional && css.optional, id === selected && css.sel, dim(id) && css.dim].filter(Boolean).join(' ')
    const router = kind === 'router' ? scope.routerOf.get(id) : undefined
    const nos = gapNo.get(id)
    const aria = [w(KIND_WORD[kind]), labelText, sub, opOf && view !== 'current' ? w(OP_WORD[opOf]) : null,
      router ? w('branchesN', { n: router.branches.length }) : null, s?.sub_pipeline ? w('lgSub') : null].filter(Boolean).join(' · ')
    const shape = kind === 'router'
      ? <polygon className={css.box} points={`${NODE_W / 2},-6 ${NODE_W + 4},${NODE_H / 2} ${NODE_W / 2},${NODE_H + 6} -4,${NODE_H / 2}`} />
      : <rect className={css.box} width={NODE_W} height={NODE_H} rx={kind === 'source' || kind === 'sink' ? NODE_H / 2 : 10} />
    nodes.push(
      <g key={id} className={cls} transform={`translate(${at.x},${at.y})`} {...target(at, aria, id === selected, () => onSelect(id))} onClick={() => onSelect(id)}>
        {shape}
        {kind === 'ai' && <rect className={css.aiRing} x={3} y={3} width={NODE_W - 6} height={NODE_H - 6} rx={8} />}
        {opOf === 'delete' && <rect width={NODE_W} height={NODE_H} rx={10} fill="url(#pp-hatch)" opacity={0.5} />}
        {dead.has(id) && showHidden && <rect width={NODE_W} height={NODE_H} rx={10} fill="url(#pp-ghost)" />}
        <text x={kind === 'router' ? NODE_W / 2 : 12} y={sub ? 22 : 31} textAnchor={kind === 'router' ? 'middle' : 'start'} className={css.title}>
          {kind === 'ai' && <tspan className={css.aiGlyph}>✦ </tspan>}{fit(labelText, kind === 'router' ? 15 : 18)}
        </text>
        {sub && <text x={kind === 'router' ? NODE_W / 2 : 12} y={39} textAnchor={kind === 'router' ? 'middle' : 'start'} className={css.sub}>{clip(sub, kind === 'router' ? 20 : 24)}</text>}
        {s?.sub_pipeline && <g className={css.subMark} transform={`translate(${NODE_W - 22},8)`}><rect width={14} height={10} rx={2} /><rect x={3} y={3} width={14} height={10} rx={2} /></g>}
        {(s?.marks ?? []).filter((m) => m !== 'ai').slice(0, 2).map((m, i) => <circle key={m} cx={NODE_W - 12 - i * 10} cy={NODE_H - 10} r={3.2} className={css[`mark_${m}`]}><title>{w.known('mark_', m)}</title></circle>)}
        {extra?.isNew && <text x={NODE_W - 10} y={16} textAnchor="end" className={css.newTag}>+</text>}
        {nos && <g className={css.gapBadge} transform={`translate(${kind === 'router' ? NODE_W / 2 - 11 : -9},-9)`}><rect width={Math.max(22, 14 + nos.length * 9)} height={18} rx={9} /><text x={Math.max(22, 14 + nos.length * 9) / 2} y={13} textAnchor="middle">{nos.slice(0, 3).join(',')}</text></g>}
        {s && ports(s)}
      </g>,
    )
  }

  for (const s of scope.stages) {
    const at = g.at.get(s.id)
    if (!at) continue
    const ideal = view === 'ideal' ? scope.ideal.get(s.id) : undefined
    const router = s.kind === 'router' ? scope.routerOf.get(s.id) : undefined
    const sub = router ? `${router.on} · ${w('branchesN', { n: router.branches.length })}` : s.tools.length ? s.tools.join(' · ') : (s.entry.path ? `${s.entry.path.split('/').pop()}${s.entry.line ? `:${s.entry.line}` : ''}` : null)
    drawStage(s.id, s, ideal?.label ?? s.label, s.kind, at, sub, op.get(s.id))
  }
  for (const s of scope.added) {
    const at = added.get(s.id)
    if (at) drawStage(s.id, null, s.label, 'stage', at, s.rule ? `${w('rule')} ${s.rule}` : null, s.op, { isNew: true })
  }

  const kinds = new Set(scope.stages.map((s) => s.kind))
  return (
    <div className={[frame.canvasWrap, className].filter(Boolean).join(' ')}>
      {(title || head) && (
        <div className={frame.toolbar}>
          {title}
          <div className={frame.toolRow}>
            {head}
            <span className={frame.spacer} />
            <div className={zoomCss.zoom} role="group" aria-label={mw('zoom')}>
              <AriaButton className={zoomCss.zoomBtn} aria-label={mw('zoomOut')} onPress={() => zoom.zoomBy(1 / 1.3)}><span aria-hidden="true">−</span></AriaButton>
              <AriaButton className={zoomCss.zoomBtn} aria-label={mw('zoomIn')} onPress={() => zoom.zoomBy(1.3)}><span aria-hidden="true">+</span></AriaButton>
              <AriaButton className={zoomCss.zoomBtn} aria-label={mw('zoomFit')} onPress={() => setT(wholeView)}><FitIcon /></AriaButton>
            </div>
          </div>
        </div>
      )}
      <div className={frame.canvas} ref={attach}>
        <svg ref={svg} className={frame.canvasSvg} viewBox={`0 0 ${Math.max(size.w, 1)} ${Math.max(size.h, 1)}`} preserveAspectRatio="xMinYMin meet"
          direction="ltr" role="group" aria-label={label} data-dragging={zoom.dragging ? '' : undefined}>
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
          <g transform={`translate(${t.x},${t.y}) scale(${t.k})`}>
            {laneParts}
            {hiddenParts}
            {edgesDrawn}
            {gapParts}
            {nodes}
            {labelsDrawn}
          </g>
        </svg>
        {legend && <Legend kinds={kinds} scope={scope} view={view} hidden={showHidden} />}
      </div>
    </div>
  )
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

/** The legend: only what this drawing holds. */
export function Legend({ kinds, scope, view, hidden, inline }: { kinds: Set<string>; scope: Scope; view: View; hidden: boolean; inline?: boolean }) {
  const w = usePipelineWords()
  const ops = view === 'current' ? [] : [...new Set([...(view === 'ideal' ? [...scope.ideal.values()].map((s) => s.op) : scope.gap.map((g) => g.operation))])].filter((o) => o !== 'retain')
  const line = (cls: string) => <svg className={frame.lgLine} aria-hidden="true"><path d="M1,5h28" className={cls} /></svg>
  return (
    <Wrap inline={inline} label={w('legend')}>
      <div className={frame.lgRow}><span className={css.lgBox} />{w('lgStage')}</div>
      {kinds.has('router') && <div className={frame.lgRow}><span className={css.lgDiamond} />{w('lgRouter')}</div>}
      {kinds.has('ai') && <div className={frame.lgRow}><span className={[css.lgBox, css.lgAi].join(' ')} />{w('lgAi')}</div>}
      {scope.fans.length > 0 && <div className={frame.lgRow}><span className={css.lgFork} />{w('lgFork')}</div>}
      {scope.stages.some((s) => s.sub_pipeline) && <div className={frame.lgRow}><span className={css.lgSub} />{w('lgSub')}</div>}
      <div className={frame.lgRow}>{line(css.lgData)}{w('lgData')}</div>
      {(scope.edges.some((e) => e.kind === 'control' || e.matched_by === 'order') || scope.routers.length > 0) && <div className={frame.lgRow}>{line(css.lgControl)}{w('lgControl')}</div>}
      {scope.errors.length > 0 && <div className={frame.lgRow}>{line(css.lgError)}{w('lgError')}</div>}
      {hidden && scope.hidden.some((h) => h.kind !== 'dead_stage') && <div className={frame.lgRow}>{line(css.lgHidden)}{w('lgHidden')}</div>}
      {hidden && scope.hidden.some((h) => h.kind === 'dead_stage') && <div className={frame.lgRow}><span className={[css.lgBox, css.lgDead].join(' ')} />{w('lgDead')}</div>}
      {scope.unresolved.length > 0 && view !== 'ideal' && <div className={frame.lgRow}><span className={css.lgGap} />{w('lgGap')}</div>}
      {ops.map((o) => <div key={o} className={frame.lgRow}><span className={[frame.sw, css[`sw_${o}`] ?? frame[`sw_${o}`]].join(' ')} />{w(OP_WORD[o])}</div>)}
    </Wrap>
  )
}

