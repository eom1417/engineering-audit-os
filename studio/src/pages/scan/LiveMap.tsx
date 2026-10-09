// The check's stages drawn live (the canvas, zoom and pan of the pipeline map: useZoom, the paths frame). Each stage
// is a card in its state's colour with its timer; the running one glows; a light runs along each link into it from the
// stages it needed, and once along each link out of a stage that has just ended to the stages it opened. Only those few
// elements move; with reduced motion nothing moves and the state is told by colour, outline and words alone.
// The drawing is a picture (role img): the stage list under it is the way to every stage by keyboard and touch.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { opened, type ScanProgress, type ScanStage } from '../../data/scan'
import { usePrefs } from '../../i18n/prefs'
import { FitIcon } from '../../map/parts'
import zoomCss from '../../map/parts.module.css'
import { useZoom } from '../../map/useZoom'
import { useMapWords } from '../../map/words'
import { Icon } from '../../components/Icon'
import frame from '../paths/paths.module.css'
import { centred, firstView, links, NODE_H, NODE_W, place } from './geometry'
import { Ticker } from './Ticker'
import { useScanWords } from './words'
import css from './scan.module.css'

const BURST_MS = 1300

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

function fit(text: string, room: number): string {
  return text.length <= room ? text : text.slice(0, room - 1) + '…'
}

/** One dot that runs once along `d`, from the moment it is drawn. */
function Burst({ d }: { d: string }) {
  const motion = useRef<SVGAnimateMotionElement>(null)
  useEffect(() => { try { motion.current?.beginElement() } catch { /* no SMIL: the dot stays at its start */ } }, [])
  return (
    <circle r={5} className={css.burst}>
      <animateMotion ref={motion} dur="0.9s" begin="indefinite" fill="freeze" path={d} calcMode="spline" keyTimes="0;1" keySplines="0.3 0 0 1" />
    </circle>
  )
}

export interface LiveMapProps {
  progress: ScanProgress
  skew: number
  lastEnded: { stage: string; at: number } | null
  selected: string | null
  onSelect: (name: string) => void
  summary: string
}

export function LiveMap({ progress, skew, lastEnded, selected, onSelect, summary }: LiveMapProps) {
  const w = useScanWords()
  const mw = useMapWords()
  const { lang } = usePrefs()
  const reduced = useReducedMotion()
  const svg = useRef<SVGSVGElement>(null)
  const [attach, box] = useBox()
  const zoom = useZoom(svg)
  const { setT } = zoom
  const stages = progress.stages
  // the flow runs the way the whole map reads larger in this box: left to right, or top to bottom
  const layout = useMemo(() => {
    const across = place(stages, true)
    const down = place(stages, false)
    const scale = (l: typeof across) => Math.min((box.w - 16) / l.width, (box.h - 16) / l.height)
    return scale(across) >= scale(down) ? across : down
  }, [stages, box.w, box.h])
  const drawn = useMemo(() => links(stages, layout), [stages, layout])
  const by = useMemo(() => new Map(stages.map((s) => [s.name, s])), [stages])
  const running = stages.find((s) => s.state === 'running')
  const interrupted = progress.state === 'interrupted'

  // the camera: the whole map when it reads, else it follows the running stage until the person moves it themselves
  const [follow, setFollow] = useState(true)
  const focusName = running?.name ?? selected ?? [...stages].reverse().find((s) => s.state !== 'waiting')?.name ?? stages[0]?.name
  const focus = focusName ? layout.at.get(focusName) : undefined
  const phone = box.w < 600
  const over = progress.state !== 'running'
  useEffect(() => {
    if (follow) setT(firstView(layout, box, focus, phone ? 0.78 : 0.86, over && !phone ? 0.5 : 0.7))
  }, [follow, layout, box, focus, phone, over, setT])
  const takeOver = () => setFollow(false)

  // the burst out of the stage that just ended, for a moment
  const [burst, setBurst] = useState<{ from: string; to: string[]; key: number } | null>(null)
  useEffect(() => {
    if (!lastEnded || reduced || Date.now() - lastEnded.at > BURST_MS) return
    setBurst({ from: lastEnded.stage, to: opened(progress, lastEnded.stage), key: lastEnded.at })
    const done = window.setTimeout(() => setBurst(null), BURST_MS)
    return () => window.clearTimeout(done)
    // only a new end starts a burst; the progress it reads is the one that came with it
  }, [lastEnded, reduced])

  const t = zoom.t
  const stateOf = (s: ScanStage) => (interrupted && s.state === 'running' ? 'stopped' : s.state)
  const line2 = (s: ScanStage) => {
    const state = stateOf(s)
    if (state === 'running') {
      const step = s.steps.find((x) => x.status === 'running')
      const total = s.steps[0]?.total
      const done = s.steps.filter((x) => !['waiting', 'running'].includes(x.status)).length
      return <><Ticker since={s.started_at} skew={skew} />{total ? ` · ${done}/${total}` : ''}{step ? ` · ${fit(step.name, 12)}` : ''}</>
    }
    if (state === 'ok') return `${w('state_ok')} · ${s.seconds !== null && s.seconds < 1 ? '<1' : Math.round(s.seconds ?? 0)}${lang === 'ar' ? ' ث' : ' s'}`
    return w.known('state_', state)
  }

  return (
    <div className={[frame.canvasWrap, css.mapWrap].join(' ')}>
      <div className={css.mapTools}>
        {!follow && running && (
          <AriaButton className={css.followBtn} onPress={() => setFollow(true)}><Icon name="live" />{w('follow')}</AriaButton>
        )}
        <div className={zoomCss.zoom} role="group" aria-label={mw('zoom')}>
          <AriaButton className={zoomCss.zoomBtn} aria-label={mw('zoomOut')} onPress={() => { takeOver(); zoom.zoomBy(1 / 1.3) }}><span aria-hidden="true">−</span></AriaButton>
          <AriaButton className={zoomCss.zoomBtn} aria-label={mw('zoomIn')} onPress={() => { takeOver(); zoom.zoomBy(1.3) }}><span aria-hidden="true">+</span></AriaButton>
          <AriaButton className={zoomCss.zoomBtn} aria-label={mw('zoomFit')} onPress={() => { takeOver(); setT(centred(layout, box, focus, Math.max(0.7, Math.min(1, (box.w - 16) / layout.width, (box.h - 16) / layout.height)))) }}><FitIcon /></AriaButton>
        </div>
      </div>
      <div className={[frame.canvas, css.canvas].join(' ')} ref={attach} onPointerDown={takeOver} onWheel={takeOver} data-motion={reduced ? 'reduced' : 'full'}>
        <svg ref={svg} className={frame.canvasSvg} viewBox={`0 0 ${Math.max(box.w, 1)} ${Math.max(box.h, 1)}`} preserveAspectRatio="xMinYMin meet"
          direction="ltr" role="img" aria-label={w('mapAria', { n: stages.length, s: summary })} data-dragging={zoom.dragging ? '' : undefined}>
          <g transform={`translate(${t.x},${t.y}) scale(${t.k})`}>
            {drawn.map((link) => {
              const a = by.get(link.from)
              const b = by.get(link.to)
              const into = b?.state === 'running' && a?.state === 'ok' && !interrupted
              const passed = a?.state === 'ok' && b && b.state !== 'waiting' && b.state !== 'not_reached'
              const near = selected && (link.from === selected || link.to === selected)
              return <path key={`${link.from}>${link.to}`} d={link.d}
                className={[css.edge, passed && css.edgePassed, into && css.edgeInto, near && css.edgeNear, !b?.requested && css.edgeOff].filter(Boolean).join(' ')} />
            })}
            {!reduced && !interrupted && drawn.filter((link) => by.get(link.to)?.state === 'running' && by.get(link.from)?.state === 'ok').map((link) => (
              <circle key={`flow-${link.from}>${link.to}`} r={4.5} className={css.flow} data-flow="">
                <animateMotion dur="1.5s" repeatCount="indefinite" path={link.d} />
              </circle>
            ))}
            {burst && drawn.filter((link) => link.from === burst.from && burst.to.includes(link.to)).map((link) => <Burst key={`${burst.key}-${link.to}`} d={link.d} />)}
            {stages.map((s) => {
              const at = layout.at.get(s.name)
              if (!at) return null
              const state = stateOf(s)
              const title = w.stageTitle(s.name)
              return (
                <g key={s.name} transform={`translate(${at.x},${at.y})`} onClick={() => onSelect(s.name)} data-stage={s.name} data-state={state}
                  className={[css.node, css[`st_${state}`], !s.requested && css.notAsked, s.necessity === 'optional' && css.optional, s.name === selected && css.sel].filter(Boolean).join(' ')}>
                  {state === 'running' && <rect className={css.halo} x={-7} y={-7} width={NODE_W + 14} height={NODE_H + 14} rx={16} data-glow="" />}
                  <rect className={css.box} width={NODE_W} height={NODE_H} rx={11} />
                  <circle className={css.stateDot} cx={lang === 'ar' ? NODE_W - 14 : 14} cy={20} r={4.5} />
                  <text className={css.nodeTitle} x={lang === 'ar' ? NODE_W - 26 : 26} y={24} direction={lang === 'ar' ? 'rtl' : 'ltr'}>{fit(title, 17)}</text>
                  <text className={css.nodeSub} x={lang === 'ar' ? NODE_W - 12 : 12} y={44} direction={lang === 'ar' ? 'rtl' : 'ltr'}>{line2(s)}</text>
                </g>
              )
            })}
          </g>
        </svg>
      </div>
    </div>
  )
}
