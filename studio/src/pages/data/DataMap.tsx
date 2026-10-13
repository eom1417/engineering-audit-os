// The data paths overview as SVG, from the places EAOS wrote: the components that write and read on one side, the
// stores on the other, an edge per (component, store) weighted by the modules behind it. Two hatched bands stand for
// the tiers the records do not reach (input field, form and key before the callers; the server handler between
// callers and stores), each with how many writes it knows. The geometry never mirrors with the page (DESIGN.md §6).
import { useMemo, type ReactNode, type RefObject } from 'react'
import type { DataPaths, DataView, Store } from '../../data/dataMap'
import { isCluster, labelOf, membersOf, nodeOf, tierCounts, toneOf, touches, viewOf, type Mode } from './model'
import { fit, pressKey } from '../../map/draw'
import { ownerWord } from './parts'
import { useDataWords } from './words'
import css from './Data.module.css'

const BAND = 150 // the entry band's width, before the callers' lane
const HEAD = 44 // room above the lanes for their titles

export interface DataMapProps {
  dp: DataPaths
  mode: Mode
  focus?: string
  reads: boolean
  onFocus: (id: string) => void
  svgRef?: RefObject<SVGSVGElement | null>
  transform?: string
  className?: string
}

export function DataMap({ dp, mode, focus: chosen, reads, onFocus, svgRef, transform, className }: DataMapProps) {
  const w = useDataWords()
  const view: DataView = viewOf(dp, mode)
  const focus = chosen ? nodeOf(view, chosen) : undefined // a store inside a cluster lights its cluster
  const stores = useMemo(() => new Map(dp.stores.map((s) => [s.id, s])), [dp])
  const [bw, bh] = view.box
  const width = view.size[0] + BAND
  const height = Math.max(view.size[1], 200) + HEAD
  const at = (id: string) => { const p = view.place[id] ?? [0, 0]; return [p[0] + BAND, p[1] + HEAD] as const }
  const lit = touches(view, focus)
  const handler = tierCounts(dp.paths, 'handler')
  const entry = tierCounts(dp.paths, 'key')
  const total = dp.paths.length
  const gapX = BAND + 24 + bw + 56 // the server band sits in the middle of the room between the two lanes
  const gapW = view.size[0] - 2 * (24 + bw + 56)
  const manyIn = (id: string) => membersOf(view, id).some((m) => stores.get(m)?.multi_writer)

  const edges = view.edges.filter((e) => reads || e.kind === 'write')
  const node = (id: string, lane: Lane) => {
    const cluster = isCluster(id)
    const store = lane === 'store' && !cluster ? stores.get(id) : undefined
    const on = focus === id
    const quiet = !reads && store !== undefined && store.writers.length === 0 // only read: its edges are hidden
    const storeTone = cluster ? (manyIn(id) && mode !== 'change' ? 'rebuild' : 'none') : toneOf(store, mode)
    return <MapNode key={id} id={id} lane={lane} at={at(id)} box={view.box} store={store} on={on} onFocus={onFocus}
      tone={lane === 'store' ? storeTone : 'none'}
      label={lane === 'store' ? labelOf(id, stores) : (cluster ? id.slice(8) : id)}
      count={cluster ? membersOf(view, id).length : store?.writers.length ?? 0}
      faded={(Boolean(focus) && !on && !lit.has(id)) || (!focus && quiet)} />
  }

  return (
    <svg ref={svgRef} className={[css.map, className].filter(Boolean).join(' ')} viewBox={`0 0 ${width} ${height}`}
      role="group" aria-label={w('mapAria', { c: view.lanes.caller.length, s: view.lanes.store.length })} direction="ltr">
      <defs>
        <pattern id="dp-hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect className={css.hatchBg} width="8" height="8" /><rect className={css.hatchFg} width="2.5" height="8" />
        </pattern>
      </defs>
      <g transform={transform}>
        <Band x={8} width={BAND - 30} height={height} title={w('band_entry')} sub={w('band_known', { k: entry.known, n: total })} />
        {gapW > 40 && <Band x={gapX} width={gapW} height={height} title={w('band_server')} sub={w('band_known', { k: handler.known, n: total })} />}
        <text className={css.laneTitle} x={BAND + 24} y={22}>{w(mode === 'target' ? 'lane_callerTarget' : 'lane_caller')}</text>
        <text className={css.laneTitle} x={BAND + view.size[0] - 24 - bw} y={22}>{w('lane_store')}</text>
        <g className={css.edges}>
          {edges.map((e) => {
            const [x1, y1] = at(e.from)
            const [x2, y2] = at(e.to)
            const sx = x1 + bw, sy = y1 + bh / 2, tx = x2, ty = y2 + bh / 2, mx = (sx + tx) / 2
            const on = focus !== undefined && (e.from === focus || e.to === focus)
            return <path key={`${e.from}>${e.to}>${e.kind}`} className={[css.edge, e.kind === 'read' && css.read, on && css.edgeOn, focus && !on && css.edgeOff].filter(Boolean).join(' ')}
              d={`M${sx},${sy} C${mx},${sy} ${mx},${ty} ${tx},${ty}`} strokeWidth={Math.min(1 + Math.log2(1 + e.modules), 5)} />
          })}
        </g>
        {view.lanes.caller.map((id) => node(id, 'caller'))}
        {view.lanes.store.map((id) => node(id, 'store'))}
      </g>
    </svg>
  )
}

const KIND_MARK: Record<Store['kind'], string> = { table: '▦', resource: '⇄', bucket: '▤', rpc: 'ƒ', auth: '⚿' }

/** A hatched tier the records do not reach, its title (a line per tier, broken at its arrows, so it fits the band) and
 * how many writes it knows. */
function Band({ x, width, height, title, sub }: { x: number; width: number; height: number; title: string; sub: ReactNode }) {
  const lines = title.split(/\s*[←→]\s*/)
  return (
    <>
      <rect className={css.band} x={x} y={HEAD - 8} width={width} height={height - HEAD} rx={10} fill="url(#dp-hatch)" />
      <text className={css.bandTitle} y={HEAD + 18} textAnchor="middle">
        {lines.map((line, i) => <tspan key={i} x={x + width / 2} dy={i ? 16 : 0}>{line}</tspan>)}
      </text>
      <text className={css.bandSub} x={x + width / 2} y={HEAD + 36 + 16 * (lines.length - 1)} textAnchor="middle">{sub}</text>
    </>
  )
}

type Lane = 'caller' | 'store'

interface MapNodeProps {
  id: string; lane: Lane; at: readonly [number, number]; box: readonly [number, number]; store?: Store
  tone: string; label: string; count: number; on: boolean; faded: boolean; onFocus: (id: string) => void
}

/** One caller or store box: a cluster stacked with its member count, a store with its kind and writers. */
function MapNode({ id, lane, at: [x, y], box: [bw, bh], store, tone, label, count, on, faded, onFocus }: MapNodeProps) {
  const w = useDataWords()
  const cluster = isCluster(id)
  const name = `${label}${cluster ? ` (${count})` : ''}${store ? `, ${w(`kind_${store.kind}`)}, ${ownerWord(store, w)}` : ''}`
  const mid = y + bh / 2 + 4
  return (
    <g className={[css.node, css[`tone_${tone}`], on && css.on, faded && css.faded, cluster && css.cluster].filter(Boolean).join(' ')}
      role="button" tabIndex={0} aria-label={name} aria-pressed={on} onClick={() => onFocus(id)} onKeyDown={pressKey(() => onFocus(id))}>
      {cluster && <rect className={css.stack} x={x + 4} y={y - 4} width={bw} height={bh} rx={8} />}
      <rect className={css.box} x={x} y={y} width={bw} height={bh} rx={8} />
      {lane === 'store' && <text className={css.kind} x={x + 10} y={mid}>{store ? KIND_MARK[store.kind] : '⋯'}</text>}
      <text className={css.label} x={x + (lane === 'store' ? 34 : 10)} y={mid}>{fit(label, lane === 'store' ? 20 : 26)}</text>
      {(cluster || (store && store.writers.length > 0)) && (
        <text className={[css.count, store?.multi_writer && css.countMany].filter(Boolean).join(' ')} x={x + bw - 10} y={mid} textAnchor="end">
          {cluster ? count : `${store!.multi_writer ? '⚠ ' : ''}✎${count}`}
        </text>
      )}
    </g>
  )
}

/** The map's key: writes and reads, a gap, more than one writer; and the Change view's three colours. */
export function DataLegend({ mode, inline }: { mode: Mode; inline?: boolean }) {
  const w = useDataWords()
  return (
    <ul className={[css.legend, inline && css.legendInline].filter(Boolean).join(' ')} aria-label={w('legend')}>
      <li><svg width="26" height="10" aria-hidden="true"><path className={css.lgWrite} d="M1,5 H25" /></svg>{w('lgWrite')}</li>
      <li><svg width="26" height="10" aria-hidden="true"><path className={css.lgRead} d="M1,5 H25" /></svg>{w('lgRead')}</li>
      <li><span className={css.lgGap} aria-hidden="true" />{w('lgGap')}</li>
      {mode === 'change'
        ? (['single_already', 'merged_in_target', 'still_multiple'] as const).map((c) => (
          <li key={c}><span className={[css.sw, css[`sw_${c}`]].join(' ')} aria-hidden="true" />{w(`ch_${c}`)}</li>))
        : <li><span className={[css.sw, css.sw_still_multiple].join(' ')} aria-hidden="true" />{w('lgMany')}</li>}
    </ul>
  )
}
