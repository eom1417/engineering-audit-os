// The data paths overview as SVG, from the places EAOS wrote: the components that write and read on one side, the
// stores on the other, an edge per (component, store) weighted by the modules behind it. Two hatched bands stand for
// the tiers the records do not reach (input field, form and key before the callers; the server handler between
// callers and stores), each with how many writes it knows. The geometry never mirrors with the page (DESIGN.md §6).
import { useMemo, type KeyboardEvent, type RefObject } from 'react'
import type { DataPaths, DataView, Store } from '../../data/dataMap'
import { isCluster, labelOf, membersOf, nodeOf, tierCounts, toneOf, touches, viewOf, type Mode } from './model'
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
  /** false: a specimen (the gallery), drawn without buttons */
  interactive?: boolean
}

function short(text: string, max: number): string {
  return text.length <= max ? text : '…' + text.slice(text.length - max + 1)
}

export function DataMap({ dp, mode, focus: chosen, reads, onFocus, svgRef, transform, className, interactive = true }: DataMapProps) {
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
  const storeOf = (id: string): Store | undefined => stores.get(id)
  const manyIn = (id: string) => membersOf(view, id).some((m) => stores.get(m)?.multi_writer)
  const key = (id: string) => (e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onFocus(id) } }

  const edges = view.edges.filter((e) => reads || e.kind === 'write')
  const node = (id: string, lane: 'caller' | 'store') => {
    const [x, y] = at(id)
    const cluster = isCluster(id)
    const store = lane === 'store' && !cluster ? storeOf(id) : undefined
    const tone = lane === 'store' ? (cluster ? (manyIn(id) && mode !== 'change' ? 'rebuild' : 'none') : toneOf(store, mode)) : 'none'
    const label = lane === 'store' ? labelOf(id, stores) : (cluster ? id.slice(8) : id)
    const count = cluster ? membersOf(view, id).length : store ? store.writers.length : 0
    const on = focus === id
    const quiet = !reads && store !== undefined && store.writers.length === 0 // only read: its edges are hidden
    const faded = (Boolean(focus) && !on && !lit.has(id)) || (!focus && quiet)
    const name = lane === 'store'
      ? `${label}${cluster ? ` (${count})` : ''}${store ? `, ${w(`kind_${store.kind}`)}, ${ownerWord(store, w)}` : ''}`
      : `${label}${cluster ? ` (${count})` : ''}`
    return (
      <g key={id} className={[css.node, css[`tone_${tone}`], on && css.on, faded && css.faded, cluster && css.cluster].filter(Boolean).join(' ')}
        {...(interactive ? { role: 'button', tabIndex: 0, 'aria-label': name, 'aria-pressed': on, onClick: () => onFocus(id), onKeyDown: key(id) } : {})}>
        {cluster && <rect className={css.stack} x={x + 4} y={y - 4} width={bw} height={bh} rx={8} />}
        <rect className={css.box} x={x} y={y} width={bw} height={bh} rx={8} />
        {lane === 'store' && <text className={css.kind} x={x + 10} y={y + bh / 2 + 4}>{store ? KIND_MARK[store.kind] : '⋯'}</text>}
        <text className={css.label} x={x + (lane === 'store' ? 34 : 10)} y={y + bh / 2 + 4}>{short(label, lane === 'store' ? 20 : 26)}</text>
        {(cluster || (store && store.writers.length > 0)) && (
          <text className={[css.count, store?.multi_writer && css.countMany].filter(Boolean).join(' ')} x={x + bw - 10} y={y + bh / 2 + 4} textAnchor="end">
            {cluster ? count : `${store!.multi_writer ? '⚠ ' : ''}✎${count}`}
          </text>
        )}
      </g>
    )
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
        <rect className={css.band} x={8} y={HEAD - 8} width={BAND - 30} height={height - HEAD} rx={10} fill="url(#dp-hatch)" />
        <text className={css.bandTitle} x={8 + (BAND - 30) / 2} y={HEAD + 18} textAnchor="middle">{w('band_entry')}</text>
        <text className={css.bandSub} x={8 + (BAND - 30) / 2} y={HEAD + 36} textAnchor="middle">{w('band_known', { k: entry.known, n: total })}</text>
        {gapW > 40 && (
          <>
            <rect className={css.band} x={gapX} y={HEAD - 8} width={gapW} height={height - HEAD} rx={10} fill="url(#dp-hatch)" />
            <text className={css.bandTitle} x={gapX + gapW / 2} y={HEAD + 18} textAnchor="middle">{w('band_server')}</text>
            <text className={css.bandSub} x={gapX + gapW / 2} y={HEAD + 36} textAnchor="middle">{w('band_known', { k: handler.known, n: total })}</text>
          </>
        )}
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
