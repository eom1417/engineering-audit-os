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
type Graph = ReturnType<typeof callGraph>

/** Column 0 sits at the reading start: the inline-start side in either direction. */
function xOf(col: number, rtl: boolean): number {
  const x = col * (COL + GAP_X)
  return rtl ? W - x - COL : x
}

/** Every box of every column, centred in the drawing's height, keyed by `column:id`. */
function placeColumns(columns: Fn[][], height: number): Map<string, Placed> {
  const placed = new Map<string, Placed>()
  columns.forEach((list, col) => list.forEach((f, i) => {
    const y = (height - list.length * ROW) / 2 + i * ROW + (ROW - BOX_H) / 2
    placed.set(`${col}:${f.id}`, { fn: f, col, y })
  }))
  return placed
}

/** The links from each column to the next: callers' callers to callers, callers to the function, and on. */
function linksOf(g: Graph, fn: Fn, placed: Map<string, Placed>): [Placed, Placed][] {
  const at = (col: number, id: string | undefined) => (id === undefined ? undefined : placed.get(`${col}:${id}`))
  const pairs: [Placed | undefined, Placed | undefined][] = [
    ...g.callers2.map((h): [Placed | undefined, Placed | undefined] => [at(0, h.fn.id), at(1, h.via ?? undefined)]),
    ...g.callers.map((f): [Placed | undefined, Placed | undefined] => [at(1, f.id), at(2, fn.id)]),
    ...g.callees.map((f): [Placed | undefined, Placed | undefined] => [at(2, fn.id), at(3, f.id)]),
    ...g.callees2.map((h): [Placed | undefined, Placed | undefined] => [at(3, h.via ?? undefined), at(4, h.fn.id)]),
  ]
  return pairs.filter((pair): pair is [Placed, Placed] => !!pair[0] && !!pair[1])
}

function LinkPath({ link: [a, b], rtl }: { link: [Placed, Placed]; rtl: boolean }) {
  const x1 = rtl ? xOf(a.col, rtl) : xOf(a.col, rtl) + COL
  const x2 = rtl ? xOf(b.col, rtl) + COL : xOf(b.col, rtl)
  const y1 = a.y + BOX_H / 2, y2 = b.y + BOX_H / 2, mid = (x1 + x2) / 2
  return <path className={css.cgEdge} d={`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`} />
}

/** One function's box; any but the centre one is a link that opens that function. */
function GraphNode({ p, rtl, open }: { p: Placed; rtl: boolean; open: (id: string) => void }) {
  const centre = p.col === 2
  const x = xOf(p.col, rtl)
  return (
    <g className={[css.cgNode, centre && css.cgCentre, css[`cg_${level(p.fn)}`]].filter(Boolean).join(' ')}
      role={centre ? undefined : 'link'} tabIndex={centre ? undefined : 0} aria-label={centre ? undefined : p.fn.name}
      onClick={centre ? undefined : () => open(p.fn.id)}
      onKeyDown={centre ? undefined : (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(p.fn.id) } }}>
      <title>{p.fn.name}</title>
      <rect x={x + 0.5} y={p.y + 0.5} width={COL - 1} height={BOX_H - 1} rx={6} />
      <text x={x + COL / 2} y={p.y + BOX_H / 2 + 4} textAnchor="middle">{label(p.fn)}</text>
    </g>
  )
}

export function CallGraphView({ fn, byId }: { fn: Fn; byId: Map<string, Fn> }) {
  const w = useFunctionWords()
  const { dir } = usePrefs()
  const navigate = useNavigate()
  const g = callGraph(fn, byId)
  const columns: Fn[][] = [g.callers2.map((h) => h.fn), g.callers, [fn], g.callees, g.callees2.map((h) => h.fn)]
  const rows = Math.max(1, ...columns.map((c) => c.length))
  const height = rows * ROW
  if (!g.callers.length && !g.callees.length) return <p className={css.empty}>{w('graphNone')}</p>
  const rtl = dir === 'rtl'
  const placed = placeColumns(columns, height)
  const open = (id: string) => navigate({ to: '/system/f/$functionId', params: { functionId: id }, search: (prev: Record<string, unknown>) => prev })
  const heads = [w('graphTwo'), w('graphOne'), '', w('graphOut'), w('graphOut2')]
  const more = g.more.callers + g.more.callees
  return (
    <div className={css.cg}>
      <div className={css.cgHeads} aria-hidden="true">{heads.map((h, i) => <span key={i}>{h}</span>)}</div>
      <svg className={css.cgSvg} viewBox={`0 0 ${W} ${height}`} role="group" direction="ltr"
        aria-label={w('graphAria', { f: fn.name, a: fn.callers.length, b: fn.callees.length })}>
        {linksOf(g, fn, placed).map((link) => <LinkPath key={`${link[0].col}${link[0].fn.id}>${link[1].fn.id}`} link={link} rtl={rtl} />)}
        {[...placed.values()].map((p) => <GraphNode key={`${p.col}:${p.fn.id}`} p={p} rtl={rtl} open={open} />)}
      </svg>
      {more > 0 && <p className={css.cgNote}>{w('graphMore', { n: more })}</p>}
      {g.more.far > 0 && <p className={css.cgNote}>{w('graphFar', { n: g.more.far })}</p>}
      <p className={css.cgNote}>{w('graphHint')}</p>
    </div>
  )
}
