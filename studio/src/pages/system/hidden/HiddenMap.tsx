// What the user sees against what runs unseen (studio/hidden.json): the screen areas on one side, the unseen groups on
// the other (hatched, dashed), and a curve from an area to each group it sets in motion, as thick as the items. The
// layout is fixed by the data's order (areas by name, groups in the contract's order), so it never moves between
// scans. The SVG is direction neutral; the page mirrors its chrome, never the geometry.
import { useId, type KeyboardEvent, type Ref } from 'react'
import type { Hidden, HiddenGroupId } from '../../../data/journeys'
import { usePrefs } from '../../../i18n/prefs'
import type { ZoomState } from '../../../map/useZoom'
import { clip } from '../journeys/model'
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

export function HiddenMap({ hidden: h, variant, focus, onlyNoScreen, showHidden, onFocus, transform, svgRef, dragging, label, className }: HiddenMapProps) {
  const w = useJourneyWords()
  const { lang } = usePrefs()
  const uid = useId().replace(/:/g, '')
  const place = layout(h, showHidden)
  const at = new Map([...place.areas, ...place.groups].map((p) => [p.id, p]))
  const interactive = variant === 'full' && Boolean(onFocus)
  const items = new Map(h.items.map((i) => [i.id, i]))
  const links = showHidden && !onlyNoScreen ? h.links : []
  const lit = focus ? new Set([focus, ...h.links.filter((l) => l.from === focus || l.to === focus).flatMap((l) => [l.from, l.to])]) : null
  const tf = transform ? { transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})` } : undefined
  const press = (id: string) => onFocus?.(id)
  const key = (e: KeyboardEvent, id: string) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); press(id) } }
  const button = (id: string, name: string, pressed: boolean) => interactive
    ? { role: 'button', tabIndex: 0, 'aria-label': name, 'aria-pressed': pressed, onClick: () => press(id), onKeyDown: (e: KeyboardEvent) => key(e, id) }
    : {}
  const areaName = (name: string) => name === '/' ? w('startArea') : name === 'public' ? w('public') : name
  const dir = lang === 'ar' ? 'rtl' : 'ltr'
  const cx = (p: Placed) => (lang === 'ar' ? p.x + p.w - 12 : p.x + 12)
  // SVG anchors follow the text's own direction: right-to-left text starts at its right end
  const anchor = 'start'
  const identAnchor = lang === 'ar' ? 'end' : 'start'
  const farAnchor = 'end'
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
        <text x={lang === 'ar' ? AREA_W : 0} y={-20} className={css.side} direction={dir} textAnchor={anchor}>{w('seenSide')}</text>
        {showHidden && <text x={lang === 'ar' ? X_GROUP + GROUP_W : X_GROUP} y={-20} className={css.side} direction={dir} textAnchor={anchor}>{w('unseenSide')}</text>}
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
        {place.areas.map((p) => {
          const a = h.seen.find((x) => x.id === p.id)!
          const off = lit && !lit.has(p.id)
          return (
            <g key={p.id} className={[css.area, focus === p.id && css.sel, off && css.faded].filter(Boolean).join(' ')}
              {...button(p.id, `${areaName(a.name)}: ${w('areaSub', { s: a.screens.length, d: a.dialog_count })}`, focus === p.id)}>
              <rect x={p.x} y={p.y} width={p.w} height={p.h} rx={8} className={css.box} />
              <text x={cx(p)} y={p.y + 25} className={a.name === '/' || a.name === 'public' ? css.name : css.ident} direction={a.name === '/' || a.name === 'public' ? dir : 'ltr'} textAnchor={a.name === '/' || a.name === 'public' ? anchor : identAnchor}>{clip(areaName(a.name), 18)}</text>
              <text x={lang === 'ar' ? p.x + 12 : p.x + p.w - 12} y={p.y + 25} className={css.sub} direction={dir} textAnchor={farAnchor}>{w('areaSub', { s: a.screens.length, d: a.dialog_count })}</text>
            </g>
          )
        })}
        {place.groups.map((p) => {
          const g = h.groups.find((x) => x.id === p.id)!
          const n = onlyNoScreen ? g.no_screen : g.count.value ?? 0
          const top = g.items.map((id) => items.get(id)).filter((i) => i && (!onlyNoScreen || i.no_screen)).slice(0, 1)
          const off = lit && !lit.has(p.id)
          return (
            <g key={p.id} className={[css.group, n === 0 && css.empty, focus === p.id && css.sel, off && css.faded].filter(Boolean).join(' ')}
              {...button(p.id, `${w(`group_${g.id as HiddenGroupId}`)}: ${w('groupSub', { n })}`, focus === p.id)}>
              <rect x={p.x} y={p.y} width={p.w} height={p.h} rx={8} className={css.hatch} style={{ fill: `url(#h${uid})` }} />
              <rect x={p.x} y={p.y} width={p.w} height={p.h} rx={8} className={css.gbox} />
              <text x={cx(p)} y={p.y + 22} className={css.name} direction={dir} textAnchor={anchor}>{w(`group_${g.id as HiddenGroupId}`)}</text>
              <text x={lang === 'ar' ? p.x + 12 : p.x + p.w - 12} y={p.y + 22} className={css.count} textAnchor={lang === 'ar' ? 'start' : 'end'}>{n}</text>
              {top.map((i, k) => (
                <text key={i!.id} x={p.x + 12} y={p.y + 47 + k * 18} className={[css.item, i!.no_screen && css.itemAlone].filter(Boolean).join(' ')}>{clip(i!.name, 36)}</text>
              ))}
              {g.no_screen > 0 && !onlyNoScreen && (
                <text x={cx(p)} y={p.y + p.h - 9} className={css.alone} direction={dir} textAnchor={anchor}>{`${w('noScreen')}: ${g.no_screen}`}</text>
              )}
            </g>
          )
        })}
      </g>
    </svg>
  )
}
