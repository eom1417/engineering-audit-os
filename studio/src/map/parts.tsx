// The pieces around the map: the canvas with its zoom, the legend, the minimap, the neighbourhood (ego) diagram, the
// inspector of a component (today's or the target's) and the ranked list, the map's non-visual twin.
import { useEffect, useMemo, useRef, type ReactNode } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { buttonClass } from '../components/Button'
import { OperationChip } from '../components/Chip'
import { Go } from '../components/Go'
import { Icon } from '../components/Icon'
import { FoldList, Panel, RowButton } from '../components/Panel'
import type { CurrentNode, MapEdge, MapView, Operation, SystemMap, TargetNode } from '../data/system'
import { usePrefs } from '../i18n/prefs'
import { Id, N, Txt } from '../i18n/text'
import { BINS, neighbours, ranked, type MapMode, type Neighbour } from './model'
import { TerritoryMap, type Variant } from './TerritoryMap'
import { useZoom, visibleWorld } from './useZoom'
import { OP_WORD, useMapWords } from './words'
import css from './parts.module.css'
import { SelectComponentCards } from '../command/Selectable'

const SEVERITIES = ['critical', 'high', 'medium', 'low'] as const
const SEV_WORD = { critical: ['حرجة', 'Critical'], high: ['عالية', 'High'], medium: ['متوسطة', 'Medium'], low: ['منخفضة', 'Low'] } as const

// ---------------------------------------------------------------- the canvas

export interface CanvasProps {
  system: SystemMap
  mode: MapMode
  focus?: string
  lit?: string[]
  only?: Operation
  onFocus: (id: string) => void
  /** The toolbar's first line (the title) and second line (the switches, before the zoom buttons) */
  title?: ReactNode
  head?: ReactNode
  variant?: Extract<Variant, 'full' | 'compare'>
  legend?: boolean
  minimap?: boolean
  /** Centre the map on this id when it changes (search, list) */
  centreOn?: string
  className?: string
  /** Shown instead of the map (the list view), under the same toolbar */
  replace?: ReactNode
  /** The "show hidden" lens: components holding unseen work (studio/hidden.json), by id, with how many items */
  marked?: Record<string, number>
}

export function MapCanvas({ system, mode, focus, lit, only, onFocus, title, head, variant = 'full', legend = true, minimap = true, centreOn, className, replace, marked }: CanvasProps) {
  const w = useMapWords()
  const svg = useRef<SVGSVGElement>(null)
  const zoom = useZoom(svg)
  const view = mode === 'target' ? system.target : system.current
  const label = mode === 'target'
    ? w('mapAriaTarget', { c: view.nodes.length, r: view.regions.length, e: view.edges.length })
    : w('mapAria', { c: view.nodes.length, r: view.regions.length, e: view.edges.length })
  const { centreOn: centre, fit } = zoom
  useEffect(() => { fit() }, [mode, fit])
  useEffect(() => {
    const node = centreOn ? view.nodes.find((n) => n.id === centreOn) : undefined
    if (node) centre(node.x, node.y, 1.8)
  }, [centreOn, view, centre])
  return (
    <CanvasFrame title={title} head={head} zoom={replace ? undefined : zoom} className={className}>
      {replace ?? <div className={css.canvas}>
        <TerritoryMap view={view} mode={mode} variant={variant} focus={focus} lit={lit} only={only} onFocus={onFocus} marked={marked}
          transform={zoom.t} dragging={zoom.dragging} svgRef={svg} label={label} className={css.canvasSvg} />
        {legend && <Legend system={system} mode={mode} view={view} marked={marked} />}
        {minimap && (
          <div className={[css.minimap, css.float].join(' ')} aria-hidden="true">
            <TerritoryMap view={view} mode={mode} variant="mini" frame={visibleWorld(zoom.t, view.bounds)} />
          </div>
        )}
      </div>}
    </CanvasFrame>
  )
}

/** A map's frame, shared by every map of the Studio: the toolbar (a title line, then the switches and the zoom
 * buttons) above the canvas. `zoom` is the map's useZoom(); without it the zoom buttons are hidden (a list view). */
export function CanvasFrame({ title, head, zoom, className, children }:
  { title?: ReactNode; head?: ReactNode; zoom?: Pick<ReturnType<typeof useZoom>, 'zoomBy' | 'fit'>; className?: string; children: ReactNode }) {
  const w = useMapWords()
  return (
    <div className={[css.canvasWrap, className].filter(Boolean).join(' ')}>
      <div className={css.toolbar}>
        {title && <div className={css.toolTitle}>{title}</div>}
        <div className={css.toolRow}>
        {head}
        <span className={css.toolSpacer} />
        {zoom && <div className={css.zoom} role="group" aria-label={w('zoom')}>
          <AriaButton className={css.zoomBtn} aria-label={w('zoomOut')} onPress={() => zoom.zoomBy(1 / 1.4)}><span aria-hidden="true">−</span></AriaButton>
          <AriaButton className={css.zoomBtn} aria-label={w('zoomIn')} onPress={() => zoom.zoomBy(1.4)}><span aria-hidden="true">+</span></AriaButton>
          <AriaButton className={css.zoomBtn} aria-label={w('zoomFit')} onPress={zoom.fit}><FitIcon /></AriaButton>
        </div>}
        </div>
      </div>
      {children}
    </div>
  )
}

/** The class of a map's drawing area (position: relative, the map's water) and of its SVG filling it. */
export const canvasClass = { canvas: css.canvas, svg: css.canvasSvg, float: css.float }

export function FitIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" className={css.fitIcon}>
      <path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10" />
    </svg>
  )
}

// ---------------------------------------------------------------- legend

export function Legend({ system, mode, view, inline, marked }: { system: SystemMap; mode: MapMode; view: MapView; inline?: boolean; marked?: Record<string, number> }) {
  const w = useMapWords()
  const files = view.nodes.map((n) => n.files).sort((a, b) => a - b)
  const sizes = files.length ? [files[0], files[Math.floor(files.length / 2)], files[files.length - 1]] : []
  const imports = view.edges.map((e) => e.imports)
  const lo = imports.length ? Math.min(...imports) : 0
  const hi = imports.length ? Math.max(...imports) : 0
  const scale = view.scale ?? 1
  const ops: Operation[] = mode === 'target' ? ['introduce', 'merge', 'rebuild', 'modify', 'retain'] : ['retain', 'modify', 'rebuild', 'delete']
  const count = (op: Operation) => mode === 'target' ? view.nodes.filter((n) => n.op === op).length : system.operations[op]?.value ?? 0
  return (
    <div className={[css.legend, !inline && css.float, inline && css.legendInline].filter(Boolean).join(' ')}>
      {mode === 'current' ? (
        <div className={css.lgBins} role="list" aria-label={w('legendFindings')}>
          <span className={css.lgCap}>{w('findingsWord')}</span>
          {BINS.map((b) => (
            <span key={b.bin} role="listitem" className={css.lgBin}><span className={[css.sw, css[`fb${b.bin}`]].join(' ')} /><bdi dir="ltr" className="num">{b.label}</bdi></span>
          ))}
        </div>
      ) : (
        <ul className={css.lgOps} aria-label={w('legendOps')}>
          {ops.filter((op) => count(op) > 0).map((op) => (
            <li key={op}><span className={[css.sw, css[`op_${op}`]].join(' ')} />{w(OP_WORD[op])}<N value={count(op)} className={css.lgN} /></li>
          ))}
        </ul>
      )}
      {sizes.length > 0 && (
        <div className={css.lgKey}>
          <svg width="58" height="26" viewBox="0 0 58 26" aria-hidden="true" className={css.lgSize}>
            {sizes.map((f, i) => {
              const r = Math.min(12, (4.5 + 3.1 * Math.sqrt(f)) * scale * 0.55)
              return <circle key={i} cx={[7, 23, 45][i]} cy={25 - r - 1} r={r} />
            })}
          </svg>
          <span>{w('sizeIsFiles')} <bdi dir="ltr" className="num">{sizes.join(' · ')}</bdi></span>
        </div>
      )}
      {imports.length > 0 && (
        <div className={css.lgKey}>
          <svg width="44" height="10" aria-hidden="true" className={css.lgEdge}><path d="M2 5h12" strokeWidth="1.2" /><path d="M18 5h24" strokeWidth="4.4" /></svg>
          <span>{w('lineIsImports')} <bdi dir="ltr" className="num">{lo === hi ? lo : `${lo}–${hi}`}</bdi></span>
        </div>
      )}
      {marked && Object.keys(marked).length > 0 && (
        <div className={css.lgKey}>
          <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true" className={css.lgHidden}><circle cx="11" cy="11" r="5" className={css.lgDot} /><circle cx="11" cy="11" r="9" /></svg>
          <span>{w('hiddenRing', { n: Object.keys(marked).length })}</span>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- the neighbourhood

const GAP = 10

function egoLabel(id: string) {
  const parts = id.split('/')
  const last = parts.slice(-2).join('/')
  return parts.length > 2 || last.length > 14 ? (parts[parts.length - 1].length > 13 ? parts[parts.length - 1].slice(0, 12) + '…' : '…/' + parts[parts.length - 1]) : last
}

/** Callers on the inline-start side, the component in the middle, what it uses on the inline-end side (≤ 11 boxes). */
export function Ego({ id, edges, onFocus, touch }: { id: string; edges: MapEdge[]; onFocus: (id: string) => void; touch?: boolean }) {
  const { dir } = usePrefs()
  // on the phone every box is a 44px target and the diagram fits the 300px card
  const EGO_W = touch ? 300 : 328
  const BOX_W = touch ? 86 : 92
  const BOX_H = touch ? 46 : 30
  const w = useMapWords()
  const { uses, usedBy } = neighbours(edges, id)
  const left = usedBy.slice(0, 5)
  const right = uses.slice(0, 6)
  const rows = Math.max(left.length, right.length, 1)
  const height = rows * (BOX_H + GAP) - GAP
  const flip = dir === 'rtl'
  const xOf = (side: 'in' | 'out') => (side === 'in') !== flip ? 0 : EGO_W - BOX_W
  const cx = EGO_W / 2 - 44
  const yOf = (i: number, n: number) => (height - (n * (BOX_H + GAP) - GAP)) / 2 + i * (BOX_H + GAP)
  const centreY = height / 2 - 18
  const box = (n: Neighbour, i: number, count: number, side: 'in' | 'out') => {
    const x = xOf(side)
    const y = yOf(i, count)
    const fromX = side === 'in' ? (flip ? x : x + BOX_W) : (flip ? x + BOX_W : x)
    const toX = side === 'in' ? (flip ? cx + 88 : cx) : (flip ? cx : cx + 88)
    const mid = (fromX + toX) / 2
    return (
      <g key={`${side}${n.id}`}>
        <path className={css.egEdge} d={`M${fromX},${y + BOX_H / 2} C${mid},${y + BOX_H / 2} ${mid},${centreY + 18} ${toX},${centreY + 18}`}
          strokeWidth={Math.min(4.5, 0.8 + Math.log1p(n.imports) * 0.8)} />
        <g className={css.egN} role="button" tabIndex={0} aria-label={`${n.id}, ${w('importsN', { n: n.imports })}`}
          onClick={() => onFocus(n.id)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onFocus(n.id) } }}>
          <rect className={css.egBg} x={x + 0.5} y={y + 0.5} width={BOX_W - 1} height={BOX_H - 1} rx={6} />
          <text className={css.egT} x={x + BOX_W / 2} y={y + BOX_H / 2 - 2} textAnchor="middle">{egoLabel(n.id)}</text>
          <text className={css.egM} x={x + BOX_W / 2} y={y + BOX_H / 2 + 10} textAnchor="middle">{n.imports}</text>
        </g>
      </g>
    )
  }
  return (
    <div className={css.ego}>
      <div className={css.egoCaps}>
        <span>{w('usedBy')} <N value={usedBy.length} /></span>
        <span>{w('uses')} <N value={uses.length} /></span>
      </div>
      <svg className={css.egoSvg} width={EGO_W} height={height} viewBox={`0 0 ${EGO_W} ${height}`} direction="ltr" role="group" aria-label={w('neighbourhood')}>
        {left.map((n, i) => box(n, i, left.length, 'in'))}
        {right.map((n, i) => box(n, i, right.length, 'out'))}
        <g className={css.egC}>
          <rect x={cx} y={centreY} width={88} height={36} rx={8} />
          <text x={cx + 44} y={centreY + 22} textAnchor="middle">{egoLabel(id)}</text>
        </g>
      </svg>
      {(usedBy.length > left.length || uses.length > right.length) && (
        <p className={css.egoCap}>{w('more', { n: usedBy.length - left.length + uses.length - right.length })}</p>
      )}
      <p className={css.egoCap}>{w('egoHint')}</p>
    </div>
  )
}

// ---------------------------------------------------------------- the inspector

function Metric({ k, v }: { k: string; v: number | null }) {
  const w = useMapWords()
  return <div><dt>{k}</dt><dd>{v === null ? <span className={css.muted}>{w('notMeasured')}</span> : <N value={v} />}</dd></div>
}

export function SeverityBars({ node }: { node: CurrentNode }) {
  const { lang } = usePrefs()
  const max = Math.max(1, ...SEVERITIES.map((s) => node.findings[s]))
  return (
    <ul className={css.sevList}>
      {SEVERITIES.filter((s) => s !== 'critical' || node.findings.critical > 0).map((s) => (
        <li key={s}>
          <span className={css.sevK}>{SEV_WORD[s][lang === 'ar' ? 0 : 1]}</span>
          <span className={css.sevBar} aria-hidden="true"><i className={css[`sev_${s}`]} style={{ inlineSize: `${(node.findings[s] / max) * 100}%` }} /></span>
          <N value={node.findings[s]} className={css.sevN} />
        </li>
      ))}
    </ul>
  )
}

export function Inspector({ system, mode, id, onFocus, touch }: { system: SystemMap; mode: MapMode; id: string; onFocus: (id: string) => void; touch?: boolean }) {
  if (mode === 'target') {
    const node = system.target.nodes.find((n) => n.id === id)
    return node ? <TargetInspector system={system} node={node} onFocus={onFocus} touch={touch} /> : null
  }
  const node = system.current.nodes.find((n) => n.id === id)
  return node ? <CurrentInspector system={system} node={node} mode={mode} onFocus={onFocus} touch={touch} /> : null
}

function CurrentInspector({ system, node, mode, onFocus, touch }: { system: SystemMap; node: CurrentNode; mode: MapMode; onFocus: (id: string) => void; touch?: boolean }) {
  const w = useMapWords()
  const { uses, usedBy } = useMemo(() => neighbours(system.current.edges, node.id), [system, node.id])
  return (
    <div className={css.inspect}>
      <div className={css.insHead}>
        <span className={css.insK}>{w('component')}</span>
        <h2 className={css.insTitle}><Id value={node.id} /></h2>
        <OperationChip relation={node.op} to={node.target} />
        {node.merged_with > 0 && <span className={css.insNote}>{w('mergedWith', { n: node.merged_with })}</span>}
      </div>
      <dl className={css.metrics}>
        <Metric k={w('files')} v={node.files} />
        <Metric k={w('usedBy')} v={node.fan_in} />
        <Metric k={w('uses')} v={node.fan_out} />
        <Metric k={w('findings')} v={node.findings.total} />
      </dl>
      {node.findings.total > 0 && (
        <section className={css.insSec} aria-label={w('bySeverity')}>
          <h3 className={css.insH}>{w('bySeverity')}</h3>
          <SeverityBars node={node} />
        </section>
      )}
      {(uses.length > 0 || usedBy.length > 0) && (
        <section className={css.insSec} aria-label={w('neighbourhood')}>
          <h3 className={css.insH}>{w('neighbourhood')}</h3>
          <Ego id={node.id} edges={system.current.edges} onFocus={onFocus} touch={touch} />
        </section>
      )}
      {(node.decision || node.reason) && (
        <section className={css.insSec} aria-label={w('plannedDecision')}>
          <h3 className={css.insH}>{w('plannedDecision')}</h3>
          <div className={css.decision}>
            {node.decision && <Id value={node.decision.id} className={css.decId} />}
            <Txt block>{node.decision?.chosen || node.reason}</Txt>
          </div>
        </section>
      )}
      <div className={css.insFoot}>
        <SelectComponentCards component={node.id} />
        {node.findings.total > 0 && (
          <Go to="/problems" search={{ component: node.id }} className={buttonClass('secondary', { block: true })}>
            {w('openItsFindings', { n: node.findings.total })}<Icon name="chevron" />
          </Go>
        )}
        {node.target && mode !== 'target' && (
          <Go to="/system" search={{ view: 'target', focus: node.target }} className={buttonClass('ghost', { block: true })}>
            {w('showOnTarget')}<Icon name="chevron" />
          </Go>
        )}
        <Go to="/system/paths" search={{ part: node.id }} className={buttonClass('ghost', { block: true })}>
          {w('itsPaths')}<Icon name="chevron" />
        </Go>
      </div>
    </div>
  )
}

function TargetInspector({ system, node, onFocus, touch }: { system: SystemMap; node: TargetNode; onFocus: (id: string) => void; touch?: boolean }) {
  const w = useMapWords()
  const { uses, usedBy } = useMemo(() => neighbours(system.target.edges, node.id), [system, node.id])
  const sources = node.sources.map((s) => system.current.nodes.find((n) => n.id === s)).filter((n): n is CurrentNode => Boolean(n))
  return (
    <div className={css.inspect}>
      <div className={css.insHead}>
        <span className={css.insK}>{w('targetComponent')}</span>
        <h2 className={css.insTitle}><Id value={node.id} /></h2>
        <OperationChip relation={node.op} />
      </div>
      {node.responsibility && (
        <div className={css.insResp}><span className={css.insRespK}>{w('responsibility')}</span><Txt block>{node.responsibility}</Txt></div>
      )}
      <dl className={css.metrics}>
        <Metric k={w('files')} v={node.files} />
        <Metric k={w('comesFrom')} v={node.sources.length} />
        <Metric k={w('usedBy')} v={usedBy.length} />
        <Metric k={w('uses')} v={uses.length} />
      </dl>
      <section className={css.insSec} aria-label={w('comesFrom')}>
        <h3 className={css.insH}>{w('comesFrom')}</h3>
        {sources.length === 0 ? <p className={css.muted}>{w('comesFromNone')}</p> : (
          <Panel>
            <FoldList items={sources} first={6} label={w('comesFrom')} render={(s) => (
              <Go to="/system" search={{ view: 'change', focus: s.id }} className={css.srcRow}>
                <Id value={s.id} keep={2} /><OperationChip relation={s.op} /><Icon name="chevron" className={css.chev} />
              </Go>
            )} />
          </Panel>
        )}
      </section>
      {(uses.length > 0 || usedBy.length > 0) && (
        <section className={css.insSec} aria-label={w('neighbourhood')}>
          <h3 className={css.insH}>{w('neighbourhood')}</h3>
          <Ego id={node.id} edges={system.target.edges} onFocus={onFocus} touch={touch} />
        </section>
      )}
      {node.carried > 0 && <p className={css.insNote}>{w('carried')}: <N value={node.carried} /></p>}
    </div>
  )
}

// ---------------------------------------------------------------- the ranked list

export function RankedList({ system, mode, focus, onFocus, first = 6 }:
  { system: SystemMap; mode: MapMode; focus?: string; onFocus: (id: string) => void; first?: number }) {
  const w = useMapWords()
  if (mode === 'target') {
    const nodes = [...system.target.nodes].sort((a, b) => b.files - a.files || a.id.localeCompare(b.id))
    return (
      <Panel>
        <FoldList items={nodes} first={first} label={w('allComponents')} render={(n) => (
          <RowButton pressed={n.id === focus} onPress={() => onFocus(n.id)} title={<Id value={n.id} />}
            sub={<OperationChip relation={n.op} />} end={<><N value={n.files} /><span className="sr">{w('files')}</span></>} />
        )} />
      </Panel>
    )
  }
  const nodes = ranked(system.current)
  const max = Math.max(1, ...nodes.map((n) => n.findings.total))
  return (
    <Panel>
      <FoldList items={nodes} first={first} label={w('allComponents')} render={(n) => (
        <RowButton pressed={n.id === focus} onPress={() => onFocus(n.id)} title={<Id value={n.id} keep={3} />}
          sub={mode === 'change' ? <OperationChip relation={n.op} to={n.target} /> : (
            <span className={css.rankBar} aria-hidden="true">
              {(['high', 'medium', 'low'] as const).map((s) => n.findings[s] + (s === 'high' ? n.findings.critical : 0) > 0 && (
                <i key={s} className={css[`sev_${s}`]} style={{ inlineSize: `${((n.findings[s] + (s === 'high' ? n.findings.critical : 0)) / max) * 100}%` }} />
              ))}
            </span>
          )}
          end={<><N value={n.findings.total} /><span className="sr">{w('findings')}</span></>} />
      )} />
    </Panel>
  )
}
