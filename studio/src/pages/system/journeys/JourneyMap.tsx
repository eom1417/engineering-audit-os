// The journeys drawn from studio/journeys.json: every screen a frame on EAOS's pinned grid (columns = clicks from the
// start), the menu as its own node, the links as curves with arrowheads, broken links as red stubs. Today shows the
// flags; Change colours each frame by its folder's operation; Target ghosts what its folder deletes and marks every
// screen the target has not decided. Hidden routes (layouts, redirects, catch-alls) are hatched and only drawn with
// the "show hidden" lens. The SVG is direction neutral: the page mirrors the chrome around it, never the geometry.
import { useId, type Ref } from 'react'
import type { Journeys, Screen, ScreenFlag, Task } from '../../../data/journeys'
import { usePrefs } from '../../../i18n/prefs'
import { fit, pressable } from '../../../map/draw'
import type { ZoomState } from '../../../map/useZoom'
import { useJourneyWords } from '../words'
import { areaScreens, captions, clusters, edgeKey, litSet, pathEdges, shownEdges, shownScreens, type JourneyMode } from './model'
import css from './JourneyMap.module.css'

export interface JourneyMapProps {
  journeys: Journeys
  mode: JourneyMode
  variant: 'full' | 'preview'
  focus?: string
  task?: Task
  flag?: ScreenFlag
  showHidden: boolean
  /** screen id -> unseen items its area sets in motion (the "show hidden" lens) */
  unseen?: Map<string, number>
  onFocus?: (id: string) => void
  transform?: ZoomState
  svgRef?: Ref<SVGSVGElement>
  dragging?: boolean
  label?: string
  className?: string
  /** a base for screen shots (paths in journeys.json are relative to the report folder) */
  shotBase?: string
  /** a map of many screens: one frame per area (CLUSTER_AT); pressing an area calls onFocus('area:<id>') */
  clustered?: boolean
  /** an expanded area: only its screens and the screens they link with */
  area?: string
}

type Words = ReturnType<typeof useJourneyWords>
type Grid = Journeys['grid']
type Edge = ReturnType<typeof shownEdges>[number]
type Menu = Journeys['menus'][number]
type Caption = ReturnType<typeof captions>[number]

const TOP = 56

export function JourneyMap(props: JourneyMapProps) {
  return props.clustered ? <ClusterMap {...props} /> : <ScreenMap {...props} />
}

function zoomStyle(transform?: ZoomState) {
  return transform ? { transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})` } : undefined
}

/** The whole grid, or only the expanded area's screens with a margin around them. */
function viewBoxOf(g: Grid, only: Set<string> | null, screens: Screen[]) {
  if (!only || !screens.length) return `${-8} ${-TOP} ${g.width + 56} ${g.height + TOP + 16}`
  const box = [Math.min(...screens.map((s) => s.x)), Math.min(...screens.map((s) => s.y)),
    Math.max(...screens.map((s) => s.x)) + g.box_w, Math.max(...screens.map((s) => s.y)) + g.box_h]
  return `${box[0] - 40} ${box[1] - TOP} ${box[2] - box[0] + 100} ${box[3] - box[1] + TOP + 40}`
}

function captionText(c: Caption, w: Words) {
  if (c.kind === 'start') return w('start')
  if (c.kind === 'none') return w('noWayInCol')
  return c.n === 1 ? w('oneClick') : w('clicks', { n: c.n })
}

function MapDefs({ uid }: { uid: string }) {
  return (
    <defs>
      <pattern id={`h${uid}`} width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect className={css.hatchBg} width="7" height="7" /><rect className={css.hatchFg} width="2" height="7" />
      </pattern>
      <pattern id={`d${uid}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect className={css.delBg} width="6" height="6" /><rect className={css.delFg} width="2" height="6" />
      </pattern>
      <marker id={`a${uid}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0,1 L7,4 L0,7z" className={css.arrow} />
      </marker>
      <marker id={`p${uid}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M0,1 L7,4 L0,7z" className={css.arrowOn} />
      </marker>
    </defs>
  )
}

/** The links: on the task's path or touching the focused node they are drawn on, the others fade while one is lit. */
function EdgeLayer({ edges, onPath, focus, dim, full, uid }: { edges: Edge[]; onPath: Set<string>; focus?: string; dim: boolean; full: boolean; uid: string }) {
  return (
    <g className={css.edges}>
      {edges.map((e) => {
        const on = onPath.has(edgeKey(e.from, e.to)) || (focus !== undefined && (e.from === focus || e.to === focus))
        const off = dim && !on
        return (
          <path key={edgeKey(e.from, e.to)} d={e.d}
            className={[css.edge, css[`via_${e.via}`], e.back && css.back, on && css.edgeOn, off && css.edgeOff].filter(Boolean).join(' ')}
            markerEnd={e.via === 'menu_of' ? undefined : `url(#${on ? 'p' : 'a'}${uid})`}>
            {full && <title>{`${e.from} → ${e.to}`}</title>}
          </path>
        )
      })}
    </g>
  )
}

function MenuNode({ m, g, w, className, step, press }: { m: Menu; g: Grid; w: Words; className: string; step?: number; press: object }) {
  const { lang } = usePrefs()
  return (
    <g className={className} {...press}>
      <rect x={m.x} y={m.y + 6} width={g.box_w} height={g.box_h - 12} rx={(g.box_h - 12) / 2} className={css.menuBox} />
      <text x={m.x + g.box_w / 2} y={m.y + g.box_h / 2 - 2} textAnchor="middle" direction={lang === 'ar' ? 'rtl' : 'ltr'} className={css.menuTitle}>{w('menu')}</text>
      <text x={m.x + g.box_w / 2} y={m.y + g.box_h / 2 + 13} textAnchor="middle" direction={lang === 'ar' ? 'rtl' : 'ltr'} className={css.menuSub}>{w('menuSub', { n: m.links, s: m.scope.length })}</text>
      {step !== undefined && <StepBadge x={m.x} y={m.y + 6} n={step} />}
    </g>
  )
}

interface FrameProps {
  s: Screen; g: Grid; uid: string; mode: JourneyMode; full: boolean; shotBase: string; className: string
  broken: Journeys['broken']; unseen?: number; step?: number; press: object
}

/** One screen: its frame (hatched when hidden, ghosted when the target deletes it), its picture, title and route, and
 * its marks: a twin, a dead end, an undecided target, unseen work, broken links and its step on the task. */
function ScreenFrame({ s, g, uid, mode, full, shotBase, className, broken, unseen, step, press }: FrameProps) {
  const fill = s.kind !== 'page' ? `url(#h${uid})` : mode === 'target' && s.op === 'delete' ? `url(#d${uid})` : undefined
  const shot = s.shots?.[0]
  return (
    <g className={className} data-node={s.id} {...press}>
      {s.flags.includes('duplicate') && <rect x={s.x + 5} y={s.y + 5} width={g.box_w} height={g.box_h} rx={8} className={css.twin} />}
      <rect x={s.x} y={s.y} width={g.box_w} height={g.box_h} rx={8} className={css.frame} style={fill ? { fill } : undefined} />
      <path d={`M${s.x + 8},${s.y + 0.5}h${g.box_w - 16}a7.5,7.5 0 0 1 7.5,7.5v4.5h-${g.box_w - 1}v-4.5a7.5,7.5 0 0 1 7.5,-7.5z`} className={css.bar} />
      <circle cx={s.x + 8} cy={s.y + 6.5} r={1.8} className={css.barDot} /><circle cx={s.x + 14} cy={s.y + 6.5} r={1.8} className={css.barDot} />
      {shot && full ? (
        <image href={`${shotBase}${shot}`} x={s.x + 1} y={s.y + 13} width={g.box_w - 2} height={g.box_h - 14} preserveAspectRatio="xMidYMin slice" />
      ) : null}
      <text x={s.x + 10} y={s.y + 32} className={css.title}>{fit(s.title, 20)}</text>
      <text x={s.x + 10} y={s.y + 49} className={css.route}>{fit(s.route, 24)}</text>
      {full && <title>{`${s.title} — ${s.route}`}</title>}
      {s.flags.includes('dead_end') && <path d={`M${s.x + g.box_w + 4},${s.y + 14}v${g.box_h - 22}`} className={css.deadEnd} />}
      {mode === 'target' && !s.decided && s.kind === 'page' && (
        <g className={css.undecided}><circle cx={s.x + g.box_w - 13} cy={s.y + g.box_h - 13} r={8} /><text x={s.x + g.box_w - 13} y={s.y + g.box_h - 9.5} textAnchor="middle">?</text></g>
      )}
      {unseen ? (
        <g className={css.unseen}><rect x={s.x + g.box_w - 36} y={s.y - 9} width={30} height={15} rx={4} style={{ fill: `url(#h${uid})` }} />
          <text x={s.x + g.box_w - 21} y={s.y + 2.5} textAnchor="middle">{unseen}</text></g>
      ) : null}
      {broken.map((b, i) => {
        const y0 = s.y + g.box_h - 12 - i * 9
        return (
          <g key={`${b.file}:${b.line}:${i}`} className={css.broken}>
            <path d={`M${s.x + g.box_w},${y0}h22`} />
            <path d={`M${s.x + g.box_w + 24},${y0 - 4}l8,8m0,-8l-8,8`} className={css.brokenX} />
          </g>
        )
      })}
      {step !== undefined && <StepBadge x={s.x} y={s.y} n={step} />}
    </g>
  )
}

function ScreenMap({ journeys: j, mode, variant, focus, task, flag, showHidden, unseen, onFocus, transform, svgRef, dragging, label, className, shotBase = '../', area }: JourneyMapProps) {
  const w = useJourneyWords()
  const { lang } = usePrefs()
  const uid = useId().replace(/:/g, '')
  const g = j.grid
  const full = variant === 'full'
  const { only, screens, edges, menus } = visiblePart(j, showHidden, area)
  const lit = litSet(j, focus, task, flag)
  const look: Look = { mode, focus, task, lit, step: new Map((task?.path ?? []).map((id, i) => [id, i + 1])) }
  const dim = lit !== null
  const interactive = full && Boolean(onFocus)
  const stepOf = (id: string) => (task ? look.step.get(id) : undefined)

  return (
    <svg ref={svgRef} viewBox={viewBoxOf(g, only, screens)} preserveAspectRatio="xMidYMid meet" direction="ltr"
      className={[css.map, css[variant], dim && css.dim, dragging && css.dragging, className].filter(Boolean).join(' ')}
      role={label ? (interactive ? 'group' : 'img') : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <MapDefs uid={uid} />
      <rect className={css.water} x={-4000} y={-4000} width={g.width + 8000} height={g.height + 8000} />
      <g style={zoomStyle(transform)} className={css.world}>
        {full && !only && <Captions j={j} w={w} ar={lang === 'ar'} />}
        <EdgeLayer edges={edges} onPath={pathEdges(task)} focus={focus} dim={dim} full={full} uid={uid} />
        {menus.map((m) => (
          <MenuNode key={m.id} m={m} g={g} w={w} className={menuLook(m, look)} step={stepOf(m.id)}
            press={pressable(interactive, m.id, `${w('menu')}: ${w('menuSub', { n: m.links, s: m.scope.length })}`, focus === m.id, onFocus)} />
        ))}
        {screens.map((s) => (
          <ScreenFrame key={s.id} s={s} g={g} uid={uid} mode={mode} full={full} shotBase={shotBase} className={frameLook(s, look)}
            broken={j.broken.filter((b) => b.from === s.id)} unseen={showHidden ? unseen?.get(s.id) : undefined} step={stepOf(s.id)}
            press={pressable(interactive, s.id, screenAria(s, w, lang === 'ar'), focus === s.id, onFocus)} />
        ))}
      </g>
    </svg>
  )
}

/** What the map shows: every shown screen, link and menu, or only an expanded area's screens and their links. */
function visiblePart(j: Journeys, showHidden: boolean, area?: string) {
  const only = area ? areaScreens(j, area) : null
  return {
    only,
    screens: shownScreens(j, showHidden).filter((s) => !only || only.has(s.id)),
    edges: shownEdges(j, showHidden).filter((e) => !only || (only.has(e.from) && only.has(e.to))),
    menus: only ? [] : j.menus,
  }
}

/** What a node's look depends on: the lens, the focused node, the task's path and what is lit. */
interface Look { mode: JourneyMode; focus?: string; task?: Task; step: Map<string, number>; lit: ReturnType<typeof litSet> }

const faded = (l: Look, id: string) => !!l.lit && !l.lit.has(id)

function frameLook(s: Screen, l: Look): string {
  return [
    css.screen,
    s.kind !== 'page' && css.hidden,
    l.mode === 'change' && s.op && css['op_' + s.op],
    l.mode === 'target' && s.op === 'delete' && css.removed,
    s.flags.includes('no_way_in') && css.noWayIn,
    l.focus === s.id && css.sel,
    l.task && l.step.has(s.id) && css.onPath,
    faded(l, s.id) && css.faded,
  ].filter(Boolean).join(' ')
}

function menuLook(m: Menu, l: Look): string {
  return [css.menu, faded(l, m.id) && css.faded, l.task && l.step.has(m.id) && css.onPath, l.focus === m.id && css.sel].filter(Boolean).join(' ')
}

/** A screen as a screen reader says it: its title, route and flags. */
function screenAria(s: Screen, w: Words, ar: boolean): string {
  const sep = ar ? '، ' : ', '
  return w('screenAria', { t: s.title, r: s.route, f: s.flags.length ? sep + s.flags.map((f) => w(`flag_${f}`)).join(sep) : '' })
}

/** Over each column, how many clicks from the start it stands. */
function Captions({ j, w, ar }: { j: Journeys; w: Words; ar: boolean }) {
  const g = j.grid
  return captions(j).map((c) => (
    <text key={c.col} x={g.pad + c.col * g.col_w} y={-TOP + 22} className={css.caption} direction={ar ? 'rtl' : 'ltr'} textAnchor="start" dx={ar ? g.box_w : 0}>
      {captionText(c, w)}
    </text>
  ))
}

function StepBadge({ x, y, n }: { x: number; y: number; n: number }) {
  return (
    <g className={css.step}>
      <circle cx={x} cy={y} r={11} />
      <text x={x} y={y + 4} textAnchor="middle">{n}</text>
    </g>
  )
}

/** The areas of a large app: one frame per area with its screens and flags, the links between areas counted. */
function ClusterMap({ journeys: j, variant, focus, onFocus, transform, svgRef, dragging, label, className }: JourneyMapProps) {
  const w = useJourneyWords()
  const { lang } = usePrefs()
  const uid = useId().replace(/:/g, '')
  const g = j.grid
  const { nodes, edges, width, height } = clusters(j)
  const interactive = variant === 'full' && Boolean(onFocus)
  return (
    <svg ref={svgRef} viewBox={`-8 -24 ${width + 16} ${height + 40}`} preserveAspectRatio="xMidYMid meet" direction="ltr"
      className={[css.map, css[variant], dragging && css.dragging, className].filter(Boolean).join(' ')}
      role={label ? (interactive ? 'group' : 'img') : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <defs>
        <marker id={`a${uid}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,1 L7,4 L0,7z" className={css.arrow} />
        </marker>
      </defs>
      <rect className={css.water} x={-4000} y={-4000} width={width + 8000} height={height + 8000} />
      <g style={zoomStyle(transform)} className={css.world}>
        <g className={css.edges}>
          {edges.map((e) => <path key={`${e.from}>${e.to}`} d={e.d} strokeWidth={1 + Math.log2(1 + e.count)} className={css.edge} markerEnd={`url(#a${uid})`} />)}
        </g>
        {nodes.map((c) => {
          const id = `area:${c.id}`
          const problems = c.flags.broken_link + c.flags.no_way_in + c.flags.dead_end + c.flags.duplicate
          return (
            <g key={c.id} className={[css.screen, css.cluster, focus === id && css.sel].filter(Boolean).join(' ')}
              {...pressable(interactive, id, `${c.id}: ${w('clusterSub', { s: c.screens.length })}`, undefined, onFocus)}>
              <rect x={c.x + 6} y={c.y + 6} width={g.box_w} height={g.box_h} rx={8} className={css.twin} />
              <rect x={c.x} y={c.y} width={g.box_w} height={g.box_h} rx={8} className={css.frame} />
              <text x={c.x + 10} y={c.y + 24} className={css.title}>{fit(c.id, 20)}</text>
              <text x={lang === 'ar' ? c.x + g.box_w - 10 : c.x + 10} y={c.y + 46} className={css.clusterSub} direction={lang === 'ar' ? 'rtl' : 'ltr'}>
                {w('clusterSub', { s: c.screens.length }) + (problems ? ` · ${w('clusterFlags', { n: problems })}` : '')}</text>
            </g>
          )
        })}
      </g>
    </svg>
  )
}
