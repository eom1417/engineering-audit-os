// The two-step call graph around one function (C-experience 3.3): who calls its callers, who calls it, the function,
// what it calls, what those call. Five columns read left to right in English and right to left in Arabic; each column
// keeps its most complex five, and what is cut is counted under the drawing. A box opens that function. Beyond two
// steps a call graph stops being readable; the lists below hold every caller and callee.
import { useNavigate } from '@tanstack/react-router'
import { usePrefs } from '../../i18n/prefs'
import { callGraph, level, shortName, type Fn } from './model'
import { useFunctionWords } from './words'
import css from './Functions.module.css'

const W = 760
const COL = 132
const ROW = 40
const BOX_H = 30
const GAP_X = (W - 5 * COL) / 4
const MAX_LABEL = 17

function label(fn: Fn): string {
  const name = shortName(fn)
  return name.length > MAX_LABEL ? name.slice(0, MAX_LABEL - 1) + '…' : name
}

interface Placed { fn: Fn; col: number; y: number }

export function CallGraphView({ fn, byId }: { fn: Fn; byId: Map<string, Fn> }) {
  const w = useFunctionWords()
  const { dir } = usePrefs()
  const navigate = useNavigate()
  const g = callGraph(fn, byId)
  const columns: Fn[][] = [g.callers2.map((h) => h.fn), g.callers, [fn], g.callees, g.callees2.map((h) => h.fn)]
  const rows = Math.max(1, ...columns.map((c) => c.length))
  const height = rows * ROW
  if (!g.callers.length && !g.callees.length) return <p className={css.empty}>{w('graphNone')}</p>
  // Column 0 sits at the reading start: the inline-start side in either direction.
  const xOf = (col: number) => {
    const x = col * (COL + GAP_X)
    return dir === 'rtl' ? W - x - COL : x
  }
  const placed = new Map<string, Placed>()
  columns.forEach((list, col) => list.forEach((f, i) => {
    const y = (height - list.length * ROW) / 2 + i * ROW + (ROW - BOX_H) / 2
    placed.set(`${col}:${f.id}`, { fn: f, col, y })
  }))
  const at = (col: number, id: string) => placed.get(`${col}:${id}`)
  const edges: [Placed, Placed][] = []
  for (const h of g.callers2) { const a = at(0, h.fn.id), b = h.via ? at(1, h.via) : undefined; if (a && b) edges.push([a, b]) }
  for (const f of g.callers) { const a = at(1, f.id), b = at(2, fn.id); if (a && b) edges.push([a, b]) }
  for (const f of g.callees) { const a = at(2, fn.id), b = at(3, f.id); if (a && b) edges.push([a, b]) }
  for (const h of g.callees2) { const a = h.via ? at(3, h.via) : undefined, b = at(4, h.fn.id); if (a && b) edges.push([a, b]) }
  const open = (id: string) => navigate({ to: '/system/f/$functionId', params: { functionId: id }, search: (prev: Record<string, unknown>) => prev })
  const edge = ([a, b]: [Placed, Placed]) => {
    const rtl = dir === 'rtl'
    const x1 = rtl ? xOf(a.col) : xOf(a.col) + COL
    const x2 = rtl ? xOf(b.col) + COL : xOf(b.col)
    const y1 = a.y + BOX_H / 2, y2 = b.y + BOX_H / 2, mid = (x1 + x2) / 2
    return <path key={`${a.col}${a.fn.id}>${b.fn.id}`} className={css.cgEdge} d={`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`} />
  }
  const heads = [w('graphTwo'), w('graphOne'), '', w('graphOut'), w('graphOut2')]
  const more = g.more.callers + g.more.callees
  return (
    <div className={css.cg}>
      <div className={css.cgHeads} aria-hidden="true">{heads.map((h, i) => <span key={i}>{h}</span>)}</div>
      <svg className={css.cgSvg} viewBox={`0 0 ${W} ${height}`} role="group" direction="ltr"
        aria-label={w('graphAria', { f: fn.name, a: fn.callers.length, b: fn.callees.length })}>
        {edges.map(edge)}
        {[...placed.values()].map((p) => {
          const centre = p.col === 2
          const x = xOf(p.col)
          return (
            <g key={`${p.col}:${p.fn.id}`} className={[css.cgNode, centre && css.cgCentre, css[`cg_${level(p.fn)}`]].filter(Boolean).join(' ')}
              role={centre ? undefined : 'link'} tabIndex={centre ? undefined : 0} aria-label={centre ? undefined : p.fn.name}
              onClick={centre ? undefined : () => open(p.fn.id)}
              onKeyDown={centre ? undefined : (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(p.fn.id) } }}>
              <title>{p.fn.name}</title>
              <rect x={x + 0.5} y={p.y + 0.5} width={COL - 1} height={BOX_H - 1} rx={6} />
              <text x={x + COL / 2} y={p.y + BOX_H / 2 + 4} textAnchor="middle">{label(p.fn)}</text>
            </g>
          )
        })}
      </svg>
      {more > 0 && <p className={css.cgNote}>{w('graphMore', { n: more })}</p>}
      {g.more.far > 0 && <p className={css.cgNote}>{w('graphFar', { n: g.more.far })}</p>}
      <p className={css.cgNote}>{w('graphHint')}</p>
    </div>
  )
}
