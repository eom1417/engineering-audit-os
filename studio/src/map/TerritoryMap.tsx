// The territory map (DESIGN.md §6), drawn from studio/system.json: land per region, import edges, dots sized by files,
// map-style labels placed by EAOS. Three variants from one drawing:
//   full     the interactive canvas: every dot a button, labels by priority, the focus ringed with its edges in accent
//            (arrowheads and import counts on them) and the rest faded
//   preview  the Home card and the phone: land, strong edges, dots, region names in large type
//   mini     the minimap: land and dots, and the frame of what the canvas shows
// The SVG is direction neutral (direction="ltr"): the page mirrors the chrome around it, never the geometry.
import { useId, useMemo, type KeyboardEvent } from 'react'
import type { CurrentNode, MapEdge, MapView, Operation, TargetNode } from '../data/system'
import { usePrefs } from '../i18n/prefs'
import { findingsBin, type MapMode } from './model'
import type { ZoomState } from './useZoom'
import { OP_WORD, useMapWords } from './words'
import css from './Map.module.css'

type AnyNode = CurrentNode | TargetNode
type Region = MapView<AnyNode>['regions'][number]
type Words = ReturnType<typeof useMapWords>
export type Variant = 'full' | 'preview' | 'mini' | 'compare'

export interface TerritoryMapProps {
  view: MapView<CurrentNode> | MapView<TargetNode>
  mode: MapMode
  variant: Variant
  focus?: string
  /** Ids lit from elsewhere (the counterpart on the other map) */
  lit?: string[]
  /** Only this operation at full strength (a number on the journey strip links here) */
  only?: Operation
  onFocus?: (id: string) => void
  transform?: ZoomState
  /** The world frame the canvas shows, drawn on the minimap */
  frame?: [number, number, number, number]
  label?: string
  className?: string
  svgRef?: React.Ref<SVGSVGElement>
  dragging?: boolean
  /** The "show hidden" lens: components holding unseen work get a dashed ring */
  marked?: Record<string, number>
}

/** How a node is drawn: by operation or by findings, and whether it is the focus, lit or faded. */
interface NodeLook {
  byOp: boolean
  focusId?: string
  lit: string[]
  dim: boolean
  only?: Operation
  near: Set<string>
  /** A focus or lit ids narrow the map to their neighbourhood */
  narrowed: boolean
}

function isCurrent(node: AnyNode): node is CurrentNode {
  return 'findings' in node
}

/** The strong edges a preview keeps: six imports or more, or the twelve heaviest when few reach six. */
function strongEdges(edges: MapEdge[]): MapEdge[] {
  const strong = edges.filter((e) => e.imports >= 6)
  return strong.length >= 8 ? strong : [...edges].sort((a, b) => b.imports - a.imports).slice(0, 12)
}

function isOn(n: AnyNode, look: NodeLook): boolean {
  return (look.only ? n.op === look.only : true) && (look.narrowed ? look.near.has(n.id) : true)
}

function nodeClass(n: AnyNode, look: NodeLook): string {
  return [
    css.node,
    look.byOp ? css[`op_${n.op}`] : css[`fb_${findingsBin(isCurrent(n) ? n.findings.total : 0)}`],
    look.focusId === n.id && css.sel,
    look.lit.includes(n.id) && css.lit,
    look.dim && !isOn(n, look) && css.faded,
  ].filter(Boolean).join(' ')
}

function nodeName(n: AnyNode, w: Words): string {
  return isCurrent(n)
    ? w('nodeAria', { id: n.id, files: n.files, n: n.findings.total, op: w(OP_WORD[n.op]) })
    : w('nodeAriaTarget', { id: n.id, files: n.files, op: w(OP_WORD[n.op]), s: n.sources.length })
}

/** The full canvas keeps a band below the land for the legend and the minimap that float over its bottom corners. */
function viewBox(bounds: MapView<AnyNode>['bounds'], variant: Variant): string {
  const [bx, by, bw, bh] = bounds
  if (variant === 'mini') return `${bx - 20} ${by - 20} ${bw + 40} ${bh + 40}`
  return variant === 'full' ? `${bx} ${by} ${bw} ${bh + 120}` : `${bx} ${by} ${bw} ${bh}`
}

function drawnEdges(edges: MapEdge[], variant: Variant): MapEdge[] {
  if (variant === 'preview') return strongEdges(edges)
  return variant === 'mini' ? [] : [...edges].sort((a, b) => a.imports - b.imports)
}

export function TerritoryMap({ view, mode, variant, focus, lit = [], only, onFocus, transform, frame, label, className, svgRef, dragging, marked }: TerritoryMapProps) {
  const { lang } = usePrefs()
  const uid = useId().replace(/:/g, '')
  const hatch = `h${uid}`
  const arrow = `a${uid}`
  const full = variant === 'full' || variant === 'compare'
  const mini = variant === 'mini'
  const [bx, by, bw, bh] = view.bounds

  const focusNode = focus ? view.nodes.find((n) => n.id === focus) : undefined
  const near = useMemo(() => {
    const set = new Set<string>(lit)
    if (focusNode) {
      set.add(focusNode.id)
      for (const e of view.edges) {
        if (e.from === focusNode.id) set.add(e.to)
        if (e.to === focusNode.id) set.add(e.from)
      }
    }
    return set
  }, [focusNode, view.edges, lit])
  const dim = !mini && (Boolean(focusNode) || lit.length > 0 || Boolean(only))
  const look: NodeLook = { byOp: mode !== 'current', focusId: focusNode?.id, lit, dim, only, near, narrowed: Boolean(focusNode) || lit.length > 0 }

  const edges = useMemo(() => drawnEdges(view.edges, variant), [view.edges, variant])
  // the import counts of the focus's ten heaviest edges (more would crowd the land around it)
  const focusEdges = focusNode ? view.edges.filter((e) => e.from === focusNode.id || e.to === focusNode.id).sort((a, b) => b.imports - a.imports).slice(0, 10) : []
  const nodes = useMemo(() => [...view.nodes].sort((a, b) => b.r - a.r), [view.nodes])

  const g = transform && !mini ? { transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})` } : undefined
  const interactive = full && Boolean(onFocus)

  return (
    <svg ref={svgRef} viewBox={viewBox(view.bounds, variant)} preserveAspectRatio="xMidYMid meet" direction="ltr"
      className={[css.map, css[variant], dim && css.dim, dragging && css.dragging, className].filter(Boolean).join(' ')}
      role={label ? (interactive ? 'group' : 'img') : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <MapDefs hatch={hatch} arrow={arrow} full={full} />
      <rect className={css.water} x={bx - 2000} y={by - 2000} width={bw + 4000} height={bh + 4000} />
      <g style={g} className={css.world}>
        {!mini && <Graticule />}
        <Lands view={view} mini={mini} />
        {edges.length > 0 && <Edges edges={edges} focusId={focusNode?.id} full={full} arrow={arrow} />}
        <g className={css.nodes}>
          {nodes.map((n) => (
            <MapNode key={n.id} n={n} look={look} variant={variant} hatch={hatch} marked={Boolean(marked?.[n.id])}
              onPress={interactive ? onFocus : undefined} />
          ))}
        </g>
        {full && focusEdges.length > 0 && <Weights edges={focusEdges} />}
        {!mini && <Labels view={view} variant={variant} lang={lang} focus={focusNode?.id} near={near} dim={dim} only={only} />}
      </g>
      {mini && frame && <rect className={css.frame} x={frame[0]} y={frame[1]} width={frame[2]} height={frame[3]} rx={10} />}
    </svg>
  )
}

function MapDefs({ hatch, arrow, full }: { hatch: string; arrow: string; full: boolean }) {
  return (
    <defs>
      <pattern id={hatch} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect className={css.hatchBg} width="6" height="6" /><rect className={css.hatchFg} width="2.2" height="6" />
      </pattern>
      {full && (
        <marker id={arrow} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0,1 L7,4 L0,7z" className={css.arrowHead} />
        </marker>
      )}
    </defs>
  )
}

function Graticule() {
  return (
    <g className={css.grat}>
      {Array.from({ length: 9 }, (_, i) => <path key={`x${i}`} d={`M${(i + 1) * 100},0V900`} />)}
      {Array.from({ length: 8 }, (_, i) => <path key={`y${i}`} d={`M0,${(i + 1) * 100}H1000`} />)}
    </g>
  )
}

function Lands({ view, mini }: { view: MapView<AnyNode>; mini: boolean }) {
  return (
    <g className={css.lands}>
      {view.regions.flatMap((r) => r.land.filter((l) => !mini || l.level === 0).sort((a, b) => a.level - b.level)
        .map((l, i) => <path key={`${r.id}${i}`} d={l.d} className={css[`land${l.level}`]} fillRule="evenodd" />))}
    </g>
  )
}

function Edges({ edges, focusId, full, arrow }: { edges: MapEdge[]; focusId?: string; full: boolean; arrow: string }) {
  const w = useMapWords()
  return (
    <g className={css.edges}>
      {edges.map((e) => {
        const on = focusId !== undefined && (e.from === focusId || e.to === focusId)
        return (
          <path key={`${e.from}>${e.to}`} d={e.d} strokeWidth={e.width}
            className={[css.edge, on && css.edgeOn, e.cycle && css.edgeCycle].filter(Boolean).join(' ')}
            markerEnd={on && full ? `url(#${arrow})` : undefined}>
            {full && <title>{`${e.from} → ${e.to}: ${w('importsN', { n: e.imports })}`}</title>}
          </path>
        )
      })}
    </g>
  )
}

interface MapNodeProps {
  n: AnyNode
  look: NodeLook
  variant: Variant
  hatch: string
  /** It holds unseen work: a dashed ring */
  marked: boolean
  /** Set on the interactive canvas: the node is a button */
  onPress?: (id: string) => void
}

function MapNode({ n, look, variant, hatch, marked, onPress }: MapNodeProps) {
  const w = useMapWords()
  const mini = variant === 'mini'
  const fill = look.byOp && n.op === 'delete' ? { fill: `url(#${hatch})` } : undefined
  const r = mini ? n.r * 0.9 : n.r
  if (!onPress) {
    return (
      <g className={nodeClass(n, look)}>
        {marked && !mini ? <circle className={css.hiddenRing} cx={n.x} cy={n.y} r={r + 4.5} /> : null}
        <circle className={css.dot} cx={n.x} cy={n.y} r={r} style={fill} />
      </g>
    )
  }
  const key = (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onPress(n.id) }
  }
  return (
    <g className={nodeClass(n, look)} role="button" tabIndex={0} aria-label={nodeName(n, w)}
      aria-pressed={look.focusId === n.id} onClick={() => onPress(n.id)} onKeyDown={key} data-node={n.id}>
      <circle className={css.halo} cx={n.x} cy={n.y} r={r + 9} />
      {marked ? <circle className={css.hiddenRing} cx={n.x} cy={n.y} r={r + 4.5} /> : null}
      <circle className={css.dot} cx={n.x} cy={n.y} r={r} style={fill} />
      <circle className={css.hit} cx={n.x} cy={n.y} r={Math.max(r, 14)} />
    </g>
  )
}

function Weights({ edges }: { edges: MapEdge[] }) {
  return (
    <g className={css.weights} aria-hidden="true">
      {edges.filter((e) => e.mid).map((e) => (
        <text key={`${e.from}>${e.to}`} x={e.mid![0]} y={e.mid![1]} className={css.weight} textAnchor="middle" dominantBaseline="central">{e.imports}</text>
      ))}
    </g>
  )
}

interface LabelsProps { view: MapView<AnyNode>; variant: Variant; lang: 'ar' | 'en'; focus?: string; near: Set<string>; dim: boolean; only?: Operation }

function Labels({ view, variant, lang, focus, near, dim, only }: LabelsProps) {
  const target = view.nodes.length > 0 && !('findings' in view.nodes[0])
  return (
    <g className={css.labels} aria-hidden="true">
      {variant !== 'preview' && view.nodes.map((n) => (
        <NodeLabel key={n.id} n={n} compare={variant === 'compare'} selected={focus === n.id} near={near} dim={dim} only={only} />
      ))}
      {view.regions.map((r) => <RegionLabel key={r.id} r={r} variant={variant} lang={lang} target={target} />)}
    </g>
  )
}

interface NodeLabelProps { n: AnyNode; compare: boolean; selected: boolean; near: Set<string>; dim: boolean; only?: Operation }

function NodeLabel({ n, compare, selected, near, dim, only }: NodeLabelProps) {
  const l = n.label
  const show = selected || (compare ? (l.placed && l.big) || (dim && near.has(n.id)) : l.placed)
  if (!show) return null
  const off = dim && !near.has(n.id) && !(only && n.op === only)
  return (
    <text x={l.x} y={l.y} fontSize={compare ? l.size * 1.45 : l.size} textAnchor={l.anchor} direction="ltr"
      className={[css.lbl, l.big && css.big, selected && css.lblSel, off && css.lblOff].filter(Boolean).join(' ')}>{n.short}</text>
  )
}

/** A region name's size: [Arabic words, other names] per variant; the canvas and the minimap share the last. */
const REGION_SIZE: Partial<Record<Variant, [number, number]>> = { preview: [40, 30], compare: [22, 17] }

function RegionLabel({ r, variant, lang, target }: { r: Region; variant: Variant; lang: 'ar' | 'en'; target: boolean }) {
  const w = useMapWords()
  const preview = variant === 'preview'
  const arabic = lang === 'ar' && !r.name.ident
  const x = preview ? r.label.tx : r.label.x
  const y = preview ? r.label.ty : r.label.y
  const [arSize, size] = REGION_SIZE[variant] ?? [15, 12]
  return (
    <g>
      <text x={x} y={y} fontSize={arabic ? arSize : size} textAnchor="middle" direction={arabic ? 'rtl' : 'ltr'}
        className={[css.reg, r.name.ident ? css.regId : lang === 'en' && css.regEn].filter(Boolean).join(' ')}>{r.name[lang]}</text>
      {variant === 'full' && (
        <text x={x} y={y + 15} fontSize={11} textAnchor="middle" direction={lang === 'ar' ? 'rtl' : 'ltr'} className={css.regSub}>
          {w(target ? 'regionSubTarget' : 'regionSub', { c: r.components, f: r.files })}
        </text>
      )}
    </g>
  )
}
