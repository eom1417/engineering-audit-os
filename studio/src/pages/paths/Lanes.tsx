// The swimlane diagram: seven lanes from the screen to the data, the boxes where EAOS placed them (studio/paths.json
// columns), the links between them. Used for one path (every step) and for the overview (clusters). Pan with a drag,
// zoom with the wheel, a pinch or the buttons (the map's own useZoom); every box is a button for the keyboard.
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { useZoom } from '../../map/useZoom'
import { usePhone } from '../SystemMap'
import { FitIcon } from '../../map/parts'
import zoomCss from '../../map/parts.module.css'
import { useMapWords } from '../../map/words'
import { curve, geometry, NODE_H, NODE_W, type Lane, type PathMode, type PathOp } from './model'
import { LANE_WORD, OP_WORD, usePathWords } from './words'
import css from './paths.module.css'

export interface DrawNode {
  id: string
  lane: Lane
  title: string
  sub?: string | null
  kind: 'step' | 'gap' | 'table' | 'store' | 'external' | 'group'
  op?: PathOp | null
  dim?: boolean
  count?: number
  aria: string
}

export interface DrawEdge { key: string; from: string; to: string; style: 'solid' | 'possible' | 'gap'; dim?: boolean; width?: number }

const KIND_CLASS: Record<DrawNode['kind'], string | undefined> = {
  step: undefined, gap: css.gap, table: css.kindTable, store: css.kindStore, external: css.kindExternal, group: css.kindGroup,
}

/** A sentence too long for its box: cut at its end. */
function clip(text: string, room: number): string {
  return text.length <= room ? text : text.slice(0, room - 1) + '…'
}

/** "…/pages/DriversPage.tsx" for a label too long for its box (identifiers keep their end). */
function fit(text: string, room: number): string {
  if (text.length <= room) return text
  const tail = text.slice(-(room - 1))
  const cut = tail.indexOf('/')
  return '…' + (cut > 0 && cut < tail.length - 6 ? tail.slice(cut) : tail)
}

function useSize(ref: React.RefObject<HTMLElement | null>) {
  const [size, setSize] = useState({ w: 0, h: 0 })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const update = () => setSize({ w: el.clientWidth, h: el.clientHeight })
    update()
    const watch = new ResizeObserver(update)
    watch.observe(el)
    return () => watch.disconnect()
  }, [ref])
  return size
}

export interface LanesProps {
  columns: string[][]
  nodes: Map<string, DrawNode>
  edges: DrawEdge[]
  mode: PathMode
  selected?: string
  onSelect: (id: string) => void
  label: string
  /** The toolbar's rows above the canvas */
  title?: ReactNode
  head?: ReactNode
  legend?: 'float' | 'none'
  className?: string
  /** Centre on this node when it changes */
  centreOn?: string
}

export function Lanes({ columns, nodes, edges, mode, selected, onSelect, label, title, head, legend = 'float', className, centreOn }: LanesProps) {
  const w = usePathWords()
  const mw = useMapWords()
  const svg = useRef<SVGSVGElement>(null)
  const box = useRef<HTMLDivElement>(null)
  const size = useSize(box)
  const zoom = useZoom(svg)
  const g = useMemo(() => geometry(columns), [columns])
  const { setT } = zoom
  const phone = usePhone()
  const fitView = useMemo(() => {
    // on a phone the boxes stay at their size (44px targets) and the person pans; elsewhere the lanes fit the width
    const k = size.w && !phone ? Math.max(0.55, Math.min(1, (size.w - 24) / g.width, (size.h - 12) / g.height)) : 1
    return { k, x: size.w ? Math.max(12, (size.w - g.width * k) / 2) : 0, y: 6 }
  }, [size.w, size.h, g.width, g.height, phone])
  useEffect(() => { setT(fitView) }, [fitView, setT])
  useEffect(() => {
    const at = centreOn ? g.at.get(centreOn) : undefined
    if (at && size.w) setT((cur) => ({ k: Math.max(cur.k, 0.9), x: size.w / 2 - (at.x + NODE_W / 2) * Math.max(cur.k, 0.9), y: size.h / 2 - (at.y + NODE_H / 2) * Math.max(cur.k, 0.9) }))
  }, [centreOn, g, size.w, size.h, setT])

  const linked = useMemo(() => {
    const on = new Set<string>()
    if (selected) for (const e of edges) if (e.from === selected || e.to === selected) on.add(e.key)
    return on
  }, [edges, selected])
  const ops = useMemo(() => [...new Set([...nodes.values()].map((n) => n.op).filter(Boolean))] as PathOp[], [nodes])
  const hasPossible = edges.some((e) => e.style === 'possible')
  const hasGap = [...nodes.values()].some((n) => n.kind === 'gap')

  return (
    <div className={[css.canvasWrap, className].filter(Boolean).join(' ')}>
      {(title || head) && (
        <div className={css.toolbar}>
          {title}
          <div className={css.toolRow}>
            {head}
            <span className={css.spacer} />
            <div className={zoomCss.zoom} role="group" aria-label={mw('zoom')}>
              <AriaButton className={zoomCss.zoomBtn} aria-label={mw('zoomOut')} onPress={() => zoom.zoomBy(1 / 1.3)}><span aria-hidden="true">−</span></AriaButton>
              <AriaButton className={zoomCss.zoomBtn} aria-label={mw('zoomIn')} onPress={() => zoom.zoomBy(1.3)}><span aria-hidden="true">+</span></AriaButton>
              <AriaButton className={zoomCss.zoomBtn} aria-label={mw('zoomFit')} onPress={() => setT(fitView)}><FitIcon /></AriaButton>
            </div>
          </div>
        </div>
      )}
      <div className={css.canvas} ref={box}>
        <svg ref={svg} className={css.canvasSvg} viewBox={`0 0 ${Math.max(size.w, 1)} ${Math.max(size.h, 1)}`} preserveAspectRatio="xMinYMin meet"
          direction="ltr" role="group" aria-label={label} data-dragging={zoom.dragging ? '' : undefined}>
          <defs>
            <pattern id="paths-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" className={css.hatchBg} /><line x1="0" y1="0" x2="0" y2="6" className={css.hatchLine} />
            </pattern>
            <marker id="paths-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L8,4 L0,8 z" className={css.arrow} />
            </marker>
            <marker id="paths-arrow-on" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L8,4 L0,8 z" className={css.arrowOn} />
            </marker>
          </defs>
          <g transform={`translate(${zoom.t.x},${zoom.t.y}) scale(${zoom.t.k})`}>
            {g.lanes.map((l, i) => (
              <g key={l.lane}>
                <rect x={l.x} y={0} width={l.w} height={g.height} className={i % 2 ? css.laneBandAlt : css.laneBand} />
                <line x1={l.x} y1={0} x2={l.x} y2={g.height} className={css.laneLine} />
                <text x={l.x + l.w / 2} y={20} textAnchor="middle" className={css.laneHead}>{l.count ? w(LANE_WORD[l.lane]) : '·'}</text>
                {l.count > 0 && <text x={l.x + l.w / 2} y={34} textAnchor="middle" className={css.laneCount}>{l.count}</text>}
              </g>
            ))}
            {edges.map((e) => {
              const a = g.at.get(e.from)
              const b = g.at.get(e.to)
              if (!a || !b) return null
              const on = linked.has(e.key)
              const cls = [css.edge, e.style === 'possible' && css.possible, e.style === 'gap' && css.toGap, on && css.on,
                selected && !on && css.edgeDim, e.dim && css.edgeDim].filter(Boolean).join(' ')
              return <path key={e.key} d={curve(a, b)} className={cls} strokeWidth={on ? 2 : e.width} markerEnd={`url(#${on ? 'paths-arrow-on' : 'paths-arrow'})`} />
            })}
            {[...g.at.entries()].map(([id, at]) => {
              const n = nodes.get(id)
              if (!n) return null
              const cls = [css.node, KIND_CLASS[n.kind], n.op && mode === 'change' && css[`op_${n.op}`], mode === 'target' && n.op === 'delete' && css.op_delete,
                id === selected && css.sel, n.dim && css.dim].filter(Boolean).join(' ')
              const room = n.count !== undefined ? 16 : 20
              return (
                <g key={id} className={cls} transform={`translate(${at.x},${at.y})`} role="button" tabIndex={0} aria-label={n.aria}
                  aria-pressed={id === selected} onClick={() => onSelect(id)}
                  onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onSelect(id) } }}>
                  <rect className={css.box} width={NODE_W} height={NODE_H} rx={8} />
                  {n.op === 'delete' && (mode === 'change' || mode === 'target') && <rect width={NODE_W} height={NODE_H} rx={8} fill="url(#paths-hatch)" opacity={0.5} />}
                  {n.kind === 'gap' && <text x={NODE_W - 12} y={28} textAnchor="middle" className={css.gapMark}>?</text>}
                  <text x={10} y={n.sub ? 18 : 27} className={css.nodeTitle}>{fit(n.title, room)}</text>
                  {n.sub && <text x={10} y={34} className={css.nodeSub}>{clip(n.sub, 26)}</text>}
                  {n.count !== undefined && <text x={NODE_W - 10} y={27} textAnchor="end" className={css.nodeCount}>{n.count}</text>}
                </g>
              )
            })}
          </g>
        </svg>
        {legend === 'float' && <Legend mode={mode} ops={ops} possible={hasPossible} gap={hasGap} />}
      </div>
    </div>
  )
}

export function Legend({ mode, ops, possible, gap, inline }: { mode: PathMode; ops: PathOp[]; possible: boolean; gap: boolean; inline?: boolean }) {
  const w = usePathWords()
  return (
    <div className={[css.legend, inline && css.legendInline].filter(Boolean).join(' ')}>
      <div className={css.lgRow}><svg className={css.lgLine} aria-hidden="true"><path d="M1,4h28" className={css.lgSolid} /></svg>{w('traced')}</div>
      {possible && <div className={css.lgRow}><svg className={css.lgLine} aria-hidden="true"><path d="M1,4h28" className={css.lgPossible} /></svg>{w('possibleLink')}</div>}
      {gap && <div className={css.lgRow}><span className={[css.sw, css.sw_gap].join(' ')} />{w('gapLegend')}</div>}
      {mode === 'change' && ops.map((op) => <div key={op} className={css.lgRow}><span className={[css.sw, css[`sw_${op}`]].join(' ')} />{w(OP_WORD[op])}</div>)}
      {mode === 'target' && <div className={css.lgRow}>{w('legendTarget')}</div>}
    </div>
  )
}
