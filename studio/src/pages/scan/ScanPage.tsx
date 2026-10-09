// "Live check": EAOS's own stages as the check runs, whoever started it (the assistant, `eaos start`, the Studio).
// The header says where the run is (stage n of N, elapsed, and a time left only when the last run of this project is
// known); the map draws the stages with their states; the panel tells the chosen stage: what it does, its timer, its
// steps (each tool inside `engines`, each extractor inside `facts`), what it produced, and why it did not run. The
// stage list under the map is the same stages as rows, the way to every stage by keyboard and touch.
// It stays after the run as the record of the last check.
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useMemo, useState, type ReactNode } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { Button } from '../../components/Button'
import { Chip, type Tone } from '../../components/Chip'
import { Panel, Props, Skeleton, StateMessage } from '../../components/Panel'
import { useLive } from '../../data/context'
import { ENDED, clock, secondsLeft, summarize, type ScanProgress, type ScanStage } from '../../data/scan'
import { useScan } from '../../data/ScanProvider'
import { usePrefs } from '../../i18n/prefs'
import { Id, Txt, When } from '../../i18n/text'
import { layout } from '../../shell/Layout'
import { LiveMap } from './LiveMap'
import { TickerText } from './Ticker'
import { useScanWords } from './words'
import css from './scan.module.css'

export const STATE_TONE: Record<string, Tone> = {
  waiting: 'neutral', running: 'accent', ok: 'good', skipped: 'neutral', unavailable: 'warning', failed: 'critical',
  not_reached: 'neutral', stopped: 'warning',
}
const STEP_TONE: Record<string, Tone> = {
  waiting: 'neutral', running: 'accent', ok: 'good', observed: 'good', unavailable: 'warning', not_applicable: 'neutral', error: 'critical',
}
/** Steps shown before "show all": a long stage (21 tools) folds, as every long phone list does (DESIGN.md). */
const STEPS_FIRST = 8
const RUN_TONE: Record<string, Tone> = { COMPLETE: 'good', PARTIAL: 'warning', INCOMPLETE: 'warning', ERROR: 'critical', STOPPED: 'warning' }

export function ScanPage() {
  const w = useScanWords()
  const { mode } = useLive()
  const { progress, skew, lastEnded } = useScan()
  const search = useSearch({ strict: false }) as { stage?: string }
  const navigate = useNavigate()
  const select = (name: string) => void navigate({ to: '/scan', search: { stage: name }, replace: true })

  if (mode !== 'live') {
    return <div className={layout.page}><Head /><Panel><StateMessage icon="live" title={w('snapshotTitle')} sub={w('snapshotSub')} /></Panel></div>
  }
  if (!progress) return <div className={layout.page}><Head /><Panel><Skeleton label={w('loading')} /></Panel></div>
  if (progress.state === 'none' || !progress.stages.length) {
    return <div className={layout.page}><Head /><Panel><StateMessage icon="live" title={w('noneTitle')} sub={w('noneSub')} /></Panel></div>
  }
  return <Live progress={progress} skew={skew} lastEnded={lastEnded} chosen={search.stage ?? null} select={select} />
}

function Head({ children }: { children?: ReactNode }) {
  const w = useScanWords()
  return (
    <div className={css.head}>
      <h1 className={css.title}>{w('title')}</h1>
      <p className={css.lead}>{w('lead')}</p>
      {children}
    </div>
  )
}

function Live({ progress, skew, lastEnded, chosen, select }:
  { progress: ScanProgress; skew: number; lastEnded: { stage: string; at: number } | null; chosen: string | null; select: (name: string) => void }) {
  const w = useScanWords()
  const sum = summarize(progress)
  const interrupted = progress.state === 'interrupted'
  const running = sum.running[0]
  const fallback = running ?? progress.stages.find((s) => s.state === 'failed') ?? [...progress.stages].reverse().find((s) => s.requested && ENDED.includes(s.state)) ?? progress.stages[0]
  const selected = progress.stages.find((s) => s.name === chosen) ?? fallback
  const words = running ? w('stageOf', { n: sum.position, t: sum.total }) : w('endedOf', { n: sum.ended, t: sum.total })
  const mapSummary = `${w.known('run_', progress.state)}. ${running ? `${w.stageTitle(running.name)}: ${w('state_running')}. ` : ''}${words}`
  return (
    <div className={[layout.page, css.page].join(' ')} data-run={progress.run ?? ''} data-run-state={progress.state}>
      <Head><RunLine progress={progress} skew={skew} /></Head>
      {interrupted && <div className={css.warn} role="note">{w('interruptedSub')}</div>}
      <div className={css.grid}>
        <Panel className={css.mapPanel} label={w('map')}>
          <LiveMap progress={progress} skew={skew} lastEnded={lastEnded} selected={selected?.name ?? null} onSelect={select} summary={mapSummary} />
        </Panel>
        {selected && <StagePanel stage={selected} progress={progress} skew={skew} onSelect={select} />}
        <StageList progress={progress} selected={selected?.name ?? null} onSelect={select} />
      </div>
      <Announcer progress={progress} />
    </div>
  )
}

function RunLine({ progress, skew }: { progress: ScanProgress; skew: number }) {
  const w = useScanWords()
  const { num } = usePrefs()
  const sum = summarize(progress)
  const running = progress.state === 'running'
  const left = secondsLeft(progress, skew)
  const tone: Tone = running ? 'accent' : progress.state === 'interrupted' ? 'warning' : RUN_TONE[progress.status ?? ''] ?? 'neutral'
  return (
    <div className={css.runLine} data-hook="scan-run-line">
      <Chip tone={tone}>{w.known('run_', progress.state)}{progress.state === 'done' && progress.status ? ` · ${w.known('status_', progress.status)}` : ''}</Chip>
      <span className={css.runFact}>{running ? w('stageOf', { n: sum.position, t: sum.total }) : w('endedOf', { n: sum.ended, t: sum.total })}</span>
      <span className={css.runFact}>
        {running
          ? <>{w('elapsed')} <TickerText since={progress.started_at} skew={skew} /></>
          : <>{w('took')} <bdi dir="ltr">{clock(progress.seconds)}</bdi></>}
      </span>
      {running && (left === null
        ? <span className={css.runFact}>{Object.keys(progress.previous).length ? null : w('firstRun')}</span>
        : <span className={css.runFact} title={w('leftWhy')}>{left < 60 ? w('leftLess') : w('left', { m: num(Math.ceil(left / 60)) })}</span>)}
      {progress.started_at && <span className={css.runFact}>{w('started')} <When iso={progress.started_at} /></span>}
    </div>
  )
}

function StagePanel({ stage, progress, skew, onSelect }: { stage: ScanStage; progress: ScanProgress; skew: number; onSelect: (name: string) => void }) {
  const w = useScanWords()
  const { lang, t } = usePrefs()
  const [stepsOpen, setStepsOpen] = useState(false)
  const state = progress.state === 'interrupted' && stage.state === 'running' ? 'stopped' : stage.state
  const last = progress.previous[stage.name]
  const unit = lang === 'ar' ? ' ث' : ' s'
  const rows: [ReactNode, ReactNode, boolean?][] = []
  rows.push([w('needs'), stage.requires.length
    ? <span className={css.needs}>{stage.requires.map((name) => (
        <AriaButton key={name} className={css.needLink} onPress={() => onSelect(name)}>{w.stageTitle(name)}</AriaButton>))}</span>
    : w('needsNothing')])
  rows.push([w('necessity'), <>{w(stage.necessity === 'optional' ? 'optional' : 'required')}{stage.necessity === 'optional' && stage.absent_when
    ? <span className={css.muted}> · {w('absentWhen')}: <Txt>{w.absent(stage.name, stage.absent_when)}</Txt></span> : null}</>])
  const time = state === 'running' ? <TickerText since={stage.started_at} skew={skew} />
    : stage.seconds !== null && ENDED.includes(stage.state) && stage.state !== 'not_reached' && stage.state !== 'skipped' ? <bdi dir="ltr">{stage.seconds}{unit}</bdi> : null
  if (time || last !== undefined) rows.push([w('time'), <>{time}{last !== undefined ? <span className={css.muted}>{time ? ' · ' : ''}{w('lastTime', { t: `${last}${unit}` })}</span> : null}</>])
  const reasonShown = stage.reason && state !== 'ok'
  const detail = Object.entries(stage.detail ?? {})
  return (
    <Panel className={css.stagePanel} label={w.stageTitle(stage.name)}>
      <div className={css.stageHead} data-hook="scan-stage-panel" data-stage={stage.name}>
        <h2 className={css.stageTitle}>{w.stageTitle(stage.name)} <Id value={stage.name} className={css.stageId} /></h2>
        <Chip tone={STATE_TONE[state] ?? 'neutral'}>{w.known('state_', state)}</Chip>
      </div>
      <p className={css.about}>{w.about(stage.name, stage.description)}</p>
      {stage.resumed && <p className={css.muted}>{w('keptFromBefore')}</p>}
      {reasonShown && <div className={state === 'failed' ? css.reasonBad : css.reason}><strong>{w('why')}:</strong> <Txt>{stage.reason}</Txt></div>}
      <Props rows={rows} />
      {stage.steps.length > 0 && (
        <section className={css.block} aria-label={w('steps')}>
          <h3 className={css.blockTitle}>{w('steps')} <span className={css.muted}>{w('stepsOf', { d: stage.steps.filter((s) => !['waiting', 'running'].includes(s.status)).length, t: stage.steps.length })}</span></h3>
          <ul className={css.steps}>
            {(stepsOpen || stage.steps.length <= STEPS_FIRST ? stage.steps : stage.steps.filter((x, i) => i < STEPS_FIRST || x.status === 'running')).map((step) => (
              <li key={step.name} className={css.stepRow} data-step-status={step.status}>
                <bdi dir="ltr" className={css.stepName}>{step.name}</bdi>
                <span className={css.stepEnd}>
                  {step.seconds !== null && <bdi dir="ltr" className={css.muted}>{step.seconds}{unit}</bdi>}
                  <Chip tone={STEP_TONE[step.status] ?? 'neutral'}>{w.known('step_', step.status)}</Chip>
                </span>
                {step.reason && step.status !== 'ok' && step.status !== 'observed' && <span className={css.stepWhy}><Txt>{step.reason}</Txt></span>}
              </li>
            ))}
          </ul>
          {stage.steps.length > STEPS_FIRST && (
            <Button variant="ghost" className={css.bigBtn} onPress={() => setStepsOpen(!stepsOpen)} aria-expanded={stepsOpen}>
              {stepsOpen ? t('showLess') : t('showAllN', { n: stage.steps.length })}
            </Button>
          )}
        </section>
      )}
      <section className={css.block} aria-label={w(state === 'ok' ? 'produced' : 'producesWhenDone')}>
        <h3 className={css.blockTitle}>{w(state === 'ok' ? 'produced' : 'producesWhenDone')}</h3>
        {state === 'ok' && !stage.artifacts.length
          ? <p className={css.muted}>{w('producedNothing')}</p>
          : <ul className={css.files}>{(state === 'ok' ? stage.artifacts : stage.produces).map((file) => <li key={file}><bdi dir="ltr">{file}</bdi></li>)}</ul>}
      </section>
      {detail.length > 0 && (
        <section className={css.block} aria-label={w('reported')}>
          <h3 className={css.blockTitle}>{w('reported')}</h3>
          <ul className={css.files}>{detail.map(([key, value]) => <li key={key}><bdi dir="ltr">{key}: {String(value)}</bdi></li>)}</ul>
        </section>
      )}
    </Panel>
  )
}

function StageList({ progress, selected, onSelect }: { progress: ScanProgress; selected: string | null; onSelect: (name: string) => void }) {
  const w = useScanWords()
  const { lang } = usePrefs()
  const ordered = useMemo(() => [...progress.stages].sort((a, b) => a.layer - b.layer || a.order - b.order), [progress.stages])
  return (
    <Panel className={css.listPanel} as="section" label={w('stages')}>
      <h2 className={css.blockTitle}>{w('stages')}</h2>
      <ul className={css.list}>
        {ordered.map((s) => {
          const state = progress.state === 'interrupted' && s.state === 'running' ? 'stopped' : s.state
          return (
            <li key={s.name}>
              <AriaButton className={[css.listRow, s.name === selected && css.listSel].filter(Boolean).join(' ')} onPress={() => onSelect(s.name)}
                aria-pressed={s.name === selected} data-list-stage={s.name}>
                <span className={[css.listDot, css[`dot_${state}`]].join(' ')} aria-hidden="true" />
                <span className={css.listMain}>
                  <span className={css.listTitle}>{w.stageTitle(s.name)}</span>
                  <span className={css.listSub}>{w.known('state_', state)}{state === 'ok' && s.seconds !== null ? ` · ${s.seconds}${lang === 'ar' ? ' ث' : ' s'}` : ''}</span>
                </span>
              </AriaButton>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}

/** Says politely what ended, in the person's language: one line per stage end and one for the run's end. */
function Announcer({ progress }: { progress: ScanProgress }) {
  const w = useScanWords()
  let text = ''
  if (progress.state === 'done') text = w('announceRun', { w: w.known('status_', progress.status ?? '') })
  else {
    const last = progress.stages.filter((s) => s.ended_at && s.requested && s.state !== 'skipped')
      .sort((a, b) => (a.ended_at ?? '').localeCompare(b.ended_at ?? '')).pop()
    if (last) text = w('announceEnded', { s: w.stageTitle(last.name), w: w.known('state_', last.state) })
  }
  return <div className="sr" role="status" aria-live="polite">{text}</div>
}
