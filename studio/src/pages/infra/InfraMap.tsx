// The infrastructure as a context diagram: the application in the middle, one lane per kind of infrastructure in a
// fixed slot around it, a line from the application to each lane named by the relation. Today draws what the records
// found; Target draws the target architecture's decision per area (keep, or introduce, dashed); Change draws today's
// items with what the target adds. A lane with nothing found is dashed with its reason; a lane the target says nothing
// about is hatched. Slots are fixed, so a lane keeps its place across views and scans; the geometry never mirrors.
import type { KeyboardEvent, RefObject } from 'react'
import type { Infra, Lane } from '../../data/dataMap'
import { useDataWords, type DataWord } from '../data/words'
import { MAX_ROWS, nodeName, rowsOf, type Mode, type Row } from './model'
import css from './Infra.module.css'

export const WORLD = { w: 1040, h: 940 }
const LANE_W = 290
const ROW_H = 30
const HEAD = 42
const SLOT: Record<Lane, [number, number]> = {
  hosting: [16, 16], ci: [16, 322], environments: [16, 628],
  databases: [734, 16], queues: [734, 322], services: [734, 628], observability: [375, 628],
}
const APP = { x: 390, y: 300, w: 260, h: 96 }

function short(text: string, max: number) {
  return text.length <= max ? text : text.slice(0, max - 1) + '…'
}

export interface InfraMapProps {
  infra: Infra
  mode: Mode
  focus?: string
  onFocus: (id: string) => void
  svgRef?: RefObject<SVGSVGElement | null>
  transform?: string
  className?: string
}

export function InfraMap({ infra, mode, focus, onFocus, svgRef, transform, className }: InfraMapProps) {
  const w = useDataWords()
  const key = (id: string) => (e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onFocus(id) } }
  const rowText = (row: Row) => row.kind === 'node' ? nodeName(row.node, w) : row.kind === 'item' ? w(`area_${row.item.area}` as DataWord) : w('moreN', { n: row.more })
  return (
    <svg ref={svgRef} className={[css.map, className].filter(Boolean).join(' ')} viewBox={`0 0 ${WORLD.w} ${WORLD.h}`} role="group"
      aria-label={w('lanesAria', { n: infra.lanes.length })} direction="ltr">
      <defs>
        <pattern id="infra-hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect className={css.hatchBg} width="8" height="8" /><rect className={css.hatchFg} width="2.5" height="8" />
        </pattern>
      </defs>
      <g transform={transform}>
        {infra.lanes.map((lane) => {
          const [x, y] = SLOT[lane.id]
          const ax = x + LANE_W / 2 < APP.x ? APP.x : x > APP.x + APP.w ? APP.x + APP.w : APP.x + APP.w / 2
          const ay = y > APP.y + APP.h ? APP.y + APP.h : APP.y + APP.h / 2
          const lx = x + LANE_W / 2 < APP.x ? x + LANE_W : x > APP.x + APP.w ? x : x + LANE_W / 2
          const ly = lane.id === 'observability' ? y : y + HEAD / 2
          return (
            <g key={`e-${lane.id}`}>
              <path className={css.link} d={`M${ax},${ay} C${(ax + lx) / 2},${ay} ${(ax + lx) / 2},${ly} ${lx},${ly}`} />
              <text className={css.rel} x={(ax + lx) / 2} y={(ay + ly) / 2 - 4} textAnchor="middle">{w(`rel_${lane.relation}` as DataWord)}</text>
            </g>
          )
        })}
        <g className={css.app}>
          <rect x={APP.x} y={APP.y} width={APP.w} height={APP.h} rx={14} />
          <text className={css.appTitle} x={APP.x + APP.w / 2} y={APP.y + 42} textAnchor="middle">{w('app')}</text>
          {infra.app.reference && <text className={css.appSub} x={APP.x + APP.w / 2} y={APP.y + 66} textAnchor="middle">{infra.app.reference}</text>}
        </g>
        {infra.lanes.map((lane) => {
          const [x, y] = SLOT[lane.id]
          const target = infra.target?.lanes.find((l) => l.id === lane.id)
          const rows = rowsOf(infra, lane.id, mode)
          const silent = mode !== 'current' && (!target || target.state === 'not_measured')
          const empty = rows.length === 0
          const height = HEAD + Math.max(rows.length, 1) * ROW_H + 12
          return (
            <g key={lane.id} className={css.lane}>
              <rect className={[css.laneBox, empty && css.laneEmpty].filter(Boolean).join(' ')} x={x} y={y} width={LANE_W} height={height} rx={12}
                fill={silent && mode === 'target' ? 'url(#infra-hatch)' : undefined} />
              <text className={css.laneTitle} x={x + 14} y={y + 27}>{w(`lane_${lane.id}`)}</text>
              <text className={css.laneN} x={x + LANE_W - 14} y={y + 27} textAnchor="end">{lane.count.value ?? '–'}</text>
              {empty && (
                <text className={css.emptyText} x={x + 14} y={y + HEAD + 19}>
                  {mode === 'target' ? w('silent') : w(`empty_${lane.reason}` as DataWord)}
                </text>
              )}
              {rows.slice(0, MAX_ROWS).map((row, i) => {
                const id = row.kind === 'node' ? row.node.id : row.kind === 'item' ? `target:${lane.id}:${row.item.area}` : `more:${lane.id}`
                const ry = y + HEAD + i * ROW_H
                const tone = row.kind === 'item' ? row.item.op : 'none'
                return (
                  <g key={id} className={[css.row, css[`op_${tone}`], focus === id && css.on].filter(Boolean).join(' ')} role="button" tabIndex={0}
                    aria-label={rowText(row)} aria-pressed={focus === id} onClick={() => onFocus(id)} onKeyDown={key(id)}>
                    <rect className={css.rowBox} x={x + 8} y={ry} width={LANE_W - 16} height={ROW_H - 4} rx={6} />
                    {row.kind === 'item' && <text className={css.opMark} x={x + 18} y={ry + 18}>{row.item.op === 'keep' ? '●' : '+'}</text>}
                    <text className={row.kind === 'node' && row.node.kind === 'host' ? css.rowMono : css.rowText} x={x + (row.kind === 'item' ? 34 : 18)} y={ry + 18}>
                      {short(rowText(row), row.kind === 'item' ? 30 : 28)}
                    </text>
                    {row.kind === 'node' && row.node.evidence > 1 && <text className={css.rowN} x={x + LANE_W - 18} y={ry + 18} textAnchor="end">{row.node.evidence}</text>}
                  </g>
                )
              })}
              {silent && mode === 'change' && <text className={css.silentNote} x={x + 14} y={y + height + 18}>{w('silent')}</text>}
            </g>
          )
        })}
      </g>
    </svg>
  )
}
