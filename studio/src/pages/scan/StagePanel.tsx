// The chosen stage: what it does, its live timer, the external programs it runs now, its steps (a counted one with its
// bar), what it produced (the check's files open to read in a sheet, through /api/report-file) and why it did not run,
// in the person's language from its reason_code. On the desktop it sits beside the map; on the phone it is a bottom
// sheet the person opens by choosing a stage.
import { useEffect, useState } from 'react'
import { Button as AriaButton } from 'react-aria-components'
import { Button } from '../../components/Button'
import { Chip, type Tone } from '../../components/Chip'
import { Props } from '../../components/Panel'
import { Sheet } from '../../components/Sheet'
import { liveToken } from '../../data/live'
import { ENDED, shownState, type ScanProgress, type ScanStage, type ScanStep } from '../../data/scan'
import { usePrefs } from '../../i18n/prefs'
import { Id, Txt } from '../../i18n/text'
import { TickerText } from './Ticker'
import { useScanWords } from './words'
import css from './scan.module.css'

const STATE_TONE: Record<string, Tone> = {
  waiting: 'neutral', running: 'accent', ok: 'good', skipped: 'neutral', unavailable: 'warning', failed: 'critical',
  not_reached: 'neutral', stopped: 'warning',
}
const STEP_TONE: Record<string, Tone> = {
  waiting: 'neutral', running: 'accent', ok: 'good', observed: 'good', unavailable: 'warning', not_applicable: 'neutral',
  error: 'critical', failed: 'critical', skipped: 'neutral',
}
/** Steps shown before "show all": a long stage (21 tools) folds, as every long phone list does (DESIGN.md). */
const STEPS_FIRST = 8

/** A file the check produced, read as text: never rendered, only shown. */
interface FileSheetProps { path: string | null; onClose: () => void }

function FileSheet({ path, onClose }: FileSheetProps) {
  const w = useScanWords()
  const [text, setText] = useState<{ path: string; body: string; failed?: boolean } | null>(null)
  useEffect(() => {
    if (!path) return
    let on = true
    fetch(`/api/report-file?path=${encodeURIComponent(path)}`, { headers: { 'X-EAOS-Token': liveToken() ?? '' }, cache: 'no-store', credentials: 'same-origin' })
      .then(async (answer) => {
        const body = answer.ok ? await answer.text() : ((await answer.json().catch(() => ({}))) as { error?: string }).error ?? 'failed'
        if (on) setText({ path, body: answer.ok ? body : w.known('file_', body) || w('file_failed'), failed: !answer.ok })
      })
      .catch(() => { if (on) setText({ path, body: w('file_failed'), failed: true }) })
    return () => { on = false }
  }, [path, w])
  const shown = text?.path === path ? text : null
  return (
    <Sheet isOpen={path !== null} onOpenChange={(open) => { if (!open) onClose() }} title={path ?? ''}>
      {!shown ? <p className={css.muted}>{w('fileLoading')}</p>
        : shown.failed ? <p role="alert">{shown.body}</p>
          : <pre className={css.fileText} dir="ltr" tabIndex={0} data-file-text="">{shown.body}</pre>}
    </Sheet>
  )
}

function Programs({ stage, skew }: { stage: ScanStage; skew: number }) {
  const w = useScanWords()
  if (!stage.programs.length && !stage.activity_note) return null
  return (
    <section className={css.block} aria-label={w('runningNow')}>
      <h3 className={css.blockTitle}>{w('runningNow')}</h3>
      {stage.programs.length
        ? <ul className={css.files} data-programs="">{stage.programs.map((p) => (
            <li key={p.pid}><bdi dir="ltr">{p.name}</bdi> <span className={css.muted}>{w('programFor')} <TickerText since={p.since} skew={skew} /></span></li>))}</ul>
        : <p className={css.muted}><Txt>{stage.activity_note}</Txt></p>}
    </section>
  )
}

function StepRow({ step, unit }: { step: ScanStep; unit: string }) {
  const w = useScanWords()
  const counted = step.kind === 'count' && step.total > 0
  return (
    <li className={css.stepRow} data-step-status={step.status}>
      <bdi dir="ltr" className={css.stepName}>{step.name}{counted ? ` ${step.done}/${step.total}` : ''}</bdi>
      <span className={css.stepEnd}>
        {step.seconds !== null && <bdi dir="ltr" className={css.muted}>{step.seconds}{unit}</bdi>}
        <Chip tone={STEP_TONE[step.status] ?? 'neutral'}>{w.known('step_', step.status)}</Chip>
      </span>
      {counted && <span className={css.bar} aria-hidden="true"><span className={css.barFill} style={{ inlineSize: `${(100 * step.done) / step.total}%` }} /></span>}
      {step.artifact && <Id value={step.artifact} className={css.stepWhy} />}
      {step.reason && !['ok', 'observed'].includes(step.status) && <span className={css.stepWhy}><Txt>{w.reason(step.reason_code, step.reason)}</Txt></span>}
    </li>
  )
}

function Steps({ steps, unit }: { steps: ScanStep[]; unit: string }) {
  const w = useScanWords()
  const { t } = usePrefs()
  const [open, setOpen] = useState(false)
  if (!steps.length) return null
  const shown = open || steps.length <= STEPS_FIRST ? steps : steps.filter((x, i) => STEPS_FIRST > i || x.status === 'running')
  return (
    <section className={css.block} aria-label={w('steps')}>
      <h3 className={css.blockTitle}>{w('steps')} <span className={css.muted}>{w('stepsOf', { d: steps.filter((s) => !['waiting', 'running'].includes(s.status)).length, t: steps.length })}</span></h3>
      <ul className={css.steps}>{shown.map((step) => <StepRow key={step.name} step={step} unit={unit} />)}</ul>
      {steps.length > STEPS_FIRST && (
        <Button variant="ghost" className={css.bigBtn} onPress={() => setOpen(!open)} aria-expanded={open}>
          {open ? t('showLess') : t('showAllN', { n: steps.length })}
        </Button>
      )}
    </section>
  )
}

function Produced({ stage, state, readable }: { stage: ScanStage; state: string; readable: boolean }) {
  const w = useScanWords()
  const [file, setFile] = useState<string | null>(null)
  const files = state === 'ok' ? stage.artifacts : stage.produces
  const title = w(state === 'ok' ? 'produced' : 'producesWhenDone')
  return (
    <section className={css.block} aria-label={title}>
      <h3 className={css.blockTitle}>{title}</h3>
      {state === 'ok' && !files.length
        ? <p className={css.muted}>{w('producedNothing')}</p>
        : <ul className={css.files}>{files.map((path) => (
            <li key={path}>{state === 'ok' && readable
              ? <AriaButton className={css.fileLink} onPress={() => setFile(path)} data-file={path} aria-label={w('openFile', { f: path })}><bdi dir="ltr">{path}</bdi></AriaButton>
              : <bdi dir="ltr">{path}</bdi>}</li>))}</ul>}
      {readable && <FileSheet path={file} onClose={() => setFile(null)} />}
    </section>
  )
}

/** The stage's own time (live while it runs) and the last run's. */
function Time({ stage, state, skew, last, unit }: { stage: ScanStage; state: string; skew: number; last: number | undefined; unit: string }) {
  const w = useScanWords()
  const ran = stage.seconds !== null && ENDED.includes(stage.state) && !['not_reached', 'skipped'].includes(stage.state)
  const before = last === undefined ? '' : w('lastTime', { t: String(last) + unit })
  return (
    <>
      {state === 'running' && <TickerText since={stage.started_at} skew={skew} />}
      {ran && <bdi dir="ltr">{stage.seconds}{unit}</bdi>}
      {before && <span className={css.muted}>{state === 'running' || ran ? ' · ' : ''}{before}</span>}
    </>
  )
}

interface FactsProps { stage: ScanStage; state: string; flow: string; skew: number; last: number | undefined; unit: string; onSelect: (name: string) => void }

function Facts({ stage, state, flow, skew, last, unit, onSelect }: FactsProps) {
  const w = useScanWords()
  const optional = stage.necessity === 'optional'
  return (
    <Props rows={[
      [w('needs'), stage.requires.length
        ? <span className={css.needs}>{stage.requires.map((name) => (
            <AriaButton key={name} className={css.needLink} onPress={() => onSelect(name)}>{w.stageTitle(name, flow)}</AriaButton>))}</span>
        : w('needsNothing')],
      [w('necessity'), <>{w(optional ? 'optional' : 'required')}{optional && stage.absent_when
        ? <span className={css.muted}> · {w('absentWhen')}: <Txt>{w.absent(stage.name, flow, stage.absent_when)}</Txt></span> : null}</>],
      [w('time'), <Time stage={stage} state={state} skew={skew} last={last} unit={unit} />],
    ]} />
  )
}

function Reported({ detail }: { detail: Record<string, string | number> }) {
  const w = useScanWords()
  if (!Object.keys(detail).length) return null
  return (
    <section className={css.block} aria-label={w('reported')}>
      <h3 className={css.blockTitle}>{w('reported')}</h3>
      <ul className={css.files}>{Object.entries(detail).map(([key, value]) => <li key={key}><bdi dir="ltr">{key}: {String(value)}</bdi></li>)}</ul>
    </section>
  )
}

interface StagePanelProps { stage: ScanStage; progress: ScanProgress; skew: number; onSelect: (name: string) => void }

export function StagePanel({ stage, progress, skew, onSelect }: StagePanelProps) {
  const w = useScanWords()
  const { lang } = usePrefs()
  const flow = progress.flow ?? 'check'
  const state = shownState(progress, stage)
  const unit = lang === 'ar' ? ' ث' : ' s'
  return (
    <>
      <div className={css.stageHead} data-hook="scan-stage-panel" data-stage={stage.name}>
        <h2 className={css.stageTitle}>{w.stageTitle(stage.name, flow)} <Id value={stage.name} className={css.stageId} /></h2>
        <Chip tone={STATE_TONE[state] ?? 'neutral'}>{w.known('state_', state)}</Chip>
      </div>
      <p className={css.about}>{w.about(stage.name, flow, stage.description)}</p>
      {stage.resumed && <p className={css.muted}>{w('keptFromBefore')}</p>}
      {stage.reason && state !== 'ok' && (
        <div className={state === 'failed' ? css.reasonBad : css.reason} data-reason-code={stage.reason_code}>
          <strong>{w('why')}:</strong> <Txt>{w.reason(stage.reason_code, stage.reason)}</Txt>
        </div>
      )}
      <Facts stage={stage} state={state} flow={flow} skew={skew} last={progress.previous[stage.name]} unit={unit} onSelect={onSelect} />
      {state === 'running' && <Programs stage={stage} skew={skew} />}
      <Steps key={stage.name} steps={stage.steps} unit={unit} />
      <Produced stage={stage} state={state} readable={flow === 'check'} />
      <Reported detail={stage.detail} />
    </>
  )
}
