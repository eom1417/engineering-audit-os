// "Live check": EAOS's own work as it runs, whoever started it (the assistant, `eaos start`, the Studio). The journey
// strip shows the four steps of the work; the map below draws the chosen step's flow (by default the one running), its
// toolbar in a row above it. The run line says where the flow is (stage n of N, elapsed, and a time left only from the
// last run of this project); the panel tells the chosen stage (beside the map on the desktop, a bottom sheet on the
// phone); the stage list under the map is the way to every stage by keyboard and touch. After a check, "replay" plays
// its real progress file again, faster, labelled as a replay. It stays after the run as the record of the last one.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { Button } from '../../components/Button'
import { Chip, type Tone } from '../../components/Chip'
import { Panel, Skeleton, StateMessage } from '../../components/Panel'
import { Sheet } from '../../components/Sheet'
import { useActions } from '../../data/actions/store'
import type { Run } from '../../data/actions/types'
import { useLive } from '../../data/context'
import { clock, ENDED, shownState, summarize, type AllProgress, type Estimate, type JourneyStep, type RunState, type ScanProgress, type ScanStage } from '../../data/scan'
import { runningFlow, useScan, type Transport } from '../../data/ScanProvider'
import { usePrefs } from '../../i18n/prefs'
import { When } from '../../i18n/text'
import { usePageChrome } from '../../shell/chrome'
import { layout } from '../../shell/Layout'
import { usePhone } from '../SystemMap'
import { Journey } from './Journey'
import { LiveMap } from './LiveMap'
import { useReplay, type Replay } from './replay'
import { StagePanel } from './StagePanel'
import { TickerText } from './Ticker'
import { useScanWords } from './words'
import css from './scan.module.css'

const RUN_TONE: Record<string, Tone> = { COMPLETE: 'good', PARTIAL: 'warning', INCOMPLETE: 'warning', ERROR: 'critical', STOPPED: 'warning' }
const SPEEDS = [10, 30]
const ANNOUNCE_MS = 3000

/** Why the page cannot draw a flow yet: a snapshot, the first read, or no stages to draw; null when it can. */
function blocked(mode: string, all: AllProgress | null, flow: string): 'snapshot' | 'loading' | 'none' | null {
  if (mode !== 'live') return 'snapshot'
  if (!all) return 'loading'
  return all.flows[flow]?.stages.length ? null : 'none'
}

function Blocked({ why }: { why: 'snapshot' | 'loading' | 'none' }) {
  const w = useScanWords()
  if (why === 'loading') return <div className={layout.page}><Head /><Panel><Skeleton label={w('loading')} /></Panel></div>
  return <div className={layout.page}><Head /><Panel><StateMessage icon="live" title={w(`${why}Title`)} sub={w(`${why}Sub`)} /></Panel></div>
}

export function LiveCheckPage() {
  const w = useScanWords()
  const { mode } = useLive()
  const { all, skew, transport } = useScan()
  const search = useSearch({ strict: false }) as { stage?: string; flow?: string }
  const navigate = useNavigate()
  const flow = search.flow || runningFlow(all) || 'check'
  usePageChrome(w('title'))
  const why = blocked(mode, all, flow)
  if (why || !all) return <Blocked why={why ?? 'loading'} />
  const show = (next: { flow?: string; stage?: string }) => void navigate({ to: '/scan', search: { flow: next.flow || flow, stage: next.stage }, replace: true })
  return <Flow all={all} flow={flow} skew={skew} transport={transport} stage={search.stage || null} show={show} />
}

interface FlowProps { all: AllProgress; flow: string; skew: number; transport: Transport; stage: string | null; show: (next: { flow?: string; stage?: string }) => void }

/** From the press of Check until the check it asked for writes its first line: until then the page holds the last run. */
export function starting(active: Run | null, progress: ScanProgress): boolean {
  if (active?.action !== 'audit' || progress.state === 'running') return false
  return !progress.started_at || Date.parse(active.started ?? active.created) > Date.parse(progress.started_at) + 1000
}

function Flow({ all, flow, skew, transport, stage, show }: FlowProps) {
  const replay = useReplay(all.flows.check)
  const { active } = useActions()
  const live = all.flows[flow]
  const shown = flow === 'check' ? replay.replay : null
  const view = shown ?? { id: 0, speed: undefined, progress: live, skew }
  const tools = flow === 'check' && live.run && live.state !== 'running' && !shown ? <ReplayTools start={replay.start} /> : null
  return (
    <div className={[layout.page, css.page].join(' ')} data-run={view.progress.run} data-run-state={view.progress.state} data-flow={flow}
      data-transport={transport} data-replay={view.speed}>
      <Head><RunLine progress={view.progress} skew={view.skew} journey={all.journey} /></Head>
      <Journey steps={all.journey} flow={flow} onFlow={(next) => show({ flow: next })} />
      <Notes progress={view.progress} replay={shown} stop={replay.stop} starting={flow === 'check' && starting(active, live)} />
      <Live key={`${flow}-${view.id}`} progress={view.progress} skew={view.skew} chosen={stage} select={(name) => show({ stage: name })} tools={tools} />
      <Announcer progress={view.progress} journey={all.journey} />
    </div>
  )
}

interface NotesProps { progress: ScanProgress; replay: Replay | null; stop: () => void; starting: boolean }

/** The lines above the map: a check asked for says it is starting, a replay says it is one, and a run nobody hears
 * from says so. */
function Notes({ progress, replay, stop, starting }: NotesProps) {
  const w = useScanWords()
  const quiet = progress.state === 'interrupted' || progress.state === 'stalled'
  return (
    <>
      {starting && <div className={css.replayNote} role="status" data-starting="">{w('starting')}</div>}
      {replay && (
        <div className={css.replayNote} role="note">
          <span>{w('replaying', { s: replay.speed })}</span>
          <Button variant="secondary" className={css.bigBtn} onPress={stop}>{w('replayEnd')}</Button>
        </div>
      )}
      {quiet && <div className={css.warn} role="note">{w(progress.state === 'stalled' ? 'stalledSub' : 'interruptedSub')}</div>}
    </>
  )
}

function Head({ children }: { children?: React.ReactNode }) {
  const w = useScanWords()
  return (
    <div className={css.head}>
      <h1 className={css.title}>{w('title')}</h1>
      <p className={css.lead}>{w('lead')}</p>
      {children}
    </div>
  )
}

interface ReplayToolsProps { start: (speed: number) => Promise<void> }

function ReplayTools({ start }: ReplayToolsProps) {
  const w = useScanWords()
  return (
    <span className={css.replayTools} role="group" aria-label={w('replay')}>
      <span className={css.replayLabel}>{w('replay')}</span>
      {SPEEDS.map((speed) => (
        <AriaButton key={speed} className={css.toolBtn} onPress={() => void start(speed)} data-replay-speed={speed}
          aria-label={w('replay') + ' ' + w('replayAt', { s: speed })}><bdi dir="ltr">{w('replayAt', { s: speed })}</bdi></AriaButton>
      ))}
    </span>
  )
}

/** Chooses a stage (undefined: none, which closes the phone's sheet). */
type Select = (name: string | undefined) => void

/** The stage the panel shows when none is chosen: the running one, else the one that failed, else the last ended. */
function fallbackStage(progress: ScanProgress): ScanStage {
  return progress.stages.find((s) => s.state === 'running') ?? progress.stages.find((s) => s.state === 'failed')
    ?? [...progress.stages].reverse().find((s) => s.requested && ENDED.includes(s.state)) ?? progress.stages[0]
}

interface LiveProps { progress: ScanProgress; skew: number; chosen: string | null; select: Select; tools: React.ReactNode }
interface StageSideProps { stage: ScanStage; picked: boolean; progress: ScanProgress; skew: number; select: Select }

/** "Stage n of N" while it runs, "n of N stages" ended once it has stopped. */
function whereWords(progress: ScanProgress, w: ReturnType<typeof useScanWords>): string {
  const sum = summarize(progress)
  return sum.running.length ? w('stageOf', { n: sum.position, t: sum.total }) : w('endedOf', { n: sum.ended, t: sum.total })
}

/** What the map's picture says to a screen reader: the flow's state, its running stage, where it is. */
function mapSummary(progress: ScanProgress, w: ReturnType<typeof useScanWords>): string {
  const running = progress.stages.find((s) => s.state === 'running')
  const now = running ? w.stageTitle(running.name, progress.flow ?? 'check') + ': ' + w('state_running') + '. ' : ''
  return w.known('run_', progress.state) + '. ' + now + whereWords(progress, w)
}

/** The chosen stage's panel: beside the map, or on the phone a bottom sheet that opens when a stage is chosen. */
function StageSide({ stage, picked, progress, skew, select }: StageSideProps) {
  const w = useScanWords()
  const phone = usePhone()
  const panel = <StagePanel stage={stage} progress={progress} skew={skew} onSelect={select} />
  const title = w.stageTitle(stage.name, progress.flow ?? 'check')
  if (phone) return <Sheet isOpen={picked} onOpenChange={(open) => { if (!open) select(undefined) }} title={title}>{panel}</Sheet>
  return <Panel className={css.stagePanel} label={title}>{panel}</Panel>
}

function Live({ progress, skew, chosen, select, tools }: LiveProps) {
  const w = useScanWords()
  const picked = progress.stages.find((s) => s.name === chosen)
  const selected = picked ?? fallbackStage(progress)
  return (
    <div className={css.grid}>
      <Panel className={css.mapPanel} label={w('map')}>
        <LiveMap progress={progress} skew={skew} selected={selected.name} onSelect={select} summary={mapSummary(progress, w)} tools={tools} />
      </Panel>
      <StageSide stage={selected} picked={!!picked} progress={progress} skew={skew} select={select} />
      <StageList progress={progress} selected={selected.name} onSelect={select} />
    </div>
  )
}

function runTone(progress: ScanProgress): Tone {
  const tones: Partial<Record<RunState, Tone>> = { running: 'accent', none: 'neutral', done: RUN_TONE[String(progress.status)] || 'neutral' }
  return tones[progress.state] || 'warning'
}

/** The time left: a range from the server's estimate, or why there is none. */
function Left({ estimate }: { estimate: Estimate }) {
  const w = useScanWords()
  const { num } = usePrefs()
  const [low, high] = [estimate.low ?? 0, estimate.high ?? 0]
  const text = estimate.basis === 'first_run' ? w('firstRun')
    : 60 > high ? w('leftLess') : w('left', { a: num(Math.max(1, Math.round(low / 60))), b: num(Math.ceil(high / 60)) })
  return <span className={css.runFact} title={w('leftWhy')}>{text}</span>
}

function RunLine({ progress, skew, journey }: { progress: ScanProgress; skew: number; journey: JourneyStep[] }) {
  const w = useScanWords()
  const { lang } = usePrefs()
  const state = progress.state
  const step = journey.find((s) => s.flow === progress.flow)
  const status = state === 'done' && progress.status ? ` · ${w.known('status_', progress.status)}` : ''
  return (
    <div className={css.runLine} data-hook="scan-run-line">
      <Chip tone={runTone(progress)}>{step ? `${step.title[lang]} · ` : ''}{w.known('run_', state)}{status}</Chip>
      {state !== 'none' && <span className={css.runFact}>{whereWords(progress, w)}</span>}
      {state === 'running' && <span className={css.runFact}>{w('elapsed')} <TickerText since={progress.started_at} skew={skew} /></span>}
      {state === 'done' && <span className={css.runFact}>{w('took')} <bdi dir="ltr">{clock(progress.seconds)}</bdi></span>}
      {state === 'running' && progress.estimate && <Left estimate={progress.estimate} />}
      {progress.started_at && <span className={css.runFact}>{w('started')} <When iso={progress.started_at} /></span>}
    </div>
  )
}

interface StageListProps { progress: ScanProgress; selected: string | null; onSelect: (name: string) => void }

function StageList({ progress, selected, onSelect }: StageListProps) {
  const w = useScanWords()
  const { lang } = usePrefs()
  const flow = progress.flow ?? 'check'
  const ordered = useMemo(() => [...progress.stages].sort((a, b) => (a.layer ?? 0) - (b.layer ?? 0) || (a.order ?? 0) - (b.order ?? 0)), [progress.stages])
  return (
    <Panel className={css.listPanel} as="section" label={w('stages')}>
      <h2 className={css.blockTitle}>{w('stages')}</h2>
      <ul className={css.list}>
        {ordered.map((s) => {
          const state = shownState(progress, s)
          const counted = state === 'running' ? s.steps.find((x) => x.status === 'running' && x.kind === 'count') : undefined
          return (
            <li key={s.name}>
              <AriaButton className={[css.listRow, s.name === selected && css.listSel].filter(Boolean).join(' ')} onPress={() => onSelect(s.name)}
                aria-pressed={s.name === selected} data-list-stage={s.name} data-list-state={state}>
                <span className={[css.listDot, css[`dot_${state}`]].join(' ')} aria-hidden="true" />
                <span className={css.listMain}>
                  <span className={css.listTitle}>{w.stageTitle(s.name, flow)}</span>
                  <span className={css.listSub}>{w.known('state_', state)}{state === 'ok' && s.seconds !== null ? ` · ${s.seconds}${lang === 'ar' ? ' ث' : ' s'}` : ''}
                    {counted ? <> · <bdi dir="ltr">{counted.done}/{counted.total}</bdi></> : null}</span>
                </span>
              </AriaButton>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}

/** The latest thing that happened in the flow, in words: a stage that started or ended, or the flow's end. */
function latest(progress: ScanProgress, journey: JourneyStep[], w: ReturnType<typeof useScanWords>, lang: 'ar' | 'en'): string {
  const flow = progress.flow ?? 'check'
  if (progress.state === 'done') {
    const step = journey.find((s) => s.flow === flow)
    return w('announceRun', { f: step ? step.title[lang] : flow, w: w.known('status_', progress.status ?? '') })
  }
  const moments = progress.stages.filter((s) => s.requested && s.state !== 'skipped')
    .flatMap((s) => [{ at: s.started_at, text: w('announceStarted', { s: w.stageTitle(s.name, flow) }) },
      { at: s.ended_at, text: w('announceEnded', { s: w.stageTitle(s.name, flow), w: w.known('state_', s.state) }) }])
    .filter((m) => m.at)
  return moments.sort((a, b) => (a.at ?? '').localeCompare(b.at ?? '')).pop()?.text ?? ''
}

/** Says politely what happened, in the person's language, at most once every 3 s (the newest news wins). */
function Announcer({ progress, journey }: { progress: ScanProgress; journey: JourneyStep[] }) {
  const w = useScanWords()
  const { lang } = usePrefs()
  const text = latest(progress, journey, w, lang)
  const [said, setSaid] = useState(text)
  const last = useRef(0)
  useEffect(() => {
    const timer = window.setTimeout(() => { last.current = Date.now(); setSaid(text) }, Math.max(0, last.current + ANNOUNCE_MS - Date.now()))
    return () => window.clearTimeout(timer)
  }, [text])
  return <div className="sr" role="status" aria-live="polite">{said}</div>
}
