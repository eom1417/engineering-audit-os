// One flow's stages drawn live (the canvas, zoom and pan of the pipeline map: useZoom, the paths frame). Each stage is
// a card in the state it has been shown in (motion.ts) with its timer and its counted step; the running one glows, a
// stage shown ending ok sends a light along each link to the stages it opened, a failure pulses once and an absent
// stage fades in dashed. The glow and each light carry the time of the line that caused them (data-at). The toolbar
// sits in its own row above the canvas, so it never covers a stage. With reduced motion nothing moves and the state is
// told by colour, outline and words alone. The drawing is a picture (role img): the stage list is the way to every
// stage by keyboard and touch.
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { shownState, type ScanProgress, type ScanStage } from '../../data/scan'
import { usePrefs } from '../../i18n/prefs'
import { FitIcon } from '../../map/parts'
import zoomCss from '../../map/parts.module.css'
import { useZoom, type ZoomState } from '../../map/useZoom'
import { useMapWords } from '../../map/words'
import { Icon } from '../../components/Icon'
import frame from '../paths/paths.module.css'
import { centred, firstView, links, NODE_H, NODE_W, place, type At, type Layout, type Link } from './geometry'
import { follow, nextDue, release, still, type Light, type Motion } from './motion'
import { Ticker } from './Ticker'
import { useScanWords } from './words'
import css from './scan.module.css'

function useBox(): [(el: HTMLDivElement | null) => void, { w: number; h: number }] {
  const [size, setSize] = useState({ w: 0, h: 0 })
  const watcher = useRef<ResizeObserver | null>(null)
  const attach = useCallback((el: HTMLDivElement | null) => {
    watcher.current?.disconnect()
    if (!el) return
    watcher.current = new ResizeObserver(([entry]) => setSize({ w: entry.contentRect.width, h: entry.contentRect.height }))
    watcher.current.observe(el)
  }, [])
  return [attach, size]
}

/** True when the person asked their system for less motion. */
export function useReducedMotion(): boolean {
  const query = typeof window !== 'undefined' && window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null
  const [reduced, setReduced] = useState(() => !!query?.matches)
  useEffect(() => {
    if (!query) return
    const change = () => setReduced(query.matches)
    query.addEventListener('change', change)
    return () => query.removeEventListener('change', change)
  }, [query])
  return reduced
}

/** The map's motion over the exact state: changes queued and shown in turn (motion.ts); none with reduced motion. */
function useMotion(progress: ScanProgress, reduced: boolean): Motion {
  const [motion, setMotion] = useState(() => still(progress))
  useEffect(() => setMotion((was) => (reduced ? still(progress) : release(follow(was, progress), progress, Date.now()))), [progress, reduced])
  useEffect(() => {
    const due = nextDue(motion, Date.now())
    if (due === null) return
    const timer = window.setTimeout(() => setMotion((was) => release(was, progress, Date.now())), due)
    return () => window.clearTimeout(timer)
  }, [motion, progress])
  return motion
}

function fit(text: string, room: number): string {
  return text.length <= room ? text : text.slice(0, room - 1) + '…'
}

/** One light that runs once along `d`, from the moment it is drawn. */
function TravellingLight({ d, from, to, at }: { d: string; from: string; to: string; at: string | null }) {
  const motion = useRef<SVGAnimateMotionElement>(null)
  useEffect(() => { try { motion.current?.beginElement() } catch { /* no SMIL: the light stays at its start */ } }, [])
  return (
    <circle r={5} className={css.light} data-light="" data-from={from} data-to={to} data-at={at ?? ''}>
      <animateMotion ref={motion} dur="0.7s" begin="indefinite" fill="freeze" path={d} calcMode="spline" keyTimes="0;1" keySplines="0.3 0 0 1" />
    </circle>
  )
}

export interface LiveMapProps {
  progress: ScanProgress
  skew: number
  selected: string | null
  onSelect: (name: string) => void
  summary: string
  /** More controls for the toolbar row (the replay) */
  tools?: ReactNode
}

/** The second line of a stage's card: its timer, counted step and running step, or its state. */
function Line2({ stage, state, skew }: { stage: ScanStage; state: string; skew: number }) {
  const w = useScanWords()
  const { lang } = usePrefs()
  if (state === 'running') {
    const step = stage.steps.find((x) => x.status === 'running')
    const what = step?.kind === 'count' ? `${step.done}/${step.total}` : step ? fit(step.name, 12) : ''
    return <><Ticker since={stage.started_at} skew={skew} />{what ? ` · ${what}` : ''}</>
  }
  if (state === 'ok' && stage.seconds !== null) return <>{`${w('state_ok')} · ${1 > stage.seconds ? '<1' : Math.round(stage.seconds)}${lang === 'ar' ? ' ث' : ' s'}`}</>
  return <>{w.known('state_', state)}</>
}

/** One stage's card, in the state it is shown in; the running one with its glow (the time of its start line). */
interface StageNodeProps { stage: ScanStage; state: string; at: { x: number; y: number }; flow: string; selected: boolean; fresh: boolean; skew: number; onSelect: (name: string) => void }

function StageNode({ stage, state, at, flow, selected, fresh, skew, onSelect }: StageNodeProps) {
  const w = useScanWords()
  const { lang } = usePrefs()
  const [dot, x, end, dir] = lang === 'ar' ? [NODE_W - 14, NODE_W - 26, NODE_W - 12, 'rtl'] : [14, 26, 12, 'ltr']
  return (
    <g transform={`translate(${at.x},${at.y})`} onClick={() => onSelect(stage.name)} data-stage={stage.name} data-state={state} data-fresh={fresh ? '' : undefined}
      className={[css.node, css[`st_${state}`], !stage.requested && css.notAsked, selected && css.sel].filter(Boolean).join(' ')}>
      {state === 'running' && <rect className={css.halo} x={-7} y={-7} width={NODE_W + 14} height={NODE_H + 14} rx={16} data-glow="" data-at={stage.started_at ?? ''} />}
      <rect className={css.box} width={NODE_W} height={NODE_H} rx={11} />
      <circle className={css.stateDot} cx={dot} cy={20} r={4.5} />
      <text className={css.nodeTitle} x={x} y={24} direction={dir}>{fit(w.stageTitle(stage.name, flow), 17)}</text>
      <text className={css.nodeSub} x={end} y={44} direction={dir}><Line2 stage={stage} state={state} skew={skew} /></text>
    </g>
  )
}

/** The toolbar row above the canvas: what the page adds (the replay), follow, and zoom. */
interface ToolbarProps { tools?: ReactNode; following: boolean | null; onFollow: () => void; zoomBy: (factor: number) => void; fit: () => void }

function Toolbar({ tools, following, onFollow, zoomBy, fit: fitAll }: ToolbarProps) {
  const w = useScanWords()
  const mw = useMapWords()
  return (
    <div className={css.toolbar} role="toolbar" aria-label={w('tools')}>
      {tools}
      <span className={css.toolbarEnd}>
        {following !== null && (
          <AriaButton className={css.followBtn} onPress={onFollow} aria-pressed={following}><Icon name="live" />{w('follow')}</AriaButton>
        )}
        <span className={zoomCss.zoom} role="group" aria-label={mw('zoom')}>
          <AriaButton className={zoomCss.zoomBtn} aria-label={mw('zoomOut')} onPress={() => zoomBy(1 / 1.3)}><span aria-hidden="true">−</span></AriaButton>
          <AriaButton className={zoomCss.zoomBtn} aria-label={mw('zoomIn')} onPress={() => zoomBy(1.3)}><span aria-hidden="true">+</span></AriaButton>
          <AriaButton className={zoomCss.zoomBtn} aria-label={mw('zoomFit')} onPress={fitAll}><FitIcon /></AriaButton>
        </span>
      </span>
    </div>
  )
}

/** The flow runs the way the whole map reads larger in this box: left to right, or top to bottom. */
function useLayout(stages: ScanStage[], box: { w: number; h: number }): Layout {
  return useMemo(() => {
    const across = place(stages, true)
    const down = place(stages, false)
    const scale = (l: Layout) => Math.min((box.w - 16) / l.width, (box.h - 16) / l.height)
    return scale(across) >= scale(down) ? across : down
  }, [stages, box.w, box.h])
}

function edgeClass(from: string | undefined, to: string | undefined, near: boolean, asked: boolean): string {
  const passed = from === 'ok' && to !== undefined && to !== 'waiting' && to !== 'not_reached'
  return [css.edge, passed && css.edgePassed, from === 'ok' && to === 'running' && css.edgeInto, near && css.edgeNear, !asked && css.edgeOff].filter(Boolean).join(' ')
}

/** The last stage that left waiting, else the first: where the camera rests when nothing runs. */
function lastMoved(stages: ScanStage[]): string {
  return [...stages].reverse().find((s) => s.state !== 'waiting')?.name ?? stages[0]?.name ?? ''
}

/** The camera: the whole map when it reads, else it follows the running (or chosen) stage until the person moves it
 * themselves. */
function useCamera(layout: Layout, box: { w: number; h: number }, focusName: string, over: boolean, setT: (t: ZoomState) => void) {
  const [following, setFollowing] = useState(true)
  const focus = layout.at.get(focusName)
  const phone = 600 > box.w
  useEffect(() => {
    if (following) setT(firstView(layout, box, focus, phone ? 0.78 : 0.86, over && !phone ? 0.5 : 0.7))
  }, [following, layout, box, focus, phone, over, setT])
  return { following, setFollowing, focus }
}

/** The links between stages, each in the shown state of its two ends, and the lights travelling on them. */
function Links({ drawn, looks, lights, selected, asked }: { drawn: Link[]; looks: Map<string, string>; lights: Light[]; selected: string | null; asked: Set<string> }) {
  return (
    <>
      {drawn.map((link) => <path key={`${link.from}>${link.to}`} d={link.d} className={edgeClass(looks.get(link.from), looks.get(link.to),
        link.from === selected || link.to === selected, asked.has(link.to))} />)}
      {lights.map((light) => {
        const link = drawn.find((l) => l.from === light.from && l.to === light.to)
        return link && <TravellingLight key={`${light.from}>${light.to}@${light.at}`} d={link.d} from={light.from} to={light.to} at={light.at} />
      })}
    </>
  )
}

export function LiveMap({ progress, skew, selected, onSelect, summary, tools }: LiveMapProps) {
  const w = useScanWords()
  const reduced = useReducedMotion()
  const motion = useMotion(progress, reduced)
  const svg = useRef<SVGSVGElement>(null)
  const [attach, box] = useBox()
  const zoom = useZoom(svg)
  const stages = progress.stages
  const layout = useLayout(stages, box)
  const drawn = useMemo(() => links(stages, layout), [stages, layout])
  const looks = new Map(stages.map((s) => [s.name, shownState(progress, { ...s, state: motion.shown[s.name] ?? s.state })]))
  const running = stages.find((s) => looks.get(s.name) === 'running')
  const camera = useCamera(layout, box, running?.name ?? selected ?? lastMoved(stages), progress.state !== 'running', zoom.setT)
  const takeOver = () => camera.setFollowing(false)
  const wrap = useRef<HTMLDivElement>(null)
  const runningName = running?.name
  useEffect(() => {        // following, the page too brings the map into view each time a stage starts
    if (camera.following && runningName) wrap.current?.scrollIntoView({ block: 'nearest', behavior: reduced ? 'auto' : 'smooth' })
  }, [camera.following, runningName, reduced])
  const fitAll = () => { takeOver(); zoom.setT(centred(layout, box, camera.focus, Math.max(0.7, Math.min(1, (box.w - 16) / layout.width, (box.h - 16) / layout.height)))) }
  const t = zoom.t

  return (
    <div className={css.mapWrap} ref={wrap}>
      <Toolbar tools={tools} following={running ? camera.following : null} onFollow={() => camera.setFollowing(!camera.following)}
        zoomBy={(factor) => { takeOver(); zoom.zoomBy(factor) }} fit={fitAll} />
      <div className={css.canvasWrap}>
      <div className={[frame.canvas, css.canvas].join(' ')} ref={attach} onPointerDown={takeOver} onWheel={takeOver} data-motion={reduced ? 'reduced' : 'full'}>
        <svg ref={svg} className={frame.canvasSvg} viewBox={`0 0 ${Math.max(box.w, 1)} ${Math.max(box.h, 1)}`} preserveAspectRatio="xMinYMin meet"
          direction="ltr" role="img" aria-label={w('mapAria', { n: stages.length, s: summary })} data-dragging={zoom.dragging ? '' : undefined}>
          <g transform={`translate(${t.x},${t.y}) scale(${t.k})`}>
            <Links drawn={drawn} looks={looks} lights={motion.lights} selected={selected} asked={new Set(stages.filter((s) => s.requested).map((s) => s.name))} />
            {stages.map((s) => layout.at.has(s.name) && (
              <StageNode key={s.name} stage={s} state={looks.get(s.name) as string} at={layout.at.get(s.name) as At} flow={progress.flow ?? 'check'}
                selected={s.name === selected} fresh={s.name in motion.fresh} skew={skew} onSelect={onSelect} />
            ))}
          </g>
        </svg>
      </div>
      </div>
    </div>
  )
}
