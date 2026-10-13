// What the user sees against what runs unseen (studio/hidden.json): the screen areas on one side, the unseen groups on
// the other (hatched, dashed), and a curve from an area to each group it sets in motion, as thick as the items. The
// layout is fixed by the data's order (areas by name, groups in the contract's order), so it never moves between
// scans. The SVG is direction neutral; the page mirrors its chrome, never the geometry.
import { useId, type Ref } from 'react'
import type { Hidden, HiddenGroupId } from '../../../data/journeys'
import { usePrefs } from '../../../i18n/prefs'
import type { ZoomState } from '../../../map/useZoom'
import { fit, pressable } from '../../../map/draw'
import { byId } from '../../change/model'
import { useJourneyWords } from '../words'
import css from './Hidden.module.css'

export const AREA_W = 290
export const GROUP_W = 300
const AREA_H = 40
const GROUP_H = 80
const GAP = 8
const X_GROUP = 580

export interface Placed { id: string; x: number; y: number; w: number; h: number }

/** The boxes' places: areas down the start side, groups down the end side, each column centred on the taller. */
export function layout(h: Hidden, showHidden: boolean): { areas: Placed[]; groups: Placed[]; width: number; height: number } {
  const areas = [...h.seen].sort((a, b) => (a.name === '/' ? -1 : b.name === '/' ? 1 : a.name === 'public' ? -1 : b.name === 'public' ? 1 : a.name.localeCompare(b.name)))
  const left = areas.length * (AREA_H + GAP) - GAP
  const right = showHidden ? h.groups.length * (GROUP_H + GAP + 4) - GAP - 4 : 0
  const height = Math.max(left, right, 200)
  const top = (n: number) => (height - n) / 2
  return {
    areas: areas.map((a, i) => ({ id: a.id, x: 0, y: top(left) + i * (AREA_H + GAP), w: AREA_W, h: AREA_H })),
    groups: showHidden ? h.groups.map((g, i) => ({ id: g.id, x: X_GROUP, y: top(right) + i * (GROUP_H + GAP + 4), w: GROUP_W, h: GROUP_H })) : [],
    width: showHidden ? X_GROUP + GROUP_W : AREA_W,
    height,
  }
}

export interface HiddenMapProps {
  hidden: Hidden
  variant: 'full' | 'preview'
  focus?: string
  onlyNoScreen?: boolean
  showHidden: boolean
  onFocus?: (id: string) => void
  transform?: ZoomState
  svgRef?: Ref<SVGSVGElement>
  dragging?: boolean
  label?: string
  className?: string
}

/** What a box of the map needs from the map around it. */
interface BoxCtx {
  w: ReturnType<typeof useJourneyWords>
  lang: string
  dir: 'rtl' | 'ltr'
  focus?: string
  lit: Set<string> | null
  props: (id: string, name: string) => ReturnType<typeof pressable>
}

/** Where a box's text starts, 12px in from the side its language reads from; `far`: from the other side. SVG anchors
 * follow the text's own direction: right-to-left text starts at its right end. */
const inset = (p: Placed, lang: string, far = false) => ((lang === 'ar') !== far ? p.x + p.w - 12 : p.x + 12)

export function HiddenMap({ hidden: h, variant, focus, onlyNoScreen, showHidden, onFocus, transform, svgRef, dragging, label, className }: HiddenMapProps) {
  const w = useJourneyWords()
  const { lang } = usePrefs()
  const uid = useId().replace(/:/g, '')
  const place = layout(h, showHidden)
  const interactive = variant === 'full' && Boolean(onFocus)
  const lit = focus ? new Set([focus, ...h.links.filter((l) => l.from === focus || l.to === focus).flatMap((l) => [l.from, l.to])]) : null
  const tf = transform ? { transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})` } : undefined
  const dir = lang === 'ar' ? 'rtl' : 'ltr'
  const c: BoxCtx = { w, lang, dir, focus, lit, props: (id, name) => pressable(interactive, id, name, focus === id, onFocus) }
  const seen = byId(h.seen)
  const groups = byId(h.groups)
  const items = byId(h.items)
  return (
    <svg ref={svgRef} viewBox={`-16 -44 ${place.width + 32} ${place.height + 60}`} preserveAspectRatio="xMidYMid meet" direction="ltr"
      className={[css.map, css[variant], lit && css.dim, dragging && css.dragging, className].filter(Boolean).join(' ')}
      role={label ? (interactive ? 'group' : 'img') : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <defs>
        <pattern id={`h${uid}`} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect className={css.hatchBg} width="8" height="8" /><rect className={css.hatchFg} width="2" height="8" />
        </pattern>
      </defs>
      <rect className={css.water} x={-4000} y={-4000} width={place.width + 8000} height={place.height + 8000} />
      <g style={tf} className={css.world}>
        <text x={lang === 'ar' ? AREA_W : 0} y={-20} className={css.side} direction={dir} textAnchor="start">{w('seenSide')}</text>
        {showHidden && <text x={lang === 'ar' ? X_GROUP + GROUP_W : X_GROUP} y={-20} className={css.side} direction={dir} textAnchor="start">{w('unseenSide')}</text>}
        <HiddenLinks links={showHidden && !onlyNoScreen ? h.links : []} at={byId([...place.areas, ...place.groups])} lit={lit} focus={focus} />
        {place.areas.map((p) => <AreaBox key={p.id} p={p} a={seen.get(p.id)!} c={c} />)}
        {place.groups.map((p) => <GroupBox key={p.id} p={p} g={groups.get(p.id)!} items={items} c={c} uid={uid} onlyNoScreen={onlyNoScreen} />)}
      </g>
    </svg>
  )
}

/** A curve from an area to each group it sets in motion, as thick as the items. */
function HiddenLinks({ links, at, lit, focus }: { links: Hidden['links']; at: Map<string, Placed>; lit: Set<string> | null; focus?: string }) {
  return (
        <g className={css.links}>
          {links.map((l) => {
            const a = at.get(l.from)
            const g = at.get(l.to)
            if (!a || !g) return null
            // the ends spread along each box's side, in the order of the boxes at the other end, so curves do not knot
            const outs = links.filter((x) => x.from === l.from).map((x) => at.get(x.to)?.y ?? 0).sort((p, q) => p - q)
            const ins = links.filter((x) => x.to === l.to).map((x) => at.get(x.from)?.y ?? 0).sort((p, q) => p - q)
            const spread = (box: Placed, list: number[], y: number) => box.y + box.h * (0.2 + 0.6 * (list.length > 1 ? list.indexOf(y) / (list.length - 1) : 0.5))
            const x1 = a.x + a.w, y1 = spread(a, outs, g.y), x2 = g.x, y2 = spread(g, ins, a.y), mid = (x1 + x2) / 2
            const on = lit ? lit.has(l.from) && lit.has(l.to) && (focus === l.from || focus === l.to) : false
            return (
              <path key={`${l.from}>${l.to}`} d={`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`} strokeWidth={1 + Math.log2(1 + l.count) * 1.2}
                className={[css.link, on && css.linkOn, lit && !on && css.linkOff].filter(Boolean).join(' ')} />
            )
          })}
        </g>
  )
}

/** A screen area: its name (a word for the start and the public area, else its path) and its screens and dialogs. */
function AreaBox({ p, a, c }: { p: Placed; a: Hidden['seen'][number]; c: BoxCtx }) {
  const named = a.name === '/' || a.name === 'public'
  const title = a.name === '/' ? c.w('startArea') : a.name === 'public' ? c.w('public') : a.name
  const sub = c.w('areaSub', { s: a.screens.length, d: a.dialog_count })
  return (
    <g className={[css.area, c.focus === p.id && css.sel, c.lit && !c.lit.has(p.id) && css.faded].filter(Boolean).join(' ')} {...c.props(p.id, `${title}: ${sub}`)}>
      <rect x={p.x} y={p.y} width={p.w} height={p.h} rx={8} className={css.box} />
      <text x={inset(p, c.lang)} y={p.y + 25} className={named ? css.name : css.ident} direction={named ? c.dir : 'ltr'}
        textAnchor={named || c.lang !== 'ar' ? 'start' : 'end'}>{fit(title, 18)}</text>
      <text x={inset(p, c.lang, true)} y={p.y + 25} className={css.sub} direction={c.dir} textAnchor="end">{sub}</text>
    </g>
  )
}

/** An unseen group, hatched: its name, its count, its first item, and how many items no screen sets in motion. */
function GroupBox({ p, g, items, c, uid, onlyNoScreen }:
  { p: Placed; g: Hidden['groups'][number]; items: Map<string, Hidden['items'][number]>; c: BoxCtx; uid: string; onlyNoScreen?: boolean }) {
  const n = onlyNoScreen ? g.no_screen : g.count.value ?? 0
  const top = g.items.map((id) => items.get(id)).filter((i) => i && (!onlyNoScreen || i.no_screen)).slice(0, 1)
  const name = c.w(`group_${g.id as HiddenGroupId}`)
  return (
    <g className={[css.group, n === 0 && css.empty, c.focus === p.id && css.sel, c.lit && !c.lit.has(p.id) && css.faded].filter(Boolean).join(' ')}
      {...c.props(p.id, `${name}: ${c.w('groupSub', { n })}`)}>
      <rect x={p.x} y={p.y} width={p.w} height={p.h} rx={8} className={css.hatch} style={{ fill: `url(#h${uid})` }} />
      <rect x={p.x} y={p.y} width={p.w} height={p.h} rx={8} className={css.gbox} />
      <text x={inset(p, c.lang)} y={p.y + 22} className={css.name} direction={c.dir} textAnchor="start">{name}</text>
      <text x={inset(p, c.lang, true)} y={p.y + 22} className={css.count} textAnchor={c.lang === 'ar' ? 'start' : 'end'}>{n}</text>
      {top.map((i, k) => (
        <text key={i!.id} x={p.x + 12} y={p.y + 47 + k * 18} className={[css.item, i!.no_screen && css.itemAlone].filter(Boolean).join(' ')}>{fit(i!.name, 36)}</text>
      ))}
      {g.no_screen > 0 && !onlyNoScreen && (
        <text x={inset(p, c.lang)} y={p.y + p.h - 9} className={css.alone} direction={c.dir} textAnchor="start">{`${c.w('noScreen')}: ${g.no_screen}`}</text>
      )}
    </g>
  )
}
